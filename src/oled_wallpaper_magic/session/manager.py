from __future__ import annotations

import json
import shutil
from datetime import UTC
from pathlib import Path
from typing import Any

from oled_wallpaper_magic.config import AppConfig
from oled_wallpaper_magic.session.metadata import ImageRecord, Session, new_session_id


class SessionManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def create_session(self, config: AppConfig, count: int) -> Session:
        session_id = new_session_id()
        root = self.base_dir / session_id
        root.mkdir(parents=True, exist_ok=True)

        images = [
            ImageRecord(index=i + 1, seed=0)
            for i in range(count)
        ]

        session = Session(
            id=session_id,
            root=root,
            config=config,
            images=images,
            review_state={},
            current_index=0,
        )
        self.save_session(session)
        return session

    def save_session(self, session: Session) -> None:
        manifest = {
            "session_id": session.id,
            "created_at": session.created_at.isoformat(),
            "config": session.config.model_dump(mode="json") if session.config else None,
            "images": [
                {
                    "filename": img.filename,
                    "index": img.index,
                    "seed": img.seed,
                    "palette": img.palette,
                    "circle_count": img.circle_count,
                    "generation_time_ms": img.generation_time_ms,
                }
                for img in session.images
            ],
            "review_state": session.review_state,
            "current_index": session.current_index,
        }
        meta_path = session.root / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        state_path = session.root / "review_state.json"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": session.id,
                    "current_index": session.current_index,
                    "states": session.review_state,
                    "updated_at": self._now_iso(),
                },
                f,
                indent=2,
            )

    def load_session(self, session_id: str) -> Session:
        root = self.base_dir / session_id
        meta_path = root / "metadata.json"

        try:
            with open(meta_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Session metadata not found: {meta_path}") from None
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted session metadata: {meta_path}: {e}") from None

        required_fields = ["session_id", "images"]
        for field in required_fields:
            if field not in manifest:
                raise ValueError(f"Missing required field '{field}' in session metadata")

        images = [
            ImageRecord(
                filename=img.get("filename", ""),
                index=img.get("index", 0),
                seed=img.get("seed", 0),
                palette=img.get("palette", {}),
                circle_count=img.get("circle_count", 0),
                generation_time_ms=img.get("generation_time_ms", 0.0),
            )
            for img in manifest.get("images", [])
        ]

        config_data = manifest.get("config")
        config = AppConfig.model_validate(config_data) if config_data else None

        return Session(
            id=manifest["session_id"],
            root=root,
            config=config,
            images=images,
            review_state=manifest.get("review_state", {}),
            current_index=manifest.get("current_index", 0),
        )

    def list_sessions(self) -> list[dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        sessions = []
        for d in sorted(self.base_dir.iterdir(), reverse=True):
            if d.is_dir() and d.name.startswith("session_"):
                meta_path = d / "metadata.json"
                if meta_path.exists():
                    try:
                        with open(meta_path) as f:
                            m = json.load(f)
                        sessions.append({
                            "id": m.get("session_id", d.name),
                            "created_at": m.get("created_at", ""),
                            "count": len(m.get("images", [])),
                            "path": str(d),
                        })
                    except (json.JSONDecodeError, OSError):
                        continue
        return sessions

    def finalize(self, session: Session, save_dir: Path, purge: bool = False) -> int:
        save_dir.mkdir(parents=True, exist_ok=True)
        kept = 0

        for filename, status in session.review_state.items():
            if status == "keep":
                src = session.root / "generated" / filename
                if src.exists():
                    session_date = session.id.split("_")[1]
                    base_name = filename.replace("img_", "").replace(".png", "")
                    dest_name = f"oled_{session_date}_{base_name}.png"
                    dest = save_dir / dest_name
                    shutil.copy2(src, dest)
                    kept += 1

        if purge:
            shutil.rmtree(session.root)

        return kept

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime
        return datetime.now(UTC).isoformat()
