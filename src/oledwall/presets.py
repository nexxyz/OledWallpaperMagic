from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from oledwall.config import AppConfig, ColorConfig, GenerationConfig, Resolution, SessionConfig

BUILTIN_PRESETS_DIR = Path(__file__).parent.parent.parent / "presets"

PRESET_DESCRIPTIONS: dict[str, str] = {
    "minimal": "Sparse, calm — few large circles with soft falloff",
    "dense": "Many overlapping circles, sharper edges",
    "ultrawide": "Optimized for 3440x1440, medium density with glow",
    "vivid": "High saturation random colors, medium circles",
    "subtle": "Low saturation pastels, soft glow",
    "awesome_bubbles": "Deep contrast bubbles with strong violet glow",
    "cool_violet": "Cool violet ambience with broader circle spread",
}

BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "minimal": {
        "description": "Sparse, calm — few large circles with soft falloff",
        "generation": {
            "min_circles": 3,
            "max_circles": 6,
            "min_radius": 150,
            "max_radius": 600,
            "curve": "gaussian",
            "curve_param": 1.5,
            "glow_strength": 0.2,
            "glow_mu": 0.88,
            "glow_sigma": 0.07,
        },
    },
    "dense": {
        "description": "Many overlapping circles, sharper edges",
        "generation": {
            "min_circles": 15,
            "max_circles": 30,
            "min_radius": 40,
            "max_radius": 200,
            "curve": "ease",
            "curve_param": 3.0,
            "glow_strength": 0.4,
            "glow_mu": 0.88,
            "glow_sigma": 0.07,
        },
    },
    "ultrawide": {
        "description": "Optimized for 3440x1440, medium density with glow",
        "generation": {
            "min_circles": 8,
            "max_circles": 22,
            "min_radius": 80,
            "max_radius": 520,
            "curve": "gaussian",
            "curve_param": 2.0,
            "glow_strength": 0.35,
            "glow_mu": 0.88,
            "glow_sigma": 0.07,
        },
    },
    "vivid": {
        "description": "High saturation random colors, medium circles",
        "generation": {
            "min_circles": 5,
            "max_circles": 15,
            "min_radius": 80,
            "max_radius": 350,
            "curve": "gaussian",
            "curve_param": 2.0,
            "glow_strength": 0.25,
            "glow_mu": 0.88,
            "glow_sigma": 0.07,
        },
    },
    "subtle": {
        "description": "Low saturation pastels, soft glow",
        "generation": {
            "min_circles": 4,
            "max_circles": 12,
            "min_radius": 100,
            "max_radius": 400,
            "curve": "gaussian",
            "curve_param": 1.8,
            "glow_strength": 0.15,
            "glow_mu": 0.88,
            "glow_sigma": 0.09,
        },
    },
    "awesome_bubbles": {
        "description": "Deep contrast bubbles with strong violet glow",
        "generation": {
            "min_circles": 8,
            "max_circles": 30,
            "min_radius": 47,
            "max_radius": 1012,
            "curve": "linear",
            "curve_param": 1.14,
            "glow_strength": 0.64,
            "glow_mu": 0.83,
            "glow_sigma": 0.10,
            "primary_opacity_min": 0.48,
            "primary_opacity_max": 1.0,
        },
        "colors": {
            "background": (0, 0, 0),
            "primary": (102, 74, 55),
            "secondary": (70, 78, 155),
            "glow": (84, 45, 233),
        },
        "seed": 1471975476,
    },
    "cool_violet": {
        "description": "Cool violet ambience with broader circle spread",
        "generation": {
            "min_circles": 8,
            "max_circles": 50,
            "min_radius": 47,
            "max_radius": 1012,
            "curve": "linear",
            "curve_param": 0.84,
            "glow_strength": 0.69,
            "glow_mu": 0.83,
            "glow_sigma": 0.10,
            "primary_opacity_min": 0.48,
            "primary_opacity_max": 0.91,
        },
        "colors": {
            "background": (0, 0, 0),
            "primary": (102, 74, 55),
            "secondary": (70, 78, 155),
            "glow": (84, 45, 233),
        },
        "seed": 1471975476,
    },
}


class PresetData:
    def __init__(self, name: str, data: dict[str, Any], source: str):
        self.name = name
        self.data = data
        self.source = source

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
        return AppConfig(generation=gen, colors=colors, session=session, seed=seed if isinstance(seed, int) else None)

    def to_toml(self) -> str:
        import io
        import toml
        buf = io.StringIO()
        toml.dump(self.data, buf)
        return buf.getvalue()


class PresetStore:
    def __init__(self, user_dir: Path | None = None):
        if user_dir is None:
            user_dir = Path.home() / ".config" / "oledwall" / "presets"
        self.user_dir = user_dir

    def _user_presets(self) -> dict[str, dict[str, Any]]:
        if not self.user_dir.exists():
            return {}
        result = {}
        for f in self.user_dir.glob("*.toml"):
            with open(f, "rb") as fh:
                result[f.stem] = tomllib.load(fh)
        return result

    def list_presets(self) -> list[dict[str, str]]:
        all_names = set(BUILTIN_PRESETS.keys()) | set(self._user_presets().keys())
        result = []
        for name in sorted(all_names):
            source = "user" if name in self._user_presets() else "built-in"
            desc = PRESET_DESCRIPTIONS.get(name, self._user_presets().get(name, {}).get("description", ""))
            result.append({"name": name, "description": desc, "source": source})
        return result

    def get(self, name: str) -> PresetData | None:
        if name in self._user_presets():
            return PresetData(name, self._user_presets()[name], "user")
        if name in BUILTIN_PRESETS:
            return PresetData(name, BUILTIN_PRESETS[name], "built-in")
        return None

    def save(self, name: str, data: dict[str, Any]) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / f"{name}.toml"
        with open(path, "wb") as fh:
            import tomli_w
            tomli_w.dump(data, fh)  # type: ignore[attr-defined]

    def delete(self, name: str) -> bool:
        if name in BUILTIN_PRESETS:
            return False
        path = self.user_dir / f"{name}.toml"
        if path.exists():
            path.unlink()
            return True
        return False


preset_store = PresetStore()
