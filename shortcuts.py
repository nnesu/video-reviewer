"""Keyboard shortcuts: the action list with defaults, saving to settings.ini, and the settings dialog."""
from PySide6.QtCore import QKeyCombination, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QKeySequenceEdit, QMessageBox, QVBoxLayout

import theme as T
from browser import settings

# (id, label, default). Empty default = unassigned.
ACTIONS = [
    ("play", "Play / Pause", "Space"),
    ("frame_back", "Previous frame", "Left"),
    ("frame_fwd", "Next frame", "Right"),
    ("back5", "Back 5 seconds", "Shift+Left"),
    ("fwd5", "Forward 5 seconds", "Shift+Right"),
    ("comment", "New comment", ""),
    ("save", "Save comment", "Return"),
    ("cancel", "Cancel comment", "Esc"),
    ("clear", "Clear highlight", ""),
    ("edit", "Edit selected comment", ""),
    ("delete", "Delete selected comment", ""),
    ("open", "Open video", ""),
    ("export", "Export review", ""),
    ("shortcuts", "Keyboard shortcuts", "Ctrl+,"),
]
DEFAULTS = {a: d for a, _, d in ACTIONS}
NEWLINE = QKeySequence("Shift+Return")  # fixed: new line inside a comment


def load():
    s = settings()
    s.beginGroup("shortcuts")
    out = {a: s.value(a, d) for a, d in DEFAULTS.items()}
    s.endGroup()
    return out


def save(keys):
    s = settings()
    s.beginGroup("shortcuts")
    for a, k in keys.items():
        s.setValue(a, k)
    s.endGroup()


def display(key):
    return QKeySequence(key).toString(QKeySequence.NativeText).replace("Return", "Enter")


def event_seq(e):
    """Key event as a QKeySequence, with numpad Enter treated as Enter."""
    key = e.key()
    mods = e.modifiers() & ~Qt.KeypadModifier
    if key == Qt.Key_Enter:
        key = Qt.Key_Return
    return QKeySequence(QKeyCombination(mods, Qt.Key(key)))


def conflicts(keys):
    """Return a message for the first shortcut used twice (or clashing with Shift+Enter), else None."""
    seen = {NEWLINE.toString(): "New line in comment"}
    labels = {a: l for a, l, _ in ACTIONS}
    for a, k in keys.items():
        if not k:
            continue
        if k in seen:
            return f"{display(k)} is used by both “{seen[k]}” and “{labels[a]}”."
        seen[k] = labels[a]
    return None


class ShortcutDialog(QDialog):
    def __init__(self, keys, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(T.label("Keyboard Shortcuts", "title"))
        lay.addWidget(T.label("Click a box and press the keys. Leave it empty for no shortcut.", "meta"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.edits = {}
        for row, (a, label, _) in enumerate(ACTIONS):
            ed = QKeySequenceEdit(QKeySequence(keys.get(a, "")))
            ed.setMaximumSequenceLength(1)
            ed.setClearButtonEnabled(True)
            self.edits[a] = ed
            grid.addWidget(T.label(label), row, 0)
            grid.addWidget(ed, row, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        lay.addWidget(T.label("Shift+Enter always adds a new line in a comment.", "hint"))
        lay.addSpacing(4)
        lay.addWidget(T.frame("hairline"))
        bottom = QHBoxLayout()
        reset = T.button("Reset to Defaults", variant="ghost")
        reset.clicked.connect(lambda: [ed.setKeySequence(QKeySequence(DEFAULTS[a])) for a, ed in self.edits.items()])
        cancel = T.button("Cancel", variant="ghost")
        cancel.clicked.connect(self.reject)
        ok = T.button("Save", variant="primary")
        ok.clicked.connect(self.try_accept)
        bottom.addWidget(reset)
        bottom.addStretch()
        bottom.addWidget(cancel)
        bottom.addWidget(ok)
        lay.addLayout(bottom)

    def keys(self):
        return {a: ed.keySequence().toString() for a, ed in self.edits.items()}

    def try_accept(self):
        msg = conflicts(self.keys())
        if msg:
            QMessageBox.warning(self, "Shortcut already used", msg)
            return
        self.accept()
