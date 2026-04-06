from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Any

import pydantic
from pydantic import BaseModel, Field, field_validator, model_validator

RGB = tuple[int, int, int]
COLOR_VALUE = RGB | Literal["random"]


def parse_color(value: str) -> RGB | Literal["random"]:
    if value.lower() == "random":
        return "random"
    value = value.strip()
    m = re.match(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})", value)
    if m:
        return (int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16))
    m = re.match(r"#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])", value)
    if m:
        return (int(m.group(1) * 2, 16), int(m.group(2) * 2, 16), int(m.group(3) * 2, 16))
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", value, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise ValueError(f"Cannot parse color: '{value}'. Expected hex (#RRGGBB or #RGB), rgb(r,g,b), or 'random'.")


class Resolution(BaseModel):
    width: int = Field(ge=1, le=7680)
    height: int = Field(ge=1, le=4320)


class GenerationConfig(BaseModel):
    min_circles: int = Field(default=4, ge=1)
    max_circles: int = Field(default=20, ge=1)
    min_radius: int = Field(default=60, ge=1)
    max_radius: int = Field(default=400, ge=1)
    curve: Literal["linear", "ease", "exp", "gaussian", "flat"] = "gaussian"
    curve_param: float = Field(default=2.0, gt=0)
    glow_strength: float = Field(default=0.3, ge=0)
    glow_mu: float = Field(default=0.88, ge=0, le=2)
    glow_sigma: float = Field(default=0.07, gt=0)
    primary_opacity_min: float = Field(default=0.4, ge=0, le=1)
    primary_opacity_max: float = Field(default=1.0, ge=0, le=1)
    primary_secondary_mix: float = Field(default=0.5, ge=0, le=1)
    enforce_both_colors: bool = True
    workers: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def check_ranges(self):
        if not self.min_circles <= self.max_circles:
            raise ValueError(f"min_circles ({self.min_circles}) must be <= max_circles ({self.max_circles})")
        if not self.min_radius <= self.max_radius:
            raise ValueError(f"min_radius ({self.min_radius}) must be <= max_radius ({self.max_radius})")
        if not self.primary_opacity_min <= self.primary_opacity_max:
            raise ValueError(
                f"primary_opacity_min ({self.primary_opacity_min}) must be <= primary_opacity_max ({self.primary_opacity_max})"
            )
        return self


class ColorConfig(BaseModel):
    background: RGB = (0, 0, 0)
    primary: RGB | Literal["random"] = "random"
    secondary: RGB | Literal["random"] = "random"
    glow: RGB = (255, 243, 200)
    primary_is_random: bool = True
    secondary_is_random: bool = True

    @field_validator("primary", mode="before")
    @classmethod
    def _primary_from_str(cls, v):
        if isinstance(v, str):
            if v.lower() == "random":
                return "random"
            return parse_color(v)
        return v

    @field_validator("secondary", mode="before")
    @classmethod
    def _secondary_from_str(cls, v):
        if isinstance(v, str):
            if v.lower() == "random":
                return "random"
            return parse_color(v)
        return v

    @model_validator(mode="after")
    def _sync_random_flags(self):
        if isinstance(self.primary, str):
            self.primary_is_random = True
        elif isinstance(self.primary, tuple):
            self.primary_is_random = False
        if isinstance(self.secondary, str):
            self.secondary_is_random = True
        elif isinstance(self.secondary, tuple):
            self.secondary_is_random = False
        return self

    def is_random(self, field: str) -> bool:
        return getattr(self, f"{field}_is_random", False)


class SessionConfig(BaseModel):
    count: int = Field(default=50, ge=1)
    save_dir: Path = Path("./wallpapers/kept")
    temp_dir: Path = Path("./wallpapers/_batch")
    format: Literal["png"] = "png"
    purge_discarded: bool = False


class AppConfig(BaseModel):
    resolution: Resolution = Field(default_factory=lambda: Resolution(width=2560, height=1440))
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    colors: ColorConfig = Field(default_factory=ColorConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    seed: int | None = None

    @classmethod
    def from_preset(cls, name: str) -> AppConfig:
        from oledwall.presets import preset_store

        preset = preset_store.get(name)
        if preset is None:
            raise ValueError(f"Preset '{name}' not found")
        return preset.to_config()

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_toml(self) -> str:
        import io
        import toml

        buf = io.StringIO()
        toml.dump(self.model_dump(), buf)
        return buf.getvalue()
