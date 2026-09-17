"""The text editor, driven on the text-editor page.

The commit gestures the upstream `field-editors.js` asserts on a text cell, against the widget the
cell opens: Enter commits on a single-line input, a newline is what Enter means in a textarea so
the commit there is the blur, Escape restores, readonly and disabled keep their contract, and the
stored form strips both ends and keeps no empty string (field_types/text).

    .venv/bin/python tools/qa.py --page text-editor --drive tools/drives/text-editor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
    from sg_widgets_qt.primitives.input import Textarea

    failures: list[str] = []
    seen: dict = {}

    editors = find("text-editor", all=True)
    if len(editors) < 5:
        return {"verdict": f"FAIL the page holds {len(editors)} text editors, wanted 5"}
    one, many, readonly, disabled, invalid = editors[:5]

    committed: list = []
    one.committed.connect(committed.append)

    # Typing and Enter commit the parsed value, and the payload is the string the API stores.
    type_text(one.control, "  edited by qa  ")
    press_enter(one.control)
    wait(60)
    seen["committed"] = committed[-1:]
    if committed[-1:] != ["edited by qa"]:
        failures.append(f"Enter committed {committed[-1:]}, wanted ['edited by qa']")

    # An empty input stores null: clearing the input and clearing the field are one act.
    type_text(one.control, "   ")
    press_enter(one.control)
    wait(60)
    seen["cleared"] = committed[-1:]
    if committed[-1:] != [None]:
        failures.append(f"an empty input committed {committed[-1:]}, wanted [None]")

    # Escape restores the stored value.
    type_text(one.control, "typed and thrown away")
    escape(one.control)
    wait(60)
    seen["restored"] = one.control.text()
    if one.control.text() != "":
        failures.append(f"Escape left {one.control.text()!r}")

    # Blur commits.
    one.set_value("Plate delivered.")
    wait(20)
    type_text(one.control, "left the control")
    one.control.clearFocus()
    wait(60)
    seen["blurred"] = committed[-1:]
    if committed[-1:] != ["left the control"]:
        failures.append(f"leaving the control committed {committed[-1:]}")

    # A newline is what Enter means in a textarea, so the commit there is the blur alone.
    many_committed: list = []
    many.committed.connect(many_committed.append)
    seen["textarea"] = isinstance(many.control, Textarea)
    if not isinstance(many.control, Textarea):
        failures.append("the multiline case draws no textarea")
    type_text(many.control, "first line")
    press_enter(many.control)
    wait(60)
    seen["enterInTextarea"] = many_committed[-1:]
    if many_committed:
        failures.append("Enter in a textarea committed instead of adding a line")
    many.control.clearFocus()
    wait(60)
    if not many_committed:
        failures.append("leaving a textarea did not commit")

    # Readonly keeps full contrast and takes the writing away; disabled is inert.
    seen["readonly"] = readonly.control.isReadOnly()
    if readonly.control.isReadOnly() is not True:
        failures.append("readonly left the input writable")
    if readonly.isEnabled() is not True:
        failures.append("readonly disabled the control, which drops its contrast")
    seen["disabled"] = disabled.isEnabled()
    if disabled.isEnabled() is not False:
        failures.append("disabled is still live")
    before = disabled.value
    key(disabled.control, QtCore.Qt.Key.Key_Return)
    if disabled.value != before:
        failures.append("a disabled editor still committed")

    # The invalid case shows the caller's message and reads invalid.
    seen["invalid"] = (invalid.message, invalid.reads_invalid)
    if not invalid.message or invalid.reads_invalid is not True:
        failures.append(f"the invalid case reads {seen['invalid']}")

    # The size ladder, measured on the real control.
    ladder = {}
    for step, height in CONTROL_HEIGHT.items():
        one.set_size(step)
        wait(20)
        ladder[step] = one.control.sizeHint().height()
        if ladder[step] != height:
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    one.set_size("md")
    seen["ladder"] = ladder

    return {
        "verdict": (
            "PASS Enter commits the stripped string, an empty input stores null, Escape restores, "
            "a blur commits, a textarea takes the newline, and the ladder is 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
