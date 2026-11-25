"""Video picker: folder browser showing only videos, with pinned folders saved between runs."""
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QFileInfo, QSettings, QStandardPaths, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileIconProvider, QFileSystemModel, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QSplitter, QTreeView, QVBoxLayout, QWidget,
)

import theme as T

VIDEO_EXTS = ["mp4", "mov", "mkv", "avi", "webm", "m4v", "wmv", "mpg", "mpeg"]


# Next to VideoReviewer.exe when built, next to this file when run from source.
SETTINGS_FILE = (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent) / "settings.ini"


def settings():
    return QSettings(str(SETTINGS_FILE), QSettings.IniFormat)


def load_pins():
    return [p for p in settings().value("pins", [], type=list) if p]  # ini gives a 1-item list back as str without type=


def save_pins(pins):
    settings().setValue("pins", pins)


def places():
    out = []
    for loc, name in [(QStandardPaths.DesktopLocation, "Desktop"), (QStandardPaths.MoviesLocation, "Videos"),
                      (QStandardPaths.DownloadLocation, "Downloads"), (QStandardPaths.HomeLocation, "Home")]:
        p = QStandardPaths.writableLocation(loc)
        if p and Path(p).is_dir():
            out.append((name, p))
    out += [(d.absolutePath().rstrip("/"), d.absolutePath()) for d in QDir.drives()]
    return out


class MonoIcons(QFileIconProvider):
    """Theme line icons instead of the colored native shell icons."""
    def __init__(self):
        super().__init__()
        self.folder, self.video = T.icon("folder"), T.icon("video")

    def icon(self, arg):
        if isinstance(arg, QFileInfo):
            return self.folder if arg.isDir() else self.video
        return self.folder


def fit_height(lst):
    """Size a list to its rows so the sidebar sections stack without gaps."""
    lst.ensurePolished()
    row = max(lst.sizeHintForRow(0), lst.fontMetrics().height() + 18)  # hidden lists report -1
    lst.setFixedHeight(min(260, row * lst.count() + 4))  # scrolls past ~8 rows


class VideoBrowser(QDialog):
    def __init__(self, parent=None, start=None):
        super().__init__(parent)
        self.setWindowTitle("Open video")
        self.resize(920, 560)
        self.selected = None
        self.pins = load_pins()

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        split = QSplitter()
        split.setHandleWidth(1)
        root.addWidget(split)

        # ---- sidebar: pinned + places ----
        side = QWidget(objectName="sidebar")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 14, 10, 12)
        sl.setSpacing(6)
        sl.addWidget(T.label("PINNED", "hint"))
        self.pin_list = QListWidget(objectName="nav")
        self.pin_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pin_list.customContextMenuRequested.connect(self.pin_menu)
        self.pin_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.pin_list.model().rowsMoved.connect(self.pins_reordered)
        self.pin_empty = T.label("Pin a folder to keep it here.", "hint")
        self.pin_empty.setWordWrap(True)
        sl.addWidget(self.pin_list)
        sl.addWidget(self.pin_empty)
        sl.addSpacing(8)
        sl.addWidget(T.label("PLACES", "hint"))
        self.place_list = QListWidget(objectName="nav")
        for name, p in places():
            it = QListWidgetItem(T.icon("folder"), name)
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            self.place_list.addItem(it)
        sl.addWidget(self.place_list)
        sl.addStretch()
        fit_height(self.place_list)
        for lst in (self.pin_list, self.place_list):
            lst.itemClicked.connect(lambda it: self.go(it.data(Qt.UserRole)))
        split.addWidget(side)

        # ---- main: path bar + files ----
        main = QWidget(objectName="main")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(16, 14, 16, 14)
        ml.setSpacing(10)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.up_btn = T.button("", "up", "icon", "Up one folder")
        self.up_btn.clicked.connect(self.go_up)
        self.path_box = QLineEdit()
        self.path_box.returnPressed.connect(lambda: self.go(self.path_box.text().strip().strip('"')))
        self.pin_btn = T.button("Unpin Folder", "pin", "outline")
        self.pin_btn.setMinimumWidth(self.pin_btn.sizeHint().width())  # longest label, so it never clips
        self.pin_btn.clicked.connect(self.toggle_pin)
        bar.addWidget(self.up_btn)
        bar.addWidget(self.path_box, 1)
        bar.addWidget(self.pin_btn)
        ml.addLayout(bar)

        self.model = QFileSystemModel(self)
        self.icons = MonoIcons()  # model doesn't own it; keep a reference
        self.model.setIconProvider(self.icons)
        self.model.setRootPath("")
        self.model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot | QDir.Drives)
        self.model.setNameFilters([f"*.{e}" for e in VIDEO_EXTS + [e.upper() for e in VIDEO_EXTS]])
        self.model.setNameFilterDisables(False)  # hide non-videos instead of greying them
        self.tree = QTreeView(objectName="files")
        self.tree.setModel(self.model)
        self.tree.setRootIsDecorated(False)
        self.tree.setItemsExpandable(False)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.AscendingOrder)
        self.tree.setColumnHidden(2, True)  # "Type" column
        self.tree.setColumnWidth(0, 380)
        self.tree.setUniformRowHeights(True)
        self.tree.doubleClicked.connect(self.activate)
        self.tree.selectionModel().currentChanged.connect(self.update_open)
        ml.addWidget(self.tree, 1)

        foot = QHBoxLayout()
        self.hint = T.label("Double-click a folder to open it, or a video to review it.", "hint")
        cancel = T.button("Cancel", variant="ghost")
        cancel.clicked.connect(self.reject)
        self.open_btn = T.button("Open Video", variant="primary")
        self.open_btn.clicked.connect(lambda: self.activate(self.tree.currentIndex()))
        foot.addWidget(self.hint)
        foot.addStretch()
        foot.addWidget(cancel)
        foot.addWidget(self.open_btn)
        ml.addLayout(foot)
        split.addWidget(main)
        split.setSizes([210, 710])
        split.setStretchFactor(1, 1)

        self.refresh_pins()
        start = start or settings().value("last_dir") or QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
        self.go(start if start and Path(start).is_dir() else QDir.homePath())

    # ---- navigation ----
    def go(self, path):
        if not path or not Path(path).is_dir():
            self.path_box.setText(self.cwd if hasattr(self, "cwd") else "")
            return
        self.cwd = str(Path(path))
        self.path_box.setText(self.cwd)
        self.tree.setRootIndex(self.model.index(QDir.fromNativeSeparators(self.cwd)))
        self.up_btn.setEnabled(Path(self.cwd).parent != Path(self.cwd))
        self.update_pin_btn()
        self.update_open()

    def go_up(self):
        self.go(str(Path(self.cwd).parent))

    def activate(self, idx):
        if not idx.isValid():
            return
        p = self.model.filePath(idx)
        if self.model.isDir(idx):
            self.go(p)
        else:
            self.selected = Path(p)
            settings().setValue("last_dir", self.cwd)
            self.accept()

    def update_open(self, *_):
        idx = self.tree.currentIndex()
        self.open_btn.setEnabled(idx.isValid() and idx.parent() == self.tree.rootIndex() and not self.model.isDir(idx))

    # ---- pins ----
    def refresh_pins(self):
        self.pin_list.clear()
        for p in self.pins:
            it = QListWidgetItem(T.icon("pin"), Path(p).name or p)
            it.setData(Qt.UserRole, p)
            it.setToolTip(p if Path(p).is_dir() else f"{p} (not found)")
            if not Path(p).is_dir():
                it.setForeground(T.qcolor(T.TEXT_3))
            self.pin_list.addItem(it)
        self.pin_empty.setVisible(not self.pins)
        self.pin_list.setVisible(bool(self.pins))
        fit_height(self.pin_list)
        self.update_pin_btn()

    def update_pin_btn(self):
        pinned = getattr(self, "cwd", None) in self.pins
        self.pin_btn.setText("Unpin Folder" if pinned else "Pin Folder")

    def toggle_pin(self):
        if self.cwd in self.pins:
            self.pins.remove(self.cwd)
        else:
            self.pins.append(self.cwd)
        save_pins(self.pins)
        self.refresh_pins()

    def pins_reordered(self, *_):
        self.pins = [self.pin_list.item(i).data(Qt.UserRole) for i in range(self.pin_list.count())]
        save_pins(self.pins)

    def pin_menu(self, pos):
        it = self.pin_list.itemAt(pos)
        if not it:
            return
        menu = QMenu(self)
        unpin = menu.addAction("Unpin")
        if menu.exec(self.pin_list.mapToGlobal(pos)) == unpin:
            self.pins.remove(it.data(Qt.UserRole))
            save_pins(self.pins)
            self.refresh_pins()
