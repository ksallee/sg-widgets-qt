"""The number editor: the six data types, the steppers, the keyboard and the blocked states."""
from __future__ import annotations

import pytest
from qtpy import QtCore
from qtpy.QtTest import QTest

from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.widgets.number_editor import INLINE_WIDTH, NumberEditor

from .editors import escape, place, press_enter, themed_root, type_into


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_paints(root):
    editor = place(root, NumberEditor(value=1001))
    assert editor.objectName() == "number-editor"
    assert editor.input.text() == "1,001"
    assert not editor.grab().isNull()


@pytest.mark.parametrize(
    ("data_type", "value", "draft"),
    [
        ("number", 1001, "1,001"),
        ("float", "1.777778", "1.777778"),
        ("percent", 50, "50"),
        ("currency", 12500, "12,500"),
        ("duration", 480, "8:00"),
        ("timecode", 3600000, "01:00:00"),
    ],
)
def test_every_data_type_puts_its_stored_value_back_in_the_input(root, data_type, value, draft):
    editor = place(root, NumberEditor(value=value, data_type=data_type))
    assert editor.input.text() == draft


def test_a_duration_unit_form_commits_the_minutes_it_stores(root):
    editor = place(root, NumberEditor(value=480, data_type="duration", hint=True))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, "1h 30m")
    press_enter(editor.input)
    assert seen == [90]
    assert editor.value == 90


def test_a_float_commits_the_decimal_string_the_api_takes(root):
    editor = place(root, NumberEditor(value="1.777778", data_type="float", precision=2))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, "2")
    press_enter(editor.input)
    assert seen == ["2.0"]


def test_a_decimal_on_a_whole_number_type_is_refused(root):
    editor = place(root, NumberEditor(value=1001, data_type="number"))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, "3.7")
    press_enter(editor.input)
    assert seen == []
    assert editor.message == "Whole numbers only."
    assert editor.reads_invalid is True
    assert editor.value == 1001


def test_escape_restores_the_stored_value(root):
    editor = place(root, NumberEditor(value=1001))
    type_into(editor.input, "banana")
    escape(editor.input)
    assert editor.input.text() == "1,001"
    assert editor.message is None


def test_the_arrows_step_and_shift_steps_ten_times(root):
    editor = place(root, NumberEditor(value=50, data_type="percent", min=0, max=100))
    QTest.keyClick(editor.input, QtCore.Qt.Key.Key_Up)
    assert editor.value == 51
    QTest.keyClick(
        editor.input, QtCore.Qt.Key.Key_Down, QtCore.Qt.KeyboardModifier.ShiftModifier
    )
    assert editor.value == 41
    QTest.keyClick(editor.input, QtCore.Qt.Key.Key_PageUp)
    assert editor.value == 100


def test_a_step_reads_what_is_in_the_input(root):
    editor = place(root, NumberEditor(value=480, data_type="duration"))
    type_into(editor.input, "1h 30m")
    QTest.keyClick(editor.input, QtCore.Qt.Key.Key_Up)
    assert editor.value == 105


def test_a_stepper_goes_inert_at_the_bound_it_would_cross(root):
    editor = place(root, NumberEditor(value=100, data_type="percent", min=0, max=100))
    assert editor._increment.isEnabled() is False
    assert editor._decrement.isEnabled() is True


def test_readonly_drops_the_steppers_and_disabled_is_inert(root):
    readonly = place(root, NumberEditor(value=50, readonly=True))
    disabled = place(root, NumberEditor(value=50, disabled=True))
    assert readonly.input.isReadOnly() is True
    assert readonly._increment.isVisible() is False
    assert readonly._decrement.isVisible() is False
    assert disabled.isEnabled() is False
    QTest.keyClick(readonly.input, QtCore.Qt.Key.Key_Up)
    assert readonly.value == 50


def test_the_row_form_takes_the_width_its_type_needs(root):
    editor = place(root, NumberEditor(value=75, data_type="timecode", inline=True, size="sm"))
    assert editor.inline is True
    assert editor._group.width() == INLINE_WIDTH["timecode"]
    assert editor._group.sizeHint().height() == CONTROL_HEIGHT["sm"]
