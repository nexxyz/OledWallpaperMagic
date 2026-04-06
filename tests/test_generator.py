import numpy as np

from oled_wallpaper_magic.generator.palette import hsv_to_rgb, rgb_to_hsv, random_vivid_color, ensure_hue_separation
from oled_wallpaper_magic.generator.fuzzy_circle import (
    linear_alpha, ease_alpha, exp_alpha, gaussian_alpha, flat_alpha,
    glow_ring_alpha, get_alpha_curve,
)
from oled_wallpaper_magic.generator.circle import FuzzyCircle
from oled_wallpaper_magic.generator.engine import GenerationEngine
from oled_wallpaper_magic.config import AppConfig, Resolution


def test_hsv_roundtrip():
    for r, g, b in [(255, 0, 0), (0, 255, 0), (128, 64, 200), (0, 0, 0), (255, 255, 255)]:
        h, s, v = rgb_to_hsv(r, g, b)
        r2, g2, b2 = hsv_to_rgb(h, s, v)
        assert abs(r2 - r) <= 1 and abs(g2 - g) <= 1 and abs(b2 - b) <= 1


def test_alpha_curves_in_range():
    t = np.linspace(0, 2, 500)
    for name, fn in [
        ("linear", linear_alpha),
        ("ease", ease_alpha),
        ("exp", exp_alpha),
        ("gaussian", gaussian_alpha),
        ("flat", flat_alpha),
    ]:
        a = fn(t, 2.0)
        assert a.min() >= -1e-6, f"{name} min below 0"
        assert a.max() <= 1.0 + 1e-6, f"{name} max above 1"
    glow = glow_ring_alpha(t, 0.88, 0.07)
    assert glow.min() >= -1e-6
    assert glow.max() <= 1.0 + 1e-6


def test_ensure_hue_separation():
    primary = (255, 0, 0)
    secondary = (254, 5, 0)
    secondary_sep = ensure_hue_separation(primary, secondary, min_degrees=35)
    hp, _, _ = rgb_to_hsv(*primary)
    hs, _, _ = rgb_to_hsv(*secondary_sep)
    diff = min(abs(hp - hs), 1.0 - abs(hp - hs))
    assert diff * 360 >= 34.9, f"Hue diff {diff * 360:.1f}° < 35°"


def test_fuzzy_circle_render():
    canvas = np.zeros((200, 200, 3), dtype=np.float32)
    circle = FuzzyCircle(
        cx=100, cy=100, radius=50,
        color=(255, 0, 0), opacity=1.0,
        curve_name="gaussian", curve_param=2.0,
        glow_color=(255, 255, 200), glow_strength=0.3,
        glow_mu=0.88, glow_sigma=0.07,
    )
    circle.render(canvas)
    assert canvas.dtype == np.float32
    assert canvas.shape == (200, 200, 3)
    assert canvas.max() > 0
    assert canvas[100, 100].sum() > 0
    assert canvas[0, 0].sum() == 0


def test_get_alpha_curve_invalid():
    try:
        get_alpha_curve("nonexistent")
        assert False
    except ValueError:
        pass


def test_determinism():
    from oled_wallpaper_magic.config import ColorConfig

    config = AppConfig(
        resolution=Resolution(width=320, height=180),
        colors=ColorConfig(
            primary=(100, 150, 200),
            secondary=(200, 100, 150),
            glow=(255, 243, 200),
        ),
    )
    engine = GenerationEngine(config)

    img1 = engine.generate_single(seed=42)
    img2 = engine.generate_single(seed=42)

    assert img1.pixels.shape == img2.pixels.shape
    assert np.array_equal(img1.pixels, img2.pixels), "Same seed should produce identical pixels"
    assert img1.seed == img2.seed == 42


def test_different_seeds_different_output():
    from oled_wallpaper_magic.config import ColorConfig

    config = AppConfig(
        resolution=Resolution(width=320, height=180),
        colors=ColorConfig(
            primary=(100, 150, 200),
            secondary=(200, 100, 150),
            glow=(255, 243, 200),
        ),
    )
    engine = GenerationEngine(config)

    img1 = engine.generate_single(seed=1)
    img2 = engine.generate_single(seed=2)

    assert not np.array_equal(img1.pixels, img2.pixels), "Different seeds should produce different pixels"
    assert img1.seed == 1
    assert img2.seed == 2


def test_parallel_batch_yields_correct_count():
    from oled_wallpaper_magic.config import ColorConfig

    config = AppConfig(
        resolution=Resolution(width=160, height=90),
        colors=ColorConfig(
            primary=(100, 150, 200),
            secondary=(200, 100, 150),
            glow=(255, 243, 200),
        ),
    )
    config.generation.workers = 0
    engine = GenerationEngine(config)

    images = list(engine.generate_batch(count=10, session_seed=99))
    assert len(images) == 10
    for img in images:
        assert img.pixels.shape == (90, 160, 3)
        assert img.generation_time_ms > 0


def test_config_validation_min_max():
    from oled_wallpaper_magic.config import GenerationConfig
    from pydantic import ValidationError

    ok = GenerationConfig(min_circles=1, max_circles=5)
    assert ok.min_circles == 1 and ok.max_circles == 5

    try:
        GenerationConfig(min_circles=10, max_circles=5)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass
