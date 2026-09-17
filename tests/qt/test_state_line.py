"""The empty and error line: its two states, its paddings, its glyph and its elision.

Every test runs on both bindings, offscreen, and paints into a pixmap rather than a window.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_core.state import ERROR_LABEL, LOADING_LABEL, NO_ROWS_LABEL, StateLabels
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.state_line import STATE_LINE_PAD, StateLine


@pytest.fixture
def root(qtbot):
    """A shown root wearing the default light theme, which every leaf reads through."""
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget, width: int = 320):
    widget.setParent(parent)
    widget.resize(width, widget.sizeHint().height())
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


def test_constructs_with_its_defaults(root):
    line = place(root, StateLine())
    assert line.state == "empty"
    assert line.pad == "popover"
    assert line.icon is None
    assert line.objectName() == "state-line"


def test_paints_the_label(root):
    line = place(root, StateLine(state="empty", label="No department matches"))
    assert counts(image(line))


@pytest.mark.parametrize("pad", sorted(STATE_LINE_PAD))
def test_every_padding_sets_the_height(root, pad):
    line = place(root, StateLine(state="empty", label="No rows", pad=pad))
    bare = place(root, StateLine(state="empty", label="No rows", pad="none"))
    assert line.sizeHint().height() == bare.sizeHint().height() + 2 * STATE_LINE_PAD[pad]


def test_the_error_state_is_destructive_and_the_empty_one_muted(root):
    theme = theme_for("default")
    empty = place(root, StateLine(state="empty", label="No rows"))
    error = place(root, StateLine(state="error", label="The read was refused"))
    assert theme.color("destructive").name() in counts(image(error))
    assert theme.color("destructive").name() not in counts(image(empty))
    assert theme.color("muted_foreground").name() in counts(image(empty))


def test_the_glyph_widens_the_line(root):
    bare = place(root, StateLine(state="empty", label="No rows"))
    glyphed = place(root, StateLine(state="empty", label="No rows", icon="search-x"))
    assert glyphed.sizeHint().width() > bare.sizeHint().width()


def test_a_label_that_does_not_fit_is_elided_and_carries_itself(root):
    label = "No department in this project matches what was typed into the box"
    line = place(root, StateLine(state="empty", label=label), width=120)
    image(line)
    assert line.toolTip() == label


def test_a_label_that_fits_carries_no_tooltip(root):
    line = place(root, StateLine(state="empty", label="No rows"), width=320)
    image(line)
    assert line.toolTip() == ""


def test_the_slot_name_is_the_object_name(root):
    line = StateLine(state="error", label="No next page", slot_name="state-line-page-error")
    assert line.objectName() == "state-line-page-error"
    line.set_slot_name("state-line")
    assert line.objectName() == "state-line"


def test_apply_state_takes_the_line_core_settles(root):
    line = place(root, StateLine())
    line.apply_state("empty", StateLabels())
    assert line.label == NO_ROWS_LABEL
    line.apply_state("error", StateLabels(), message="  The read was refused  ")
    assert line.state == "error"
    assert line.label == "The read was refused"
    line.apply_state("error", StateLabels())
    assert line.label == ERROR_LABEL
    line.apply_state("loading", StateLabels())
    assert line.label == LOADING_LABEL


def test_every_setter_repaints(root):
    line = place(root, StateLine())
    for setter, value in (
        (line.set_state, "error"),
        (line.set_label, "The read timed out"),
        (line.set_icon, "circle-alert"),
        (line.set_pad, "table"),
        (line.set_size, "lg"),
    ):
        setter(value)
        QtWidgets.QApplication.processEvents()
    assert line.state == "error"
    assert line.pad == "table"
    assert line.size == "lg"
    assert counts(image(line))


def test_disabled_paints_at_half_opacity(root):
    line = place(root, StateLine(state="error", label="The read was refused"))
    lit = counts(image(line))
    line.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    assert line.disabled_opacity() == 0.5
    assert counts(image(line)) != lit
