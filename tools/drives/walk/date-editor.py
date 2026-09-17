"""date-editor: open the calendar, pick a day with the mouse, and type one.

    .venv/bin/python tools/qa.py --page date-editor --drive tools/drives/walk/date-editor.py

The trigger opens a popover holding a typed day over a month grid. The walk presses a day in the
grid, types a day and presses Enter, types a day that is not one and reads the line, restores with
Escape, fills the unset row, and proves the read-only and the inert rows never open.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, press_enter, retype, set_view, wear  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

from sg_widgets_qt.theme import theme_of  # noqa: E402

#: How many weeks a month grid draws.
WEEKS = 6


def day_cell(grid, skip: str = "") -> tuple:
    """A cell of the grid holding a day, and the day it holds. `skip` is a day to walk past."""
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
    demo = find("date-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no date-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- the day picked with the mouse -------------------------------------------------------
    middle = cases["md"]
    editor = middle.editor
    walk.same("md: the demo opens on the stored day", "2026-09-02", editor.value)
    walk.same("md: the trigger reads the stored day", "2026-09-02", editor.trigger.text)

    click(editor.trigger)
    wait(400)
    walk.check("md: the trigger opens the calendar", editor.is_open, True, editor.is_open)
    walk.check("md: the calendar stands on a window of its own", popups() != [], "a popover", popups())

    box, day = day_cell(editor.calendar.grid(), skip=editor.value)
    walk.check("md: the grid offers a day to press", box is not None, "a day", day)
    press_day(editor.calendar.grid(), box)
    wait(400)
    walk.same("md: the pressed day is stored", day.isoformat(), editor.value)
    walk.same("md: the trigger follows the pick", day.isoformat(), editor.trigger.text)
    walk.same("md: the readout follows the pick", f'"{day.isoformat()}"', middle.readout.text)
    walk.check("md: a picked day closes the calendar", not editor.is_open, False, editor.is_open)
    walk.same("md: nothing was left standing over the page", [], popups())

    # --- the day typed ------------------------------------------------------------------------
    click(editor.trigger)
    wait(400)
    retype(editor.day_input, "2026-12-25")
    press_enter(editor.day_input)
    wait(400)
    walk.same("md: a typed day commits on Enter", "2026-12-25", editor.value)
    walk.same("md: the trigger follows the typed day", "2026-12-25", editor.trigger.text)
    walk.check("md: Enter closes the calendar", not editor.is_open, False, editor.is_open)

    # --- a day that is not one -----------------------------------------------------------------
    click(editor.trigger)
    wait(400)
    retype(editor.day_input, "31/02/2026")
    press_enter(editor.day_input)
    wait(300)
    walk.same("md: a day in another shape is refused", "2026-12-25", editor.value)
    walk.same("md: the line names the shape", "Not a date. Use YYYY-MM-DD.", editor.message)
    walk.check("md: the line is on show", editor.error_line.isVisible(), True, False)
    walk.check("md: the refusal leaves the calendar up", editor.is_open, True, editor.is_open)

    key(editor.day_input, QtCore.Qt.Key.Key_Escape)
    wait(400)
    walk.same("md: Escape clears the refusal", None, editor.message)
    walk.same("md: Escape puts the stored day back", "2026-12-25", editor.day_input.text())
    walk.check("md: Escape closes the calendar", not editor.is_open, False, editor.is_open)
    walk.same("md: nothing was left standing over the page", [], popups())

    # --- the unset row ---------------------------------------------------------------------------
    unset = cases["unset"]
    empty = unset.editor
    walk.same("unset: the demo opens on nothing", None, empty.value)
    walk.same("unset: the trigger shows the placeholder", "", empty.trigger.text)
    click(empty.trigger)
    wait(400)
    box, day = day_cell(empty.calendar.grid())
    press_day(empty.calendar.grid(), box)
    wait(400)
    walk.same("unset: a picked day fills the field", day.isoformat(), empty.value)
    walk.same("unset: the readout follows", f'"{day.isoformat()}"', unset.readout.text)

    # --- the three marked rows ----------------------------------------------------------------------
    bad = cases["invalid"]
    walk.same("invalid: the line names the reason", "Outside the shoot window.", bad.editor.message)
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

    # --- the view controls ----------------------------------------------------------------------------
    click(editor.trigger)
    wait(400)
    wear(prefs, wait, theme="dark", settle=350)
    walk.check("header: the open calendar stays up while the view moves", editor.is_open, True, editor.is_open)
    walk.check("header: the open calendar wears the dark theme", theme_of(editor.calendar).dark, True, False)
    wear(prefs, wait, theme="light", settle=350)
    key(editor.day_input, QtCore.Qt.Key.Key_Escape)
    wait(400)

    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("date-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}
        walk.same("header: the editors wear the size step", "lg", rebuilt["md"].editor.size)
        walk.same("header: the ladder rows keep the size they named", "sm", rebuilt["sm"].editor.size)
        target = rebuilt["md"].editor
        click(target.trigger)
        wait(400)
        walk.check("header: the rebuilt trigger still opens", target.is_open, True, target.is_open)
        box, day = day_cell(target.calendar.grid(), skip=target.value)
        press_day(target.calendar.grid(), box)
        wait(400)
        walk.same("header: the rebuilt calendar still picks", day.isoformat(), target.value)
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the trigger opens the calendar, a pressed day and a typed day both commit and close"
        " it, a day in another shape is named under the control, Escape restores and closes, the"
        " blocked rows never open, and the open calendar follows the view"
    )
