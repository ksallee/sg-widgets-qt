"""text-editor: type and commit, leave and commit, restore on Escape, and the blocked states.

    .venv/bin/python tools/qa.py --page text-editor --drive tools/drives/walk/text-editor.py

The caption on each row names a state. The walk does what the row invites: type into the input and
press Enter, type again and leave the field, type once more and press Escape, prove the textarea
takes a newline from Enter and commits on the blur alone, prove the two blocked rows refuse the
keyboard, and read the line the invalid row stands over. Then it moves the view controls and reads
the page again, because a demo that stops answering after a rebuild is the defect this catches.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, blur, key, popups, press_enter, retype, set_view  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("text-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no text-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- the single line: the three ways a draft ends -----------------------------------
    one = cases["input"]
    field = one.editor.control
    walk.same("input: the demo opens on the stored line", "Plate delivered.", one.editor.value)

    retype(field, "Enter commits")
    press_enter(field)
    wait(150)
    walk.same("input: Enter commits the draft", "Enter commits", one.editor.value)
    walk.same("input: the readout follows the commit", '"Enter commits"', one.readout.text)

    retype(field, "Leaving commits")
    blur(field)
    wait(200)
    walk.same("input: leaving the field commits it", "Leaving commits", one.editor.value)
    walk.same("input: the readout follows the blur", '"Leaving commits"', one.readout.text)

    retype(field, "Thrown away")
    key(field, QtCore.Qt.Key.Key_Escape)
    wait(150)
    walk.same("input: Escape keeps the stored line", "Leaving commits", one.editor.value)
    walk.same("input: Escape puts the stored line back in the field", "Leaving commits", field.text())

    # Clearing the field stores nothing at all, which is how the field is un-set.
    retype(field, "")
    press_enter(field)
    wait(150)
    walk.same("input: an emptied field stores nothing", None, one.editor.value)
    walk.same("input: the readout reads null", "null", one.readout.text)

    # --- the textarea: Enter is a newline, the blur is the commit -------------------------
    many = cases["multiline"]
    area = many.editor.control
    held = many.editor.value
    area.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    area.selectAll()
    QTest.keyClick(area, QtCore.Qt.Key.Key_Delete)
    QTest.keyClicks(area, "First line")
    press_enter(area)
    QTest.keyClicks(area, "Second line")
    wait(150)
    walk.same("multiline: Enter is a newline, not a commit", held, many.editor.value)
    walk.check(
        "multiline: the newline reached the draft",
        area.toPlainText() == "First line\nSecond line",
        "First line\\nSecond line",
        area.toPlainText(),
    )
    blur(area)
    wait(200)
    walk.same("multiline: leaving the textarea commits it", "First line\nSecond line", many.editor.value)

    # --- the three blocked rows ------------------------------------------------------------
    read = cases["readonly"]
    stored = read.editor.value
    read.editor.control.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    QTest.keyClicks(read.editor.control, "XYZ")
    press_enter(read.editor.control)
    wait(150)
    walk.same("readonly: the keyboard does not reach the value", stored, read.editor.value)
    walk.check("readonly: the input says it is read-only", read.editor.control.isReadOnly(), True, False)

    off = cases["disabled"]
    walk.check("disabled: the row is inert", not off.editor.isEnabled(), False, off.editor.isEnabled())

    bad = cases["invalid"]
    walk.same("invalid: the line names the reason", "The site refused this value.", bad.editor.message)
    walk.check("invalid: the line is on show", bad.editor.error_line.isVisible(), True, False)
    walk.check("invalid: the control reads invalid", bad.editor.reads_invalid, True, False)

    # --- the view controls ------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg")
    walk.same("header: every control moved", [], missed)
    walk.same("header: the page wears dark", "dark", prefs.theme)
    again = find("text-editor-demo")
    walk.check("header: the demo survived the size step", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}["input"]
        walk.same("header: the editors wear the size step", "lg", rebuilt.editor.size)
        retype(rebuilt.editor.control, "After the rebuild")
        press_enter(rebuilt.editor.control)
        wait(150)
        walk.same("header: the rebuilt editor still commits", "After the rebuild", rebuilt.editor.value)

    set_view(page, wait, motion="reduced", palette="nova", density="compact")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    walk.same("header: the palette holds", "nova", prefs.palette)
    walk.same("header: the density holds", "compact", prefs.density)
    set_view(page, wait, theme="light", size="md", motion="normal", palette="slate", density="default")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result("PASS the text editor commits on Enter and on leaving, restores on Escape,"
                       " refuses the keyboard where it is blocked, and follows the view controls")
