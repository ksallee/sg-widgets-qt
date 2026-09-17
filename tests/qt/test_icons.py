"""The lucide glyphs: the licence beside them, that every one parses, and the rendering."""
from __future__ import annotations

import pytest
from qtpy import QtSvg
from qtpy.QtCore import QByteArray, QRect, Qt
from qtpy.QtGui import QColor, QPainter, QPixmap

from sg_widgets_qt import icons


def test_the_lucide_licence_sits_beside_the_icons():
    licence = icons.LUCIDE_DIR / "LICENSE"
    assert licence.is_file()
    text = licence.read_text(encoding="utf-8")
    assert "ISC License" in text
    assert "Lucide Icons and Contributors" in text


def test_the_icons_are_there():
    names = icons.icon_names()
    assert len(names) >= 80
    for name in ("chevron-down", "x", "search", "check", "triangle-alert", "search-x", "loader-circle"):
        assert name in names
        assert icons.has_icon(name) is True


def test_every_svg_parses(qapp):
    for path in sorted(icons.LUCIDE_DIR.glob("*.svg")):
        renderer = QtSvg.QSvgRenderer(QByteArray(path.read_bytes()))
        assert renderer.isValid(), path.name


def test_every_icon_renders(qapp):
    for name in icons.icon_names():
        glyph = icons.pixmap(name, "#112233", 16)
        assert glyph.isNull() is False, name
        assert glyph.size().width() == 16, name


def test_an_icon_is_drawn_in_the_colour_asked_for(qapp):
    glyph = icons.icon("chevron-down", "#ff0000", 16).pixmap(16, 16)
    assert glyph.isNull() is False

    image = glyph.toImage()
    middle = image.width() // 2
    column = [image.pixelColor(middle, y) for y in range(image.height())]
    painted = [c for c in column if c.alpha() > 0]
    assert painted, "the centre column of a chevron is where its vertex sits"
    assert any(c.red() > 128 and c.green() < 64 and c.blue() < 64 for c in painted)


def test_the_colour_may_be_a_qcolor(qapp):
    assert icons.icon("check", QColor("#00ff00"), 16) is icons.icon("check", "#00ff00", 16)


def test_the_pixmap_carries_the_device_pixel_ratio(qapp):
    glyph = icons.pixmap("x", "#000000", 16, dpr=2.0)
    assert glyph.devicePixelRatio() == 2.0
    assert glyph.width() == 32
    assert glyph.size().width() == 32


def test_the_cache_answers_with_the_same_objects(qapp):
    first = icons.icon("chevron-right", "#ffffff", 16)
    second = icons.icon("chevron-right", "#ffffff", 16)
    assert first is second
    assert icons.icon("chevron-right", "#ffffff", 20) is not first
    assert icons.icon("chevron-right", "#000000", 16) is not first
    assert icons.pixmap("chevron-right", "#ffffff", 16) is icons.pixmap("chevron-right", "#ffffff", 16)


def test_paint_icon_draws_into_the_rect(qapp):
    surface = QPixmap(32, 32)
    surface.fill(Qt.GlobalColor.transparent)
    painter = QPainter(surface)
    icons.paint_icon(painter, QRect(8, 8, 16, 16), "square", "#ff0000")
    painter.end()

    image = surface.toImage()
    assert image.pixelColor(0, 0).alpha() == 0
    inside = [
        image.pixelColor(x, y)
        for x in range(8, 24)
        for y in range(8, 24)
        if image.pixelColor(x, y).alpha() > 0
    ]
    assert inside
    assert all(c.red() > 128 and c.green() < 64 for c in inside)


def test_a_missing_name_raises_key_error(qapp):
    assert icons.has_icon("no-such-glyph") is False
    with pytest.raises(KeyError) as error:
        icons.icon("no-such-glyph", "#000000", 16)
    assert "no-such-glyph" in str(error.value)

    with pytest.raises(KeyError):
        icons.pixmap("no-such-glyph", "#000000", 16)
