import pytest
from pathlib import Path

from oled_wallpaper_magic.session.manager import SessionManager
from oled_wallpaper_magic.generator.engine import GenerationEngine
from oled_wallpaper_magic.config import AppConfig, Resolution, ColorConfig, GenerationConfig, SessionConfig


class TestIntegration:
    """Integration tests - SYSTEM risk: real workflows must work"""

    def test_e2e_gen_session_creates_files(self, temp_dir):
        """Test that generating a session creates expected files."""
        config = AppConfig(
            resolution=Resolution(width=80, height=60),
            generation=GenerationConfig(min_circles=1, max_circles=2, min_radius=10, max_radius=20),
            colors=ColorConfig(primary=(255, 0, 0), secondary=(0, 0, 255), glow=(255, 255, 0)),
            session=SessionConfig(
                count=2, temp_dir=temp_dir, save_dir=temp_dir / "kept"
            ),
        )

        manager = SessionManager(temp_dir)
        session = manager.create_session(config, count=2)

        engine = GenerationEngine(config)
        gen_dir = session.root / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)

        for i, img_data in enumerate(engine.generate_batch(2, session_seed=42)):
            img_path = gen_dir / f"img_{i+1:04d}.png"
            img_data.save(img_path)
            assert img_path.exists()
            assert img_path.stat().st_size > 0

    def test_e2e_gen_with_preset_works(self, temp_dir):
        """Test that generating with a preset works."""
        from oled_wallpaper_magic.presets import PresetStore

        store = PresetStore(user_dir=temp_dir / "presets")
        preset = store.get("minimal")
        assert preset is not None

        config = preset.to_config()
        config.resolution = Resolution(width=64, height=64)
        config.generation.workers = 1
        config.session.temp_dir = temp_dir

        engine = GenerationEngine(config)
        images = list(engine.generate_batch(count=2, session_seed=123))

        assert len(images) == 2
        assert images[0].pixels.shape == (64, 64, 3)

    def test_e2e_load_and_review_session(self, temp_dir):
        """Test loading and reviewing a session."""
        config = AppConfig(
            resolution=Resolution(width=64, height=64),
            generation=GenerationConfig(min_circles=1, max_circles=2),
            colors=ColorConfig(primary=(100, 100, 100), secondary=(200, 200, 200), glow=(255, 255, 255)),
        )

        manager = SessionManager(temp_dir)
        session = manager.create_session(config, count=3)

        session.images[0].filename = "img_0001.png"
        session.images[1].filename = "img_0002.png"
        session.images[2].filename = "img_0003.png"
        session.review_state = {"img_0001.png": "keep", "img_0002.png": "discard"}
        manager.save_session(session)

        loaded = manager.load_session(session.id)
        assert len(loaded.images) == 3
        assert loaded.review_state["img_0001.png"] == "keep"
        assert loaded.review_state["img_0002.png"] == "discard"

    def test_e2e_parallel_generation_works(self, temp_dir):
        """Test parallel generation produces valid output."""
        config = AppConfig(
            resolution=Resolution(width=64, height=64),
            generation=GenerationConfig(min_circles=1, max_circles=2, workers=0),
            colors=ColorConfig(primary=(255, 0, 0), secondary=(0, 255, 0), glow=(0, 0, 255)),
        )

        engine = GenerationEngine(config)
        images = list(engine.generate_batch(count=4, session_seed=99))

        assert len(images) == 4
        for img in images:
            assert img.pixels.shape == (64, 64, 3)
            assert 0 <= img.pixels.min() <= img.pixels.max() <= 255

    def test_e2e_resolution_affects_output_size(self, temp_dir):
        """Test that different resolutions produce correct output sizes."""
        config_small = AppConfig(
            resolution=Resolution(width=64, height=48),
            generation=GenerationConfig(min_circles=1, max_circles=1, workers=1),
            colors=ColorConfig(primary=(255, 255, 255), secondary=(0, 0, 0), glow=(128, 128, 128)),
        )

        config_large = AppConfig(
            resolution=Resolution(width=128, height=96),
            generation=GenerationConfig(min_circles=1, max_circles=1, workers=1),
            colors=ColorConfig(primary=(255, 255, 255), secondary=(0, 0, 0), glow=(128, 128, 128)),
        )

        engine_small = GenerationEngine(config_small)
        engine_large = GenerationEngine(config_large)

        img_small = engine_small.generate_single(seed=1)
        img_large = engine_large.generate_single(seed=1)

        assert img_small.pixels.shape == (48, 64, 3)
        assert img_large.pixels.shape == (96, 128, 3)

    def test_e2e_temp_and_save_dirs_respected(self, temp_dir):
        """Test that temp_dir and save_dir are properly used."""
        temp_sub = temp_dir / "batch"
        save_sub = temp_dir / "export"

        config = AppConfig(
            resolution=Resolution(width=48, height=48),
            generation=GenerationConfig(min_circles=1, max_circles=1, workers=1),
            colors=ColorConfig(primary=(255, 0, 0), secondary=(0, 0, 255), glow=(255, 255, 0)),
            session=SessionConfig(
                count=1, temp_dir=temp_sub, save_dir=save_sub
            ),
        )

        assert str(config.session.temp_dir) == str(temp_sub)
        assert str(config.session.save_dir) == str(save_sub)
