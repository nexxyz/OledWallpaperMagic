from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

from oled_wallpaper_magic.config import (
    AppConfig,
    ColorConfig,
    GenerationConfig,
    SessionConfig,
)

_base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent.parent

BUILTIN_PRESETS_DIR = _base / "presets"


class PresetData:
    def __init__(self, name: str, data: dict[str, Any]):
        self.name = name
        self.data = data

    def to_config(self) -> AppConfig:
        def _tuple(value: Any) -> tuple[int, int, int]:
            if isinstance(value, (list, tuple)) and len(value) == 3:
                return (int(value[0]), int(value[1]), int(value[2]))
            return (0, 0, 0)

        gen_data = self.data.get("generation", {})
        color_data = self.data.get("colors", {})
        session_data = self.data.get("session", {})
        gen = GenerationConfig(**gen_data)
        colors = ColorConfig(
            background=_tuple(color_data.get("background", (0, 0, 0))),
            primary=color_data.get("primary", "random"),
            secondary=color_data.get("secondary", "random"),
            glow=_tuple(color_data.get("glow", (255, 243, 200))),
        )
        session = SessionConfig(**session_data)
        seed = self.data.get("seed")
        final_seed = seed if isinstance(seed, int) else None
        return AppConfig(
            generation=gen, colors=colors, session=session, seed=final_seed
        )

    def to_toml(self) -> str:
        import io

        import tomli_w

        buf = io.BytesIO()
        tomli_w.dump(self.data, buf)
        return buf.getvalue().decode("utf-8")


class PresetStore:
    def __init__(self, user_dir: Path | None = None):
        if user_dir is None:
            user_dir = Path.home() / ".config" / "oledwall" / "presets"
        self.user_dir = user_dir

    def _builtin_presets(self) -> dict[str, dict[str, Any]]:
        if not BUILTIN_PRESETS_DIR.exists():
            return {}
        result = {}
        for f in BUILTIN_PRESETS_DIR.glob("*.toml"):
            with open(f, "rb") as fh:
                result[f.stem] = tomllib.load(fh)
        return result

    def _user_presets(self) -> dict[str, dict[str, Any]]:
        if not self.user_dir.exists():
            return {}
        result = {}
        for f in self.user_dir.glob("*.toml"):
            with open(f, "rb") as fh:
                result[f.stem] = tomllib.load(fh)
        return result

    def list_presets(self) -> list[dict[str, str]]:
        all_names = set(self._builtin_presets().keys()) | set(self._user_presets().keys())
        result = []
        for name in sorted(all_names):
            if name in self._user_presets():
                desc_data = self._user_presets()[name].get("description", "")
                if isinstance(desc_data, dict):
                    desc = desc_data.get("text", "")
                else:
                    desc = str(desc_data) if desc_data else ""
            else:
                desc_data = self._builtin_presets()[name].get("description", {})
                if isinstance(desc_data, dict):
                    desc = desc_data.get("text", "")
                else:
                    desc = str(desc_data) if desc_data else ""
            result.append({"name": name, "description": desc})
        return result

    def get(self, name: str) -> PresetData | None:
        if name in self._user_presets():
            return PresetData(name, self._user_presets()[name])
        if name in self._builtin_presets():
            return PresetData(name, self._builtin_presets()[name])
        return None

    def save(self, name: str, data: dict[str, Any]) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / f"{name}.toml"
        with open(path, "wb") as fh:
            import tomli_w

            tomli_w.dump(data, fh)

    def delete(self, name: str) -> bool:
        if name in self._builtin_presets():
            return False
        path = self.user_dir / f"{name}.toml"
        if path.exists():
            path.unlink()
            return True
        return False


preset_store = PresetStore()
