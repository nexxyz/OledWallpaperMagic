from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oledwall.config import AppConfig
from oledwall.session.metadata import Session, ImageRecord, new_session_id


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

        with open(meta_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        images = [
            ImageRecord(
                filename=img["filename"],
                index=img["index"],
                seed=img["seed"],
                palette=img.get("palette", {}),
                circle_count=img.get("circle_count", 0),
                generation_time_ms=img.get("generation_time_ms", 0.0),
            )
            for img in manifest["images"]
        ]

        config_data = manifest.get("config")
        config = AppConfig.model_validate(config_data) if config_data else None

        return Session(
            id=session_id,
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
                    with open(meta_path) as f:
                        m = json.load(f)
                    sessions.append({
                        "id": m["session_id"],
                        "created_at": m["created_at"],
                        "count": len(m.get("images", [])),
                        "path": str(d),
                    })
        return sessions

    def finalize(self, session: Session, save_dir: Path, purge: bool = False) -> int:
        import shutil

        save_dir.mkdir(parents=True, exist_ok=True)
        kept = 0

        for filename, status in session.review_state.items():
            if status == "keep":
                src = session.root / "generated" / filename
                if src.exists():
                    dest_name = f"oled_{session.id.split('_')[1]}_{filename.replace('img_', '').replace('.png', '')}.png"
                    dest = save_dir / dest_name
                    shutil.copy2(src, dest)
                    kept += 1

        if purge:
            import shutil
            shutil.rmtree(session.root)

        return kept

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
