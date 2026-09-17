"""date-time-editor: pick a day, type a time, and read the zone the trigger is in.

    .venv/bin/python tools/qa.py --page date-time-editor \
        --drive tools/drives/walk/date-time-editor.py

The value is an instant, shown in a zone. The walk presses a day in the grid, types a time and
commits, reads what each half refuses, proves a picked day leaves the popover up because the time
is the other half of the value, and reads the second zone's own reading of the same instant.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, press_enter, retype, set_view, wear  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

from sg_widgets_qt.theme import theme_of  # noqa: E402

WEEKS = 6
APPROVED_AT = "2026-03-04T13:06:07Z"


def day_cell(grid, skip: str = "") -> tuple:
    for week in range(WEEKS):
        for column in range(7):
            box = grid.cell_rect(column, week)
            day = grid.date_at(box.center())
            if day is not None and day.isoformat() != skip:
                return box, day
    return None, None


def press_day(grid, box) -> None:
    QTest.mouseClick(
        grid, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, box.center()
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("date-time-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no date-time-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- the instant, in the zone the row names -----------------------------------------------
    middle = cases["md"]
    editor = middle.editor
    walk.same("md: the demo opens on the stored instant", APPROVED_AT, editor.value)
    walk.same("md: the trigger reads it in the row's zone", "2026-03-04 05:06", editor.trigger.text)
    walk.same("md: the row names its zone", "America/Los_Angeles", editor.zone_name)

    click(editor.trigger)
    wait(400)
    walk.check("md: the trigger opens the popover", editor.is_open, True, editor.is_open)
    walk.same("md: the day half is filled from the value", "2026-03-04", editor.date_input.text())
    walk.same("md: the time half is filled from the value", "05:06", editor.time_input.text())

    # --- a day pressed leaves the popover up, because the time is the other half -----------------
    box, day = day_cell(editor.calendar.grid(), skip=editor.date_input.text())
    press_day(editor.calendar.grid(), box)
    wait(400)
    walk.same("md: the pressed day moves the instant", day.isoformat(), editor.trigger.text.split(" ")[0])
    walk.check("md: a pressed day leaves the popover up", editor.is_open, True, editor.is_open)
    walk.check(
        "md: the readout follows the pick",
        middle.readout.text.strip('"') == editor.value,
        editor.value,
        middle.readout.text,
    )

    # --- a time typed ------------------------------------------------------------------------------
    retype(editor.time_input, "23:45")
    press_enter(editor.time_input)
    wait(400)
    walk.same("md: the typed time reads back on the trigger", "23:45", editor.trigger.text.split(" ")[1])
    walk.check("md: Enter closes the popover", not editor.is_open, False, editor.is_open)
    walk.same("md: nothing was left standing over the page", [], popups())

    # --- what each half refuses ----------------------------------------------------------------------
    held = editor.value
    click(editor.trigger)
    wait(400)
    retype(editor.time_input, "99:99")
    press_enter(editor.time_input)
    wait(300)
    walk.same("md: a time that is not one is refused", held, editor.value)
    walk.same("md: the line names the shape of a time", "Not a time. Use HH:MM.", editor.message)
    walk.check("md: the line is on show", editor.error_line.isVisible(), True, False)

    retype(editor.date_input, "not a day")
    press_enter(editor.date_input)
    wait(300)
    walk.same("md: a day that is not one is refused", held, editor.value)
    walk.same("md: the line names the shape of a day", "Not a date. Use YYYY-MM-DD.", editor.message)

    key(editor.date_input, QtCore.Qt.Key.Key_Escape)
    wait(400)
    walk.same("md: Escape clears the refusal", None, editor.message)
    walk.check("md: Escape closes the popover", not editor.is_open, False, editor.is_open)
    walk.same("md: Escape puts the stored instant back", held, editor.value)

    # --- a second zone reads the same instant differently -----------------------------------------------
    paris = cases["Paris, seconds"]
    walk.same("Paris: the row holds the same instant", APPROVED_AT, paris.editor.value)
    walk.same("Paris: the row names its own zone", "Europe/Paris", paris.editor.zone_name)
    walk.same("Paris: the trigger reads it in Paris, with seconds", "2026-03-04 14:06:07", paris.editor.trigger.text)

    # --- the unset row --------------------------------------------------------------------------------
    unset = cases["unset"]
    empty = unset.editor
    walk.same("unset: the demo opens on nothing", None, empty.value)
    click(empty.trigger)
    wait(400)
    box, day = day_cell(empty.calendar.grid())
    press_day(empty.calendar.grid(), box)
    wait(400)
    walk.check(
        "unset: a picked day fills the field at midnight",
        empty.value == f"{day.isoformat()}T00:00:00Z",
        f"{day.isoformat()}T00:00:00Z",
        empty.value,
    )
    walk.same("unset: the readout follows", f'"{empty.value}"', unset.readout.text)
    key(empty.time_input, QtCore.Qt.Key.Key_Escape)
    wait(400)

    # --- the three marked rows --------------------------------------------------------------------------
    bad = cases["invalid"]
    walk.same("invalid: the line names the reason", "Before the version was delivered.", bad.editor.message)
    walk.check("invalid: the trigger reads invalid", bad.editor.reads_invalid, True, False)

    read = cases["readonly"]
    click(read.editor.trigger)
    wait(300)
    walk.check("readonly: the trigger does not open", not read.editor.is_open, False, read.editor.is_open)

    off = cases["disabled"]
    click(off.editor.trigger)
    wait(300)
    walk.check("disabled: the row is inert", not off.editor.isEnabled(), False, off.editor.isEnabled())
    walk.check("disabled: the trigger does not open", not off.editor.is_open, False, off.editor.is_open)
    walk.same("blocked rows: nothing was left standing over the page", [], popups())

    # --- the view controls -----------------------------------------------------------------------------------
    click(editor.trigger)
    wait(400)
    wear(prefs, wait, theme="dark", settle=350)
    walk.check("header: the open popover stays up while the view moves", editor.is_open, True, editor.is_open)
    walk.check("header: the open popover wears the dark theme", theme_of(editor.calendar).dark, True, False)
    wear(prefs, wait, theme="light", settle=350)
    key(editor.date_input, QtCore.Qt.Key.Key_Escape)
    wait(400)

    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("date-time-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}
        walk.same("header: the editors wear the size step", "lg", rebuilt["md"].editor.size)
        walk.same("header: the ladder rows keep the size they named", "sm", rebuilt["sm"].editor.size)
        target = rebuilt["md"].editor
        click(target.trigger)
        wait(400)
        walk.check("header: the rebuilt trigger still opens", target.is_open, True, target.is_open)
        retype(target.time_input, "09:15")
        press_enter(target.time_input)
        wait(400)
        walk.same("header: the rebuilt popover still commits", "09:15", target.trigger.text.split(" ")[1])
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the popover opens on both halves of the instant, a pressed day leaves it up and a"
        " typed time closes it, each half names what it refuses, the second zone reads the same"
        " instant in its own, and the blocked rows never open"
    )
