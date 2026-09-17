"""The base every leaf editor stands on, driven on the value-editor page.

The port of `~/dev/sg-widgets/tools/drives/value-editor.js`: Enter commits what parsed, a range
that runs backwards is refused and shows the error line without reaching the value, Escape
restores, and leaving the control commits too. The row form wears the caller's message.

    .venv/bin/python tools/qa.py --page value-editor --drive tools/drives/value-editor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT

    failures: list[str] = []
    seen: dict = {}

    editors = find("range-editor", all=True)
    if len(editors) != 2:
        return {"verdict": f"FAIL the page holds {len(editors)} range editors, wanted 2"}
    cut, delivery = editors
    field = cut.input

    committed: list = []
    cut.committed.connect(committed.append)

    # Enter commits what parsed, and the payload is the API shape the editor stores.
    type_text(field, "1001-1200")
    press_enter(field)
    wait(60)
    seen["committed"] = None if not committed else (committed[-1].first, committed[-1].last)
    if seen["committed"] != (1001, 1200):
        failures.append(f"Enter left the value at {seen['committed']}")

    # A range that runs backwards is refused, and the value it was is untouched.
    type_text(field, "1200-1001")
    press_enter(field)
    wait(60)
    seen["refused"] = cut.message
    if not seen["refused"]:
        failures.append("the refused range showed no error line")
    if cut.reads_invalid is not True:
        failures.append("the refused range left the control reading valid")
    if len(committed) != 1:
        failures.append("the refused range reached the value")

    # Escape restores the stored range and drops the message.
    escape(field)
    wait(60)
    seen["restored"] = field.text()
    if field.text() != "1001-1200" or cut.message is not None:
        failures.append(f"Escape left {field.text()!r} and {cut.message!r}")

    # Leaving the control commits too.
    type_text(field, "1002-1150")
    field.clearFocus()
    wait(60)
    seen["blurred"] = None if len(committed) < 2 else (committed[-1].first, committed[-1].last)
    if seen["blurred"] != (1002, 1150):
        failures.append(f"leaving the control left the value at {seen['blurred']}")

    # The row form wears the caller's message, not one a parse made.
    seen["inline"] = delivery.inline
    seen["given"] = delivery.message
    if delivery.inline is not True:
        failures.append("the row form does not read inline")
    if not str(delivery.message or "").startswith("The site refused"):
        failures.append(f"the caller's message reads {delivery.message!r}")

    # The size ladder, measured on the real control.
    ladder = {}
    for step, height in CONTROL_HEIGHT.items():
        cut.set_size(step)
        wait(20)
        ladder[step] = cut.input.sizeHint().height()
        if ladder[step] != height:
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    cut.set_size("md")
    seen["ladder"] = ladder

    # Readonly drops the affordance and keeps full contrast; disabled is inert.
    cut.set_readonly(True)
    wait(20)
    seen["readonly"] = cut.input.isReadOnly()
    if cut.input.isReadOnly() is not True:
        failures.append("readonly left the input writable")
    cut.set_readonly(False)
    cut.set_disabled(True)
    wait(20)
    before = len(committed)
    key(cut.input, QtCore.Qt.Key.Key_Return)
    if len(committed) != before:
        failures.append("a disabled editor still committed")
    cut.set_disabled(False)

    return {
        "verdict": (
            "PASS the base commits on Enter and on leaving, refuses a backwards range, restores "
            "on Escape, and stands on 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
