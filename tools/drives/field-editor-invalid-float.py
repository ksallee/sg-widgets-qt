"""field-editor: something that is not a number on a float field never emits.

The port of `~/dev/sg-widgets/tools/drives/field-editor-invalid-float.js`. Invalid input goes
invalid, names the reason and leaves the stored value standing, and the edit half stays open
while the parse error is on show.

    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-invalid-float.py
    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-invalid-float.py --qt5
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtCore import Qt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import press, until  # noqa: E402

TYPED = "not a number"


def drive(page, wait, find, prefs) -> dict:
    editor = find("field-editor-float")
    if editor is None:
        return {"verdict": "FAIL no float field on this page"}
    emitted: list = []
    editor.value_changed.connect(emitted.append)
    before = editor.value

    editor.display.setFocus(Qt.FocusReason.OtherFocusReason)
    press(editor.display, Qt.Key.Key_Return)
    if not until(lambda: editor.control is not None, wait, 4000):
        return {"verdict": "FAIL Enter on the value did not open the editor"}
    caret = editor.control.input
    caret.setText(TYPED)
    wait(150)
    press(caret, Qt.Key.Key_Return)
    wait(300)

    control = editor.control
    # The parse error is the editor's own `message`, which its `FieldError` line draws.
    message = str(getattr(control, "message", "") or "") if control is not None else ""
    invalid = bool(message)
    failures: list[str] = []
    if emitted:
        failures.append(f"emitted {emitted}, wanted nothing")
    if editor.value != before:
        failures.append(f"the stored value moved to {editor.value!r}")
    if editor.mode != "edit":
        failures.append("left the editor while invalid")
    if not invalid:
        failures.append("the control is not drawn invalid")
    if not message:
        failures.append("no parse error is shown")
    return {
        "verdict": (
            "PASS an invalid float goes invalid, names the reason and emits nothing"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "emitted": emitted,
        "value": editor.value,
        "mode": editor.mode,
        "invalid": invalid,
        "message": message,
    }
