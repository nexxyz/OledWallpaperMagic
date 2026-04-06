import pytest
from pathlib import Path
import tempfile

from oled_wallpaper_magic.config import AppConfig, Resolution, GenerationConfig, ColorConfig, SessionConfig


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for file I/O tests."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def small_resolution():
    """Small resolution for fast tests."""
    return Resolution(width=160, height=90)


@pytest.fixture
def sample_config(small_resolution):
    """Provide a sample AppConfig for testing."""
    return AppConfig(
        resolution=small_resolution,
        generation=GenerationConfig(
            min_circles=2,
            max_circles=5,
            min_radius=20,
            max_radius=50,
        ),
        colors=ColorConfig(
            primary=(100, 150, 200),
            secondary=(200, 100, 150),
            glow=(255, 243, 200),
        ),
        session=SessionConfig(count=3),
    )


@pytest.fixture
def tiny_config():
    """Minimal config for quick tests."""
    return AppConfig(
        resolution=Resolution(width=64, height=64),
        generation=GenerationConfig(
            min_circles=1,
            max_circles=2,
            min_radius=5,
            max_radius=15,
        ),
        colors=ColorConfig(
            primary=(255, 0, 0),
            secondary=(0, 0, 255),
            glow=(255, 255, 0),
        ),
    )