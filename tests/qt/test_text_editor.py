"""The text editor: the two forms, the commit, the restore and the blocked states."""
from __future__ import annotations

import pytest
from qtpy import QtCore

from sg_widgets_core.schema import FieldSchema
from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.primitives.input import Input, Textarea
from sg_widgets_qt.widgets.text_editor import TextEditor

from .editors import escape, place, press_enter, themed_root, type_into

FIELD = FieldSchema(
    name="description",
    display_name="Description",
    entity_type="Shot",
    data_type="text",
    editable=True,
    mandatory=False,
    unique=False,
)


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_paints(root):
    editor = place(root, TextEditor(value="Plate delivered.", field=FIELD))
    assert editor.objectName() == "text-editor"
    assert isinstance(editor.control, Input)
    assert editor.control.text() == "Plate delivered."
    assert not editor.grab().isNull()


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_it_stands_on_every_rung_of_the_ladder(root, size):
    editor = place(root, TextEditor(value="A note", size=size))
    assert editor.control.sizeHint().height() == CONTROL_HEIGHT[size]


def test_typing_and_enter_commit_the_stripped_string(root):
    editor = place(root, TextEditor(value="Plate delivered."))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.control, "  padded  ")
    press_enter(editor.control)
    assert seen == ["padded"]
    assert editor.value == "padded"


def test_an_empty_input_commits_null(root):
    editor = place(root, TextEditor(value="Plate delivered."))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.control, "   ")
    press_enter(editor.control)
    assert seen == [None]
    assert editor.value is None


def test_escape_restores_the_stored_value(root):
    editor = place(root, TextEditor(value="Plate delivered."))
    type_into(editor.control, "half typed")
    escape(editor.control)
    assert editor.control.text() == "Plate delivered."
    assert editor.value == "Plate delivered."


def test_a_message_from_the_caller_shows_and_reads_invalid(root):
    editor = place(root, TextEditor(value=None, invalid=True, error="The site refused this value."))
    assert editor.message == "The site refused this value."
    assert editor.reads_invalid is True
    assert editor.control.invalid is True


def test_the_multiline_form_is_a_textarea_that_keeps_enter_for_a_newline(root):
    editor = place(root, TextEditor(value="One.\nTwo.", multiline=True))
    assert isinstance(editor.control, Textarea)
    seen = []
    editor.committed.connect(seen.append)
    editor.control.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    editor.control.setPlainText("One.\nTwo.\nThree.")
    press_enter(editor.control)
    assert seen == []
    editor.control.clearFocus()
    assert editor.value == "One.\nTwo.\nThree."


def test_readonly_drops_the_affordances_and_disabled_is_inert(root):
    readonly = place(root, TextEditor(value="sh010_comp_v001", readonly=True))
    disabled = place(root, TextEditor(value="sh010_comp_v001", disabled=True))
    assert readonly.control.isReadOnly() is True
    assert readonly.isEnabled() is True
    assert disabled.isEnabled() is False
    type_into(readonly.control, "typed")
    press_enter(readonly.control)
    assert readonly.value == "sh010_comp_v001"


def test_a_value_from_outside_lands_in_the_control(root):
    editor = place(root, TextEditor(value="First."))
    editor.set_value("Second.")
    assert editor.control.text() == "Second."
