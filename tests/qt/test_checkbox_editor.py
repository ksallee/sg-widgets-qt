"""The checkbox editor: two states, no third one, and the two blocked ones."""
from __future__ import annotations

import pytest
from qtpy import QtCore
from qtpy.QtTest import QTest

from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.widgets.checkbox_editor import CheckboxEditor

from .editors import place, themed_root


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_paints(root):
    editor = place(root, CheckboxEditor(value=True))
    assert editor.objectName() == "checkbox-editor"
    assert editor.value is True
    assert editor.switch.checked is True
    assert not editor.grab().isNull()


def test_the_toggle_commits_a_boolean(root):
    editor = place(root, CheckboxEditor(value=False))
    seen = []
    editor.committed.connect(seen.append)
    editor.toggle()
    assert seen == [True]
    assert editor.value is True
    editor.toggle()
    assert seen == [True, False]


def test_space_toggles_the_switch(root):
    editor = place(root, CheckboxEditor(value=False))
    seen = []
    editor.committed.connect(seen.append)
    QTest.keyClick(editor.switch, QtCore.Qt.Key.Key_Space)
    assert seen == [True]


def test_a_value_from_outside_does_not_commit(root):
    editor = place(root, CheckboxEditor(value=False))
    seen = []
    editor.committed.connect(seen.append)
    editor.set_value(True)
    assert seen == []
    assert editor.switch.checked is True


def test_the_two_words_follow_the_state(root):
    editor = place(root, CheckboxEditor(value=False, labels=("Approved", "Not approved")))
    assert editor._label.text == "Not approved"
    editor.toggle()
    assert editor._label.text == "Approved"


def test_a_message_from_the_caller_clears_when_the_field_is_answered(root):
    editor = place(root, CheckboxEditor(value=False, error="The site refused this value."))
    cleared = []
    editor.error_changed.connect(cleared.append)
    assert editor.message == "The site refused this value."
    editor.toggle()
    assert editor.message is None
    assert cleared == [None]


def test_readonly_drops_the_affordances_and_disabled_is_inert(root):
    readonly = place(root, CheckboxEditor(value=True, readonly=True))
    disabled = place(root, CheckboxEditor(value=False, disabled=True))
    assert readonly.switch.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
    assert readonly.switch.isEnabled() is True
    assert disabled.isEnabled() is False
    readonly.toggle()
    assert readonly.value is True
    assert readonly.switch.checked is True


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_the_row_stands_on_every_rung_of_the_ladder(root, size):
    editor = place(root, CheckboxEditor(value=True, size=size))
    assert editor._row.minimumHeight() == CONTROL_HEIGHT[size]
