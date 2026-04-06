import pytest
from typer.testing import CliRunner

from oled_wallpaper_magic.cli import app


runner = CliRunner()


class TestCLI:
    """Test CLI - MEDIUM risk: broken CLI = broken automation"""

    def test_cli_help_contains_all_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "gen" in result.stdout
        assert "gui" in result.stdout
        assert "review" in result.stdout
        assert "presets" in result.stdout

    def test_cli_gen_help(self):
        result = runner.invoke(app, ["gen", "--help"])
        assert result.exit_code == 0
        assert "--count" in result.stdout
        assert "--resolution" in result.stdout
        assert "--seed" in result.stdout

    def test_cli_review_help(self):
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0
        assert "SESSION_PATH" in result.stdout

    def test_cli_presets_list(self):
        result = runner.invoke(app, ["presets", "list"])
        assert result.exit_code == 0
        assert "minimal" in result.stdout
        assert "dense" in result.stdout

    def test_cli_presets_show(self):
        result = runner.invoke(app, ["presets", "show", "minimal"])
        assert result.exit_code == 0
        assert "min_circles" in result.stdout

    def test_cli_presets_show_invalid(self):
        result = runner.invoke(app, ["presets", "show", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_cli_gen_with_temp_dir(self, tmp_path):
        result = runner.invoke(
            app,
            ["gen", "--count", "2", "--temp-dir", str(tmp_path / "batch")],
        )
        assert result.exit_code == 0