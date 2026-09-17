"""The thumbnail: the ladder, the aspects, the three states, the play badge and the inert tile.

Every test runs on both bindings, offscreen, and never reaches the network: every picture here is
a `data:` url, which the loader decodes where it stands.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_core.render import THUMBNAIL_PENDING_PATH
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.base import THUMB_SIZE
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.thumbnail import THUMBNAIL_ASPECT_VALUES, Thumbnail

#: An 8 by 8 block, as a self-contained data URI.
RED_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAACXBIWXMAAA7EAAAOxAGV"
    "Kw4bAAAAFklEQVQYlWM8oaHxnwEPYMInOXwUAAArkgInxYgTRAAAAABJRU5ErkJggg=="
)

#: A truncated PNG: it fails to decode, which is the load-failure fallback.
BROKEN_PNG = "data:image/png;base64,iVBORw0KGgo="

#: What Flow PT serves while a thumbnail is still transcoding (field_types/image).
PENDING = "https://sg.example.com" + THUMBNAIL_PENDING_PATH + "thumbnail_pending.png"


@pytest.fixture
def loader():
    return ImageLoader()


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget):
    widget.setParent(parent)
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def image(widget: QtWidgets.QWidget) -> QtGui.QImage:
    pixmap = widget.grab()
    assert not pixmap.isNull()
    return pixmap.toImage()


def counts(shot: QtGui.QImage) -> dict:
    tally: dict = {}
    for y in range(shot.height()):
        for x in range(shot.width()):
            name = shot.pixelColor(x, y).name()
            tally[name] = tally.get(name, 0) + 1
    return tally


def test_constructs_with_its_defaults(root, loader):
    tile = place(root, Thumbnail(loader=loader))
    assert tile.objectName() == "thumbnail"
    assert tile.state == "none"
    assert tile.aspect == "16:9"
    assert tile.size == "md"
    assert counts(image(tile))


@pytest.mark.parametrize("step", sorted(THUMB_SIZE))
def test_every_step_of_the_ladder_sets_the_height(root, loader, step):
    tile = Thumbnail(size=step, loader=loader)
    assert tile.sizeHint().height() == THUMB_SIZE[step]


@pytest.mark.parametrize("aspect", THUMBNAIL_ASPECT_VALUES)
def test_the_aspect_sets_the_width(root, loader, aspect):
    tile = Thumbnail(size="lg", aspect=aspect, loader=loader)
    height = THUMB_SIZE["lg"]
    expected = height if aspect == "square" else round(height * 16 / 9)
    assert tile.sizeHint().width() == expected
    assert tile.sizeHint().height() == height


def test_a_value_that_decodes_is_drawn(root, loader):
    tile = place(root, Thumbnail(src=RED_PNG, size="lg", loader=loader))
    assert tile.state == "ready"
    assert tile.pixmap is not None
    assert QtGui.QColor(200, 40, 40).name() in counts(image(tile))


def test_the_transient_prefix_is_the_pending_state(root, loader):
    tile = place(root, Thumbnail(src=PENDING, size="lg", loader=loader))
    assert tile.state == "pending"
    assert tile.pixmap is None
    assert counts(image(tile))


def test_a_value_that_fails_to_decode_reads_as_no_image(root, loader):
    tile = place(root, Thumbnail(src=BROKEN_PNG, size="lg", entity_type="Shot", loader=loader))
    assert tile.pixmap is None
    assert tile.state == "none"
    assert counts(image(tile))


def test_the_entity_type_changes_the_placeholder_glyph(root, loader):
    plain = place(root, Thumbnail(size="lg", loader=loader))
    shot = place(root, Thumbnail(size="lg", entity_type="Shot", loader=loader))
    assert image(plain) != image(shot)


def test_the_play_badge_is_drawn_over_the_tile(root, loader):
    quiet = place(root, Thumbnail(src=RED_PNG, size="lg", loader=loader))
    playable = place(root, Thumbnail(src=RED_PNG, size="lg", playable=True, loader=loader))
    assert playable.sizeHint() == quiet.sizeHint()
    assert image(playable) != image(quiet)


def test_a_disabled_tile_greys_its_picture(root, loader):
    tile = place(root, Thumbnail(src=RED_PNG, size="lg", loader=loader))
    lit = counts(image(tile))
    tile.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    assert tile.disabled_opacity() == 0.5
    assert counts(image(tile)) != lit


def test_a_fresh_value_retries_rather_than_keeping_the_failure(root, loader):
    tile = place(root, Thumbnail(src=BROKEN_PNG, size="lg", loader=loader))
    assert tile.state == "none"
    tile.set_src(RED_PNG)
    QtWidgets.QApplication.processEvents()
    assert tile.state == "ready"
    assert tile.pixmap is not None


def test_the_loaded_signal_fires_when_a_picture_lands(root, qtbot, loader):
    tile = place(root, Thumbnail(size="lg", loader=loader))
    with qtbot.waitSignal(tile.loaded, timeout=1000) as caught:
        tile.set_src(RED_PNG)
    assert caught.args == [True]


def test_every_setter_repaints(root, loader):
    tile = place(root, Thumbnail(loader=loader))
    tile.set_alt("sh010_0010")
    tile.set_aspect("square")
    tile.set_size("2xl")
    tile.set_entity_type("Version")
    tile.set_playable(True)
    QtWidgets.QApplication.processEvents()
    assert tile.alt == "sh010_0010"
    assert tile.toolTip() == "sh010_0010"
    assert tile.aspect == "square"
    assert tile.size == "2xl"
    assert tile.sizeHint().width() == THUMB_SIZE["2xl"]
    assert counts(image(tile))
