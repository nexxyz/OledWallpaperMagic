import pytest
from pathlib import Path
import json
import shutil

from oled_wallpaper_magic.session.manager import SessionManager
from oled_wallpaper_magic.session.metadata import Session, ImageRecord, new_session_id
from oled_wallpaper_magic.config import AppConfig, Resolution


class TestSessionLifecycle:
    """Test session lifecycle - HIGH risk: data loss/corruption"""

    def test_create_session_generates_valid_id(self, temp_dir):
        manager = SessionManager(temp_dir)
        config = AppConfig(resolution=Resolution(width=160, height=90))
        session = manager.create_session(config, count=5)

        assert session.id.startswith("session_")
        assert len(session.images) == 5

    def test_session_save_load_roundtrip(self, temp_dir, sample_config):
        manager = SessionManager(temp_dir)
        session = manager.create_session(sample_config, count=3)

        session.images[0].filename = "img_0001.png"
        session.images[0].seed = 12345
        session.images[0].circle_count = 5
        session.review_state = {"img_0001.png": "keep", "img_0002.png": "discard"}

        manager.save_session(session)

        loaded = manager.load_session(session.id)

        assert loaded.id == session.id
        assert loaded.config is not None
        assert len(loaded.images) == 3
        assert loaded.review_state["img_0001.png"] == "keep"

    def test_session_images_have_expected_structure(self, temp_dir, sample_config):
        manager = SessionManager(temp_dir)
        session = manager.create_session(sample_config, count=2)

        assert session.images[0].index == 1
        assert session.images[0].seed == 0
        assert session.images[0].filename == ""

    def test_load_session_missing_file_raises(self, temp_dir):
        manager = SessionManager(temp_dir)
        with pytest.raises(FileNotFoundError):
            manager.load_session("nonexistent_session")

    def test_load_session_corrupted_json_raises(self, temp_dir):
        session_dir = temp_dir / "session_test"
        session_dir.mkdir()
        metadata_file = session_dir / "metadata.json"
        metadata_file.write_text("{ broken json")

        manager = SessionManager(temp_dir)
        with pytest.raises(ValueError, match="Corrupted"):
            manager.load_session("session_test")

    def test_session_finalize_copies_kept_only(self, temp_dir, tiny_config):
        manager = SessionManager(temp_dir)
        session = manager.create_session(tiny_config, count=3)

        gen_dir = session.root / "generated"
        gen_dir.mkdir(parents=True, exist_ok=True)

        (gen_dir / "img_0001.png").write_bytes(b"fake image 1")
        (gen_dir / "img_0002.png").write_bytes(b"fake image 2")
        (gen_dir / "img_0003.png").write_bytes(b"fake image 3")

        session.images[0].filename = "img_0001.png"
        session.images[1].filename = "img_0002.png"
        session.images[2].filename = "img_0003.png"

        session.review_state = {
            "img_0001.png": "keep",
            "img_0002.png": "discard",
            "img_0003.png": "keep",
        }

        save_dir = temp_dir / "kept"
        kept_count = manager.finalize(session, save_dir, purge=False)

        assert kept_count == 2
        assert len(list(save_dir.glob("*.png"))) == 2

    def test_list_sessions(self, temp_dir, sample_config):
        import time
        manager = SessionManager(temp_dir)

        session1 = manager.create_session(sample_config, count=2)
        time.sleep(1.1)
        session2 = manager.create_session(sample_config, count=2)

        sessions = manager.list_sessions()
        assert len(sessions) >= 1
        ids = [s["id"] for s in sessions]
        assert session1.id in ids


class TestSessionMetadata:
    """Test session metadata structures"""

    def test_new_session_id_format(self):
        sid = new_session_id()
        assert sid.startswith("session_")
        assert len(sid) > 10

    def test_image_record_defaults(self):
        img = ImageRecord()
        assert img.filename == ""
        assert img.index == 0
        assert img.seed == 0
        assert img.circle_count == 0

    def test_session_defaults(self, temp_dir):
        session = Session(
            id="test_session",
            root=temp_dir,
            config=None,
            images=[],
            review_state={},
            current_index=0,
        )
        assert session.id == "test_session"
        assert session.current_index == 0
        assert len(session.review_state) == 0