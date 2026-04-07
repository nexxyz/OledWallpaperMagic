from __future__ import annotations

import contextlib
import importlib
import json
import random
from pathlib import Path

from oled_wallpaper_magic.config import (
    DEFAULT_SEED_RANGE,
    AppConfig,
    parse_color,
)
from oled_wallpaper_magic.generator.engine import GenerationEngine
from oled_wallpaper_magic.presets import preset_store
from oled_wallpaper_magic.session.manager import SessionManager
from oled_wallpaper_magic.uiqt.preview import render_preview_pixmap
from oled_wallpaper_magic.uiqt.review import ReviewWindow

_qt_pkg = "".join(["Py", "Side6"])
QtCore = importlib.import_module(".".join([_qt_pkg, "Qt" + "Core"]))
QtGui = importlib.import_module(".".join([_qt_pkg, "Qt" + "Gui"]))
QtWidgets = importlib.import_module(".".join([_qt_pkg, "Qt" + "Widgets"]))

QThread = QtCore.QThread
QTimer = QtCore.QTimer
Qt = QtCore.Qt
Signal = QtCore.Signal

QIntValidator = QtGui.QIntValidator

QApplication = QtWidgets.QApplication
QCheckBox = QtWidgets.QCheckBox
QComboBox = QtWidgets.QComboBox
QFileDialog = QtWidgets.QFileDialog
QFrame = QtWidgets.QFrame
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QGridLayout = QtWidgets.QGridLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QMainWindow = QtWidgets.QMainWindow
QMessageBox = QtWidgets.QMessageBox
QProgressDialog = QtWidgets.QProgressDialog
QPushButton = QtWidgets.QPushButton
QScrollArea = QtWidgets.QScrollArea
QSizePolicy = QtWidgets.QSizePolicy
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QSplitter = QtWidgets.QSplitter
QToolButton = QtWidgets.QToolButton
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget


def _random_hex(rng: random.Random) -> str:
    return f"#{rng.randint(0, 255):02X}{rng.randint(0, 255):02X}{rng.randint(0, 255):02X}"


def _is_unlocked(key: str, locks: dict[str, bool]) -> bool:
    return not locks.get(key, False)


def _randomize_generation_params(cfg: AppConfig, locks: dict[str, bool], rng: random.Random) -> None:
    if _is_unlocked("min_circles", locks):
        cfg.generation.min_circles = rng.randint(1, 30)
    if _is_unlocked("max_circles", locks):
        cfg.generation.max_circles = rng.randint(max(cfg.generation.min_circles, 2), 100)
    if _is_unlocked("min_radius", locks):
        cfg.generation.min_radius = rng.randint(10, 500)
    if _is_unlocked("max_radius", locks):
        cfg.generation.max_radius = rng.randint(max(cfg.generation.min_radius, 50), 2000)
    if _is_unlocked("curve", locks):
        cfg.generation.curve = rng.choice(["linear", "ease", "exp", "gaussian", "flat"])
    if _is_unlocked("curve_param", locks):
        cfg.generation.curve_param = round(rng.uniform(0.3, 5.0), 2)
    if _is_unlocked("glow_strength", locks):
        cfg.generation.glow_strength = round(rng.uniform(0.0, 1.2), 2)
    if _is_unlocked("glow_mu", locks):
        cfg.generation.glow_mu = round(rng.uniform(0.6, 1.0), 2)
    if _is_unlocked("glow_sigma", locks):
        cfg.generation.glow_sigma = round(rng.uniform(0.02, 0.2), 2)
    if _is_unlocked("opacity_min", locks):
        cfg.generation.primary_opacity_min = round(rng.uniform(0.0, 0.7), 2)
    if _is_unlocked("opacity_max", locks):
        cfg.generation.primary_opacity_max = round(
            rng.uniform(max(cfg.generation.primary_opacity_min, 0.2), 1.0), 2
        )


def _randomize_color_params(cfg: AppConfig, locks: dict[str, bool], rng: random.Random) -> None:
    if _is_unlocked("background", locks):
        cfg.colors.background = (0, 0, 0)
    if _is_unlocked("glow", locks):
        cfg.colors.glow = parse_color(_random_hex(rng))  # type: ignore[assignment]
    if _is_unlocked("primary", locks):
        cfg.colors.primary = parse_color(_random_hex(rng))  # type: ignore[assignment]
        cfg.colors.primary_is_random = False
    if _is_unlocked("secondary", locks):
        cfg.colors.secondary = parse_color(_random_hex(rng))  # type: ignore[assignment]
        cfg.colors.secondary_is_random = False


def _randomize_seed(cfg: AppConfig, locks: dict[str, bool], rng: random.Random) -> None:
    if _is_unlocked("seed", locks):
        cfg.seed = rng.randint(0, DEFAULT_SEED_RANGE)


def _randomize_config_unlocked(base: AppConfig, locks: dict[str, bool], rng: random.Random) -> AppConfig:
    cfg = base.model_copy(deep=True)
    _randomize_generation_params(cfg, locks, rng)
    _randomize_color_params(cfg, locks, rng)
    _randomize_seed(cfg, locks, rng)
    return cfg


class GenerationThread(QThread):
    progressed = Signal(int, int)
    failed = Signal(str)
    done = Signal(object, bool)

    def __init__(
        self,
        cfg: AppConfig,
        locks: dict[str, bool],
        randomize_unlocked_per_image: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.cfg = cfg
        self.locks = dict(locks)
        self.randomize_unlocked_per_image = randomize_unlocked_per_image
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            manager = SessionManager(self.cfg.session.temp_dir)
            session = manager.create_session(self.cfg, self.cfg.session.count)
            engine = GenerationEngine(self.cfg)
            generated = session.root / "generated"
            generated.mkdir(parents=True, exist_ok=True)

            seed = self.cfg.seed if self.cfg.seed is not None else random.randint(0, DEFAULT_SEED_RANGE)
            if self.randomize_unlocked_per_image:
                rng = random.Random(seed)
                for i in range(len(session.images)):
                    if self._cancel_requested:
                        break
                    item_cfg = _randomize_config_unlocked(self.cfg, self.locks, rng)
                    item_seed = seed + i
                    item_engine = GenerationEngine(item_cfg)
                    image_data = item_engine.generate_single(item_seed)
                    img_path = generated / f"img_{i + 1:04d}.png"
                    image_data.save(img_path)
                    session.images[i].filename = img_path.name
                    session.images[i].seed = image_data.seed
                    session.images[i].circle_count = image_data.circle_count
                    session.images[i].generation_time_ms = image_data.generation_time_ms
                    self.progressed.emit(i + 1, len(session.images))
            else:
                for i, image_data in enumerate(engine.generate_batch(len(session.images), seed)):
                    if self._cancel_requested:
                        break
                    img_path = generated / f"img_{i + 1:04d}.png"
                    image_data.save(img_path)
                    session.images[i].filename = img_path.name
                    session.images[i].seed = image_data.seed
                    session.images[i].circle_count = image_data.circle_count
                    session.images[i].generation_time_ms = image_data.generation_time_ms
                    self.progressed.emit(i + 1, len(session.images))

            session.review_state = {img.filename: "unddecided" for img in session.images if img.filename}
            session.current_index = 0
            manager.save_session(session)
            self.done.emit(session, self._cancel_requested)
        except Exception as exc:  # pragma: no cover - UI path
            self.failed.emit(str(exc))


class ConfigPanelMixin:
    """Mixin providing config panel UI building and management."""

    def _build_controls(self) -> None:
        self.width_spin = self._spin(640, 7680, self.config.resolution.width)
        self.height_spin = self._spin(360, 4320, self.config.resolution.height)
        self.count_spin = self._spin(1, 300, self.config.session.count)

        self.min_circles = self._spin(1, 50, self.config.generation.min_circles)
        self.max_circles = self._spin(1, 100, self.config.generation.max_circles)
        self.min_radius = self._spin(10, 1000, self.config.generation.min_radius)
        self.max_radius = self._spin(10, 2000, self.config.generation.max_radius)

        self.curve_combo = QComboBox()
        self.curve_combo.addItems(["linear", "ease", "exp", "gaussian", "flat"])
        self.curve_combo.setCurrentText(self.config.generation.curve)
        self.curve_combo.wheelEvent = self._disable_wheel

        self.preset_combo = QComboBox()
        self.preset_combo.wheelEvent = self._disable_wheel
        self.preset_name_edit = QLineEdit("")
        self.preset_name_edit.setPlaceholderText("preset name")
        self.preset_name_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.curve_param = self._dspin(0.1, 10.0, self.config.generation.curve_param, 0.1)
        self.glow_strength = self._dspin(0.0, 1.5, self.config.generation.glow_strength, 0.05)
        self.glow_mu = self._dspin(0.0, 1.0, self.config.generation.glow_mu, 0.01)
        self.glow_sigma = self._dspin(0.01, 0.5, self.config.generation.glow_sigma, 0.01)
        self.opacity_min = self._dspin(0.0, 1.0, self.config.generation.primary_opacity_min, 0.05)
        self.opacity_max = self._dspin(0.0, 1.0, self.config.generation.primary_opacity_max, 0.05)

        self.bg_hex = self._hex_edit("#000000")
        self.primary_hex = self._hex_edit("#A0C8FF")
        self.secondary_hex = self._hex_edit("#FFC090")
        self.glow_hex = self._hex_edit("#FFF3C8")

        self.randomize_on_generate = QCheckBox("Randomize unlocked during batch")
        self.randomize_on_generate.setChecked(False)

        self.workers_spin = self._spin(0, 64, self.config.generation.workers)

        self.save_dir_edit = QLineEdit(str(self.config.session.save_dir))
        self.save_dir_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.save_dir_browse_btn = QPushButton("Browse")

        self.seed_edit = QLineEdit("")
        self.seed_edit.setPlaceholderText("blank = random")
        self.seed_edit.setValidator(QIntValidator())
        self.seed_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.screen_res_btn = QPushButton("Use Current Screen Resolution")
        self.screen_res_btn.clicked.connect(self.use_current_screen_resolution)

        self.form.addRow("Width", self.width_spin)
        self.form.addRow("Height", self.height_spin)
        self.form.addRow("", self.screen_res_btn)

        top_section = QGroupBox("Presets & Randomization")
        top_layout = QVBoxLayout(top_section)
        top_layout.setContentsMargins(10, 12, 10, 10)
        top_layout.setSpacing(8)

        preset_grid_widget = QWidget()
        preset_grid = QGridLayout(preset_grid_widget)
        preset_grid.setContentsMargins(0, 0, 0, 0)
        preset_grid.setHorizontalSpacing(6)
        preset_grid.setVerticalSpacing(6)

        preset_pick_row = QWidget()
        preset_pick_layout = QHBoxLayout(preset_pick_row)
        preset_pick_layout.setContentsMargins(0, 0, 0, 0)
        preset_pick_layout.setSpacing(6)
        preset_pick_layout.addWidget(self.preset_combo)

        preset_grid.addWidget(preset_pick_row, 0, 0)
        preset_grid.addWidget(self.preset_name_edit, 0, 1)
        preset_grid.addWidget(self.load_preset_btn, 1, 0)
        preset_grid.addWidget(self.save_preset_btn, 1, 1)
        preset_grid.setColumnStretch(0, 1)
        preset_grid.setColumnStretch(1, 1)

        top_layout.addWidget(preset_grid_widget)

        self.randomize_btn = QPushButton("Randomize")
        randomization_row = QWidget()
        randomization_layout = QHBoxLayout(randomization_row)
        randomization_layout.setContentsMargins(0, 0, 0, 0)
        randomization_layout.setSpacing(6)
        randomization_layout.addWidget(self.randomize_btn)
        randomization_layout.addWidget(self.lock_all_btn)
        randomization_layout.addWidget(self.unlock_all_btn)
        randomization_layout.addStretch(1)
        self.form.addRow(top_section)
        self.form.addRow(randomization_row)
        self._add_locked_row("Min circles", self.min_circles, "min_circles")
        self._add_locked_row("Max circles", self.max_circles, "max_circles")
        self._add_locked_row("Min radius", self.min_radius, "min_radius")
        self._add_locked_row("Max radius", self.max_radius, "max_radius")
        self._add_locked_row("Curve", self.curve_combo, "curve")
        self._add_locked_row("Sharpness", self.curve_param, "curve_param")
        self._add_locked_row("Glow strength", self.glow_strength, "glow_strength")
        self._add_locked_row("Glow position", self.glow_mu, "glow_mu")
        self._add_locked_row("Glow width", self.glow_sigma, "glow_sigma")
        self._add_locked_row("Min opacity", self.opacity_min, "opacity_min")
        self._add_locked_row("Max opacity", self.opacity_max, "opacity_max")
        self._add_locked_row("Background", self.bg_hex, "background")

        pri_row = QWidget()
        pri_layout = QHBoxLayout(pri_row)
        pri_layout.setContentsMargins(0, 0, 0, 0)
        pri_layout.addWidget(self.primary_hex)
        self._add_locked_row("Primary", pri_row, "primary")

        sec_row = QWidget()
        sec_layout = QHBoxLayout(sec_row)
        sec_layout.setContentsMargins(0, 0, 0, 0)
        sec_layout.addWidget(self.secondary_hex)
        self._add_locked_row("Secondary", sec_row, "secondary")

        self._add_locked_row("Glow", self.glow_hex, "glow")
        self._add_locked_row("Seed", self.seed_edit, "seed")

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.form.addRow(sep)

        batch_section = QGroupBox("Batch Creation")
        batch_layout = QVBoxLayout(batch_section)
        batch_layout.setContentsMargins(10, 12, 10, 10)
        batch_layout.setSpacing(8)

        batch_form = QFormLayout()
        batch_form.setSpacing(6)
        batch_form.addRow("Count", self.count_spin)

        save_row = QWidget()
        save_layout = QHBoxLayout(save_row)
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.setSpacing(6)
        save_layout.addWidget(self.save_dir_edit, 1)
        save_layout.addWidget(self.save_dir_browse_btn)
        batch_form.addRow("Output folder", save_row)
        batch_form.addRow("Workers", self.workers_spin)
        batch_form.addRow("Randomization", self.randomize_on_generate)
        batch_layout.addLayout(batch_form)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.generate_btn = QPushButton("Generate Batch")
        self.open_btn = QPushButton("Open Session")
        self.cleanup_btn = QPushButton("Clean Up Sessions")
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.cleanup_btn)
        batch_layout.addWidget(btn_row)
        self.form.addRow(batch_section)

        widgets = [
            self.width_spin,
            self.height_spin,
            self.min_circles,
            self.max_circles,
            self.min_radius,
            self.max_radius,
            self.curve_param,
            self.glow_strength,
            self.glow_mu,
            self.glow_sigma,
            self.opacity_min,
            self.opacity_max,
        ]
        for w in widgets:
            w.valueChanged.connect(self.schedule_preview)
        self.curve_combo.currentTextChanged.connect(self.schedule_preview)
        self.bg_hex.editingFinished.connect(self.schedule_preview)
        self.primary_hex.editingFinished.connect(self.schedule_preview)
        self.secondary_hex.editingFinished.connect(self.schedule_preview)
        self.glow_hex.editingFinished.connect(self.schedule_preview)
        self.seed_edit.editingFinished.connect(self.schedule_preview)

        self.generate_btn.clicked.connect(self.start_generation)
        self.open_btn.clicked.connect(self.open_session)
        self.cleanup_btn.clicked.connect(self.cleanup_sessions)
        self.save_dir_browse_btn.clicked.connect(self.browse_save_dir)
        self.load_preset_btn.clicked.connect(self.apply_selected_preset)
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        self.randomize_btn.clicked.connect(self.randomize_all_but_resolution)
        self.shuffle_preview_btn.clicked.connect(self.shuffle_preview_seeds)
        self.randomize_per_preview_chk.toggled.connect(self.schedule_preview)
        self.lock_all_btn.clicked.connect(self.lock_all)
        self.unlock_all_btn.clicked.connect(self.unlock_all)

        self._refresh_preset_names()
        self._refresh_lock_buttons()
        self._sync_form_from_config()
        self._setup_tooltips()

    def _setup_tooltips(self) -> None:
        self.width_spin.setToolTip("Final image width in pixels.")
        self.height_spin.setToolTip("Final image height in pixels.")
        self.preset_combo.setToolTip("Choose a preset configuration to apply.")
        self.min_circles.setToolTip("Minimum circles per image.")
        self.max_circles.setToolTip("Maximum circles per image.")
        self.min_radius.setToolTip("Minimum circle radius in pixels.")
        self.max_radius.setToolTip("Maximum circle radius in pixels.")
        self.curve_combo.setToolTip("Falloff curve: flat creates a solid center with hard edge.")
        self.curve_param.setToolTip("Curve sharpness parameter.")
        self.glow_strength.setToolTip("Glow intensity around circle edges.")
        self.glow_mu.setToolTip("Glow ring position as fraction of radius.")
        self.glow_sigma.setToolTip("Glow ring width.")
        self.opacity_min.setToolTip("Minimum per-circle opacity.")
        self.opacity_max.setToolTip("Maximum per-circle opacity.")
        self.bg_hex.setToolTip("Background color in hex (e.g. #000000).")
        self.primary_hex.setToolTip("Primary circle color in hex (e.g. #AABBCC).")
        self.secondary_hex.setToolTip("Secondary circle color in hex (e.g. #AABBCC).")
        self.glow_hex.setToolTip("Glow color in hex.")
        self.seed_edit.setToolTip("Seed for reproducible output. Blank = random.")
        self.screen_res_btn.setToolTip("Set Width/Height from your current primary display resolution.")
        self.randomize_btn.setToolTip("Randomize unlocked parameters for exploration.")
        self.preset_name_edit.setToolTip("Name for saving a custom preset.")

        self.lock_all_btn.setToolTip("Lock every parameter from randomization.")
        self.unlock_all_btn.setToolTip("Unlock every parameter for randomization.")
        self.save_preset_btn.setToolTip("Save current non-batch settings as a custom preset.")
        self.load_preset_btn.setToolTip("Load selected preset (keeps resolution and batch settings).")

        self.count_spin.setToolTip("How many wallpapers to generate in this batch.")
        self.save_dir_edit.setToolTip("Destination folder for kept wallpapers after finalize.")
        self.save_dir_browse_btn.setToolTip("Choose output folder.")
        self.randomize_on_generate.setToolTip(
            "If enabled, each generated image randomizes unlocked parameters."
        )
        self.workers_spin.setToolTip("Parallel worker count for generation (0 = auto / all cores).")
        self.generate_btn.setToolTip("Generate a batch and open review for the session.")
        self.open_btn.setToolTip("Open an existing saved session for review.")
        self.cleanup_btn.setToolTip(
            "Delete all session folders in the temp directory "
            "(keeps your saved wallpapers)."
        )

        self.shuffle_preview_btn.setToolTip("Change preview seeds without changing any settings.")
        self.randomize_per_preview_chk.setToolTip(
            "When enabled, each preview tile randomizes unlocked parameters before rendering."
        )
        for i, lbl in enumerate(self.preview_labels):
            lbl.setToolTip(f"Live preview tile {i + 1}.")
        for i, btn in enumerate(self.preview_save_buttons):
            btn.setToolTip(f"Save Preview {i + 1} at full configured resolution.")

    def _refresh_preset_names(self) -> None:
        current = self.preset_combo.currentText().strip()
        self.preset_combo.clear()
        self._preset_lookup = {}

        for p in preset_store.list_presets():
            name = p["name"]
            self._preset_lookup[name] = name

        self.preset_combo.addItems(list(self._preset_lookup.keys()))
        if current and current in self._preset_lookup:
            self.preset_combo.setCurrentText(current)

    def save_current_preset(self) -> None:
        self._apply_form_to_config()
        name = self.preset_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Preset name required", "Enter a preset name to save.")
            return
        safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", " ")).strip().replace(" ", "_")
        if not safe:
            QMessageBox.warning(self, "Invalid name", "Preset name must contain letters or digits.")
            return

        data = {
            "generation": {
                **self.config.generation.model_dump(mode="json"),
                "workers": None,
            },
            "colors": self.config.colors.model_dump(mode="json"),
            "seed": self.config.seed,
            "locks": self._lock_state,
        }
        data["generation"].pop("workers", None)

        preset_store.save(safe, data)
        self._refresh_preset_names()
        self.preset_combo.setCurrentText(safe)

    def _default_lock_state(self) -> dict[str, bool]:
        return {
            "width": True,
            "height": True,
            "min_circles": False,
            "max_circles": False,
            "min_radius": False,
            "max_radius": False,
            "curve": False,
            "curve_param": False,
            "glow_strength": False,
            "glow_mu": False,
            "glow_sigma": False,
            "opacity_min": False,
            "opacity_max": False,
            "background": False,
            "primary": False,
            "secondary": False,
            "glow": False,
            "seed": False,
        }

    def _apply_default_style(self) -> None:
        self.config.generation.min_circles = 8
        self.config.generation.max_circles = 30
        self.config.generation.min_radius = 47
        self.config.generation.max_radius = 1012
        self.config.generation.curve = "linear"
        self.config.generation.curve_param = 1.14
        self.config.generation.glow_strength = 0.64
        self.config.generation.glow_mu = 0.83
        self.config.generation.glow_sigma = 0.10
        self.config.generation.primary_opacity_min = 0.48
        self.config.generation.primary_opacity_max = 1.0

        self.config.colors.background = (0, 0, 0)
        self.config.colors.primary = (102, 74, 55)
        self.config.colors.secondary = (70, 78, 155)
        self.config.colors.glow = (84, 45, 233)
        self.config.colors.primary_is_random = False
        self.config.colors.secondary_is_random = False

        self.config.seed = 1471975476

    def _load_lock_state(self) -> dict[str, bool]:
        state = self._default_lock_state()
        try:
            if self._locks_path.exists():
                data = json.loads(self._locks_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k in state:
                            state[k] = bool(v)
        except Exception:
            pass
        return state

    def _load_config_from_state(self, data: dict) -> None:
        cfg_data = data.get("config")
        if isinstance(cfg_data, dict):
            with contextlib.suppress(Exception):
                self.config = AppConfig.model_validate(cfg_data)

    def _load_resolution_from_state(self, data: dict) -> None:
        explicit_res = data.get("resolution")
        if isinstance(explicit_res, dict):
            width = explicit_res.get("width")
            height = explicit_res.get("height")
            if isinstance(width, int) and isinstance(height, int):
                self.config.resolution.width = width
                self.config.resolution.height = height

    def _load_save_dir_from_state(self, data: dict) -> None:
        save_dir = data.get("last_preview_save_dir")
        if isinstance(save_dir, str) and save_dir:
            self._last_preview_save_dir = Path(save_dir)

    def _load_locks_from_state(self, data: dict) -> None:
        lock_data = data.get("locks")
        if isinstance(lock_data, dict):
            merged = self._default_lock_state()
            for k, v in lock_data.items():
                if k in merged:
                    merged[k] = bool(v)
            self._lock_state = merged

    def _load_checkbox_states(self, data: dict) -> None:
        batch_rand = data.get("randomize_on_generate")
        if isinstance(batch_rand, bool):
            self.randomize_on_generate.blockSignals(True)
            self.randomize_on_generate.setChecked(batch_rand)
            self.randomize_on_generate.blockSignals(False)
        preview_rand = data.get("randomize_per_preview")
        if isinstance(preview_rand, bool):
            self.randomize_per_preview_chk.blockSignals(True)
            self.randomize_per_preview_chk.setChecked(preview_rand)
            self.randomize_per_preview_chk.blockSignals(False)

    def _load_preset_name_from_state(self, data: dict) -> None:
        preset_name = data.get("preset_name")
        if isinstance(preset_name, str) and preset_name:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText(preset_name)
            self.preset_combo.blockSignals(False)

    def _load_ui_state(self) -> None:
        try:
            if not self._ui_state_path.exists():
                return
            data = json.loads(self._ui_state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return

            self._load_config_from_state(data)
            self._load_resolution_from_state(data)
            self._load_save_dir_from_state(data)
            self._load_locks_from_state(data)
            self._load_checkbox_states(data)
            self._load_preset_name_from_state(data)
            self._refresh_lock_buttons()
            self._sync_form_from_config()
        except Exception:
            pass

    def _save_ui_state(self) -> None:
        try:
            self._apply_form_to_config()
            payload = {
                "version": 1,
                "resolution": {
                    "width": self.config.resolution.width,
                    "height": self.config.resolution.height,
                },
                "config": self.config.model_dump(mode="json"),
                "locks": self._lock_state,
                "randomize_on_generate": self.randomize_on_generate.isChecked(),
                "randomize_per_preview": self.randomize_per_preview_chk.isChecked(),
                "last_preview_save_dir": str(self._last_preview_save_dir),
                "preset_name": self.preset_combo.currentText(),
            }
            self._ui_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._ui_state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def save_lock_state(self) -> None:
        try:
            self._locks_path.parent.mkdir(parents=True, exist_ok=True)
            self._locks_path.write_text(json.dumps(self._lock_state, indent=2), encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "Save locks failed", str(exc))

    def _refresh_lock_buttons(self) -> None:
        for key, btn in self._lock_buttons.items():
            locked = self._lock_state.get(key, False)
            btn.setText("🔒" if locked else "🔓")
            btn.setToolTip("Locked: excluded from randomization" if locked else "Unlocked: randomized")

    def _toggle_lock(self, key: str) -> None:
        self._lock_state[key] = not self._lock_state.get(key, False)
        self._refresh_lock_buttons()

    def lock_all(self) -> None:
        for key in self._lock_state:
            self._lock_state[key] = True
        self._refresh_lock_buttons()

    def unlock_all(self) -> None:
        for key in self._lock_state:
            self._lock_state[key] = False
        self._refresh_lock_buttons()

    def _wrap_with_lock(self, widget: QWidget, key: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(6)
        layout.addWidget(widget, 1)
        btn = QToolButton()
        btn.setAutoRaise(False)
        btn.setFixedWidth(28)
        btn.clicked.connect(lambda _=False, k=key: self._toggle_lock(k))
        self._lock_buttons[key] = btn
        layout.addWidget(btn)
        return row

    def _add_locked_row(self, label: str, widget: QWidget, key: str) -> None:
        row = self._wrap_with_lock(widget, key)
        self.form.addRow(label, row)

    def browse_save_dir(self) -> None:
        start = self.save_dir_edit.text().strip() or str(Path.cwd())
        directory = QFileDialog.getExistingDirectory(self, "Select output folder", start)
        if directory:
            self.save_dir_edit.setText(directory)

    def use_current_screen_resolution(self) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return
        size = screen.size()
        self.width_spin.setValue(max(640, int(size.width())))
        self.height_spin.setValue(max(360, int(size.height())))
        self.schedule_preview()

    def _sync_form_from_config(self) -> None:
        self._loading_form = True
        try:
            self.width_spin.setValue(self.config.resolution.width)
            self.height_spin.setValue(self.config.resolution.height)
            self.count_spin.setValue(self.config.session.count)

            g = self.config.generation
            self.min_circles.setValue(g.min_circles)
            self.max_circles.setValue(g.max_circles)
            self.min_radius.setValue(g.min_radius)
            self.max_radius.setValue(g.max_radius)
            self.curve_combo.setCurrentText(g.curve)
            self.curve_param.setValue(g.curve_param)
            self.glow_strength.setValue(g.glow_strength)
            self.glow_mu.setValue(g.glow_mu)
            self.glow_sigma.setValue(g.glow_sigma)
            self.opacity_min.setValue(g.primary_opacity_min)
            self.opacity_max.setValue(g.primary_opacity_max)

            bg = self.config.colors.background
            self.bg_hex.setText(f"#{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}")
            glow = self.config.colors.glow
            self.glow_hex.setText(f"#{glow[0]:02X}{glow[1]:02X}{glow[2]:02X}")

            primary = self.config.colors.primary
            secondary = self.config.colors.secondary
            if isinstance(primary, tuple):
                self.primary_hex.setText(f"#{primary[0]:02X}{primary[1]:02X}{primary[2]:02X}")
            else:
                self.primary_hex.setText("#A0C8FF")
            if isinstance(secondary, tuple):
                self.secondary_hex.setText(f"#{secondary[0]:02X}{secondary[1]:02X}{secondary[2]:02X}")
            else:
                self.secondary_hex.setText("#FFC090")

            self.seed_edit.setText("" if self.config.seed is None else str(self.config.seed))
            self.save_dir_edit.setText(str(self.config.session.save_dir))
            self.workers_spin.setValue(self.config.generation.workers)
        finally:
            self._loading_form = False

    def _preserve_session_fields(self) -> tuple:
        return (
            self.config.resolution.model_copy(deep=True),
            self.config.session.count,
            self.config.session.save_dir,
            self.config.session.temp_dir,
            self.config.generation.workers,
        )

    def _restore_session_fields(self, preserve: tuple) -> None:
        self.config.resolution = preserve[0]
        self.config.session.count = preserve[1]
        self.config.session.save_dir = preserve[2]
        self.config.session.temp_dir = preserve[3]
        self.config.generation.workers = preserve[4]

    def _apply_preset_locks(self, lock_data: dict | None) -> None:
        if not isinstance(lock_data, dict):
            return
        merged = self._default_lock_state()
        for k, v in lock_data.items():
            if k in merged:
                merged[k] = bool(v)
        self._lock_state = merged
        self._refresh_lock_buttons()

    def _load_preset_data(self, name: str) -> AppConfig | None:
        preset = preset_store.get(name)
        if preset is None:
            return None
        return preset.to_config()

    def apply_selected_preset(self) -> None:
        self._apply_form_to_config()
        key = self.preset_combo.currentText().strip()
        if key not in self._preset_lookup:
            QMessageBox.warning(self, "Preset not found", f"Preset '{key}' not found")
            return

        self.preset_name_edit.setText(key)
        preserve = self._preserve_session_fields()
        loaded = self._load_preset_data(key)

        if loaded is None:
            QMessageBox.warning(self, "Preset not found", f"Preset '{key}' not found")
            return

        self.config.generation = loaded.generation
        self.config.colors = loaded.colors
        self.config.seed = loaded.seed

        lock_data = self._load_preset_extra(key, "locks")
        self._apply_preset_locks(lock_data)

        self._restore_session_fields(preserve)
        self._sync_form_from_config()
        self.schedule_preview()

    def _load_preset_extra(self, name: str, key: str):
        preset = preset_store.get(name)
        if preset is None:
            return None
        return preset.data.get(key)

    def randomize_all_but_resolution(self) -> None:
        self._apply_form_to_config()
        rng = random.Random()
        self.config = _randomize_config_unlocked(self.config, self._lock_state, rng)
        self._sync_form_from_config()
        self.schedule_preview()

    def _spin(self, lo: int, hi: int, value: int) -> QSpinBox:
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(value)
        w.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        w.wheelEvent = self._disable_wheel
        return w

    def _dspin(self, lo: float, hi: float, value: float, step: float) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setValue(value)
        w.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        w.wheelEvent = self._disable_wheel
        return w

    def _disable_wheel(self, event) -> None:
        event.ignore()

    def _hex_edit(self, value: str) -> QLineEdit:
        w = QLineEdit(value)
        w.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        return w
        w.setPlaceholderText("#AABBCC")
        return w

    def _apply_resolution_to_config(self) -> None:
        self.config.resolution.width = self.width_spin.value()
        self.config.resolution.height = self.height_spin.value()
        self.config.session.count = self.count_spin.value()
        save_dir_text = self.save_dir_edit.text().strip()
        self.config.session.save_dir = Path(save_dir_text or str(self.config.session.save_dir))

    def _apply_generation_to_config(self) -> None:
        g = self.config.generation
        g.min_circles = self.min_circles.value()
        g.max_circles = self.max_circles.value()
        g.min_radius = self.min_radius.value()
        g.max_radius = self.max_radius.value()
        g.curve = self.curve_combo.currentText()  # type: ignore[assignment]
        g.curve_param = self.curve_param.value()
        g.glow_strength = self.glow_strength.value()
        g.glow_mu = self.glow_mu.value()
        g.glow_sigma = self.glow_sigma.value()
        g.primary_opacity_min = self.opacity_min.value()
        g.primary_opacity_max = self.opacity_max.value()
        g.workers = self.workers_spin.value()

    def _apply_background_color(self) -> None:
        try:
            parsed_bg = parse_color(self.bg_hex.text())
            if isinstance(parsed_bg, tuple):
                self.config.colors.background = parsed_bg
        except Exception:
            pass

    def _apply_glow_color(self) -> None:
        try:
            parsed_glow = parse_color(self.glow_hex.text())
            if isinstance(parsed_glow, tuple):
                self.config.colors.glow = parsed_glow
        except Exception:
            pass

    def _apply_primary_color(self) -> None:
        try:
            parsed_primary = parse_color(self.primary_hex.text())
            if isinstance(parsed_primary, tuple):
                self.config.colors.primary = parsed_primary
                self.config.colors.primary_is_random = False
        except Exception:
            pass

    def _apply_secondary_color(self) -> None:
        try:
            parsed_secondary = parse_color(self.secondary_hex.text())
            if isinstance(parsed_secondary, tuple):
                self.config.colors.secondary = parsed_secondary
                self.config.colors.secondary_is_random = False
        except Exception:
            pass

    def _apply_colors_to_config(self) -> None:
        self._apply_background_color()
        self._apply_glow_color()
        self._apply_primary_color()
        self._apply_secondary_color()

    def _apply_seed_to_config(self) -> None:
        seed_text = self.seed_edit.text().strip()
        self.config.seed = int(seed_text) if seed_text else None

    def _apply_form_to_config(self) -> None:
        if self._loading_form:
            return
        self._apply_resolution_to_config()
        self._apply_generation_to_config()
        self._apply_colors_to_config()
        self._apply_seed_to_config()


class PreviewMixin:
    """Mixin providing preview rendering functionality."""

    def schedule_preview(self) -> None:
        if self._loading_form:
            return
        self._apply_form_to_config()
        self._preview_seed_override = None
        if hasattr(self, 'preview_timer'):
            self.preview_timer.start()

    def _render_previews(self) -> None:
        if self._preview_seed_override is not None:
            seed = self._preview_seed_override
        else:
            seed = self.config.seed if self.config.seed is not None else self._base_seed
        self._preview_seeds = [seed + i for i in range(4)]
        self._preview_configs = []
        for i, lbl in enumerate(self.preview_labels):
            preview_cfg = self.config
            if self.randomize_per_preview_chk.isChecked():
                preview_cfg = _randomize_config_unlocked(
                    self.config,
                    self._lock_state,
                    random.Random(self._preview_seeds[i]),
                )
            self._preview_configs.append(preview_cfg.model_copy(deep=True))
            pix = render_preview_pixmap(
                preview_cfg,
                self._preview_seeds[i],
                max(1, lbl.width()),
                max(1, lbl.height()),
            )
            lbl.setPixmap(pix)

    def shuffle_preview_seeds(self) -> None:
        self._preview_seed_override = random.randint(0, DEFAULT_SEED_RANGE)
        self.preview_timer.start()

    def save_full_size_preview(self, idx: int) -> None:
        self._apply_form_to_config()
        if idx < 0 or idx >= 4:
            idx = 0
        if not self._preview_seeds:
            self._render_previews()
        seed = self._preview_seeds[idx]
        res = self.config.resolution
        pix = render_preview_pixmap(self.config, seed, res.width, res.height)

        suggested = self._last_preview_save_dir / f"preview_{idx + 1}_{res.width}x{res.height}.png"
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Full-Size Preview",
            str(suggested),
            "PNG Images (*.png)",
        )
        if not out_path:
            return
        ok = pix.save(out_path, "PNG")
        if not ok:
            QMessageBox.critical(self, "Save failed", f"Could not save preview to:\n{out_path}")
            return
        self._last_preview_save_dir = Path(out_path).parent

    def freeze_preview_params(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._preview_configs):
            return
        self.config = self._preview_configs[idx].model_copy(deep=True)
        for key in self._lock_state:
            self._lock_state[key] = True
        self._refresh_lock_buttons()
        self._sync_form_from_config()
        QMessageBox.information(
            self,
            "Parameters Frozen",
            f"Preview {idx + 1} parameters applied to config and all parameters locked.",
        )
        self.schedule_preview()


class GenerationMixin:
    """Mixin providing generation and batch processing."""

    def start_generation(self) -> None:
        self._apply_form_to_config()
        if self._generation_thread and self._generation_thread.isRunning():
            return
        total_count = self.config.session.count
        self._progress = QProgressDialog(
            "Generating wallpapers...", "Cancel", 0, total_count, self
        )
        self._progress.setWindowTitle("Generation")
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.canceled.connect(self._cancel_generation)
        self._progress.show()

        self._generation_thread = GenerationThread(
            self.config,
            self._lock_state,
            self.randomize_on_generate.isChecked(),
        )
        self._generation_thread.progressed.connect(self._on_generation_progress)
        self._generation_thread.failed.connect(self._on_generation_failed)
        self._generation_thread.done.connect(self._on_generation_done)
        self._generation_thread.start()

    def _on_generation_progress(self, index: int, total: int) -> None:
        if self._progress is not None:
            self._progress.setMaximum(total)
            self._progress.setValue(index)
            self._progress.setLabelText(f"Generating {index}/{total}")

    def _on_generation_failed(self, message: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        QMessageBox.critical(self, "Generation failed", message)

    def _on_generation_done(self, session, canceled: bool) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        generated_count = sum(1 for img in session.images if img.filename)
        if generated_count == 0:
            if canceled:
                QMessageBox.information(self, "Generation canceled", "No images generated.")
            return
        if canceled:
            answer = QMessageBox.question(
                self,
                "Generation canceled",
                f"Generated {generated_count} images before cancel. Open review now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        review = ReviewWindow(session, 0, self)
        review.show()

    def _cancel_generation(self) -> None:
        if self._generation_thread and self._generation_thread.isRunning():
            self._generation_thread.request_cancel()

    def open_session(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Open session directory", str(Path.cwd()))
        if not directory:
            return
        path = Path(directory)
        try:
            manager = SessionManager(path.parent)
            session = manager.load_session(path.name)
        except Exception as exc:
            QMessageBox.critical(self, "Open session failed", str(exc))
            return
        review = ReviewWindow(session, session.current_index, self)
        review.show()

    def cleanup_sessions(self) -> None:
        self._apply_form_to_config()
        base_dir = self.config.session.temp_dir
        manager = SessionManager(base_dir)
        sessions = manager.list_sessions()
        if not sessions:
            QMessageBox.information(self, "No Sessions", "No session folders found to clean up.")
            return

        names = [s["id"] for s in sessions]
        msg = (
            f"Found {len(sessions)} session folder(s):\n\n"
            + "\n".join(f"  • {n}" for n in names)
            + "\n\nThis will delete all session folders (but not your kept wallpapers). Continue?"
        )
        answer = QMessageBox.question(
            self,
            "Clean Up Sessions",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for s in sessions:
            try:
                import shutil
                shutil.rmtree(Path(s["path"]))
                deleted += 1
            except Exception:
                pass
        QMessageBox.information(self, "Cleanup Complete", f"Deleted {deleted} session folder(s).")


class MainWindow(ConfigPanelMixin, PreviewMixin, GenerationMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OledWallpaperMagic")
        icon_path = Path(__file__).parent.parent.parent / "icons" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        self.resize(1400, 900)
        self.config = AppConfig()
        self._apply_default_style()
        self.config.generation.workers = 0
        self._base_seed = random.randint(0, DEFAULT_SEED_RANGE)
        self._preview_seed_override: int | None = None
        self._preview_seeds: list[int] = [self._base_seed + i for i in range(4)]
        self._preview_configs: list[AppConfig] = [self.config.model_copy(deep=True) for _ in range(4)]
        self._last_preview_save_dir = Path.cwd()
        self._locks_path = Path.home() / ".config" / "oled_wallpaper_magic" / "randomization_locks.json"
        self._ui_state_path = Path.home() / ".config" / "oled_wallpaper_magic" / "ui_state.json"
        self._ui_presets_dir = Path.home() / ".config" / "oled_wallpaper_magic" / "ui_presets"
        self._lock_state: dict[str, bool] = self._load_lock_state()
        self._lock_buttons: dict[str, QToolButton] = {}
        self._preset_lookup: dict[str, tuple[str, str]] = {}
        self._loading_form = False

        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumWidth(520)
        left_inner = QWidget()
        self.form = QFormLayout(left_inner)
        self.form.setSpacing(10)
        self.scroll.setWidget(left_inner)
        splitter.addWidget(self.scroll)

        self.lock_all_btn = QPushButton("Lock All")
        self.unlock_all_btn = QPushButton("Unlock All")
        self.save_preset_btn = QPushButton("Save Preset")
        self.load_preset_btn = QPushButton("Load Preset")

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.preview_grid = QGridLayout()
        self.preview_grid.setSpacing(8)
        self.preview_labels: list[QLabel] = []
        self.preview_save_buttons: list[QPushButton] = []
        for i in range(4):
            tile = QWidget()
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(0, 0, 0, 0)
            tile_layout.setSpacing(6)

            lbl = QLabel("Preview")
            lbl.setMinimumSize(300, 180)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background:#111; border:1px solid #333;")
            lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

            btn_row = QWidget()
            btn_layout = QHBoxLayout(btn_row)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(4)

            save_btn = QPushButton("Save full resolution")
            save_btn.setFixedWidth(120)
            save_btn.clicked.connect(lambda _=False, idx=i: self.save_full_size_preview(idx))
            save_btn.setToolTip(f"Save Preview {i + 1} at full configured resolution.")

            freeze_btn = QPushButton("Freeze these parameters")
            freeze_btn.setFixedWidth(140)
            freeze_btn.clicked.connect(lambda _=False, idx=i: self.freeze_preview_params(idx))
            freeze_btn.setToolTip(f"Apply Preview {i + 1} parameters to config and lock all.")

            btn_layout.addWidget(save_btn)
            btn_layout.addWidget(freeze_btn)

            tile_layout.addWidget(lbl, 1)
            tile_layout.addWidget(btn_row)

            self.preview_labels.append(lbl)
            self.preview_save_buttons.append(save_btn)
            self.preview_grid.addWidget(tile, i // 2, i % 2)
        right_layout.addLayout(self.preview_grid)

        tools_row = QWidget()
        tools_layout = QHBoxLayout(tools_row)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        self.shuffle_preview_btn = QPushButton("Shuffle Preview Seeds")
        tools_layout.addWidget(self.shuffle_preview_btn)
        tools_layout.addStretch(1)
        right_layout.addWidget(tools_row)

        self.randomize_per_preview_chk = QCheckBox("Randomize unlocked for each preview")
        right_layout.addWidget(self.randomize_per_preview_chk)

        splitter.addWidget(right)
        splitter.setSizes([520, 880])

        self._build_controls()
        self._load_ui_state()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self._render_previews)

        self._generation_thread: GenerationThread | None = None
        self._progress = None

        self.schedule_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.preview_timer.start()

    def closeEvent(self, event):
        self.save_lock_state()
        self._save_ui_state()
        super().closeEvent(event)


def launch_qt_gui() -> None:
    app = QApplication.instance()
    owned = app is None
    if app is None:
        app = QApplication([])
    win = MainWindow()
    win.show()
    if owned:
        app.exec()
