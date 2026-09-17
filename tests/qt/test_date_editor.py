"""The date editor: the trigger, the typed day, the calendar and the blocked states."""
from __future__ import annotations

import datetime

import pytest

from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.widgets.date_editor import DateEditor

from .editors import escape, place, press_enter, themed_root, type_into


@pytest.fixture
def root(qtbot):
    return themed_root(qtbot)


def test_it_constructs_and_paints(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    assert editor.objectName() == "date-editor"
    assert editor.trigger.text == "2026-09-02"
    assert not editor.grab().isNull()


def test_an_unset_field_shows_the_placeholder(root):
    editor = place(root, DateEditor(value=None))
    assert editor.trigger.text == ""
    assert editor.trigger.placeholder == "YYYY-MM-DD"
    assert not editor.grab().isNull()


def test_the_typed_day_commits_and_closes_the_popover(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    seen = []
    editor.committed.connect(seen.append)
    editor.set_open(True)
    assert editor.is_open is True
    type_into(editor.day_input, "2026-10-01")
    press_enter(editor.day_input)
    assert seen == ["2026-10-01"]
    assert editor.is_open is False
    assert editor.trigger.text == "2026-10-01"


def test_a_day_that_does_not_exist_is_refused(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.day_input, "2026-02-30")
    press_enter(editor.day_input)
    assert seen == []
    assert editor.message == "No such day."
    assert editor.reads_invalid is True
    assert editor.value == "2026-09-02"


def test_escape_restores_the_stored_day(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    editor.set_open(True)
    type_into(editor.day_input, "2026-10-01")
    escape(editor.day_input)
    assert editor.day_input.text() == "2026-09-02"
    assert editor.value == "2026-09-02"
    assert editor.is_open is False


def test_a_day_picked_in_the_calendar_commits_it(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    seen = []
    editor.committed.connect(seen.append)
    editor.calendar.grid().picked.emit(datetime.date(2026, 9, 11))
    assert seen == ["2026-09-11"]
    assert editor.trigger.text == "2026-09-11"


def test_an_empty_day_clears_the_field(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    seen = []
    editor.committed.connect(seen.append)
    type_into(editor.day_input, "")
    press_enter(editor.day_input)
    assert seen == [None]


def test_readonly_never_opens_and_disabled_is_inert(root):
    readonly = place(root, DateEditor(value="2026-09-02", readonly=True))
    disabled = place(root, DateEditor(value="2026-09-02", disabled=True))
    readonly.set_open(True)
    disabled.set_open(True)
    assert readonly.is_open is False
    assert disabled.is_open is False
    assert readonly.trigger.readonly is True
    assert disabled.isEnabled() is False


def test_the_open_state_is_reported(root):
    editor = place(root, DateEditor(value="2026-09-02"))
    seen = []
    editor.open_changed.connect(seen.append)
    editor.toggle()
    assert seen == [True]


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_the_trigger_stands_on_every_rung_of_the_ladder(root, size):
    editor = place(root, DateEditor(value="2026-09-02", size=size))
    assert editor.trigger.sizeHint().height() == CONTROL_HEIGHT[size]


@pytest.mark.parametrize("size", list(CONTROL_HEIGHT))
def test_the_trigger_paints_the_whole_rung_of_the_ladder(root, size):
    # The trigger is the `outline` button of `button.tsx`: its border rides the widget's own rim,
    # so the box a reader sees is the ladder height, not four pixels under it.
    editor = place(root, DateEditor(value="2026-09-02", size=size))
    trigger = editor.trigger
    assert trigger.sizeHint().height() == CONTROL_HEIGHT[size]
    trigger.resize(240, CONTROL_HEIGHT[size])
    image = trigger.grab().toImage()
    middle = trigger.width() // 2
    page = image.pixelColor(middle, CONTROL_HEIGHT[size] // 2)
    top = image.pixelColor(middle, 0)
    assert top != page, "the border stands on the widget's first row"


def test_the_popover_takes_the_caret(root, qtbot):
    # `initialFocus={dayInput}` upstream: the typed day is what the caret lands on, which means
    # the surface it stands on is a window that accepts focus.
    editor = place(root, DateEditor(value="2026-09-02"))
    editor.set_open(True)
    qtbot.waitUntil(lambda: editor.day_input.hasFocus(), timeout=2000)
    assert editor.day_input.hasFocus()
    editor.set_open(False)
