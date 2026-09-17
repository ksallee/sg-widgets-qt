"""The lucide glyphs, rendered at any colour and size.

The SVGs are the ones the upstream widgets import, downloaded by `tools/lucide.py` into
`icons/lucide/` beside their ISC licence. Every one is drawn on a 24 unit grid with
`stroke="currentColor"` and `stroke-width="2"`, so a glyph keeps lucide's stroke at any size:
the renderer scales the whole drawing, weight included.

`currentColor` is replaced with the colour asked for before the SVG is parsed, because
`QSvgRenderer` has no notion of a current colour. A rendered pixmap and its `QIcon` are cached
by name, colour and size, so a delegate may ask on every paint.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from qtpy import QtSvg
from qtpy.QtCore import QByteArray, QRect, QRectF, Qt
from qtpy.QtGui import QColor, QIcon, QPainter, QPixmap

__all__ = [
    "LUCIDE_DIR",
    "has_icon",
    "icon",
    "icon_names",
    "paint_icon",
    "pixmap",
]

#: Where `tools/lucide.py` writes the SVGs.
LUCIDE_DIR = Path(__file__).resolve().parent / "icons" / "lucide"

ColorLike = Union[QColor, str]

_SOURCE: dict[str, str] = {}
_PIXMAPS: dict[tuple[str, str, int, float], QPixmap] = {}
_ICONS: dict[tuple[str, str, int], QIcon] = {}


def icon_names() -> list[str]:
    """Every glyph on disk, sorted."""
    return sorted(p.stem for p in LUCIDE_DIR.glob("*.svg"))


def has_icon(name: str) -> bool:
    """True when `name` is a glyph this package carries."""
    return name in _SOURCE or (LUCIDE_DIR / f"{name}.svg").is_file()


def icon(name: str, color: ColorLike, size: int = 16) -> QIcon:
    """The glyph `name` in `color`, at `size` logical pixels.

    The pixmap behind it is drawn at twice the size with a device pixel ratio of 2, so the icon
    is crisp on a retina screen and scales down cleanly anywhere else.
    """
    key = (name, _color_key(color), int(size))
    cached = _ICONS.get(key)
    if cached is None:
        cached = QIcon(pixmap(name, color, size, 2.0))
        _ICONS[key] = cached
    return cached


def pixmap(name: str, color: ColorLike, size: int = 16, dpr: float = 1.0) -> QPixmap:
    """The glyph `name` in `color`, `size` logical pixels wide, drawn at `dpr` device pixels."""
    size = int(size)
    dpr = float(dpr)
    key = (name, _color_key(color), size, dpr)
    cached = _PIXMAPS.get(key)
    if cached is not None:
        return cached

    side = max(1, int(round(size * dpr)))
    renderer = QtSvg.QSvgRenderer(QByteArray(_painted_source(name, color).encode("utf-8")))
    out = QPixmap(side, side)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0.0, 0.0, float(side), float(side)))
    painter.end()
    out.setDevicePixelRatio(dpr)
    _PIXMAPS[key] = out
    return out


def paint_icon(painter: QPainter, rect: QRect, name: str, color: ColorLike) -> None:
    """Draw the glyph `name` in `color`, centred in `rect` at the square side `rect` allows."""
    box = rect.toRect() if isinstance(rect, QRectF) else rect
    side = min(box.width(), box.height())
    if side <= 0:
        return
    device = painter.device()
    dpr = float(device.devicePixelRatioF()) if device is not None else 1.0
    glyph = pixmap(name, color, side, dpr)
    x = box.x() + (box.width() - side) // 2
    y = box.y() + (box.height() - side) // 2
    painter.drawPixmap(int(x), int(y), glyph)


def _color_key(color: ColorLike) -> str:
    value = color if isinstance(color, QColor) else QColor(color)
    if not value.isValid():
        raise ValueError(f"not a colour: {color!r}")
    return value.name(QColor.NameFormat.HexArgb)


def _source(name: str) -> str:
    """The SVG text of one glyph. Raises `KeyError` on a name this package does not carry."""
    cached = _SOURCE.get(name)
    if cached is not None:
        return cached
    path = LUCIDE_DIR / f"{name}.svg"
    if not path.is_file():
        raise KeyError(name)
    text = path.read_text(encoding="utf-8")
    _SOURCE[name] = text
    return text


def _painted_source(name: str, color: ColorLike) -> str:
    key = _color_key(color)
    # `#aarrggbb` is Qt's own spelling and no SVG colour: the renderer takes `#rrggbb` plus an
    # explicit opacity instead.
    value = QColor(key)
    text = _source(name).replace("currentColor", value.name(QColor.NameFormat.HexRgb))
    if value.alpha() < 255:
        text = text.replace("<svg", f'<svg opacity="{value.alphaF():.4f}"', 1)
    return text
