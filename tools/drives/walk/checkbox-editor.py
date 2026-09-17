"""checkbox-editor: toggle each switch and read the word that follows it.

    .venv/bin/python tools/qa.py --page checkbox-editor --drive tools/drives/walk/checkbox-editor.py

Two rows carry a value and two are blocked. A switch is pressed, the word beside it is read, the
readout under it is read, and the two blocked rows are pressed to prove they stay where they are.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, set_view  # noqa: E402
from qtpy import QtCore  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("checkbox-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no checkbox-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- the two live rows ----------------------------------------------------------------
    flagged = cases["flagged"]
    walk.same("flagged: the demo opens on true", True, flagged.editor.value)
    walk.same("flagged: the word beside it reads Yes", "Yes", flagged.editor._label.text)  # noqa: SLF001
    click(flagged.editor.switch)
    wait(250)
    walk.same("flagged: a press toggles the value", False, flagged.editor.value)
    walk.same("flagged: the word follows the value", "No", flagged.editor._label.text)  # noqa: SLF001
    walk.same("flagged: the readout follows the value", "false", flagged.readout.text)
    click(flagged.editor.switch)
    wait(250)
    walk.same("flagged: a second press puts it back", True, flagged.editor.value)
    walk.same("flagged: the readout follows back", "true", flagged.readout.text)

    named = cases["client approved"]
    walk.same("named: the demo opens on false", False, named.editor.value)
    walk.same("named: the caller's own word shows", "Not approved", named.editor._label.text)  # noqa: SLF001
    click(named.editor.switch)
    wait(250)
    walk.same("named: a press toggles the value", True, named.editor.value)
    walk.same("named: the other word of the pair shows", "Approved", named.editor._label.text)  # noqa: SLF001
    walk.same("named: the readout follows", "true", named.readout.text)

    # The keyboard reaches the switch too: Space is what presses one.
    named.editor.switch.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(named.editor.switch, QtCore.Qt.Key.Key_Space)
    wait(250)
    walk.same("named: Space toggles it from the keyboard", False, named.editor.value)

    # --- the two blocked rows ---------------------------------------------------------------
    read = cases["readonly"]
    held = read.editor.value
    click(read.editor.switch)
    wait(200)
    walk.same("readonly: a press does not move it", held, read.editor.value)

    off = cases["disabled"]
    stood = off.editor.value
    click(off.editor.switch)
    wait(200)
    walk.check("disabled: the row is inert", not off.editor.isEnabled(), False, off.editor.isEnabled())
    walk.same("disabled: a press does not move it", stood, off.editor.value)

    # --- the view controls --------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("checkbox-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}["flagged"]
        walk.same("header: the switches wear the size step", "lg", rebuilt.editor.size)
        before = rebuilt.editor.value
        click(rebuilt.editor.switch)
        wait(250)
        walk.same("header: the rebuilt switch still toggles", not before, rebuilt.editor.value)
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS each switch toggles, the word and the readout follow it, the keyboard reaches it,"
        " the two blocked rows stay where they are, and the view controls are followed"
    )
