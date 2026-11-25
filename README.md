# Video Reviewer

A Windows desktop app for frame-accurate video review. Open a video, pause on any frame, write a comment and
optionally drag a box over the part of the frame it's about. Comments are exported in a format Claude (or any
reader) can use directly.

## Features

- Built-in video browser with pinned folders (right-click a pin to unpin, drag to reorder)
- Player with play/pause, ±5 s, and single-frame step (Space, Left/Right, Shift+Left/Right)
- Frame-specific comments with an optional highlight box; edit or delete them from the side panel.
  In the comment box, Enter saves, Esc cancels and Shift+Enter adds a new line
- Keyboard shortcut settings (keyboard button in the header, or Ctrl+,): assign or clear a key for every action
- Export writes `<video>_review/` next to the video:
  - `review.md` — every comment with timecode, frame number, highlight (px and normalized) and image path
  - `review.json` — the same data, machine-readable
  - `frames/` — the frame for each comment with the highlight drawn on; `frames/raw/` holds clean copies
- Reopening a reviewed video asks before replacing the old review

## Run from source

Requires Python 3.12 and PySide6.

```
pip install PySide6
python app.py
```

`ffprobe` on PATH is optional: when present it gives the exact frame rate, otherwise the app reads it from the
video's metadata (falling back to 30 fps).

## Build the exe

```
pip install pyinstaller
python make_icon.py          # only after editing logo.svg
python -m PyInstaller --noconfirm VideoReviewer.spec
```

The result is a single self-contained `dist/VideoReviewer.exe` (Windows 10/11, 64-bit); no Python or other
install is needed to run it. Pins and the last opened folder are saved to `settings.ini` next to the exe.
