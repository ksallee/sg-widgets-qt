"""The status glyph: the four kinds core resolves, the dot, and the sprite's dark treatment.

Every test runs on both bindings, offscreen, and never reaches the network: every picture here is
a `data:` url, which the loader decodes where it stands.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_core.status import HtmlIcon, ImageIcon, ImageMapIcon, StatusRecord
from sg_widgets_core.status_icons import STOCK_ICON_CELLS, STOCK_ICON_DATA_URLS
from sg_widgets_qt.images import ImageLoader, invert_lightness
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.status_glyph import DOT_SIZE, StatusGlyph

#: An 8 by 8 block, as a self-contained data URI.
RED_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAACXBIWXMAAA7EAAAOxAGV"
    "Kw4bAAAAFklEQVQYlWM8oaHxnwEPYMInOXwUAAArkgInxYgTRAAAAABJRU5ErkJggg=="
)

#: A truncated PNG: it fails to decode, which is the load-failure path.
BROKEN_PNG = "data:image/png;base64,iVBORw0KGgo="

#: A key the package bundles, and one it does not.
BUNDLED_KEY = "icon_apr"
SPRITE_KEY = "icon_x_thin_white"


def status(icon=None, code: str = "apr", name: str = "Approved") -> StatusRecord:
    return StatusRecord(id=1, code=code, name=name, bg_color="25,118,27", icon=icon)


@pytest.fixture
def loader():
    """A loader of its own, so one test's cache never answers another's."""
    return ImageLoader()


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(400, 200)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget):
    widget.setParent(parent)
    widget.resize(max(1, widget.sizeHint().width()), max(1, widget.sizeHint().height()))
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def image(widget: QtWidgets.QWidget) -> QtGui.QImage:
    pixmap = widget.grab()
    assert not pixmap.isNull()
    return pixmap.toImage()


def painted(widget: QtWidgets.QWidget) -> int:
    """How many pixels the glyph put down."""
    shot = image(widget)
    return sum(
        1
        for y in range(shot.height())
        for x in range(shot.width())
        if shot.pixelColor(x, y).alpha() > 0
    )


def test_a_status_with_no_icon_draws_nothing(root, loader):
    glyph = place(root, StatusGlyph(status=status(), loader=loader))
    assert glyph.source.kind == "none"
    assert glyph.sizeHint().isEmpty()


def test_fallback_draws_the_dot(root, loader):
    glyph = place(root, StatusGlyph(status=status(), fallback=True, loader=loader))
    assert glyph.sizeHint().width() == DOT_SIZE
    assert painted(glyph) > 0


def test_an_uploaded_icon_is_decoded_where_it_stands(root, loader):
    glyph = place(root, StatusGlyph(status=status(ImageIcon(data_url=RED_PNG)), loader=loader))
    assert glyph.source.kind == "image"
    assert glyph.source.pixmap is not None
    assert painted(glyph) > 0


def test_an_uploaded_icon_fills_the_glyph_box(root, loader):
    """A site's own icon is any size at all, so the caller's box sizes it, not the file."""
    glyph = place(root, StatusGlyph(status=status(ImageIcon(data_url=RED_PNG)), loader=loader))
    assert glyph.width() > 8  # the file is 8 by 8; the box is the chip glyph's own step
    assert painted(glyph) == glyph.width() * glyph.height()


def test_a_bundled_cell_draws_at_its_own_size(root, loader):
    glyph = place(
        root, StatusGlyph(status=status(ImageMapIcon(image_map_key=BUNDLED_KEY)), loader=loader)
    )
    cell = STOCK_ICON_CELLS[BUNDLED_KEY]
    assert glyph.source.kind == "cell"
    assert glyph.sizeHint().width() == cell.w
    assert glyph.sizeHint().height() == cell.h
    assert painted(glyph) > 0


def test_an_html_icon_draws_no_picture(root, loader):
    glyph = place(root, StatusGlyph(status=status(HtmlIcon(html="Active")), loader=loader))
    assert glyph.source.kind == "html"
    assert glyph.source.html == "Active"
    assert glyph.sizeHint().isEmpty()


def test_a_key_outside_the_bundle_needs_a_site(root, loader):
    assert SPRITE_KEY not in STOCK_ICON_DATA_URLS
    bare = place(
        root, StatusGlyph(status=status(ImageMapIcon(image_map_key=SPRITE_KEY)), loader=loader)
    )
    assert bare.source.kind == "dot"
    sited = StatusGlyph(
        status=status(ImageMapIcon(image_map_key=SPRITE_KEY)),
        site_url="https://site.example.com",
        loader=loader,
    )
    assert sited.source.kind == "sprite"
    assert sited.source.cell is not None


def test_a_picture_that_fails_to_decode_takes_the_dot(root, loader):
    glyph = place(root, StatusGlyph(status=status(ImageIcon(data_url=BROKEN_PNG)), loader=loader))
    assert glyph.source.pixmap is None
    assert painted(glyph) > 0


def test_the_sprite_inverts_its_lightness_in_dark_and_keeps_its_hue(root, loader):
    light = place(
        root, StatusGlyph(status=status(ImageMapIcon(image_map_key=BUNDLED_KEY)), loader=loader)
    )
    source = light.source.pixmap
    assert source is not None
    flipped = invert_lightness(source)
    before = source.toImage().pixelColor(source.width() // 2, source.height() // 2)
    after = flipped.toImage().pixelColor(flipped.width() // 2, flipped.height() // 2)
    assert after.hslHue() == before.hslHue()
    assert after.lightness() == 255 - before.lightness()


def test_on_color_leaves_the_sprite_as_it_is(root, loader):
    dark = QtWidgets.QWidget(root)
    apply_theme(dark, theme_for("default", dark=True))
    dark.resize(200, 80)
    dark.show()
    plain = place(
        dark, StatusGlyph(status=status(ImageMapIcon(image_map_key=BUNDLED_KEY)), loader=loader)
    )
    on_color = place(
        dark,
        StatusGlyph(
            status=status(ImageMapIcon(image_map_key=BUNDLED_KEY)), on_color=True, loader=loader
        ),
    )
    assert image(plain) != image(on_color)


def test_every_setter_repaints(root, loader):
    glyph = place(root, StatusGlyph(loader=loader))
    glyph.set_status(status(ImageMapIcon(image_map_key=BUNDLED_KEY)))
    glyph.set_site_url("https://site.example.com")
    glyph.set_fallback(True)
    glyph.set_on_color(True)
    glyph.set_size("lg")
    QtWidgets.QApplication.processEvents()
    assert glyph.fallback is True
    assert glyph.on_color is True
    assert glyph.size == "lg"
    assert glyph.site_url == "https://site.example.com"
    assert painted(glyph) > 0


def test_the_object_name_is_the_upstream_slot(root, loader):
    assert StatusGlyph(loader=loader).objectName() == "status-glyph"


def test_the_loaded_signal_fires_when_a_status_lands(root, qtbot, loader):
    glyph = place(root, StatusGlyph(loader=loader))
    with qtbot.waitSignal(glyph.loaded, timeout=1000):
        glyph.set_status(status(ImageIcon(data_url=RED_PNG)))
