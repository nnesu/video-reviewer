"""Render logo.svg into a multi-size icon.ico (PNG-compressed entries). Run: python make_icon.py"""
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SIZES = [16, 24, 32, 48, 64, 128, 256]


def png_bytes(renderer, size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p)
    p.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def build_ico(pngs):
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = len(header) + 16 * len(pngs)
    entries, data = b"", b""
    for size, png in pngs:
        dim = 0 if size >= 256 else size  # 0 means 256 in the ICO directory
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return header + entries + data


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    r = QSvgRenderer("logo.svg")
    assert r.isValid(), "logo.svg failed to parse"
    ico = build_ico([(s, png_bytes(r, s)) for s in SIZES])
    open("icon.ico", "wb").write(ico)
    assert ico[:4] == b"\0\0\1\0" and struct.unpack("<H", ico[4:6])[0] == len(SIZES)
    print(f"icon.ico: {len(SIZES)} sizes, {len(ico)} bytes")
