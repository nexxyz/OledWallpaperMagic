import pytest
from pathlib import Path
import json
import tempfile

from oled_wallpaper_magic.presets import preset_store, PresetData, PresetStore


class TestPresetStore:
    """Test preset loading and saving - HIGH risk: broken presets = broken workflow"""

    def test_preset_store_lists_builtins(self):
        presets = preset_store.list_presets()
        names = [p["name"] for p in presets]
        assert "minimal" in names
        assert "dense" in names
        assert "awesome_bubbles" in names

    def test_preset_get_valid_builtin(self):
        preset = preset_store.get("awesome_bubbles")
        assert preset is not None
        assert preset.name == "awesome_bubbles"
        assert preset.source == "built-in"

    def test_preset_get_invalid(self):
        preset = preset_store.get("nonexistent_preset")
        assert preset is None

    def test_preset_to_config(self):
        preset = preset_store.get("minimal")
        assert preset is not None

        config = preset.to_config()
        assert config.generation.min_circles == 3
        assert config.generation.max_circles == 6
        assert config.generation.curve == "gaussian"

    def test_preset_to_toml(self):
        preset = preset_store.get("dense")
        toml_str = preset.to_toml()
        assert "min_circles" in toml_str
        assert "max_circles" in toml_str

    def test_all_builtins_have_descriptions(self):
        presets = preset_store.list_presets()
        builtins = [p for p in presets if p["source"] == "built-in"]
        for p in builtins:
            assert p["description"], f"Preset {p['name']} missing description"

    def test_builtin_preset_configs_are_valid(self):
        preset_names = ["minimal", "dense", "ultrawide", "vivid", "subtle"]
        for name in preset_names:
            preset = preset_store.get(name)
            assert preset is not None, f"Preset {name} not found"
            config = preset.to_config()
            assert config.generation.min_circles <= config.generation.max_circles
            assert config.generation.min_radius <= config.generation.max_radius


class TestUserPresets:
    """Test user preset save/load cycle"""

    def test_user_preset_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            user_dir = Path(td) / "presets"
            store = PresetStore(user_dir=user_dir)

            preset_data = {
                "description": "My custom preset",
                "generation": {
                    "min_circles": 5,
                    "max_circles": 15,
                    "min_radius": 50,
                    "max_radius": 300,
                    "curve": "ease",
                },
                "colors": {
                    "primary": (255, 100, 100),
                    "secondary": (100, 100, 255),
                },
            }

            store.save("my_preset", preset_data)

            loaded = store.get("my_preset")
            assert loaded is not None
            assert loaded.source == "user"

            config = loaded.to_config()
            assert config.generation.min_circles == 5
            assert config.generation.max_circles == 15
            assert config.generation.curve == "ease"

    def test_preset_delete_user_only(self):
        with tempfile.TemporaryDirectory() as td:
            user_dir = Path(td) / "presets"
            store = PresetStore(user_dir=user_dir)

            store.save("temp_preset", {"description": "test"})

            result = store.delete("temp_preset")
            assert result is True

            assert store.get("temp_preset") is None

    def test_preset_delete_builtin_fails(self):
        result = preset_store.delete("minimal")
        assert result is False

    def test_list_presets_includes_user(self):
        with tempfile.TemporaryDirectory() as td:
            user_dir = Path(td) / "presets"
            store = PresetStore(user_dir=user_dir)

            store.save("user_test", {"description": "test preset"})

            presets = store.list_presets()
            names = [p["name"] for p in presets]
            assert "user_test" in names

            sources = [p["source"] for p in presets if p["name"] == "user_test"]
            assert "user" in sources