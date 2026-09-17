"""The checkbox editor, driven on the checkbox-editor page.

The type is two-state and never null, so this control has no draft and no clear: it writes on the
toggle (field_types/checkbox). Space toggles it, the word beside it follows the value, readonly
drops the affordance and keeps full contrast, and disabled is inert.

    .venv/bin/python tools/qa.py --page checkbox-editor --drive tools/drives/checkbox-editor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import key  # noqa: E402
from qtpy import QtCore  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT

    failures: list[str] = []
    seen: dict = {}

    editors = find("checkbox-editor", all=True)
    if len(editors) < 4:
        return {"verdict": f"FAIL the page holds {len(editors)} checkbox editors, wanted 4"}
    flagged, approved, readonly, disabled = editors[:4]

    committed: list = []
    flagged.committed.connect(committed.append)

    # Space toggles, and the payload is the boolean the API stores.
    seen["before"] = flagged.value
    key(flagged.switch, QtCore.Qt.Key.Key_Space)
    wait(60)
    seen["afterSpace"] = (flagged.value, committed[-1:])
    if flagged.value is not False or committed[-1:] != [False]:
        failures.append(f"Space gave {seen['afterSpace']}, wanted (False, [False])")
    if not isinstance(committed[-1], bool):
        failures.append("the payload is not a bool")

    # The word beside the switch follows the value.
    seen["label"] = flagged._label.text
    if flagged._label.text != flagged.labels[1]:
        failures.append(f"the word reads {flagged._label.text!r}")
    key(flagged.switch, QtCore.Qt.Key.Key_Space)
    wait(60)
    if flagged.value is not True or flagged._label.text != flagged.labels[0]:
        failures.append("the second Space did not come back")

    # The caller's two words are what the second case shows.
    seen["labels"] = approved.labels
    if approved._label.text not in approved.labels:
        failures.append(f"the second case reads {approved._label.text!r}")

    # Readonly keeps full contrast and drops the affordance: the toggle is refused and the
    # switch leaves the tab order.
    was = readonly.value
    readonly.toggle()
    wait(40)
    seen["readonly"] = (readonly.value, readonly.isEnabled())
    if readonly.value != was:
        failures.append("readonly still toggled")
    if readonly.isEnabled() is not True:
        failures.append("readonly disabled the control, which drops its contrast")
    if readonly.switch.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus:
        failures.append("readonly left the switch in the tab order")

    # Disabled is inert.
    was = disabled.value
    disabled.toggle()
    key(disabled.switch, QtCore.Qt.Key.Key_Space)
    wait(40)
    seen["disabled"] = (disabled.value, disabled.isEnabled())
    if disabled.value != was or disabled.isEnabled() is not False:
        failures.append(f"disabled reads {seen['disabled']}")

    # There is no third state and no way to clear the field.
    seen["noClear"] = not hasattr(flagged, "clear")
    if hasattr(flagged, "clear"):
        failures.append("the control offers a clear, which this type has no null for")

    # The size ladder, measured on the row the switch stands in.
    ladder = {}
    for step, height in CONTROL_HEIGHT.items():
        flagged.set_size(step)
        wait(20)
        ladder[step] = flagged._row.minimumHeight()
        if ladder[step] != height:
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    flagged.set_size("md")
    seen["ladder"] = ladder

    return {
        "verdict": (
            "PASS Space toggles and writes a bool, the word follows, readonly and disabled hold, "
            "and the row is 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
