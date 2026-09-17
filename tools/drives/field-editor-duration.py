"""field-editor: `1h 30m` on a duration field emits 90.

The port of `~/dev/sg-widgets/tools/drives/field-editor-duration.js`. A duration is stored as a
whole number of minutes (field_types/duration), so 90 is the answer, and Enter commits and puts
the row back on the display half.

    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-duration.py
    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-duration.py --qt5
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtCore import Qt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import press, until  # noqa: E402

#: What is typed, and the minutes it is worth.
TYPED = "1h 30m"
MINUTES = 90


def drive(page, wait, find, prefs) -> dict:
    editor = find("field-editor-duration")
    if editor is None:
        return {"verdict": "FAIL no duration field on this page"}
    emitted: list = []
    editor.value_changed.connect(emitted.append)

    editor.display.setFocus(Qt.FocusReason.OtherFocusReason)
    press(editor.display, Qt.Key.Key_Return)
    if not until(lambda: editor.control is not None, wait, 4000):
        return {"verdict": "FAIL Enter on the value did not open the editor"}
    caret = editor.control.input
    caret.setText(TYPED)
    wait(120)
    # The hint is behind a prop the dispatcher does not set, so the field shows none here.
    hint = getattr(editor.control, "hint", "")
    press(caret, Qt.Key.Key_Return)
    wait(300)

    failures: list[str] = []
    if emitted[-1:] != [MINUTES]:
        failures.append(f"emitted {emitted}, wanted [{MINUTES}]")
    if editor.mode != "display":
        failures.append(f"still in {editor.mode} after Enter")
    if hint:
        failures.append(f'the hint read "{hint}", wanted none')
    return {
        "verdict": (
            f"PASS {TYPED} emits {MINUTES} and Enter puts the row back on the display half"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "emitted": emitted,
        "mode": editor.mode,
        "hint": hint,
    }
