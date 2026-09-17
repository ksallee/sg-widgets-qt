"""The session every leaf editor runs on, the box it stands in, the error line and the calendar day.

The port of the upstream value-editor, field-error and editor-calendar behaviour.
"""
from __future__ import annotations

import datetime

import pytest
from qtpy import QtWidgets

from sg_widgets_core.edit import ParseError, ParseValue
from sg_widgets_qt.primitives.input import Input
from sg_widgets_qt.showcase.demos.value_editor import Range, RangeEditor, parse_range
from sg_widgets_qt.widgets.editor_calendar import from_calendar_date, to_calendar_date
from sg_widgets_qt.widgets.field_error import FieldError
from sg_widgets_qt.widgets.value_editor import EditorNote, ValueEditor, ValueSession

from .editors import escape, place, press_enter, themed_root, type_into


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def session_for(value: str | None = None, **options) -> ValueSession:
    return ValueSession(
        value,
        format=lambda stored: "" if stored is None else str(stored),
        parse=lambda draft: ParseValue(draft.strip() or None)
        if draft.strip() != "no"
        else ParseError("No."),
        **options,
    )


# --- the box -----------------------------------------------------------------------------------


def test_the_box_carries_the_slot_name_and_the_size(root):
    box = ValueEditor("range-editor", size="lg")
    box.add_control(Input(placeholder="1001-1120", size="lg"))
    place(root, box)
    assert box.objectName() == "range-editor"
    assert box.size == "lg"
    assert not box.grab().isNull()


def test_the_box_takes_the_row_form(root):
    box = place(root, ValueEditor("range-editor", inline=True))
    assert box.inline is True
    box.set_inline(False)
    assert box.inline is False


# --- the session -------------------------------------------------------------------------------


def test_a_commit_emits_the_parsed_value(qtbot):
    session = session_for(None)
    seen = []
    session.committed.connect(seen.append)
    session.set_draft("  padded  ")
    assert session.commit() is True
    assert seen == ["padded"]
    assert session.value == "padded"


def test_a_commit_that_changes_nothing_emits_nothing(qtbot):
    session = session_for("kept")
    seen = []
    session.committed.connect(seen.append)
    assert session.commit() is True
    assert seen == []


def test_a_refused_parse_reports_the_message_and_reads_invalid(qtbot):
    session = session_for("kept")
    messages = []
    session.error_changed.connect(messages.append)
    session.set_draft("no")
    assert session.commit() is False
    assert session.message == "No."
    assert session.invalid is True
    assert messages[-1] == "No."
    assert session.value == "kept"


def test_escape_restores_the_stored_value_and_drops_the_message(qtbot):
    session = session_for("kept")
    session.set_draft("no")
    session.commit()
    session.reset()
    assert session.draft == "kept"
    assert session.message is None
    assert session.invalid is False


def test_apply_takes_a_value_that_needs_no_parse(qtbot):
    session = session_for("kept")
    seen = []
    session.committed.connect(seen.append)
    session.apply("picked")
    assert seen == ["picked"]
    assert session.draft == "picked"


def test_same_says_what_differs(qtbot):
    session = ValueSession(
        Range(1001, 1120),
        format=lambda value: "" if value is None else f"{value.first}-{value.last}",
        parse=parse_range,
        same=lambda a, b: a is not None and b is not None and a.first == b.first and a.last == b.last,
    )
    seen = []
    session.committed.connect(seen.append)
    session.set_draft("1001-1120")
    session.commit()
    assert seen == []
    session.set_draft("1001-1200")
    session.commit()
    assert seen and seen[0].last == 1200


def test_a_message_from_the_caller_stands_in_for_the_parse_error(qtbot):
    session = session_for("kept", error="The site refused this value.")
    session.set_draft("no")
    session.commit()
    assert session.message == "The site refused this value."


def test_an_incoming_value_waits_while_the_control_has_focus(qtbot):
    session = session_for("kept")
    session.focus_in()
    session.set_draft("typing")
    session.set_value("elsewhere")
    assert session.draft == "typing"
    session.focus_out()
    session.set_value("landed")
    assert session.draft == "landed"


def test_enter_is_not_a_commit_where_a_newline_is_what_it_means(root, qtbot):
    session = session_for("kept", commit_on_enter=False)
    field = place(root, Input())
    session.bind(field)
    type_into(field, "typed")
    press_enter(field)
    assert session.value == "kept"


def test_a_bound_field_types_into_the_draft_and_commits_on_enter(root, qtbot):
    session = session_for("kept")
    field = place(root, Input())
    session.bind(field)
    type_into(field, "typed")
    assert session.draft == "typed"
    press_enter(field)
    assert session.value == "typed"


def test_a_bound_field_restores_on_escape(root, qtbot):
    session = session_for("kept")
    field = place(root, Input())
    session.bind(field)
    type_into(field, "typed")
    escape(field)
    assert field.text() == "kept"


def test_losing_focus_commits(root, qtbot):
    session = session_for("kept")
    field = place(root, Input())
    session.bind(field)
    type_into(field, "left")
    field.clearFocus()
    QtWidgets.QApplication.processEvents()
    assert session.value == "left"


# --- the error line ----------------------------------------------------------------------------


def test_the_error_line_shows_a_message_and_takes_no_room_without_one(root):
    line = place(root, FieldError("Not a date. Use YYYY-MM-DD."))
    assert line.message == "Not a date. Use YYYY-MM-DD."
    assert line.isVisible()
    line.set_message(None)
    assert line.message is None
    assert not line.isVisible()


def test_the_error_line_hands_the_message_to_the_callers_own(root):
    made = []

    def renderer(message: str) -> QtWidgets.QWidget:
        made.append(message)
        return EditorNote(message)

    line = place(root, FieldError("Refused.", renderer))
    assert made == ["Refused."]
    assert not line.grab().isNull()


# --- the calendar day --------------------------------------------------------------------------


def test_a_day_crosses_to_the_calendar_and_back():
    assert to_calendar_date("2026-09-02") == datetime.date(2026, 9, 2)
    assert from_calendar_date(datetime.date(2026, 9, 2)) == "2026-09-02"


@pytest.mark.parametrize("value", [None, "", "tomorrow", "2026-9-8", "2026-02-30"])
def test_a_string_that_is_not_a_day_reads_as_nothing_picked(value):
    assert to_calendar_date(value) is None


def test_nothing_picked_reads_back_as_the_empty_string():
    assert from_calendar_date(None) == ""


# --- an editor of the caller's own ---------------------------------------------------------------


def test_an_editor_built_on_the_base_commits_its_own_shape(root, qtbot):
    editor = place(root, RangeEditor(value=Range(1001, 1120)))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.input, "1001-1200")
    press_enter(editor.input)
    assert isinstance(seen[0], Range)
    assert (seen[0].first, seen[0].last) == (1001, 1200)


def test_an_editor_built_on_the_base_shows_its_own_refusal(root, qtbot):
    editor = place(root, RangeEditor(value=Range(1001, 1120)))
    type_into(editor.input, "1120-1001")
    press_enter(editor.input)
    assert editor.message == "The last frame comes before the first."
    assert editor.reads_invalid is True
    assert editor.value.last == 1120
