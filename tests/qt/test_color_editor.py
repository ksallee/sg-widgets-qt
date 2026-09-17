"""The colour editor: the triple, the hex code it converts, the token, and the picker."""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtTest import QTest

from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.widgets.color_editor import (
    SENTINEL_NOTE,
    SWATCH_SIZE,
    ColorEditor,
    ColorPicker,
)

from .editors import escape, place, press_enter, themed_root, type_into


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_paints(root):
    editor = place(root, ColorEditor(value="253,94,99"))
    assert editor.objectName() == "color-editor"
    assert editor.input.text() == "253,94,99"
    assert editor.preview.name() == "#fd5e63"
    assert not editor.grab().isNull()


@pytest.mark.parametrize(
    ("typed", "emitted"),
    [
        ("255, 128, 0", "255,128,0"),
        ("#ff8000", "255,128,0"),
        ("ff8000", "255,128,0"),
        ("#f80", "255,136,0"),
        ("pipeline_step", "pipeline_step"),
    ],
)
def test_every_accepted_spelling_commits_the_stored_form(root, typed, emitted):
    editor = place(root, ColorEditor(value="0,126,174"))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, typed)
    press_enter(editor.input)
    assert seen == [emitted]


def test_a_channel_over_255_is_refused(root):
    editor = place(root, ColorEditor(value="0,126,174"))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, "300,0,0")
    press_enter(editor.input)
    assert seen == []
    assert editor.message == "Each channel runs 0 to 255."
    assert editor.reads_invalid is True
    assert editor.value == "0,126,174"


def test_escape_restores_the_stored_value(root):
    editor = place(root, ColorEditor(value="0,126,174"))
    type_into(editor.input, "300,0,0")
    press_enter(editor.input)
    escape(editor.input)
    assert editor.input.text() == "0,126,174"
    assert editor.message is None


def test_the_swatch_follows_the_draft(root):
    editor = place(root, ColorEditor(value="0,126,174"))
    type_into(editor.input, "#ff8000")
    assert editor.swatch.color.name() == "#ff8000"
    assert editor.value == "0,126,174"


def test_the_token_is_explained_under_the_control(root):
    editor = place(root, ColorEditor(value="pipeline_step"))
    assert editor.sentinel is True
    assert editor._note.text == SENTINEL_NOTE
    assert editor.preview is None
    editor.set_hint(False)
    assert editor._note.text == ""


def test_an_empty_input_clears_the_field(root):
    editor = place(root, ColorEditor(value="0,126,174"))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, "")
    press_enter(editor.input)
    assert seen == [None]


def test_the_picker_answers_with_the_decimal_triple(root):
    picker = place(root, ColorPicker(QtGui.QColor(255, 128, 0)))
    seen = []
    picker.picked.connect(seen.append)
    QTest.keyClick(picker, QtCore.Qt.Key.Key_Left)
    assert seen and len(seen[0].split(",")) == 3
    assert not picker.grab().isNull()


def test_a_picked_colour_commits_the_triple(root):
    editor = place(root, ColorEditor(value="0,126,174"))
    seen = []
    editor.committed.connect(seen.append)
    editor.picker.set_color(QtGui.QColor(255, 128, 0))
    editor.picker.picked.emit("255,128,0")
    assert seen == ["255,128,0"]
    assert editor.input.text() == "255,128,0"


def test_readonly_never_opens_the_picker_and_disabled_is_inert(root):
    readonly = place(root, ColorEditor(value="45,45,45", readonly=True))
    disabled = place(root, ColorEditor(value="45,45,45", disabled=True))
    readonly.set_open(True)
    disabled.set_open(True)
    assert readonly.is_open is False
    assert disabled.is_open is False
    assert readonly.input.isReadOnly() is True
    assert readonly.swatch.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
    assert disabled.isEnabled() is False


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_the_swatch_is_the_square_the_upstream_ladder_names(root, size):
    # `SWATCH` of `color-editor.tsx` is `size-8`, `size-9`, `size-10`: one step over the control
    # ladder the input beside it stands on.
    editor = place(root, ColorEditor(value="253,94,99", size=size))
    assert editor.swatch.sizeHint().height() == SWATCH_SIZE[size]
    assert editor.swatch.sizeHint().width() == SWATCH_SIZE[size]
    assert SWATCH_SIZE[size] > CONTROL_HEIGHT[size]


def test_escape_inside_the_picker_closes_it(root, qtbot):
    editor = place(root, ColorEditor(value="0,126,174"))
    editor.set_open(True)
    assert editor.is_open is True
    QTest.keyClick(editor.picker, QtCore.Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: editor.is_open is False, timeout=2000)
    assert editor.is_open is False
    assert editor.value == "0,126,174", "closing the picker is not a pick"


def test_the_swatch_wears_no_hover_wash(root):
    # `color-editor.tsx` puts no hover class on the swatch: the colour it shows is the value, and
    # a wash over it would be a wash over the value.
    editor = place(root, ColorEditor(value="253,94,99"))
    swatch = editor.swatch
    before = swatch.grab().toImage().pixelColor(swatch.width() // 2, swatch.height() // 2)
    swatch.set_hovered(True)
    QtWidgets.QApplication.processEvents()
    after = swatch.grab().toImage().pixelColor(swatch.width() // 2, swatch.height() // 2)
    assert after == before
