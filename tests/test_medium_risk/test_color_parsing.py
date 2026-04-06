import pytest

from oled_wallpaper_magic.config import parse_color


class TestColorParsingInvalid:
    """Test invalid color input handling - MEDIUM risk"""

    def test_parse_color_rejects_invalid_hex(self):
        with pytest.raises(ValueError, match="Cannot parse color"):
            parse_color("#GGGFFF")

    def test_parse_color_rejects_invalid_hex_short(self):
        with pytest.raises(ValueError, match="Cannot parse color"):
            parse_color("#GGG")

    def test_parse_color_rejects_invalid_rgb(self):
        with pytest.raises(ValueError, match="Cannot parse color"):
            parse_color("notrgb(300, 0, 0)")

    def test_parse_color_rejects_invalid_rgb_negative(self):
        with pytest.raises(ValueError, match="Cannot parse color"):
            parse_color("rgb(-1, 0, 0)")

    def test_parse_color_rejects_invalid_format(self):
        with pytest.raises(ValueError, match="Cannot parse color"):
            parse_color("not-a-color")

    def test_parse_color_rejects_empty(self):
        with pytest.raises(ValueError, match="Cannot parse color"):
            parse_color("")

    def test_parse_color_rejects_hex_with_invalid_chars(self):
        with pytest.raises(ValueError):
            parse_color("#XYZ123")

    def test_parse_color_rejects_malformed_rgb(self):
        with pytest.raises(ValueError):
            parse_color("rgb(255,0)")