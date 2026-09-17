"""value-editor: the base, under an editor the base knows nothing about.

    .venv/bin/python tools/qa.py --page value-editor --drive tools/drives/walk/value-editor.py

The demo's frame-range editor supplies its own parse, so the walk proves what the base gives it:
a commit on Enter, a commit on leaving, a restore on Escape, the caller's parse error under the
control, and the message the row form was handed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, blur, key, popups, press_enter, retype, set_view  # noqa: E402
from qtpy import QtCore  # noqa: E402


def reading(editor) -> str:
    """The range the editor holds, as the demo prints it."""
    value = editor.value
    return "" if value is None else f"{value.first}-{value.last}"


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("value-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no value-editor demo"}
    cut, delivery = demo.editors
    field = cut.input

    walk.same("cut: the demo opens on the stored range", "1001-1120", reading(cut))

    retype(field, "1002-1200")
    press_enter(field)
    wait(150)
    walk.same("cut: Enter commits the range", "1002-1200", reading(cut))

    retype(field, "900-950")
    blur(field)
    wait(200)
    walk.same("cut: leaving the field commits it", "900-950", reading(cut))

    retype(field, "1-2")
    key(field, QtCore.Qt.Key.Key_Escape)
    wait(150)
    walk.same("cut: Escape keeps the stored range", "900-950", reading(cut))
    walk.same("cut: Escape puts the stored range back", "900-950", field.text())

    # --- the two ways the demo's own parse refuses a draft ---------------------------------
    retype(field, "not a range")
    press_enter(field)
    wait(200)
    walk.same("cut: a shapeless draft is refused", "900-950", reading(cut))
    walk.same(
        "cut: the line names the shape",
        "A range reads as two frames, 1001-1120.",
        cut.message,
    )
    walk.check("cut: the line is on show", cut.error_line.isVisible(), True, False)
    walk.check("cut: the control reads invalid", cut.reads_invalid, True, False)

    retype(field, "1200-1001")
    press_enter(field)
    wait(200)
    walk.same(
        "cut: a backwards range is refused by name",
        "The last frame comes before the first.",
        cut.message,
    )

    key(field, QtCore.Qt.Key.Key_Escape)
    wait(150)
    walk.same("cut: Escape clears the refusal", None, cut.message)
    walk.check("cut: the line went with it", not cut.error_line.isVisible(), False, True)

    # An emptied field stores nothing, which is the demo's own `ParseValue(None)`.
    retype(field, "")
    press_enter(field)
    wait(150)
    walk.same("cut: an emptied field stores nothing", None, cut.value)

    # --- the row form, with a message the caller named --------------------------------------
    walk.check("delivery: the row form takes the width of its value", delivery.inline, True, False)
    walk.same("delivery: the caller's message stands under it", "The site refused this range.", delivery.message)
    walk.check("delivery: the line is on show", delivery.error_line.isVisible(), True, False)
    retype(delivery.input, "1001-1099")
    press_enter(delivery.input)
    wait(200)
    walk.same("delivery: the row form still commits", "1001-1099", reading(delivery))
    walk.same(
        "delivery: the caller's message outlives the commit",
        "The site refused this range.",
        delivery.message,
    )

    # --- the view controls --------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("value-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = again.editors[0]
        walk.same("header: the editor wears the size step", "lg", rebuilt.size)
        retype(rebuilt.input, "1500-1600")
        press_enter(rebuilt.input)
        wait(150)
        walk.same("header: the rebuilt editor still commits", "1500-1600", reading(rebuilt))
        walk.same("header: the row form keeps the size it named", "sm", again.editors[1].size)
    set_view(page, wait, theme="light", size="md", density="default", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the base commits on Enter and on leaving, restores on Escape, names both of the"
        " demo's own refusals under the control, and keeps the caller's message through a commit"
    )
