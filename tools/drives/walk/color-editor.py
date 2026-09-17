"""color-editor: open the picker, drag in the square and the strip, and type a hex code.

    .venv/bin/python tools/qa.py --page color-editor --drive tools/drives/walk/color-editor.py

The swatch opens a popover holding a saturation and value square over a hue strip. The walk presses
the swatch, drags inside both, walks the knob with the arrows, closes with Escape, then types a hex
code into the triple beside it and reads what is stored, reads the refusal of a draft that is
neither, and proves the pipeline-step token explains itself and the blocked row never opens.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, press_enter, retype, set_view, wear  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

from sg_widgets_qt.theme import theme_of  # noqa: E402

SENTINEL_NOTE = "Takes the colour of the linked pipeline step."


def drag(picker, start, end, wait) -> None:
    """Press inside the picker, travel, and let go, which is how a colour is taken."""
    QTest.mousePress(
        picker, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, start
    )
    QTest.mouseMove(picker, end)
    wait(30)
    QTest.mouseRelease(
        picker, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, end
    )
    wait(200)


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("color-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no color-editor demo"}
    cases = {case.name: case for case in demo.cases}

    # --- the triple: the picker, dragged and walked -----------------------------------------
    triple = cases["triple"]
    editor = triple.editor
    walk.same("triple: the demo opens on the stored triple", "253,94,99", editor.value)

    click(editor.swatch)
    wait(400)
    walk.check("triple: the swatch opens the picker", editor.is_open, True, editor.is_open)
    walk.check("triple: the picker stands on a window of its own", popups() != [], "a popover", popups())

    picker = editor.picker
    held = editor.value
    drag(picker, QtCore.QPoint(20, 20), QtCore.QPoint(90, 60), wait)
    walk.check(
        "triple: a drag in the square takes a colour",
        editor.value != held,
        f"not {held}",
        editor.value,
    )
    walk.same("triple: the readout follows the drag", f'"{editor.value}"', triple.readout.text)
    walk.same("triple: the input follows the drag", editor.value, editor.input.text())

    held = editor.value
    strip = picker._strip_rect()  # noqa: SLF001
    drag(
        picker,
        QtCore.QPoint(10, strip.center().y()),
        QtCore.QPoint(150, strip.center().y()),
        wait,
    )
    walk.check(
        "triple: a drag in the hue strip takes another",
        editor.value != held,
        f"not {held}",
        editor.value,
    )

    held = editor.value
    key(picker, QtCore.Qt.Key.Key_Left)
    wait(200)
    walk.check(
        "triple: an arrow walks the knob",
        editor.value != held,
        f"not {held}",
        editor.value,
    )

    key(picker, QtCore.Qt.Key.Key_Escape)
    wait(400)
    walk.check("triple: Escape closes the picker", not editor.is_open, False, editor.is_open)
    walk.same("triple: nothing was left standing over the page", [], popups())

    # --- the hex code: converted on the way in -------------------------------------------------
    hexed = cases["hex accepted"]
    swapped = hexed.editor
    retype(swapped.input, "#ff8000")
    wait(150)
    walk.check(
        "hex: the swatch previews the draft before it is committed",
        swapped.preview is not None and swapped.preview.name() == "#ff8000",
        "#ff8000",
        swapped.preview.name() if swapped.preview is not None else None,
    )
    press_enter(swapped.input)
    wait(200)
    walk.same("hex: a hex code is stored as the decimal triple", "255,128,0", swapped.value)
    walk.same("hex: the input reads back as the triple", "255,128,0", swapped.input.text())
    walk.same("hex: the readout follows", '"255,128,0"', hexed.readout.text)

    retype(swapped.input, "nonsense")
    press_enter(swapped.input)
    wait(200)
    walk.same("hex: a draft that is neither is refused", "255,128,0", swapped.value)
    walk.same("hex: the line names both shapes", "Not a colour. Use r,g,b or a hex code.", swapped.message)
    walk.check("hex: the line is on show", swapped.error_line.isVisible(), True, False)
    key(swapped.input, QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.same("hex: Escape clears the refusal", None, swapped.message)
    walk.same("hex: Escape puts the stored triple back", "255,128,0", swapped.input.text())

    # --- the pipeline-step token ------------------------------------------------------------------
    token = cases["pipeline step"]
    step = token.editor
    walk.check("token: the draft reads as the token", step.sentinel, True, step.sentinel)
    walk.same("token: the line explains it", SENTINEL_NOTE, step._note.text)  # noqa: SLF001
    walk.check("token: the line is on show", step._note.isVisible(), True, False)  # noqa: SLF001
    walk.same("token: there is no colour to preview", None, step.preview)
    click(step.swatch)
    wait(400)
    walk.check("token: the swatch still opens the picker", step.is_open, True, step.is_open)
    key(step.picker, QtCore.Qt.Key.Key_Escape)
    wait(400)
    walk.check("token: the picker closed again", not step.is_open, False, step.is_open)

    # --- the blocked row --------------------------------------------------------------------------
    off = cases["disabled"]
    click(off.editor.swatch)
    wait(250)
    walk.check("disabled: the row is inert", not off.editor.isEnabled(), False, off.editor.isEnabled())
    walk.check("disabled: the swatch does not open", not off.editor.is_open, False, off.editor.is_open)

    # --- the view controls -------------------------------------------------------------------------
    # A view that moves under an open picker reaches it: the picker is a window of its own, so a
    # theme that stops at the page would leave it wearing the greys of the one before.
    click(editor.swatch)
    wait(400)
    wear(prefs, wait, theme="dark", settle=350)
    walk.check("header: the open picker stays up while the view moves", editor.is_open, True, editor.is_open)
    walk.check("header: the open picker wears the dark theme", theme_of(editor.picker).dark, True, False)
    wear(prefs, wait, motion="reduced", settle=350)
    walk.check(
        "header: the open picker wears reduced motion",
        theme_of(editor.picker).reduced_motion,
        True,
        False,
    )
    wear(prefs, wait, theme="light", motion="normal", settle=350)

    # A press on the header is a press outside the picker, so it takes the picker with it.
    missed = set_view(page, wait, theme="dark", settle=350)
    walk.same("header: the dark switch moved", [], missed)
    walk.same("header: the page wears dark", "dark", prefs.theme)
    walk.check("header: the press outside closed the picker", not editor.is_open, False, editor.is_open)
    walk.same("header: no picker was left behind", [], popups())

    missed = set_view(page, wait, size="lg", density="compact")
    walk.same("header: the size and the density moved", [], missed)
    again = find("color-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = {case.name: case for case in again.cases}["triple"]
        walk.same("header: the editors wear the size step", "lg", rebuilt.editor.size)
        click(rebuilt.editor.swatch)
        wait(400)
        walk.check("header: the rebuilt swatch still opens", rebuilt.editor.is_open, True, rebuilt.editor.is_open)
        key(rebuilt.editor.picker, QtCore.Qt.Key.Key_Escape)
        wait(400)
    set_view(page, wait, theme="light", size="md", density="default", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the swatch opens the picker, a drag in the square and in the strip takes a colour,"
        " an arrow walks the knob, a hex code is converted to the stored triple, a draft that is"
        " neither is named under the control, and the blocked row never opens"
    )
