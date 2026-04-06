import pytest
from oled_wallpaper_magic.config import parse_color, AppConfig, Resolution, GenerationConfig, SessionConfig


class TestColorParsing:
    """Test color parsing - HIGH risk: invalid input = broken generation"""

    def test_parse_color_hex6_uppercase(self):
        result = parse_color("#AABBCC")
        assert result == (170, 187, 204)

    def test_parse_color_hex6_lowercase(self):
        result = parse_color("#aabbcc")
        assert result == (170, 187, 204)

    def test_parse_color_hex3(self):
        result = parse_color("#ABC")
        assert result == (170, 187, 204)

    def test_parse_color_hex3_short(self):
        result = parse_color("#FFF")
        assert result == (255, 255, 255)

    def test_parse_color_rgb_format(self):
        result = parse_color("rgb(255, 128, 0)")
        assert result == (255, 128, 0)

    def test_parse_color_rgb_with_spaces(self):
        result = parse_color("rgb( 255 , 128 , 0 )")
        assert result == (255, 128, 0)

    def test_parse_color_random(self):
        result = parse_color("random")
        assert result == "random"

    def test_parse_color_random_case_insensitive(self):
        result = parse_color("RANDOM")
        assert result == "random"
        result = parse_color("Random")
        assert result == "random"

    def test_parse_color_invalid_hex(self):
        with pytest.raises(ValueError):
            parse_color("#GGG")

    def test_parse_color_invalid_format(self):
        with pytest.raises(ValueError):
            parse_color("not-a-color")

    def test_parse_color_empty(self):
        with pytest.raises(ValueError):
            parse_color("")


class TestConfigSerialization:
    """Test config roundtrip - HIGH risk: config loss bug"""

    def test_config_to_dict_roundtrip(self, sample_config):
        d = sample_config.to_dict()
        restored = AppConfig(**d)
        assert restored.resolution.width == sample_config.resolution.width
        assert restored.resolution.height == sample_config.resolution.height

    def test_config_model_dump_json(self, sample_config):
        json_str = sample_config.model_dump_json()
        restored = AppConfig.model_validate_json(json_str)
        assert restored.resolution == sample_config.resolution

    def test_resolution_bounds(self):
        res = Resolution(width=1920, height=1080)
        assert res.width == 1920
        assert res.height == 1080

        with pytest.raises(Exception):
            Resolution(width=0, height=1)

        with pytest.raises(Exception):
            Resolution(width=10000, height=10000)


class TestConfigDefaults:
    """Test default values - HIGH risk: wrong defaults = broken UI"""

    def test_default_session_paths(self):
        from oled_wallpaper_magic.config import DEFAULT_SAVE_DIR, DEFAULT_TEMP_DIR
        session = SessionConfig()
        assert session.save_dir == DEFAULT_SAVE_DIR
        assert session.temp_dir == DEFAULT_TEMP_DIR

    def test_default_resolution(self):
        cfg = AppConfig()
        assert cfg.resolution.width == 2560
        assert cfg.resolution.height == 1440

    def test_default_generation_values(self):
        gen = GenerationConfig()
        assert gen.min_circles == 4
        assert gen.max_circles == 20
        assert gen.curve == "gaussian"

    def test_config_validation_min_max_circles(self):
        gen = GenerationConfig(min_circles=3, max_circles=10)
        assert gen.min_circles == 3
        assert gen.max_circles == 10

        with pytest.raises(Exception):
            GenerationConfig(min_circles=10, max_circles=5)

    def test_config_validation_min_max_radius(self):
        gen = GenerationConfig(min_radius=50, max_radius=200)
        assert gen.min_radius == 50
        assert gen.max_radius == 200

        with pytest.raises(Exception):
            GenerationConfig(min_radius=200, max_radius=50)