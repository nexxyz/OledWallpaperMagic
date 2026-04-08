from __future__ import annotations

import contextlib
import importlib
import json
import random
import sys
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
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QFileDialog = QtWidgets.QFileDialog
QColorDialog = QtWidgets.QColorDialog
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
QStyle = QtWidgets.QStyle
QToolButton = QtWidgets.QToolButton
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget


def _random_hex(rng: random.Random) -> str:
    return f"#{rng.randint(0, 255):02X}{rng.randint(0, 255):02X}{rng.randint(0, 255):02X}"


def _app_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "icons" / "icon.png"
    return Path(__file__).parent.parent.parent / "icons" / "icon.png"


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
    if _is_unlocked("curve_param_min", locks):
        cfg.generation.curve_param_min = round(rng.uniform(0.3, 4.0), 2)
    if _is_unlocked("curve_param_max", locks):
        cfg.generation.curve_param_max = round(rng.uniform(cfg.generation.curve_param_min, 6.0), 2)
    if _is_unlocked("glow_strength_min", locks):
        cfg.generation.glow_strength_min = round(rng.uniform(0.0, 0.8), 2)
    if _is_unlocked("glow_strength_max", locks):
        cfg.generation.glow_strength_max = round(
            rng.uniform(cfg.generation.glow_strength_min, 1.2),
            2,
        )
    if _is_unlocked("glow_mu_min", locks):
        cfg.generation.glow_mu_min = round(rng.uniform(0.6, 1.0), 2)
    if _is_unlocked("glow_mu_max", locks):
        cfg.generation.glow_mu_max = round(rng.uniform(cfg.generation.glow_mu_min, 1.2), 2)
    if _is_unlocked("glow_sigma_min", locks):
        cfg.generation.glow_sigma_min = round(rng.uniform(0.02, 0.12), 2)
    if _is_unlocked("glow_sigma_max", locks):
        cfg.generation.glow_sigma_max = round(rng.uniform(cfg.generation.glow_sigma_min, 0.2), 2)
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


class DualRangeSlider(QWidget):
    values_changed = Signal(int, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._minimum = 0
        self._maximum = 100
        self._lower = 25
        self._upper = 75
        self._active: str | None = None
        self._handle_radius = 6
        self.setMinimumHeight(24)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = max(minimum, maximum)
        self._lower = max(self._minimum, min(self._lower, self._maximum))
        self._upper = max(self._lower, min(self._upper, self._maximum))
        self.update()

    def setValues(self, lower: int, upper: int) -> None:
        lower = max(self._minimum, min(lower, self._maximum))
        upper = max(lower, min(upper, self._maximum))
        if self._lower == lower and self._upper == upper:
            return
        self._lower = lower
        self._upper = upper
        self.values_changed.emit(self._lower, self._upper)
        self.update()

    def _track_rect(self):
        margin = self._handle_radius + 2
        y = self.height() // 2 - 2
        return QtCore.QRect(margin, y, max(1, self.width() - 2 * margin), 4)

    def _x_from_value(self, value: int) -> int:
        rect = self._track_rect()
        if self._maximum == self._minimum:
            return rect.left()
        ratio = (value - self._minimum) / (self._maximum - self._minimum)
        return rect.left() + int(round(ratio * rect.width()))

    def _value_from_x(self, x: int) -> int:
        rect = self._track_rect()
        if rect.width() <= 0:
            return self._minimum
        clamped_x = max(rect.left(), min(x, rect.right()))
        ratio = (clamped_x - rect.left()) / rect.width()
        return int(round(self._minimum + ratio * (self._maximum - self._minimum)))

    def paintEvent(self, _event) -> None:
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = self._track_rect()

        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor("#4A4A4A"))
        p.drawRoundedRect(rect, 2, 2)

        x1 = self._x_from_value(self._lower)
        x2 = self._x_from_value(self._upper)
        selected = QtCore.QRect(min(x1, x2), rect.top(), abs(x2 - x1), rect.height())
        p.setBrush(QtGui.QColor("#6AA9FF"))
        p.drawRoundedRect(selected, 2, 2)

        for x in (x1, x2):
            p.setBrush(QtGui.QColor("#E6E6E6"))
            p.setPen(QtGui.QPen(QtGui.QColor("#222222"), 1))
            p.drawEllipse(QtCore.QPoint(x, rect.center().y()), self._handle_radius, self._handle_radius)

    def mousePressEvent(self, event) -> None:
        x = event.position().toPoint().x()
        dist_low = abs(x - self._x_from_value(self._lower))
        dist_up = abs(x - self._x_from_value(self._upper))
        self._active = "lower" if dist_low <= dist_up else "upper"
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._active is None:
            return
        v = self._value_from_x(event.position().toPoint().x())
        if self._active == "lower":
            self.setValues(v, self._upper)
        else:
            self.setValues(self._lower, v)

    def mouseReleaseEvent(self, _event) -> None:
        self._active = None


class RangeLimitsDialog(QDialog):
    def __init__(self, current: dict[str, float], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Range Limits")
        self.setModal(True)
        self.resize(420, 380)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(6)

        self._fields: dict[str, QLineEdit] = {}

        def add_int(key: str, label: str) -> None:
            edit = QLineEdit(str(int(current[key])))
            edit.setValidator(QIntValidator())
            edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self._fields[key] = edit
            form.addRow(label, edit)

        def add_float(key: str, label: str) -> None:
            edit = QLineEdit(f"{float(current[key]):.3f}".rstrip("0").rstrip("."))
            edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
            self._fields[key] = edit
            form.addRow(label, edit)

        add_int("circles_limit_min", "Circles lower bound")
        add_int("circles_limit_max", "Circles upper bound")
        add_int("radius_limit_min", "Radius lower bound")
        add_int("radius_limit_max", "Radius upper bound")
        add_float("sharpness_limit_min", "Sharpness lower bound")
        add_float("sharpness_limit_max", "Sharpness upper bound")
        add_float("opacity_limit_max", "Opacity max")
        add_float("glow_strength_limit_max", "Glow strength max")
        add_float("glow_position_limit_max", "Glow position max")
        add_float("glow_width_limit_max", "Glow width max")
        add_int("count_limit_max", "Batch count max")

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, edit in self._fields.items():
            text = edit.text().strip()
            if key.endswith("_max") or key.endswith("_min"):
                if key in {
                    "count_limit_max",
                    "circles_limit_min",
                    "circles_limit_max",
                    "radius_limit_min",
                    "radius_limit_max",
                }:
                    out[key] = float(int(text))
                else:
                    out[key] = float(text)
        return out


class ConfigPanelMixin:
    """Mixin providing config panel UI building and management."""

    def _build_controls(self) -> None:
        limits = self._range_limits
        self.width_spin = self._spin(640, 7680, self.config.resolution.width)
        self.height_spin = self._spin(360, 4320, self.config.resolution.height)
        self.count_spin = self._spin(1, int(limits["count_limit_max"]), self.config.session.count)

        self.min_circles = self._spin(
            int(limits["circles_limit_min"]),
            int(limits["circles_limit_max"]),
            self.config.generation.min_circles,
        )
        self.max_circles = self._spin(
            int(limits["circles_limit_min"]),
            int(limits["circles_limit_max"]),
            self.config.generation.max_circles,
        )
        self.min_radius = self._spin(
            int(limits["radius_limit_min"]),
            int(limits["radius_limit_max"]),
            self.config.generation.min_radius,
        )
        self.max_radius = self._spin(
            int(limits["radius_limit_min"]),
            int(limits["radius_limit_max"]),
            self.config.generation.max_radius,
        )

        self.curve_combo = QComboBox()
        self.curve_combo.addItems(["linear", "ease", "exp", "gaussian", "flat"])
        self.curve_combo.setCurrentText(self.config.generation.curve)
        self.curve_combo.wheelEvent = self._disable_wheel

        self.preset_combo = QComboBox()
        self.preset_combo.wheelEvent = self._disable_wheel
        self.preset_name_edit = QLineEdit("")
        self.preset_name_edit.setPlaceholderText("preset name")
        self.preset_name_edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.curve_param_min = self._dspin(
            limits["sharpness_limit_min"],
            limits["sharpness_limit_max"],
            self.config.generation.curve_param_min,
            0.1,
        )
        self.curve_param_max = self._dspin(
            limits["sharpness_limit_min"],
            limits["sharpness_limit_max"],
            self.config.generation.curve_param_max,
            0.1,
        )
        self.glow_strength_min = self._dspin(
            0.0,
            limits["glow_strength_limit_max"],
            self.config.generation.glow_strength_min,
            0.05,
        )
        self.glow_strength_max = self._dspin(
            0.0,
            limits["glow_strength_limit_max"],
            self.config.generation.glow_strength_max,
            0.05,
        )
        self.glow_mu_min = self._dspin(
            0.0,
            limits["glow_position_limit_max"],
            self.config.generation.glow_mu_min,
            0.01,
        )
        self.glow_mu_max = self._dspin(
            0.0,
            limits["glow_position_limit_max"],
            self.config.generation.glow_mu_max,
            0.01,
        )
        self.glow_sigma_min = self._dspin(
            0.001,
            limits["glow_width_limit_max"],
            self.config.generation.glow_sigma_min,
            0.01,
        )
        self.glow_sigma_max = self._dspin(
            0.001,
            limits["glow_width_limit_max"],
            self.config.generation.glow_sigma_max,
            0.01,
        )
        self.opacity_min = self._dspin(
            0.0,
            limits["opacity_limit_max"],
            self.config.generation.primary_opacity_min,
            0.05,
        )
        self.opacity_max = self._dspin(
            0.0,
            limits["opacity_limit_max"],
            self.config.generation.primary_opacity_max,
            0.05,
        )

        self.bg_hex = self._hex_edit("#000000")
        self.primary_hex = self._hex_edit("#A0C8FF")
        self.secondary_hex = self._hex_edit("#FFC090")
        self.glow_hex = self._hex_edit("#FFF3C8")
        self.bg_swatch = self._color_swatch()
        self.primary_swatch = self._color_swatch()
        self.secondary_swatch = self._color_swatch()
        self.glow_swatch = self._color_swatch()
        self.bg_pick_btn = QPushButton("Pick")
        self.primary_pick_btn = QPushButton("Pick")
        self.secondary_pick_btn = QPushButton("Pick")
        self.glow_pick_btn = QPushButton("Pick")

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
        resolution_tools_row = QWidget()
        resolution_tools_layout = QHBoxLayout(resolution_tools_row)
        resolution_tools_layout.setContentsMargins(0, 0, 0, 0)
        resolution_tools_layout.setSpacing(6)
        resolution_tools_layout.addWidget(self.range_limits_btn)
        resolution_tools_layout.addWidget(self.screen_res_btn)
        resolution_tools_layout.addStretch(1)
        self.form.addRow("", resolution_tools_row)

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
        preset_pick_layout.addWidget(self.restore_defaults_btn)

        preset_grid.addWidget(preset_pick_row, 0, 0)
        preset_grid.addWidget(self.preset_name_edit, 0, 1)
        preset_grid.addWidget(self.load_preset_btn, 1, 0)
        preset_grid.addWidget(self.save_preset_btn, 1, 1)
        preset_grid.addWidget(self.delete_preset_btn, 1, 2)
        preset_grid.setColumnStretch(0, 1)
        preset_grid.setColumnStretch(1, 1)
        preset_grid.setColumnStretch(2, 1)

        top_layout.addWidget(preset_grid_widget)

        self.randomize_btn = QPushButton("Randomize All")
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

        circle_section = QGroupBox("Circle Configuration")
        circle_layout = QVBoxLayout(circle_section)
        circle_layout.setContentsMargins(10, 12, 10, 10)
        circle_layout.setSpacing(8)
        circle_form = QFormLayout()
        circle_form.setSpacing(6)
        self._add_locked_row("Curve", self.curve_combo, "curve", target_form=circle_form)
        self._add_locked_pair_row(
            "Circles",
            self.min_circles,
            self.max_circles,
            "min_circles",
            "max_circles",
            target_form=circle_form,
        )
        self._add_locked_pair_row(
            "Radius",
            self.min_radius,
            self.max_radius,
            "min_radius",
            "max_radius",
            target_form=circle_form,
        )
        self._add_locked_pair_row(
            "Sharpness",
            self.curve_param_min,
            self.curve_param_max,
            "curve_param_min",
            "curve_param_max",
            target_form=circle_form,
        )
        self._add_locked_pair_row(
            "Opacity",
            self.opacity_min,
            self.opacity_max,
            "opacity_min",
            "opacity_max",
            target_form=circle_form,
        )
        circle_layout.addLayout(circle_form)
        self.form.addRow(circle_section)

        glow_section = QGroupBox("Glow Configuration")
        glow_layout = QVBoxLayout(glow_section)
        glow_layout.setContentsMargins(10, 12, 10, 10)
        glow_layout.setSpacing(8)
        glow_form = QFormLayout()
        glow_form.setSpacing(6)
        self._add_locked_pair_row(
            "Strength",
            self.glow_strength_min,
            self.glow_strength_max,
            "glow_strength_min",
            "glow_strength_max",
            target_form=glow_form,
        )
        self._add_locked_pair_row(
            "Position",
            self.glow_mu_min,
            self.glow_mu_max,
            "glow_mu_min",
            "glow_mu_max",
            target_form=glow_form,
        )
        self._add_locked_pair_row(
            "Width",
            self.glow_sigma_min,
            self.glow_sigma_max,
            "glow_sigma_min",
            "glow_sigma_max",
            target_form=glow_form,
        )
        glow_layout.addLayout(glow_form)
        self.form.addRow(glow_section)

        color_seed_section = QGroupBox("Colors & Seed")
        color_seed_layout = QVBoxLayout(color_seed_section)
        color_seed_layout.setContentsMargins(10, 12, 10, 10)
        color_seed_layout.setSpacing(8)
        color_seed_form = QFormLayout()
        color_seed_form.setSpacing(6)
        bg_row = self._color_row(self.bg_hex, self.bg_swatch, self.bg_pick_btn)
        self._add_locked_row("Background", bg_row, "background", target_form=color_seed_form)
        pri_row = self._color_row(self.primary_hex, self.primary_swatch, self.primary_pick_btn)
        self._add_locked_row("Primary", pri_row, "primary", target_form=color_seed_form)
        sec_row = self._color_row(self.secondary_hex, self.secondary_swatch, self.secondary_pick_btn)
        self._add_locked_row("Secondary", sec_row, "secondary", target_form=color_seed_form)
        glow_row = self._color_row(self.glow_hex, self.glow_swatch, self.glow_pick_btn)
        self._add_locked_row("Glow", glow_row, "glow", target_form=color_seed_form)
        self._add_locked_row("Seed", self.seed_edit, "seed", target_form=color_seed_form)
        color_seed_layout.addLayout(color_seed_form)
        self.form.addRow(color_seed_section)

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
            self.curve_param_min,
            self.curve_param_max,
            self.glow_strength_min,
            self.glow_strength_max,
            self.glow_mu_min,
            self.glow_mu_max,
            self.glow_sigma_min,
            self.glow_sigma_max,
            self.opacity_min,
            self.opacity_max,
        ]
        for w in widgets:
            w.valueChanged.connect(self.schedule_preview)
        self.curve_combo.currentTextChanged.connect(self.schedule_preview)
        self.seed_edit.editingFinished.connect(self.schedule_preview)

        self.generate_btn.clicked.connect(self.start_generation)
        self.open_btn.clicked.connect(self.open_session)
        self.cleanup_btn.clicked.connect(self.cleanup_sessions)
        self.save_dir_browse_btn.clicked.connect(self.browse_save_dir)
        self.range_limits_btn.clicked.connect(self.open_range_limits_dialog)
        self.load_preset_btn.clicked.connect(self.apply_selected_preset)
        self.save_preset_btn.clicked.connect(self.save_current_preset)
        self.delete_preset_btn.clicked.connect(self.delete_selected_preset)
        self.restore_defaults_btn.clicked.connect(self.restore_default_presets)
        self.bg_pick_btn.clicked.connect(
            lambda: self._pick_color(self.bg_hex, self.bg_swatch, "Background color")
        )
        self.primary_pick_btn.clicked.connect(
            lambda: self._pick_color(self.primary_hex, self.primary_swatch, "Primary color")
        )
        self.secondary_pick_btn.clicked.connect(
            lambda: self._pick_color(self.secondary_hex, self.secondary_swatch, "Secondary color")
        )
        self.glow_pick_btn.clicked.connect(
            lambda: self._pick_color(self.glow_hex, self.glow_swatch, "Glow color")
        )
        self.randomize_btn.clicked.connect(self.randomize_all_but_resolution)
        self.shuffle_preview_btn.clicked.connect(self.shuffle_preview_seeds)
        self.randomize_per_preview_chk.toggled.connect(self.schedule_preview)
        self.lock_all_btn.clicked.connect(self.lock_all)
        self.unlock_all_btn.clicked.connect(self.unlock_all)
        self.bg_hex.editingFinished.connect(lambda: self._on_color_hex_finished(self.bg_hex, self.bg_swatch))
        self.primary_hex.editingFinished.connect(
            lambda: self._on_color_hex_finished(self.primary_hex, self.primary_swatch)
        )
        self.secondary_hex.editingFinished.connect(
            lambda: self._on_color_hex_finished(self.secondary_hex, self.secondary_swatch)
        )
        self.glow_hex.editingFinished.connect(
            lambda: self._on_color_hex_finished(self.glow_hex, self.glow_swatch)
        )

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
        self.curve_param_min.setToolTip("Minimum curve sharpness parameter.")
        self.curve_param_max.setToolTip("Maximum curve sharpness parameter.")
        self.glow_strength_min.setToolTip("Minimum glow intensity around circle edges.")
        self.glow_strength_max.setToolTip("Maximum glow intensity around circle edges.")
        self.glow_mu_min.setToolTip("Minimum glow ring position as fraction of radius.")
        self.glow_mu_max.setToolTip("Maximum glow ring position as fraction of radius.")
        self.glow_sigma_min.setToolTip("Minimum glow ring width.")
        self.glow_sigma_max.setToolTip("Maximum glow ring width.")
        self.opacity_min.setToolTip("Minimum per-circle opacity.")
        self.opacity_max.setToolTip("Maximum per-circle opacity.")
        self.bg_hex.setToolTip("Background color in hex (e.g. #000000).")
        self.primary_hex.setToolTip("Primary circle color in hex (e.g. #AABBCC).")
        self.secondary_hex.setToolTip("Secondary circle color in hex (e.g. #AABBCC).")
        self.glow_hex.setToolTip("Glow color in hex.")
        self.bg_pick_btn.setToolTip("Pick background color")
        self.primary_pick_btn.setToolTip("Pick primary color")
        self.secondary_pick_btn.setToolTip("Pick secondary color")
        self.glow_pick_btn.setToolTip("Pick glow color")
        self.seed_edit.setToolTip("Seed for reproducible output. Blank = random.")
        self.screen_res_btn.setToolTip("Set Width/Height from your current primary display resolution.")
        self.range_limits_btn.setToolTip("Range Limits")
        self.randomize_btn.setToolTip("Randomize unlocked parameters for exploration.")
        self.preset_name_edit.setToolTip("Name for saving a custom preset.")

        self.lock_all_btn.setToolTip("Lock every parameter from randomization.")
        self.unlock_all_btn.setToolTip("Unlock every parameter for randomization.")
        self.save_preset_btn.setToolTip("Save current non-batch settings as a custom preset.")
        self.load_preset_btn.setToolTip("Load selected preset (keeps resolution and batch settings).")
        self.delete_preset_btn.setToolTip("Delete selected preset.")
        self.restore_defaults_btn.setToolTip("Restore Defaults")

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

    def delete_selected_preset(self) -> None:
        name = self.preset_combo.currentText().strip()
        if not name:
            QMessageBox.information(self, "No preset selected", "Select a preset to delete.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if not preset_store.delete(name):
            QMessageBox.warning(
                self,
                "Preset not found",
                f"Preset '{name}' was not found.",
            )
            return
        self._refresh_preset_names()
        self.preset_name_edit.clear()
        self.schedule_preview()

    def restore_default_presets(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Restore Defaults",
            "Restore default presets? This will re-add missing default presets.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        restored = preset_store.restore_defaults()
        self._refresh_preset_names()
        QMessageBox.information(self, "Restore Defaults", f"Restored {restored} preset(s).")

    def _default_lock_state(self) -> dict[str, bool]:
        return {
            "width": True,
            "height": True,
            "min_circles": False,
            "max_circles": False,
            "min_radius": False,
            "max_radius": False,
            "curve": False,
            "curve_param_min": False,
            "curve_param_max": False,
            "glow_strength_min": False,
            "glow_strength_max": False,
            "glow_mu_min": False,
            "glow_mu_max": False,
            "glow_sigma_min": False,
            "glow_sigma_max": False,
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
        self.config.generation.curve_param_min = 1.14
        self.config.generation.curve_param_max = 1.14
        self.config.generation.glow_strength_min = 0.64
        self.config.generation.glow_strength_max = 0.64
        self.config.generation.glow_mu_min = 0.83
        self.config.generation.glow_mu_max = 0.83
        self.config.generation.glow_sigma_min = 0.10
        self.config.generation.glow_sigma_max = 0.10
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
            keys = self._lock_button_keys.get(key, (key,))
            locked = all(self._lock_state.get(k, False) for k in keys)
            btn.setText("🔒" if locked else "🔓")
            btn.setToolTip(
                "Locked: Within selected range" if locked else "Unlocked: Fully randomized"
            )

    def _toggle_lock(self, key: str) -> None:
        keys = self._lock_button_keys.get(key, (key,))
        locked = all(self._lock_state.get(k, False) for k in keys)
        for item_key in keys:
            self._lock_state[item_key] = not locked
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
        self._lock_button_keys[key] = (key,)
        layout.addWidget(btn)
        return row

    def _wrap_with_lock_keys(self, widget: QWidget, lock_key: str, keys: tuple[str, ...]) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(6)
        layout.addWidget(widget, 1)
        btn = QToolButton()
        btn.setAutoRaise(False)
        btn.setFixedWidth(28)
        btn.clicked.connect(lambda _=False, k=lock_key: self._toggle_lock(k))
        self._lock_buttons[lock_key] = btn
        self._lock_button_keys[lock_key] = keys
        layout.addWidget(btn)
        return row

    def _add_locked_row(
        self,
        label: str,
        widget: QWidget,
        key: str,
        target_form: QFormLayout | None = None,
    ) -> None:
        row = self._wrap_with_lock(widget, key)
        (target_form or self.form).addRow(label, row)

    def _range_row(self, min_widget: QWidget, max_widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        min_lbl = QLabel("Min")
        max_lbl = QLabel("Max")
        min_lbl.setFixedWidth(24)
        max_lbl.setFixedWidth(24)
        layout.addWidget(min_lbl)
        layout.addWidget(min_widget, 1)
        layout.addWidget(max_lbl)
        layout.addWidget(max_widget, 1)
        return row

    def _bind_pair_slider(
        self,
        min_widget: QSpinBox | QDoubleSpinBox,
        max_widget: QSpinBox | QDoubleSpinBox,
        slider: DualRangeSlider,
    ) -> None:
        factor = 100 if isinstance(min_widget, QDoubleSpinBox) else 1

        slider.setRange(
            int(round(min_widget.minimum() * factor)),
            int(round(max_widget.maximum() * factor)),
        )

        state = {"syncing": False}

        def to_slider(value: float) -> int:
            return int(round(value * factor))

        def from_slider(value: int) -> float:
            return value / factor

        def sync_from_widgets() -> None:
            state["syncing"] = True
            slider.setValues(to_slider(min_widget.value()), to_slider(max_widget.value()))
            state["syncing"] = False

        def on_min_widget_changed(_value) -> None:
            if state["syncing"]:
                return
            if min_widget.value() > max_widget.value():
                max_widget.setValue(min_widget.value())
            sync_from_widgets()

        def on_max_widget_changed(_value) -> None:
            if state["syncing"]:
                return
            if max_widget.value() < min_widget.value():
                min_widget.setValue(max_widget.value())
            sync_from_widgets()

        def on_slider_changed(min_value: int, max_value: int) -> None:
            if state["syncing"]:
                return
            state["syncing"] = True
            min_f = from_slider(min_value)
            max_f = from_slider(max_value)
            if isinstance(min_widget, QSpinBox):
                min_widget.setValue(int(round(min_f)))
            else:
                min_widget.setValue(min_f)
            if isinstance(max_widget, QSpinBox):
                max_widget.setValue(int(round(max_f)))
            else:
                max_widget.setValue(max_f)
            if max_widget.value() < min_widget.value():
                min_widget.setValue(max_widget.value())
            state["syncing"] = False
            sync_from_widgets()

        min_widget.valueChanged.connect(on_min_widget_changed)
        max_widget.valueChanged.connect(on_max_widget_changed)
        slider.values_changed.connect(on_slider_changed)
        sync_from_widgets()

    def _add_locked_pair_row(
        self,
        label: str,
        min_widget: QSpinBox | QDoubleSpinBox,
        max_widget: QSpinBox | QDoubleSpinBox,
        min_key: str,
        max_key: str,
        target_form: QFormLayout | None = None,
    ) -> None:
        range_row = self._range_row(min_widget, max_widget)

        range_slider = DualRangeSlider()
        range_slider.setToolTip(f"{label} range")

        slider_row = QWidget()
        slider_layout = QHBoxLayout(slider_row)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setSpacing(6)
        slider_layout.addWidget(QLabel("Range"))
        slider_layout.addWidget(range_slider, 1)

        self._bind_pair_slider(min_widget, max_widget, range_slider)

        widget = QWidget()
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(0, 0, 0, 0)
        widget_layout.setSpacing(4)
        widget_layout.addWidget(range_row)
        widget_layout.addWidget(slider_row)
        row = self._wrap_with_lock_keys(widget, min_key, (min_key, max_key))
        (target_form or self.form).addRow(label, row)

    def _color_swatch(self) -> QLabel:
        swatch = QLabel()
        swatch.setFixedSize(18, 18)
        swatch.setStyleSheet("border:1px solid #555; border-radius:2px;")
        return swatch

    def _color_row(self, hex_edit: QLineEdit, swatch: QLabel, pick_btn: QPushButton) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        pick_btn.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        pick_btn.setFixedWidth(52)
        layout.addWidget(swatch)
        layout.addWidget(pick_btn)
        layout.addWidget(hex_edit)
        layout.addStretch(1)
        return row

    def _set_swatch_from_hex(self, hex_edit: QLineEdit, swatch: QLabel) -> None:
        try:
            r, g, b = parse_color(hex_edit.text().strip())
            swatch.setStyleSheet(
                f"background:#{r:02X}{g:02X}{b:02X}; border:1px solid #555; border-radius:2px;"
            )
        except Exception:
            swatch.setStyleSheet("background:transparent; border:1px solid #A33; border-radius:2px;")

    def _refresh_color_swatches(self) -> None:
        self._set_swatch_from_hex(self.bg_hex, self.bg_swatch)
        self._set_swatch_from_hex(self.primary_hex, self.primary_swatch)
        self._set_swatch_from_hex(self.secondary_hex, self.secondary_swatch)
        self._set_swatch_from_hex(self.glow_hex, self.glow_swatch)

    def _on_color_hex_finished(self, hex_edit: QLineEdit, swatch: QLabel) -> None:
        self._set_swatch_from_hex(hex_edit, swatch)
        self.schedule_preview()

    def _pick_color(self, hex_edit: QLineEdit, swatch: QLabel, title: str) -> None:
        try:
            current = parse_color(hex_edit.text().strip())
            initial = QtGui.QColor(current[0], current[1], current[2])
        except Exception:
            initial = QtGui.QColor(255, 255, 255)
        chosen = QColorDialog.getColor(initial, self, title)
        if not chosen.isValid():
            return
        hex_edit.setText(chosen.name().upper())
        self._set_swatch_from_hex(hex_edit, swatch)
        self.schedule_preview()

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
            self.curve_param_min.setValue(g.curve_param_min)
            self.curve_param_max.setValue(g.curve_param_max)
            self.glow_strength_min.setValue(g.glow_strength_min)
            self.glow_strength_max.setValue(g.glow_strength_max)
            self.glow_mu_min.setValue(g.glow_mu_min)
            self.glow_mu_max.setValue(g.glow_mu_max)
            self.glow_sigma_min.setValue(g.glow_sigma_min)
            self.glow_sigma_max.setValue(g.glow_sigma_max)
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
            self._refresh_color_swatches()

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
        w.setFixedWidth(110)
        w.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        w.wheelEvent = self._disable_wheel
        return w

    def _dspin(self, lo: float, hi: float, value: float, step: float) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setValue(value)
        w.setFixedWidth(110)
        w.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        w.wheelEvent = self._disable_wheel
        return w

    def _disable_wheel(self, event) -> None:
        event.ignore()

    def _hex_edit(self, value: str) -> QLineEdit:
        w = QLineEdit(value)
        w.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        w.setPlaceholderText("#AABBCC")
        w.setFixedWidth(115)
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
        g.curve_param_min = self.curve_param_min.value()
        g.curve_param_max = self.curve_param_max.value()
        g.glow_strength_min = self.glow_strength_min.value()
        g.glow_strength_max = self.glow_strength_max.value()
        g.glow_mu_min = self.glow_mu_min.value()
        g.glow_mu_max = self.glow_mu_max.value()
        g.glow_sigma_min = self.glow_sigma_min.value()
        g.glow_sigma_max = self.glow_sigma_max.value()
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

    def _collapse_preview_ranges(self, cfg: AppConfig, seed: int) -> AppConfig:
        frozen = cfg.model_copy(deep=True)
        rng = random.Random(seed ^ 0x5A17)
        g = frozen.generation

        circles = rng.randint(g.min_circles, g.max_circles)
        g.min_circles = circles
        g.max_circles = circles

        radius = rng.randint(g.min_radius, g.max_radius)
        g.min_radius = radius
        g.max_radius = radius

        opacity = rng.uniform(g.primary_opacity_min, g.primary_opacity_max)
        g.primary_opacity_min = opacity
        g.primary_opacity_max = opacity

        curve_param = rng.uniform(g.curve_param_min, g.curve_param_max)
        g.curve_param_min = curve_param
        g.curve_param_max = curve_param

        glow_strength = rng.uniform(g.glow_strength_min, g.glow_strength_max)
        g.glow_strength_min = glow_strength
        g.glow_strength_max = glow_strength

        glow_mu = rng.uniform(g.glow_mu_min, g.glow_mu_max)
        g.glow_mu_min = glow_mu
        g.glow_mu_max = glow_mu

        glow_sigma = rng.uniform(g.glow_sigma_min, g.glow_sigma_max)
        g.glow_sigma_min = glow_sigma
        g.glow_sigma_max = glow_sigma

        return frozen

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
            preview_cfg = self._collapse_preview_ranges(preview_cfg, self._preview_seeds[i])
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
        self.setWindowTitle("OLED Wallpaper Magic")
        icon_path = _app_icon_path()
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
        self._range_limits_path = Path.home() / ".config" / "oled_wallpaper_magic" / "range_limits.json"
        self._range_limits = self._load_range_limits()
        self._lock_state: dict[str, bool] = self._load_lock_state()
        self._lock_buttons: dict[str, QToolButton] = {}
        self._lock_button_keys: dict[str, tuple[str, ...]] = {}
        self._preset_lookup: dict[str, str] = {}
        self._loading_form = False

        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumWidth(460)
        left_inner = QWidget()
        self.form = QFormLayout(left_inner)
        self.form.setSpacing(10)
        self.scroll.setWidget(left_inner)
        splitter.addWidget(self.scroll)

        self.lock_all_btn = QPushButton("Lock All")
        self.unlock_all_btn = QPushButton("Unlock All")
        self.save_preset_btn = QPushButton("Save Preset")
        self.load_preset_btn = QPushButton("Load Preset")
        self.delete_preset_btn = QPushButton("Delete Preset")
        self.restore_defaults_btn = QToolButton()
        self.restore_defaults_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.restore_defaults_btn.setText("")
        self.restore_defaults_btn.setAutoRaise(True)
        self.restore_defaults_btn.setFixedSize(24, 24)
        self.restore_defaults_btn.setIconSize(QtCore.QSize(16, 16))
        self.range_limits_btn = QToolButton()
        self.range_limits_btn.setText("⚙")
        self.range_limits_btn.setAutoRaise(False)
        self.range_limits_btn.setFixedSize(28, 24)

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
        splitter.setSizes([460, 940])

        self._build_controls()
        self._load_ui_state()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self._render_previews)

        self._generation_thread: GenerationThread | None = None
        self._progress = None

        self.schedule_preview()

    def _default_range_limits(self) -> dict[str, float]:
        return {
            "count_limit_max": 300,
            "circles_limit_min": 1,
            "circles_limit_max": 100,
            "radius_limit_min": 10,
            "radius_limit_max": 2000,
            "sharpness_limit_min": 0.1,
            "sharpness_limit_max": 10.0,
            "glow_strength_limit_max": 1.5,
            "glow_position_limit_max": 2.0,
            "glow_width_limit_max": 0.5,
            "opacity_limit_max": 1.0,
        }

    def _validate_range_limits(self, limits: dict[str, float]) -> dict[str, float]:
        out = self._default_range_limits()
        out.update(limits)

        out["count_limit_max"] = float(max(1, int(out["count_limit_max"])))
        out["circles_limit_min"] = float(max(1, int(out["circles_limit_min"])))
        out["circles_limit_max"] = float(max(int(out["circles_limit_min"]), int(out["circles_limit_max"])))
        out["radius_limit_min"] = float(max(1, int(out["radius_limit_min"])))
        out["radius_limit_max"] = float(max(int(out["radius_limit_min"]), int(out["radius_limit_max"])))

        out["sharpness_limit_min"] = max(0.001, float(out["sharpness_limit_min"]))
        out["sharpness_limit_max"] = max(out["sharpness_limit_min"], float(out["sharpness_limit_max"]))
        out["glow_strength_limit_max"] = max(0.01, float(out["glow_strength_limit_max"]))
        out["glow_position_limit_max"] = max(0.01, float(out["glow_position_limit_max"]))
        out["glow_width_limit_max"] = max(0.001, float(out["glow_width_limit_max"]))
        out["opacity_limit_max"] = max(0.01, float(out["opacity_limit_max"]))
        return out

    def _load_range_limits(self) -> dict[str, float]:
        defaults = self._default_range_limits()
        try:
            if not self._range_limits_path.exists():
                return defaults
            data = json.loads(self._range_limits_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return defaults
            parsed = {k: float(v) for k, v in data.items() if k in defaults}
            return self._validate_range_limits(parsed)
        except Exception:
            return defaults

    def _save_range_limits(self) -> None:
        int_keys = {
            "count_limit_max",
            "circles_limit_min",
            "circles_limit_max",
            "radius_limit_min",
            "radius_limit_max",
        }
        payload = {
            k: int(v) if k in int_keys else v
            for k, v in self._range_limits.items()
        }
        self._range_limits_path.parent.mkdir(parents=True, exist_ok=True)
        self._range_limits_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def open_range_limits_dialog(self) -> None:
        dialog = RangeLimitsDialog(self._range_limits, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._range_limits = self._validate_range_limits(dialog.values())
            self._save_range_limits()
        except Exception as exc:
            QMessageBox.warning(self, "Range limits not saved", str(exc))
            return
        QMessageBox.information(
            self,
            "Restart Required",
            "Range limits were saved. Please restart the app for changes to take effect.",
        )

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
