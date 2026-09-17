"""number-editor: step every numeric type with the arrows, the steppers and a drag.

    .venv/bin/python tools/qa.py --page number-editor --drive tools/drives/walk/number-editor.py

One control covers six data types, so the walk does to each row what its name invites: the arrow
keys and the pair of steppers on the whole number, a tenth on the float, the two ends of the
percent's range and a value past it, the symbol on the currency, the minutes the duration hint
names, a drag across the scrub name, a frame of timecode, and the small pair inside the row form.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, press_enter, retype, set_view  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

#: How far the drag across the scrub name travels, in pixels.
SCRUB_TRAVEL = 36


def scrub(area, wait) -> None:
    """Drag rightwards across the name over a control, which is what a scrub is."""
    middle = area.height() // 2
    QTest.mousePress(
        area,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(0, middle),
    )
    for step in range(4, SCRUB_TRAVEL + 1, 4):
        QTest.mouseMove(area, QtCore.QPoint(step, middle))
        wait(10)
    QTest.mouseRelease(
        area,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(SCRUB_TRAVEL, middle),
    )
    wait(150)


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("number-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no number-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- a whole number: the arrows, the steppers and a typed value -----------------------
    whole = cases["number"]
    editor = whole.editor
    walk.same("number: the demo opens on the stored count", 1001, editor.value)
    editor.input.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    key(editor.input, QtCore.Qt.Key.Key_Up)
    wait(120)
    walk.same("number: the up arrow steps by one", 1002, editor.value)
    walk.same("number: the readout follows the step", "1002", whole.readout.text)
    key(editor.input, QtCore.Qt.Key.Key_Down)
    wait(120)
    walk.same("number: the down arrow steps back", 1001, editor.value)
    key(editor.input, QtCore.Qt.Key.Key_Up, QtCore.Qt.KeyboardModifier.ShiftModifier)
    wait(120)
    walk.same("number: Shift takes ten steps at once", 1011, editor.value)
    key(editor.input, QtCore.Qt.Key.Key_PageDown)
    wait(120)
    walk.same("number: Page Down takes a hundred", 911, editor.value)

    click(editor._increment)  # noqa: SLF001
    wait(120)
    walk.same("number: the plus stepper steps up", 912, editor.value)
    click(editor._decrement)  # noqa: SLF001
    wait(120)
    walk.same("number: the minus stepper steps back", 911, editor.value)

    retype(editor.input, "42")
    press_enter(editor.input)
    wait(150)
    walk.same("number: a typed value commits on Enter", 42, editor.value)

    retype(editor.input, "not a number")
    press_enter(editor.input)
    wait(200)
    walk.same("number: a shapeless draft is refused", 42, editor.value)
    walk.same("number: the line names the reason", "Not a number.", editor.message)
    walk.check("number: the line is on show", editor.error_line.isVisible(), True, False)
    key(editor.input, QtCore.Qt.Key.Key_Escape)
    wait(150)
    walk.same("number: Escape clears the refusal", None, editor.message)
    walk.same("number: Escape puts the stored number back", "42", editor.input.text())

    # --- a float: the step is a tenth and the draft is rounded to the precision -------------
    decimal = cases["float, step 0.1"]
    walk.same("float: the draft is rounded to two decimals", "1.78", decimal.editor.input.text())
    decimal.editor.input.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    key(decimal.editor.input, QtCore.Qt.Key.Key_Up)
    wait(120)
    walk.same("float: the step is a tenth", "1.88", decimal.editor.value)
    walk.same("float: the readout follows", '"1.88"', decimal.readout.text)

    # --- a percent: the two ends of the range, and a value past it --------------------------
    percent = cases["percent, 0 to 100"]
    fill = percent.editor
    retype(fill.input, "100")
    press_enter(fill.input)
    wait(150)
    walk.same("percent: the top of the range commits", 100, fill.value)
    walk.check(
        "percent: the plus stepper goes inert at the top",
        not fill._increment.isEnabled(),  # noqa: SLF001
        False,
        fill._increment.isEnabled(),  # noqa: SLF001
    )
    retype(fill.input, "0")
    press_enter(fill.input)
    wait(150)
    walk.check(
        "percent: the minus stepper goes inert at the bottom",
        not fill._decrement.isEnabled(),  # noqa: SLF001
        False,
        fill._decrement.isEnabled(),  # noqa: SLF001
    )
    retype(fill.input, "250")
    press_enter(fill.input)
    wait(200)
    walk.same("percent: a value past the range is refused", 0, fill.value)
    walk.same("percent: the line names the range", "Out of range: 0 to 100.", fill.message)
    key(fill.input, QtCore.Qt.Key.Key_Escape)
    wait(150)

    # --- a currency: the symbol stands before the value --------------------------------------
    money = cases["currency"]
    walk.check(
        "currency: the symbol stands before the value",
        money.editor._prefix.isVisible(),  # noqa: SLF001
        True,
        False,
    )
    click(money.editor._increment)  # noqa: SLF001
    wait(120)
    walk.same("currency: the stepper steps by one", 12501, money.editor.value)
    walk.same("currency: the draft carries its grouping", "12,501.00", money.editor.input.text())

    # --- a duration: the hint names the minutes that will be written --------------------------
    span = cases["duration, step 15m"]
    walk.same("duration: the hint opens on the stored minutes", "480 minutes", span.editor._hint_line.text)  # noqa: SLF001
    retype(span.editor.input, "1h 30m")
    wait(150)
    walk.same("duration: the hint follows the draft", "90 minutes", span.editor._hint_line.text)  # noqa: SLF001
    press_enter(span.editor.input)
    wait(150)
    walk.same("duration: an hour and a half commits as minutes", 90, span.editor.value)
    walk.same("duration: the draft reads back as hours and minutes", "1:30", span.editor.input.text())
    click(span.editor._increment)  # noqa: SLF001
    wait(120)
    walk.same("duration: the step is a quarter of an hour", 105, span.editor.value)

    # --- a duration with a scrub: the name over it is dragged across ---------------------------
    logged = cases["duration, 6h day, scrub"]
    area = logged.editor._scrub_area  # noqa: SLF001
    walk.check("scrub: the control is named", area.isVisible(), True, area.isVisible())
    held = logged.editor.value
    scrub(area, wait)
    walk.check(
        "scrub: a drag across the name moves the value",
        logged.editor.value > held,
        f"> {held}",
        logged.editor.value,
    )
    walk.same(
        "scrub: the readout follows the drag",
        str(logged.editor.value),
        logged.readout.text,
    )

    # --- a timecode: one step is one frame -----------------------------------------------------
    code = cases["timecode, 23.976"]
    walk.same("timecode: the draft reads as frames", "01:00:00:00", code.editor.input.text())
    click(code.editor._increment)  # noqa: SLF001
    wait(120)
    walk.same("timecode: the step is one frame", "01:00:00:01", code.editor.input.text())
    retype(code.editor.input, "00:00:10:00")
    press_enter(code.editor.input)
    wait(150)
    walk.same("timecode: ten seconds commits as milliseconds", 10000, code.editor.value)

    # --- the row form: the small pair sits inside the input --------------------------------------
    row = cases["inline, size sm"]
    walk.check("inline: the pair sits inside the input", row.editor._inline_steppers.isVisible(), True, False)  # noqa: SLF001
    walk.check("inline: the outer pair is not drawn", not row.editor._increment.isVisible(), False, True)  # noqa: SLF001
    click(row.editor._inline_up)  # noqa: SLF001
    wait(120)
    walk.same("inline: the small stepper steps up", 76, row.editor.value)

    # --- the view controls ------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("number-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}
        walk.same("header: the controls wear the size step", "lg", rebuilt["number"].editor.size)
        walk.same("header: the row form keeps the size it named", "sm", rebuilt["inline, size sm"].editor.size)
        target = rebuilt["number"].editor
        click(target._increment)  # noqa: SLF001
        wait(150)
        walk.check(
            "header: the rebuilt stepper still steps",
            target.value == 1002,
            1002,
            target.value,
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS every numeric type steps from the arrows, the steppers and the drag, a typed value"
        " commits, a value out of range and a shapeless one are named under the control, the"
        " duration hint follows the draft, and the view controls are followed"
    )
