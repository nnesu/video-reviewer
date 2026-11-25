"""Video Reviewer: play a video, leave frame-accurate comments with optional highlight boxes,
export a review folder (review.md + review.json + annotated frame PNGs) for Claude to read."""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QSizeF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QKeySequence, QPainter, QPainterPath, QPen, QRegion, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaMetaData, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
import theme as T
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsRectItem, QGridLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QSlider, QSplitter, QStyle, QVBoxLayout, QWidget,
)

from browser import VideoBrowser
import shortcuts as S


def fmt(ms):
    ms = max(0, round(ms))
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, ms = divmod(r, 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def frame_at(ms, fps):
    return int(ms * fps / 1000 + 1e-6)


def frame_start_ms(frame, fps):
    return math.ceil(frame * 1000 / fps)


def probe_fps(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
        n, d = out.split("/")
        return float(n) / float(d)
    except Exception:
        return None


def build_markdown(info, comments):
    lines = [
        f"# Video review: {info['name']}",
        "",
        f"- Video file: `{info['path']}`",
        f"- Resolution: {info['width']}x{info['height']} px | FPS: {info['fps']:.3f} | Duration: {fmt(info['duration_ms'])}",
        f"- Comments: {len(comments)}",
        "- Each comment has an image of the exact frame; the highlighted area (if any) is drawn as a red box.",
        "- Highlight coordinates are in source-video pixels, origin top-left; `norm` = fraction of frame width/height.",
        "",
    ]
    for i, c in enumerate(comments, 1):
        lines += [f"## {i}. {fmt(c['time_ms'])} | frame {c['frame']}", ""]
        lines += ["> " + ln for ln in c["text"].splitlines() or [""]]
        lines.append("")
        h = c.get("highlight")
        if h:
            lines.append(
                f"- Highlight: x={h['x']}, y={h['y']}, w={h['w']}, h={h['h']} px "
                f"(norm x={h['nx']:.4f}, y={h['ny']:.4f}, w={h['nw']:.4f}, h={h['nh']:.4f})"
            )
        else:
            lines.append("- Highlight: none (comment applies to the whole frame)")
        lines += [f"- Frame image: frames/{c['image']}", ""]
    return "\n".join(lines)


class SeekSlider(QSlider):
    """Left click jumps straight to the clicked spot (Qt default only page-steps), then drag continues."""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.maximum() > 0:
            v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(e.position().x()), self.width())
            self.setValue(v)
            self.sliderMoved.emit(v)
        super().mousePressEvent(e)


class VideoView(QGraphicsView):
    """Video surface with a drag-to-highlight rectangle stored in normalized (0-1) video coords."""

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setFrameShape(QFrame.NoFrame)
        self.setBackgroundBrush(T.qcolor(T.STAGE))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.item = QGraphicsVideoItem()
        self.scene().addItem(self.item)
        self.box = QGraphicsRectItem()
        self.box.setPen(QPen(T.qcolor(T.ACCENT), 2))
        self.box.setBrush(T.qcolor(T.ACCENT_SOFT))
        self.box.setZValue(1)
        self.box.hide()
        self.scene().addItem(self.box)
        self.drawing = False
        self.norm = None
        self._start = None
        self.item.nativeSizeChanged.connect(lambda _: self.relayout())

    def video_rect(self):
        vw = QSizeF(self.viewport().size())
        ns = self.item.nativeSize()
        if ns.isEmpty():
            return QRectF(0, 0, vw.width(), vw.height())
        s = ns.scaled(vw, Qt.KeepAspectRatio)
        return QRectF((vw.width() - s.width()) / 2, (vw.height() - s.height()) / 2, s.width(), s.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 9, 9)  # round corners to sit inside the 10px stage frame
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        self.relayout()

    def relayout(self):
        vw = QSizeF(self.viewport().size())
        self.setSceneRect(0, 0, vw.width(), vw.height())
        self.item.setPos(0, 0)
        self.item.setSize(vw)
        self.set_norm(self.norm)

    def set_norm(self, n):
        self.norm = n
        if not n:
            self.box.hide()
            return
        r = self.video_rect()
        self.box.setRect(r.x() + n[0] * r.width(), r.y() + n[1] * r.height(), n[2] * r.width(), n[3] * r.height())
        self.box.show()

    def _to_norm(self, e):
        p = self.mapToScene(e.position().toPoint())
        r = self.video_rect()
        clamp = lambda v: min(max(v, 0.0), 1.0)
        return clamp((p.x() - r.x()) / r.width()), clamp((p.y() - r.y()) / r.height())

    def mousePressEvent(self, e):
        if self.drawing and e.button() == Qt.LeftButton:
            self._start = self._to_norm(e)
            self.set_norm(None)

    def mouseMoveEvent(self, e):
        if self._start:
            (x0, y0), (x, y) = self._start, self._to_norm(e)
            self.set_norm((min(x0, x), min(y0, y), abs(x - x0), abs(y - y0)))

    def mouseReleaseEvent(self, e):
        if self._start:
            self._start = None
            if self.norm and (self.norm[2] < 0.005 or self.norm[3] < 0.005):
                self.set_norm(None)  # plain click clears the highlight


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Reviewer")
        self.resize(1200, 680)
        self.setMinimumSize(900, 560)
        self.video_path = None
        self.fps = 30.0
        self.comments = []
        self.pending = None

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.view = VideoView()
        self.player.setVideoOutput(self.view.item)

        P = T.PANE_PAD

        # ---- main pane: flush header ----
        header = T.frame("header")
        header.setFixedHeight(T.HEADER_HEIGHT)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(P, 0, 10, 0)
        hl.setSpacing(12)
        self.name_lbl = T.ElidedLabel("Video Reviewer", "title")
        self.file_lbl = T.ElidedLabel("No video loaded", "hint")
        self.name_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.file_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # path elides instead of widening the window
        open_btn = T.button("Open Video", "folder", "outline")
        open_btn.clicked.connect(self.open_dialog)
        keys_btn = T.button("", "keyboard", "icon")
        keys_btn.clicked.connect(self.open_shortcuts)
        hl.addWidget(self.name_lbl)
        hl.addWidget(self.file_lbl, 1)
        hl.addWidget(keys_btn)
        hl.addWidget(open_btn)

        # ---- video stage ----
        stage = T.frame("stage")
        sl = QVBoxLayout(stage)
        sl.setContentsMargins(1, 1, 1, 1)
        sl.addWidget(self.view)

        # ---- transport: seek bar, then timecode | buttons | comment ----
        self.slider = SeekSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(self.player.setPosition)
        self.time_lbl = T.label("00:00:00.000 | frame 0", "timecode")
        self.play_btn = T.button("", "play", "play")
        self.play_btn.clicked.connect(self.toggle_play)
        buttons = [
            ("5s", "back5", "Back 5 seconds", lambda: self.seek_rel(-5000)),
            ("", "frame_back", "Previous frame", lambda: self.step(-1)),
            (None, None, None, None),
            ("", "frame_fwd", "Next frame", lambda: self.step(1)),
            ("5s", "fwd5", "Forward 5 seconds", lambda: self.seek_rel(5000)),
        ]
        tips = {"play": (self.play_btn, "Play / Pause"), "open": (open_btn, "Open a video file"),
                "shortcuts": (keys_btn, "Keyboard shortcuts")}
        center = QHBoxLayout()
        center.setSpacing(4)
        for text, ic, tip, fn in buttons:
            if ic is None:
                center.addSpacing(6)
                center.addWidget(self.play_btn)
                center.addSpacing(6)
                continue
            b = T.button(text, ic, "icon")
            b.clicked.connect(fn)
            tips[ic] = (b, tip)  # icon names double as shortcut action ids
            center.addWidget(b)
        self.comment_btn = T.button("Comment", "plus", "primary")
        tips["comment"] = (self.comment_btn, "Pause and comment on this frame")
        self.comment_btn.clicked.connect(self.start_comment)
        self.transport = QWidget()
        tg = QGridLayout(self.transport)
        tg.setContentsMargins(0, 0, 0, 0)
        tg.addWidget(self.time_lbl, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        tg.addLayout(center, 0, 1, Qt.AlignCenter)
        tg.addWidget(self.comment_btn, 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        tg.setColumnStretch(0, 1)
        tg.setColumnStretch(2, 1)

        # ---- comment composer ----
        self.editor = T.Composer()
        el = QVBoxLayout(self.editor)
        el.setContentsMargins(14, 10, 10, 10)
        el.setSpacing(6)
        self.editor_lbl = T.label("", "meta")
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("What needs to change in this frame? Drag on the video to highlight an area.")
        self.text.setFixedHeight(72)
        self.editor.watch(self.text)
        self.text.installEventFilter(self)  # Enter saves, Esc cancels, Shift+Enter new line
        row = QHBoxLayout()
        row.setSpacing(6)
        clear = T.button("Clear Highlight", "eraser", "ghost")
        clear.clicked.connect(lambda: self.view.set_norm(None))
        cancel = T.button("Cancel", variant="ghost")
        cancel.clicked.connect(self.end_comment)
        save = T.button("Save Comment", variant="primary")
        save.clicked.connect(self.save_comment)
        tips.update(clear=(clear, "Remove the highlight box"), cancel=(cancel, "Discard this comment"),
                    save=(save, "Save this comment"))
        row.addWidget(clear)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(save)
        el.addWidget(self.editor_lbl)
        el.addWidget(self.text)
        el.addLayout(row)
        self.editor.hide()

        body = QVBoxLayout()
        body.setContentsMargins(P, P, P, P - 4)
        body.setSpacing(10)
        body.addWidget(stage, 1)
        body.addWidget(self.slider)
        body.addWidget(self.transport)
        body.addSpacing(2)
        body.addWidget(self.editor)
        main = T.frame("main")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        ml.addWidget(header)
        ml.addLayout(body, 1)

        # ---- sidebar: comments ----
        sidebar = T.frame("sidebar")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)
        side_head = QWidget()
        shl = QVBoxLayout(side_head)
        shl.setContentsMargins(P, 12, P, 10)
        shl.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(T.label("Comments", "title"))
        self.count_lbl = T.label("0", "badge")
        title_row.addWidget(self.count_lbl, 0, Qt.AlignVCenter)
        title_row.addStretch()
        shl.addLayout(title_row)
        shl.addWidget(T.label("Click to jump · double-click to edit", "hint"))
        sb.addWidget(side_head)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setMouseTracking(True)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setItemDelegate(T.CommentDelegate(self.list))
        self.list.itemClicked.connect(self.jump_to)
        self.list.itemDoubleClicked.connect(lambda _: self.edit_selected())
        sb.addWidget(self.list, 1)
        footer = T.frame("sidebarFooter")
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(10, 10, 10, 10)
        fl.setSpacing(6)
        edit_btn = T.button("Edit", "pencil", "ghost")
        edit_btn.clicked.connect(self.edit_selected)
        del_btn = T.button("Delete", "trash", "quietDanger")
        del_btn.clicked.connect(self.delete_selected)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(edit_btn, 1)
        actions.addWidget(del_btn, 1)
        fl.addLayout(actions)
        export_btn = T.button("Export Review", "export")
        tips.update(edit=(edit_btn, "Edit selected comment"), delete=(del_btn, "Delete selected comment"),
                    export=(export_btn, "Write review.md / review.json"))
        export_btn.clicked.connect(self.export)
        fl.addWidget(export_btn)
        sb.addWidget(footer)

        split = QSplitter()
        split.setHandleWidth(1)
        split.setChildrenCollapsible(False)
        split.addWidget(main)
        split.addWidget(sidebar)
        sidebar.setMinimumWidth(260)
        split.setStretchFactor(0, 1)
        split.setSizes([880, 320])
        self.setCentralWidget(split)

        self._icons = {s: T.icon(s, T.SIDEBAR) for s in ("play", "pause")}
        self.player.durationChanged.connect(lambda d: self.slider.setRange(0, d))
        self.player.positionChanged.connect(self.on_position)
        self.player.playbackStateChanged.connect(
            lambda s: self.play_btn.setIcon(self._icons["pause" if s == QMediaPlayer.PlayingState else "play"]))
        self.player.mediaStatusChanged.connect(self.on_status)
        self.player.errorOccurred.connect(lambda _e, msg: QMessageBox.warning(self, "Playback error", msg))

        idle = lambda fn: lambda: None if self.pending else fn()  # blocked while writing a comment
        busy = lambda fn: lambda: fn() if self.pending else None  # only while writing a comment
        self.action_fns = {
            "play": idle(self.toggle_play), "frame_back": idle(lambda: self.step(-1)),
            "frame_fwd": idle(lambda: self.step(1)), "back5": idle(lambda: self.seek_rel(-5000)),
            "fwd5": idle(lambda: self.seek_rel(5000)), "comment": self.start_comment,
            "save": busy(self.save_comment), "cancel": busy(self.end_comment),
            "clear": busy(lambda: self.view.set_norm(None)), "edit": self.edit_selected,
            "delete": idle(self.delete_selected), "open": idle(self.open_dialog), "export": idle(self.export),
            "shortcuts": self.open_shortcuts,
        }
        self.tips = tips
        self.shortcuts = {}
        for a, fn in self.action_fns.items():
            self.shortcuts[a] = QShortcut(self)
            self.shortcuts[a].activated.connect(fn)
        self.apply_shortcuts(S.load())

    # ---------- shortcuts ----------
    def apply_shortcuts(self, keys):
        self.keys = keys
        for a, sc in self.shortcuts.items():
            sc.setKey(QKeySequence(keys.get(a, "")))
        for a, (btn, tip) in self.tips.items():
            k = keys.get(a)
            btn.setToolTip(f"{tip} ({S.display(k)})" if k else tip)

    def open_shortcuts(self):
        dlg = S.ShortcutDialog(self.keys, self)
        if dlg.exec() == QDialog.Accepted:
            S.save(dlg.keys())
            self.apply_shortcuts(S.load())

    def eventFilter(self, obj, e):
        # The comment box swallows Enter itself, so match save/cancel/clear here before it does.
        if obj is self.text and e.type() == QEvent.KeyPress:
            seq = S.event_seq(e)
            if seq == S.NEWLINE:
                self.text.insertPlainText("\n")
                return True
            for a in ("save", "cancel", "clear"):
                if self.keys.get(a) and seq == QKeySequence(self.keys[a]):
                    self.action_fns[a]()
                    return True
        return super().eventFilter(obj, e)

    # ---------- files ----------
    def review_dir(self):
        return self.video_path.parent / f"{self.video_path.stem}_review"

    def open_dialog(self):
        dlg = VideoBrowser(self, str(self.video_path.parent) if self.video_path else None)
        if dlg.exec() == QDialog.Accepted and dlg.selected:
            self.load(dlg.selected)

    def load(self, path):
        self.end_comment()
        self.video_path = path
        self.file_lbl.setText(str(path))
        self.file_lbl.setToolTip(str(path))
        self.name_lbl.setText(path.name)
        self.setWindowTitle(f"Video Reviewer - {path.name}")
        self.fps = probe_fps(path) or 0
        self.comments = []
        d = self.review_dir()
        saved = d / "review.json"
        if saved.exists():
            box = QMessageBox(QMessageBox.Question, "Existing review found",
                              f"This video already has a review in\n{d}\n\n"
                              "Start a new review? The old comments and frame images will be deleted.", parent=self)
            new_btn = QPushButton("Start new review")
            new_btn.setProperty("variant", "danger")  # set before adding so the stylesheet sees it
            box.addButton(new_btn, QMessageBox.AcceptRole)
            box.addButton("Continue old review", QMessageBox.RejectRole)
            box.setDefaultButton(new_btn)
            box.exec()
            if box.clickedButton() == new_btn:
                shutil.rmtree(d / "frames", ignore_errors=True)
                for f in ("review.json", "review.md"):
                    (d / f).unlink(missing_ok=True)
            else:
                try:
                    self.comments = json.loads(saved.read_text(encoding="utf-8"))["comments"]
                except Exception as ex:
                    QMessageBox.warning(self, "Could not load saved comments", str(ex))
        self.refresh_list()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.pause()

    def on_status(self, status):
        if status == QMediaPlayer.LoadedMedia and not self.fps:
            self.fps = float(self.player.metaData().value(QMediaMetaData.VideoFrameRate) or 0) or 30.0

    def info(self):
        ns = self.view.item.nativeSize()
        return {"name": self.video_path.name, "path": str(self.video_path), "fps": self.fps,
                "width": int(ns.width()), "height": int(ns.height()), "duration_ms": self.player.duration()}

    def save(self):
        d = self.review_dir()
        d.mkdir(exist_ok=True)
        (d / "review.json").write_text(json.dumps({"video": self.info(), "comments": self.comments}, indent=2),
                                       encoding="utf-8")
        (d / "review.md").write_text(build_markdown(self.info(), self.comments), encoding="utf-8")

    def export(self):
        if not self.video_path:
            return
        self.save()
        folder = str(self.review_dir())
        dlg = QDialog(self)
        dlg.setWindowTitle("Review exported")
        dlg.setMinimumWidth(560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(T.label("Review exported", "title"))
        n = len(self.comments)
        lay.addWidget(T.label(f"{n} comment{'' if n == 1 else 's'} saved to this folder:", "meta"))
        path_box = QLineEdit(folder)
        path_box.setReadOnly(True)
        path_box.setFocusPolicy(Qt.ClickFocus)
        path_box.setCursorPosition(0)
        lay.addWidget(path_box)
        row = QHBoxLayout()
        copy_btn = T.button("Copy Path", tooltip="Copy the folder path to the clipboard")
        open_btn = T.button("Open Folder", "folder", "outline")
        row.addWidget(copy_btn)
        row.addWidget(open_btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addSpacing(6)
        lay.addWidget(T.frame("hairline"))
        bottom = QHBoxLayout()
        keep_btn = T.button("Keep Reviewing", variant="ghost")
        finish_btn = T.button("Finish && Close", variant="primary", tooltip="Finish reviewing and close the window")
        bottom.addStretch()
        bottom.addWidget(keep_btn)
        bottom.addWidget(finish_btn)
        lay.addLayout(bottom)

        def copy():
            QApplication.clipboard().setText(folder)
            copy_btn.setText("Copied")
        copy_btn.clicked.connect(copy)
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        keep_btn.clicked.connect(dlg.reject)
        finish_btn.clicked.connect(dlg.accept)
        if dlg.exec() == QDialog.Accepted:
            self.close()  # everything is already saved above

    # ---------- transport ----------
    def on_position(self, ms):
        if not self.slider.isSliderDown():
            self.slider.setValue(ms)
        self.time_lbl.setText(f"{fmt(ms)} | frame {frame_at(ms, self.fps)}")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek_rel(self, delta):
        self.player.setPosition(min(max(0, self.player.position() + delta), self.player.duration()))

    def step(self, n):
        self.player.pause()
        f = max(0, frame_at(self.player.position(), self.fps) + n)
        self.player.setPosition(min(frame_start_ms(f, self.fps), self.player.duration()))

    # ---------- comments ----------
    def start_comment(self):
        if not self.video_path or self.pending:
            return
        self.player.pause()
        vf = self.view.item.videoSink().videoFrame()
        img = vf.toImage() if vf.isValid() else None
        if img is None or img.isNull():
            QMessageBox.information(self, "No frame", "No video frame is shown yet. Play or seek first.")
            return
        st = vf.startTime()
        if st >= 0:
            time_ms, frame = st / 1000, round(st * self.fps / 1e6)
        else:
            time_ms = self.player.position()
            frame = frame_at(time_ms, self.fps)
        self.open_editor({"time_ms": round(time_ms, 3), "frame": frame, "img": img, "edit_id": None}, "", None)

    def edit_selected(self):
        item = self.list.currentItem()
        if not item or self.pending:
            return
        self.jump_to(item)
        c = self.find(item.data(Qt.UserRole))
        frames = self.review_dir() / "frames"
        # raw copy has no box; older comments saved without one fall back to the annotated image
        img = QImage(str(frames / "raw" / c["image"]))
        if img.isNull():
            img = QImage(str(frames / c["image"]))
        h = c.get("highlight")
        norm = (h["nx"], h["ny"], h["nw"], h["nh"]) if h else None
        self.open_editor({"time_ms": c["time_ms"], "frame": c["frame"], "img": img, "edit_id": c["id"]}, c["text"], norm)

    def open_editor(self, pending, text, norm):
        self.pending = pending
        verb = "Editing comment" if pending["edit_id"] else "Comment"
        self.editor_lbl.setText(f"{verb} · {fmt(pending['time_ms'])} · frame {pending['frame']}")
        self.transport.setEnabled(False)
        self.slider.setEnabled(False)
        self.view.drawing = True
        self.editor.show()
        self.text.setPlainText(text)
        self.view.set_norm(norm)
        self.text.setFocus()

    def end_comment(self):
        self.pending = None
        self.view.drawing = False
        self.view.set_norm(None)
        self.editor.hide()
        self.transport.setEnabled(True)
        self.slider.setEnabled(True)

    def save_comment(self):
        text = self.text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Empty comment", "Type a comment first.")
            return
        p, raw, n = self.pending, self.pending["img"], self.view.norm
        img = raw.copy()
        if p["edit_id"]:
            c = self.find(p["edit_id"])
            c.update(text=text, highlight=None)
        else:
            cid = max((c["id"] for c in self.comments), default=0) + 1
            c = {"id": cid, "time_ms": p["time_ms"], "frame": p["frame"], "text": text, "highlight": None,
                 "image": f"c{cid:03}_f{p['frame']:06}.png"}
        if n:
            W, H = img.width(), img.height()
            c["highlight"] = {"x": round(n[0] * W), "y": round(n[1] * H), "w": round(n[2] * W), "h": round(n[3] * H),
                              "nx": n[0], "ny": n[1], "nw": n[2], "nh": n[3]}
            painter = QPainter(img)
            painter.setPen(QPen(QColor(255, 0, 0), max(3, W // 300)))
            h = c["highlight"]
            painter.drawRect(h["x"], h["y"], h["w"], h["h"])
            painter.end()
        frames = self.review_dir() / "frames"
        (frames / "raw").mkdir(parents=True, exist_ok=True)
        if not (img.save(str(frames / c["image"])) and raw.save(str(frames / "raw" / c["image"]))):
            QMessageBox.warning(self, "Save failed", f"Could not write {frames / c['image']}")
            return
        if not p["edit_id"]:
            self.comments.append(c)
        self.comments.sort(key=lambda x: x["time_ms"])
        self.save()
        self.refresh_list()
        self.end_comment()

    def refresh_list(self):
        self.list.clear()
        for c in self.comments:
            mark = " ▭" if c.get("highlight") else ""
            meta = f"{fmt(c['time_ms'])} · frame {c['frame']}"
            it = QListWidgetItem(f"[{meta}]{mark}\n{c['text']}")  # plain text kept for accessibility/tooltips
            it.setData(Qt.UserRole, c["id"])
            it.setData(T.ROLE_META, meta)
            it.setData(T.ROLE_TEXT, c["text"])
            it.setData(T.ROLE_HIGHLIGHT, bool(c.get("highlight")))
            self.list.addItem(it)
        self.count_lbl.setText(str(len(self.comments)))

    def find(self, cid):
        return next(c for c in self.comments if c["id"] == cid)

    def jump_to(self, item):
        if self.pending:
            return
        c = self.find(item.data(Qt.UserRole))
        self.player.pause()
        self.player.setPosition(math.ceil(c["time_ms"]))
        h = c.get("highlight")
        self.view.set_norm((h["nx"], h["ny"], h["nw"], h["nh"]) if h else None)

    def delete_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        c = self.find(item.data(Qt.UserRole))
        if QMessageBox.question(self, "Delete comment", f"Delete comment at {fmt(c['time_ms'])}?") != QMessageBox.Yes:
            return
        self.comments.remove(c)
        (self.review_dir() / "frames" / c["image"]).unlink(missing_ok=True)
        (self.review_dir() / "frames" / "raw" / c["image"]).unlink(missing_ok=True)
        self.view.set_norm(None)
        self.save()
        self.refresh_list()


def selftest():
    assert fmt(3_723_456) == "01:02:03.456"
    fps = 30000 / 1001
    for f in (0, 1, 29, 2003, 100_000):
        assert frame_at(frame_start_ms(f, fps), fps) == f, f
    md = build_markdown({"name": "v.mp4", "path": "C:/v.mp4", "fps": 30, "width": 1920, "height": 1080, "duration_ms": 5000},
                        [{"id": 1, "time_ms": 1000, "frame": 30, "text": "fix\nthis", "image": "c001_f000030.png",
                          "highlight": {"x": 1, "y": 2, "w": 3, "h": 4, "nx": .1, "ny": .2, "nw": .3, "nh": .4}}])
    assert "## 1. 00:00:01.000 | frame 30" in md and "> fix\n> this" in md and "x=1, y=2, w=3, h=4" in md
    assert "- Frame image: frames/c001_f000030.png" in md and "- Time:" not in md
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit()
    app = QApplication(sys.argv)
    T.apply(app)
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        w.load(Path(sys.argv[1]))
    sys.exit(app.exec())
