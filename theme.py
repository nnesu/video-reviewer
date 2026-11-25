"""Monochrome dark theme: design tokens, the app-wide Qt stylesheet, thin-stroke icons,
small styled widgets (elided label, composer frame, comment row delegate) and dark Windows titlebars."""
import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QObject, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QStyle, QStyledItemDelegate

# ---------- color tokens ----------
CANVAS = "#252525"          # main workspace
SIDEBAR = "#1E1E1E"         # comments panel
ELEVATED = "#2F2F2F"        # composer, inputs, pop-ups, secondary buttons
HOVER = "#383838"
SELECTED = "#2D2D2D"
STAGE = "#151515"           # behind the video
BORDER = "#363636"
BORDER_STRONG = "#4A4A4A"
DIVIDER = "#333333"         # pane separators
TEXT = "#EDEDED"
TEXT_2 = "#A3A3A3"
TEXT_3 = "#737373"
ACCENT = "#EDEDED"
ACCENT_HOVER = "#FFFFFF"
ACCENT_PRESSED = "#CFCFCF"
ACCENT_SOFT = "rgba(237, 237, 237, 0.10)"
DANGER = "#FFFFFF"
DANGER_SOFT = "rgba(255, 255, 255, 0.08)"
DANGER_SOLID = "#EDEDED"
ON_ACCENT = "#1A1A1A"         # text/icons on white accent fills

# component-specific shades
STAGE_BORDER = "#353535"
SECONDARY_BORDER = "#3F3F3F"
GHOST_BORDER = "#3C3C3C"
COMPOSER_BORDER = "#424242"
COMPOSER_FOCUS = "#595959"
TRACK = "#3C3C3C"
ROW_HOVER = "#282828"
ROW_SELECTED = "#303030"
ROW_DIVIDER = "#2A2A2A"
BADGE = "#2C2C2C"
SCROLL = "#3D3D3D"

# ---------- typography ----------
SERIF = ["Georgia", "Cambria"]
SANS = ["Segoe UI Variable Text", "Segoe UI"]
MONO = ["Cascadia Mono", "Consolas"]
FONT_BODY = 13
FONT_META = 12
FONT_TITLE = 18

# ---------- geometry ----------
RADIUS = 8
HEADER_HEIGHT = 46
PANE_PAD = 16
CONTROL_HEIGHT = 32


def _families(fams):
    return ", ".join(f'"{f}"' for f in fams)


def qcolor(token):
    """Turn a token (hex or rgba(...)) into a QColor."""
    if token.startswith("rgba"):
        r, g, b, a = (float(v) for v in token[5:-1].split(","))
        return QColor(int(r), int(g), int(b), round(a * 255))
    return QColor(token)


STYLESHEET = f"""
* {{ color: {TEXT}; font-size: {FONT_BODY}px; }}
QMainWindow, QWidget#main {{ background: {CANVAS}; }}
QWidget#sidebar {{ background: {SIDEBAR}; }}
QWidget#header {{ background: {CANVAS}; border-bottom: 1px solid {DIVIDER}; }}
QWidget#sidebarFooter {{ background: {SIDEBAR}; border-top: 1px solid {DIVIDER}; }}
QFrame#hairline {{ background: {DIVIDER}; min-height: 1px; max-height: 1px; border: none; }}
QFrame#stage {{ background: {STAGE}; border: 1px solid {STAGE_BORDER}; border-radius: 10px; }}
QToolTip {{ background: {ELEVATED}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; border-radius: 6px; padding: 4px 8px; font-size: {FONT_META}px; }}

QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-family: {_families(SERIF)}; font-size: {FONT_TITLE}px; }}
QLabel[role="meta"] {{ font-size: {FONT_META}px; color: {TEXT_2}; }}
QLabel[role="hint"] {{ font-size: {FONT_META}px; color: {TEXT_3}; }}
QLabel[role="timecode"] {{ font-family: {_families(MONO)}; font-size: {FONT_META}px; color: {TEXT_2}; }}
QLabel[role="badge"] {{ background: {BADGE}; color: {TEXT_2}; font-size: {FONT_META - 1}px; border-radius: 9px; padding: 1px 8px; }}

/* secondary (default) */
QPushButton {{
    min-height: {CONTROL_HEIGHT}px; padding: 0 12px; border-radius: {RADIUS}px;
    background: {ELEVATED}; border: 1px solid {SECONDARY_BORDER}; color: {TEXT};
}}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {SELECTED}; }}
QPushButton:focus {{ outline: none; border: 1px solid {ACCENT}; }}
QPushButton:disabled {{ color: {TEXT_3}; background: transparent; border-color: {BORDER}; }}

QPushButton[variant="primary"] {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: {ON_ACCENT}; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton[variant="primary"]:pressed {{ background: {ACCENT_PRESSED}; border-color: {ACCENT_PRESSED}; }}
QPushButton[variant="primary"]:focus {{ border: 2px solid {TEXT_3}; }}
QPushButton[variant="primary"]:disabled {{ background: {ELEVATED}; border-color: {ELEVATED}; color: {TEXT_3}; }}

QPushButton[variant="outline"] {{ background: transparent; border: 1px solid {GHOST_BORDER}; }}
QPushButton[variant="outline"]:hover {{ background: {ELEVATED}; }}

QPushButton[variant="ghost"], QPushButton[variant="icon"] {{ background: transparent; border: 1px solid transparent; color: {TEXT_2}; }}
QPushButton[variant="ghost"]:hover, QPushButton[variant="icon"]:hover {{ background: {HOVER}; color: {TEXT}; }}
QPushButton[variant="ghost"]:focus, QPushButton[variant="icon"]:focus {{ border: 1px solid {ACCENT}; }}
QPushButton[variant="ghost"]:disabled, QPushButton[variant="icon"]:disabled {{ background: transparent; border-color: transparent; color: {TEXT_3}; }}
QPushButton[variant="icon"] {{ min-width: 32px; max-height: 32px; padding: 0 6px; font-size: {FONT_META}px; }}

QPushButton[variant="quietDanger"] {{ background: transparent; border: 1px solid transparent; color: {TEXT_2}; }}
QPushButton[variant="quietDanger"]:hover {{ background: {DANGER_SOFT}; color: {DANGER}; }}
QPushButton[variant="quietDanger"]:focus {{ border: 1px solid {ACCENT}; }}

QPushButton[variant="play"] {{
    background: {TEXT}; border: none; border-radius: 17px; padding: 0;
    min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px;
}}
QPushButton[variant="play"]:hover {{ background: #FFFFFF; }}
QPushButton[variant="play"]:focus {{ border: 2px solid {ACCENT}; }}
QPushButton[variant="play"]:disabled {{ background: {HOVER}; }}

/* composer */
QFrame#composer {{ background: {ELEVATED}; border: 1px solid {COMPOSER_BORDER}; border-radius: 14px; }}
QFrame#composer[focused="true"] {{ border-color: {COMPOSER_FOCUS}; }}
QFrame#composer QPlainTextEdit {{ background: transparent; border: none; padding: 0; selection-background-color: {ACCENT}; }}
QLineEdit {{
    background: {ELEVATED}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 6px 8px;
    font-family: {_families(MONO)}; font-size: {FONT_META}px; color: {TEXT_2}; selection-background-color: {ACCENT};
}}
QLineEdit:focus {{ border-color: {BORDER_STRONG}; }}
QPlainTextEdit {{ background: {ELEVATED}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}

/* seek bar */
QSlider {{ min-height: 16px; }}
QSlider::groove:horizontal {{ height: 3px; background: {TRACK}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 1px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 10px; height: 10px; margin: -4px 0; border-radius: 5px; }}
QSlider::sub-page:horizontal:disabled {{ background: {TRACK}; }}
QSlider::handle:horizontal:disabled {{ background: {TEXT_3}; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget#nav::item {{ padding: 5px 6px; border-radius: 6px; color: {TEXT_2}; }}
QListWidget#nav::item:hover {{ background: {HOVER}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {SELECTED}; color: {TEXT}; }}

/* file browser */
QTreeView#files {{ background: {CANVAS}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; outline: none; }}
QTreeView#files::item {{ padding: 4px 2px; }}
QTreeView#files::item:hover {{ background: {HOVER}; }}
QTreeView#files::item:selected {{ background: {SELECTED}; color: {TEXT}; }}
QHeaderView::section {{
    background: {CANVAS}; color: {TEXT_3}; font-size: {FONT_META}px; border: none;
    border-bottom: 1px solid {DIVIDER}; padding: 5px 6px;
}}
QMenu {{ background: {ELEVATED}; border: 1px solid {BORDER_STRONG}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 5px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {HOVER}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 1px; }}
QScrollBar::handle:vertical {{ background: {SCROLL}; border-radius: 3px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 1px 2px; }}
QScrollBar::handle:horizontal {{ background: {SCROLL}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; width: 0; height: 0; }}

QSplitter::handle {{ background: {DIVIDER}; }}

/* pop-ups */
QMessageBox, QDialog {{ background: {CANVAS}; }}
QMessageBox QPushButton {{ min-width: 92px; }}
QMessageBox QPushButton:default {{ background: {ACCENT}; border-color: {ACCENT}; color: {ON_ACCENT}; }}
QMessageBox QPushButton:default:hover {{ background: {ACCENT_HOVER}; }}
QMessageBox QPushButton[variant="danger"], QMessageBox QPushButton[variant="danger"]:default {{ background: {DANGER_SOLID}; border-color: {DANGER_SOLID}; color: {ON_ACCENT}; }}
QMessageBox QPushButton[variant="danger"]:hover {{ background: {DANGER}; border-color: {DANGER}; }}
"""

# ---------- icons (24x24 viewBox, 1.5px stroke) ----------
_S = 'fill="none" stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "folder": f'<path {_S} d="M3.5 7.5A2 2 0 0 1 5.5 5.5H9l2 2h7.5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "play": '<path fill="{c}" d="M8.5 6.2v11.6a.9.9 0 0 0 1.37.77l9.3-5.8a.9.9 0 0 0 0-1.54l-9.3-5.8a.9.9 0 0 0-1.37.77z"/>',
    "pause": '<rect fill="{c}" x="7" y="6" width="3.5" height="12" rx="1"/><rect fill="{c}" x="13.5" y="6" width="3.5" height="12" rx="1"/>',
    "back5": f'<path {_S} d="M11 7.5 5.5 12l5.5 4.5zM18.5 7.5 13 12l5.5 4.5z"/>',
    "fwd5": f'<path {_S} d="M13 7.5l5.5 4.5-5.5 4.5zM5.5 7.5 11 12l-5.5 4.5z"/>',
    "frame_back": f'<path {_S} d="M15.5 6.5 10 12l5.5 5.5M7.5 6.5v11"/>',
    "frame_fwd": f'<path {_S} d="M8.5 6.5 14 12l-5.5 5.5M16.5 6.5v11"/>',
    "video": f'<path {_S} d="M6 4.5h8.5l4 4V18a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V6A1.5 1.5 0 0 1 6 4.5zM10.5 10.5v5l4-2.5z"/>',
    "up": f'<path {_S} d="M12 19V5.5M6.5 11 12 5.5l5.5 5.5"/>',
    "keyboard": f'<path {_S} d="M4.5 6.5h15a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 16V8a1.5 1.5 0 0 1 1.5-1.5zM7 10h.01M10 10h.01M13 10h.01M16.5 10h.01M8 14h8"/>',
    "pin": f'<path {_S} d="M9 4.5h6M10 4.5v5l-3 3.5h10l-3-3.5v-5M12 13v6.5"/>',
    "plus": f'<path {_S} d="M12 5.5v13M5.5 12h13"/>',
    "pencil": f'<path {_S} d="M4.5 19.5h4l10-10a2.5 2.5 0 0 0-3.5-3.5l-10 10zM13.5 7.5l3 3"/>',
    "trash": f'<path {_S} d="M5 7h14M10 11v5.5M14 11v5.5M9.5 7V5h5v2M6.5 7l.9 11.6a1.5 1.5 0 0 0 1.5 1.4h6.2a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/>',
    "export": f'<path {_S} d="M12 4v11M8 8l4-4 4 4M8.5 11.5H7a2 2 0 0 0-2 2V18a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4.5a2 2 0 0 0-2-2h-1.5"/>',
    "eraser": f'<path {_S} d="M8 19.5h11M5 14.5l8.5-8.5a2 2 0 0 1 2.8 0l2.2 2.2a2 2 0 0 1 0 2.8L11 18.5a2 2 0 0 1-1.4.6H8.6a2 2 0 0 1-1.4-.6L5 16.3a1.3 1.3 0 0 1 0-1.8zM9.5 10l4.5 4.5"/>',
}


def icon(name, color=TEXT_2, size=48):
    c = qcolor(color).name()
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{ICONS[name].format(c=c)}</svg>'
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    ic = QIcon(pm)
    dim = QPixmap(pm)  # disabled state: same glyph at ~35% opacity
    dp = QPainter(dim)
    dp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    dp.fillRect(dim.rect(), QColor(0, 0, 0, 90))
    dp.end()
    ic.addPixmap(dim, QIcon.Disabled)
    return ic


class _HoverIcon(QObject):
    """Swaps a button's icon between its normal and hover colors (Qt has no hover icon mode for buttons)."""

    def __init__(self, button, normal, hover):
        super().__init__(button)
        self.normal, self.hover = normal, hover
        button.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Enter:
            obj.setIcon(self.hover)
        elif ev.type() == QEvent.Leave:
            obj.setIcon(self.normal)
        return False


# icon colors per variant: (normal, hover)
_ICON_COLORS = {
    None: (TEXT, TEXT), "outline": (TEXT_2, TEXT), "ghost": (TEXT_2, TEXT), "icon": (TEXT_2, TEXT),
    "quietDanger": (TEXT_2, DANGER), "primary": (ON_ACCENT, ON_ACCENT), "play": (SIDEBAR, SIDEBAR),
}


def button(text="", icon_name=None, variant=None, tooltip=None):
    """Push button styled by the stylesheet's [variant=...] rules; focus ring shows only for keyboard focus."""
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if icon_name:
        normal, hover = _ICON_COLORS.get(variant, (TEXT, TEXT))
        b.setIcon(icon(icon_name, normal))
        b.setIconSize(QSize(16, 16) if variant != "play" else QSize(16, 16))
        if hover != normal:
            _HoverIcon(b, b.icon(), icon(icon_name, hover))
    if tooltip:
        b.setToolTip(tooltip)
    b.setFocusPolicy(Qt.TabFocus)
    b.setCursor(Qt.PointingHandCursor)
    return b


def label(text="", role=None):
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    return lb


class ElidedLabel(QLabel):
    """Single-line label that elides in the middle instead of clipping; full text in the tooltip."""

    def __init__(self, text="", role=None):
        super().__init__()
        if role:
            self.setProperty("role", role)
        self.setMinimumWidth(40)
        self._full = ""
        self.setText(text)

    def setText(self, text):
        self._full = text
        self.setToolTip(text)
        self._elide()

    def full_text(self):
        return self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def minimumSizeHint(self):
        return QSize(40, super().minimumSizeHint().height())

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self._full), super().sizeHint().height())

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(self._full, Qt.ElideMiddle, max(self.width(), 40)))


def frame(name):
    f = QFrame()
    f.setObjectName(name)
    return f


class Composer(QFrame):
    """Message-input style container whose border brightens while any child has focus."""

    def __init__(self):
        super().__init__()
        self.setObjectName("composer")

    def watch(self, widget):
        widget.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.FocusIn, QEvent.FocusOut):
            self.setProperty("focused", ev.type() == QEvent.FocusIn)
            self.style().unpolish(self)
            self.style().polish(self)
        return False


# ---------- comment list rows ----------
ROLE_META = Qt.UserRole + 1
ROLE_TEXT = Qt.UserRole + 2
ROLE_HIGHLIGHT = Qt.UserRole + 3


class CommentDelegate(QStyledItemDelegate):
    """Row: muted mono timecode + optional Highlight pill, wrapped body, hairline divider, accent bar when selected."""
    PAD_X, PAD_Y, GAP = 14, 10, 4

    @staticmethod
    def _fonts():
        body = QFont(QApplication.font())
        body.setPixelSize(FONT_BODY)
        meta = QFont(body)
        meta.setFamilies(MONO)
        meta.setPixelSize(FONT_META)
        pill = QFont(body)
        pill.setPixelSize(FONT_META - 1)
        return body, meta, pill

    def _body_height(self, text, width):
        return QFontMetrics(self._fonts()[0]).boundingRect(0, 0, width, 10_000, Qt.TextWordWrap, text).height()

    def sizeHint(self, option, index):
        width = self.parent().viewport().width() - 2 * self.PAD_X
        h = QFontMetrics(self._fonts()[1]).height() + self.GAP + self._body_height(index.data(ROLE_TEXT) or "", width)
        return QSize(width, h + 2 * self.PAD_Y + 1)

    def paint(self, p, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            p.fillRect(r, qcolor(ROW_SELECTED))
            p.fillRect(QRectF(r.left(), r.top(), 2, r.height()), qcolor(ACCENT))
        elif option.state & QStyle.State_MouseOver:
            p.fillRect(r, qcolor(ROW_HOVER))
        body, meta, pill = self._fonts()
        x, y, w = r.x() + self.PAD_X, r.y() + self.PAD_Y, r.width() - 2 * self.PAD_X
        mh = QFontMetrics(meta).height()
        meta_text = index.data(ROLE_META) or ""
        p.setFont(meta)
        p.setPen(qcolor(TEXT_2))
        p.drawText(QRectF(x, y, w, mh), Qt.AlignLeft | Qt.AlignVCenter, meta_text)
        if index.data(ROLE_HIGHLIGHT):
            px = x + QFontMetrics(meta).horizontalAdvance(meta_text) + 8
            pw = QFontMetrics(pill).horizontalAdvance("Highlight") + 12
            badge = QRectF(px, y + 1, pw, mh - 2)
            p.setPen(Qt.NoPen)
            p.setBrush(qcolor(ACCENT_SOFT))
            p.drawRoundedRect(badge, 4, 4)
            p.setFont(pill)
            p.setPen(qcolor(ACCENT))
            p.drawText(badge, Qt.AlignCenter, "Highlight")
        text = index.data(ROLE_TEXT) or ""
        p.setFont(body)
        p.setPen(qcolor(TEXT))
        p.drawText(QRectF(x, y + mh + self.GAP, w, self._body_height(text, w)), Qt.TextWordWrap, text)
        p.setPen(QPen(qcolor(ROW_DIVIDER), 1))
        p.drawLine(r.left(), r.bottom(), r.right(), r.bottom())
        p.restore()


# ---------- app setup ----------
def _dark_titlebar(widget):
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
        c = qcolor(CANVAS)
        colorref = ctypes.c_int(c.red() | c.green() << 8 | c.blue() << 16)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), 4)  # DWMWA_CAPTION_COLOR (Win11 only)
    except Exception:
        pass


class _TitlebarFilter(QObject):
    """Darkens the titlebar of every top-level window (main window, message boxes) when first shown."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and obj.isWidgetType() and obj.isWindow() and not obj.property("_darkened"):
            obj.setProperty("_darkened", True)
            _dark_titlebar(obj)
        return False


def apply(app):
    if sys.platform == "win32":
        # own taskbar identity: taskbar shows our window icon instead of a cached/generic exe icon
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VideoReviewer.App")
    app.setStyle("Fusion")
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    except AttributeError:
        pass
    f = QFont()
    f.setFamilies(SANS)
    f.setPixelSize(FONT_BODY)
    app.setFont(f)
    app.setStyleSheet(STYLESHEET)
    # bundled next to the code; PyInstaller unpacks data files into sys._MEIPASS
    app.setWindowIcon(QIcon(str(Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "icon.ico")))
    app._titlebar_filter = _TitlebarFilter(app)
    app.installEventFilter(app._titlebar_filter)
