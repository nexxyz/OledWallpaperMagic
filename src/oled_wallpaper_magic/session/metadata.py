from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from oled_wallpaper_magic.config import RGB, AppConfig

ReviewStatus = str


@dataclass
class ImageRecord:
    filename: str = ""
    index: int = 0
    seed: int = 0
    palette: dict[str, RGB] = field(default_factory=dict)
    circle_count: int = 0
    generation_time_ms: float = 0.0


@dataclass
class Session:
    id: str
    root: Path
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    config: AppConfig | None = None
    images: list[ImageRecord] = field(default_factory=list)
    review_state: dict[str, ReviewStatus] = field(default_factory=dict)
    current_index: int = 0


def new_session_id() -> str:
    return datetime.now(UTC).strftime("session_%Y%m%d_%H%M%S")
