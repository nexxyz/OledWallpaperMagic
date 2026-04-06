import pytest
import numpy as np

from oled_wallpaper_magic.generator.engine import GenerationEngine
from oled_wallpaper_magic.config import AppConfig, ColorConfig, Resolution


class TestDeterminism:
    """Test generation determinism - HIGH risk: reproducibility promise must hold"""

    def test_same_seed_produces_identical_image(self, tiny_config):
        engine = GenerationEngine(tiny_config)

        img1 = engine.generate_single(seed=42)
        img2 = engine.generate_single(seed=42)

        assert np.array_equal(img1.pixels, img2.pixels), "Same seed should produce identical pixels"
        assert img1.seed == img2.seed == 42
        assert img1.circle_count == img2.circle_count

    def test_different_seed_produces_different_image(self, tiny_config):
        engine = GenerationEngine(tiny_config)

        img1 = engine.generate_single(seed=1)
        img2 = engine.generate_single(seed=2)

        assert not np.array_equal(img1.pixels, img2.pixels), "Different seeds should produce different pixels"
        assert img1.seed == 1
        assert img2.seed == 2

    def test_session_seed_applies_to_all_images(self, tiny_config):
        engine = GenerationEngine(tiny_config)

        images = list(engine.generate_batch(count=5, session_seed=999))

        assert len(images) == 5

        img1 = engine.generate_single(seed=999)
        img2 = engine.generate_single(seed=1000)
        img3 = engine.generate_single(seed=1001)

        first_batch_img = images[0]
        assert first_batch_img.seed == 999
        assert np.array_equal(img1.pixels, first_batch_img.pixels)

    def test_zero_seed_uses_random(self, tiny_config):
        engine = GenerationEngine(tiny_config)
        img = engine.generate_single(seed=0)
        assert img.seed == 0

    def test_batch_order_is_sequential_seeds(self, tiny_config):
        engine = GenerationEngine(tiny_config)

        images = list(engine.generate_batch(count=3, session_seed=100))

        seeds = [img.seed for img in images]
        assert seeds == [100, 101, 102]

    def test_parallel_generation_matches_sequential(self, tiny_config):
        tiny_config.generation.workers = 1
        engine_single = GenerationEngine(tiny_config)

        tiny_config2 = tiny_config.model_copy()
        tiny_config2.generation.workers = 2
        engine_parallel = GenerationEngine(tiny_config2)

        img_single = engine_single.generate_single(seed=12345)

        batch = list(engine_parallel.generate_batch(count=1, session_seed=12345))
        img_parallel = batch[0]

        assert np.array_equal(img_single.pixels, img_parallel.pixels)


class TestGenerationOutput:
    """Test generation output properties"""

    def test_image_has_correct_shape(self, tiny_config):
        engine = GenerationEngine(tiny_config)
        img = engine.generate_single(seed=1)

        assert img.pixels.shape == (64, 64, 3)
        assert img.pixels.dtype == np.uint8

    def test_image_has_expected_pixel_range(self, tiny_config):
        engine = GenerationEngine(tiny_config)
        img = engine.generate_single(seed=1)

        assert img.pixels.min() >= 0
        assert img.pixels.max() <= 255

    def test_generation_time_is_recorded(self, tiny_config):
        engine = GenerationEngine(tiny_config)
        img = engine.generate_single(seed=1)

        assert img.generation_time_ms > 0
        assert isinstance(img.generation_time_ms, float)

    def test_palette_is_recorded(self, tiny_config):
        engine = GenerationEngine(tiny_config)
        img = engine.generate_single(seed=1)

        assert "primary" in img.palette
        assert "secondary" in img.palette
        assert "glow" in img.palette