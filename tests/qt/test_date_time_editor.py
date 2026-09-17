"""The date-time editor: the two halves, the zone, and the blocked states."""
from __future__ import annotations

import datetime

import pytest

from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.widgets.date_time_editor import DateTimeEditor

from .editors import escape, place, press_enter, themed_root, type_into

ZONE = "America/Los_Angeles"
STORED = "2026-03-04T13:06:07Z"


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_shows_the_instant_in_the_zone(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    assert editor.objectName() == "date-time-editor"
    assert editor.label == "2026-03-04 05:06"
    assert editor.date_input.text() == "2026-03-04"
    assert editor.time_input.text() == "05:06"
    assert not editor.grab().isNull()


def test_the_zone_is_named_under_the_trigger(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    assert editor.zone_name == ZONE
    assert editor._zone_line.text == f"Local time in {ZONE}, stored as UTC."
    editor.set_hint(False)
    assert editor._zone_line.text == ""


def test_a_typed_wall_clock_time_commits_the_utc_instant(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.time_input, "06:30")
    press_enter(editor.time_input)
    assert seen == ["2026-03-04T14:30:00Z"]
    assert editor.label == "2026-03-04 06:30"


def test_seconds_are_kept_where_the_caller_asks_for_them(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone="Europe/Paris", show_seconds=True))
    assert editor.time_input.text() == "14:06:07"
    assert editor.label == "2026-03-04 14:06:07"


def test_a_time_with_no_date_is_refused(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.date_input, "")
    press_enter(editor.date_input)
    assert seen == []
    assert editor.message == "A time needs a date."
    assert editor.reads_invalid is True


def test_escape_restores_the_stored_instant(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    editor.set_open(True)
    type_into(editor.time_input, "23:59")
    escape(editor.time_input)
    assert editor.time_input.text() == "05:06"
    assert editor.value == STORED
    assert editor.is_open is False


def test_a_picked_day_leaves_the_popover_open(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    seen = []
    editor.committed.connect(seen.append)
    editor.set_open(True)
    editor.calendar.grid().picked.emit(datetime.date(2026, 3, 5))
    assert seen == ["2026-03-05T13:06:00Z"]
    assert editor.is_open is True


def test_both_halves_empty_clear_the_field(root):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.date_input, "")
    type_into(editor.time_input, "")
    press_enter(editor.time_input)
    assert seen == [None]


def test_readonly_never_opens_and_disabled_is_inert(root):
    readonly = place(root, DateTimeEditor(value=STORED, time_zone=ZONE, readonly=True))
    disabled = place(root, DateTimeEditor(value=STORED, time_zone=ZONE, disabled=True))
    readonly.set_open(True)
    disabled.set_open(True)
    assert readonly.is_open is False
    assert disabled.is_open is False
    assert readonly.date_input.isReadOnly() is True
    assert disabled.isEnabled() is False


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_the_trigger_stands_on_every_rung_of_the_ladder(root, size):
    editor = place(root, DateTimeEditor(value=STORED, time_zone=ZONE, size=size))
    assert editor.trigger.sizeHint().height() == CONTROL_HEIGHT[size]
