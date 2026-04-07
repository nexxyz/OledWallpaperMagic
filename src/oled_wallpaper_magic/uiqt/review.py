from __future__ import annotations

import importlib
import sys
from pathlib import Path

_qt_pkg = "".join(["Py", "Side6"])
QtCore = importlib.import_module(".".join([_qt_pkg, "Qt" + "Core"]))
QtGui = importlib.import_module(".".join([_qt_pkg, "Qt" + "Gui"]))
QtWidgets = importlib.import_module(".".join([_qt_pkg, "Qt" + "Widgets"]))

QSize = QtCore.QSize
Qt = QtCore.Qt

QAction = QtGui.QAction
QIcon = QtGui.QIcon
QKeySequence = QtGui.QKeySequence
QPixmap = QtGui.QPixmap

QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QMainWindow = QtWidgets.QMainWindow
QMessageBox = QtWidgets.QMessageBox
QPushButton = QtWidgets.QPushButton
QSizePolicy = QtWidgets.QSizePolicy
QSplitter = QtWidgets.QSplitter
QVBoxLayout = QtWidgets.QVBoxLayout
QWidget = QtWidgets.QWidget

from oled_wallpaper_magic.session.manager import SessionManager
from oled_wallpaper_magic.session.metadata import Session

STATUS_COLORS = {
    "keep": "#3cd664",
    "discard": "#d63c3c",
    "unddecided": "#8f8f8f",
}


def _app_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "icons" / "icon.png"
    return Path(__file__).parent.parent.parent / "icons" / "icon.png"


class ReviewWindow(QMainWindow):
    def __init__(self, session: Session, start_index: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.session = session
        self.current_index = start_index if start_index >= 0 else 0
        self._updating_ui = False
        if self.current_index >= len(self.session.images):
            self.current_index = max(0, len(self.session.images) - 1)
        self.generated_dir = self.session.root / "generated"
        self.manager = SessionManager(self.session.root.parent)

        self.setWindowTitle(f"OledWallpaperMagic - Review - {session.id}")
        icon_path = _app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1400, 900)

        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Vertical)
        root_layout.addWidget(splitter)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        self.image_label = QLabel("", top)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background:#000; border:1px solid #333;")
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setMinimumSize(1, 1)
        top_layout.addWidget(self.image_label, 1)

        self.status_label = QLabel("", top)
        self.status_label.setStyleSheet("padding:6px; font-weight:600;")
        top_layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.keep_btn = QPushButton("Keep (K)")
        self.discard_btn = QPushButton("Discard (D)")
        self.undo_btn = QPushButton("Undecided (U)")
        self.finalize_btn = QPushButton("Finalize")
        self.keep_btn.setToolTip("Mark current image as keep and move next.")
        self.discard_btn.setToolTip("Mark current image as discard and move next.")
        self.undo_btn.setToolTip("Reset current image to undecided.")
        self.finalize_btn.setToolTip("Export kept images to output folder.")
        btn_row.addWidget(self.keep_btn)
        btn_row.addWidget(self.discard_btn)
        btn_row.addWidget(self.undo_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.finalize_btn)
        top_layout.addLayout(btn_row)

        splitter.addWidget(top)

        self.thumb_list = QListWidget()
        self.thumb_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumb_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumb_list.setWrapping(False)
        self.thumb_list.setMovement(QListWidget.Movement.Static)
        self.thumb_list.setFlow(QListWidget.Flow.LeftToRight)
        self.thumb_list.setSpacing(6)
        self.thumb_list.setIconSize(QSize(120, 68))
        self.thumb_list.setFixedHeight(120)
        self.thumb_list.setToolTip("Click a thumbnail to jump to that image.")
        splitter.addWidget(self.thumb_list)
        splitter.setSizes([760, 120])

        self.hints_label = QLabel(
            "<- / -> navigate   K keep   D discard   U undecided   "
            "G first undecided   Home/End   Enter finalize   Esc close"
        )
        self.hints_label.setStyleSheet("color:#b0b0b0; padding:4px 6px;")
        self.hints_label.setToolTip("Keyboard shortcuts for fast review.")
        root_layout.addWidget(self.hints_label)

        self.keep_btn.clicked.connect(lambda: self.mark("keep"))
        self.discard_btn.clicked.connect(lambda: self.mark("discard"))
        self.undo_btn.clicked.connect(lambda: self.mark("unddecided"))
        self.finalize_btn.clicked.connect(self.finalize)
        self.thumb_list.currentRowChanged.connect(self.on_thumb_selected)

        self._setup_actions()
        self._load_thumbs()
        self._show_current()

    def _setup_actions(self) -> None:
        self._bind("Right", self.next_image)
        self._bind("Left", self.prev_image)
        self._bind("K", lambda: self.mark("keep"))
        self._bind("D", lambda: self.mark("discard"))
        self._bind("U", lambda: self.mark("unddecided"))
        self._bind("G", self.go_first_undecided)
        self._bind("Home", self.go_first)
        self._bind("End", self.go_last)
        self._bind("Return", self.finalize)
        self._bind("Escape", self.close)

    def _bind(self, key: str, callback) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence(key))
        action.triggered.connect(callback)
        self.addAction(action)

    def _img_path(self, index: int) -> Path:
        return self.generated_dir / self.session.images[index].filename

    def _load_thumbs(self) -> None:
        self.thumb_list.clear()
        for i, img in enumerate(self.session.images):
            item = QListWidgetItem(f"{i + 1}")
            path = self.generated_dir / img.filename
            pix = QPixmap(str(path))
            if not pix.isNull():
                icon_pix = pix.scaled(
                    120, 68,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item.setIcon(QIcon(icon_pix))
            self.thumb_list.addItem(item)
        self.thumb_list.setCurrentRow(self.current_index)

    def on_thumb_selected(self, row: int) -> None:
        if self._updating_ui:
            return
        if row < 0 or row >= len(self.session.images):
            return
        self.current_index = row
        self._save_state()
        self._show_current()

    def _status(self) -> str:
        filename = self.session.images[self.current_index].filename
        return self.session.review_state.get(filename, "unddecided")

    def _show_current(self) -> None:
        if not self.session.images:
            self.image_label.setText("No images")
            return
        path = self._img_path(self.current_index)
        pix = QPixmap(str(path))
        if pix.isNull():
            self.image_label.setText(f"Missing file: {path.name}")
        else:
            self._set_image_pixmap(pix)
        status = self._status()
        img_count = len(self.session.images)
        self.status_label.setText(
            f"{self.current_index + 1}/{img_count} - {status.upper()}"
        )
        self.status_label.setStyleSheet(
            f"padding:6px; font-weight:600; color:{STATUS_COLORS.get(status, '#8f8f8f')};"
        )
        self._updating_ui = True
        try:
            self.thumb_list.setCurrentRow(self.current_index)
        finally:
            self._updating_ui = False

    def _set_image_pixmap(self, pix: QPixmap) -> None:
        size = self.image_label.size()
        if size.width() <= 1 or size.height() <= 1:
            self.image_label.setPixmap(pix)
            return
        scaled = pix.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        path = self._img_path(self.current_index) if self.session.images else None
        if path and path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._set_image_pixmap(pix)

    def _save_state(self) -> None:
        self.session.current_index = self.current_index
        self.manager.save_session(self.session)

    def next_image(self) -> None:
        if self.current_index < len(self.session.images) - 1:
            self.current_index += 1
            self._save_state()
            self._show_current()

    def prev_image(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._save_state()
            self._show_current()

    def go_first(self) -> None:
        self.current_index = 0
        self._save_state()
        self._show_current()

    def go_last(self) -> None:
        self.current_index = max(0, len(self.session.images) - 1)
        self._save_state()
        self._show_current()

    def go_first_undecided(self) -> None:
        for i, img in enumerate(self.session.images):
            status = self.session.review_state.get(img.filename, "unddecided")
            if status == "unddecided":
                self.current_index = i
                self._save_state()
                self._show_current()
                return

    def mark(self, status: str) -> None:
        if not self.session.images:
            return
        filename = self.session.images[self.current_index].filename
        self.session.review_state[filename] = status
        self._save_state()
        self._show_current()
        if self.current_index < len(self.session.images) - 1:
            self.next_image()

    def finalize(self) -> None:
        keep_count = sum(1 for s in self.session.review_state.values() if s == "keep")
        discard_count = sum(1 for s in self.session.review_state.values() if s == "discard")
        answer = QMessageBox.question(
            self,
            "Finalize Session",
            f"Finalize with {keep_count} kept and {discard_count} discarded?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        save_dir = self.session.config.session.save_dir if self.session.config else Path("./wallpapers/kept")
        kept = self.manager.finalize(self.session, save_dir, purge=False)
        QMessageBox.information(self, "Finalize Complete", f"Exported {kept} wallpapers to\n{save_dir}")
        self.close()


def launch_review_window(session: Session, start_index: int = 0) -> None:
    app = QtWidgets.QApplication.instance()
    owned = app is None
    if app is None:
        app = QtWidgets.QApplication([])
    win = ReviewWindow(session, start_index)
    win.show()
    if owned:
        app.exec()
