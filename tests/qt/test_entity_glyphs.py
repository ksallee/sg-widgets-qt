"""The glyph map: the nine types it covers, the tag everything else takes, and the icons on disk."""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_qt import icons
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_glyphs import (
    DEFAULT_ENTITY_GLYPH,
    ENTITY_GLYPHS,
    entity_glyph,
)

#: The types upstream's map names, in its own order.
LISTED = (
    "Shot",
    "Asset",
    "Sequence",
    "Version",
    "Task",
    "HumanUser",
    "Project",
    "Note",
    "PublishedFile",
)


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(200, 100)
    widget.show()
    return widget


def test_the_map_covers_the_types_upstream_names():
    assert tuple(ENTITY_GLYPHS) == LISTED


@pytest.mark.parametrize("entity_type", LISTED)
def test_every_listed_type_has_a_glyph_of_its_own(entity_type):
    name = entity_glyph(entity_type)
    assert name == ENTITY_GLYPHS[entity_type]
    assert name != DEFAULT_ENTITY_GLYPH


@pytest.mark.parametrize("entity_type", ["CustomEntity07", "Delivery", "", None])
def test_an_unlisted_type_takes_the_tag(entity_type):
    assert entity_glyph(entity_type) == DEFAULT_ENTITY_GLYPH


def test_every_glyph_the_map_names_is_on_disk():
    for name in (*ENTITY_GLYPHS.values(), DEFAULT_ENTITY_GLYPH):
        assert icons.has_icon(name), name


def test_no_two_listed_types_are_told_apart_by_nothing():
    assert len(set(ENTITY_GLYPHS.values())) == len(ENTITY_GLYPHS)


def test_every_glyph_paints(root):
    theme = theme_for("default")
    for name in (*ENTITY_GLYPHS.values(), DEFAULT_ENTITY_GLYPH):
        pixmap = icons.pixmap(name, theme.color("foreground"), 16)
        assert not pixmap.isNull()
        shot = pixmap.toImage()
        assert any(
            shot.pixelColor(x, y).alpha() > 0
            for y in range(shot.height())
            for x in range(shot.width())
        ), name


def test_a_caller_may_add_a_type_of_its_own():
    ENTITY_GLYPHS["CustomEntity07"] = "layers"
    try:
        assert entity_glyph("CustomEntity07") == "layers"
    finally:
        del ENTITY_GLYPHS["CustomEntity07"]
    assert entity_glyph("CustomEntity07") == DEFAULT_ENTITY_GLYPH


def test_the_glyph_is_drawn_in_the_colour_it_is_given(root):
    theme = theme_for("default")
    one = icons.pixmap("tag", theme.color("foreground"), 16).toImage()
    other = icons.pixmap("tag", QtGui.QColor(200, 40, 40), 16).toImage()
    assert one != other
