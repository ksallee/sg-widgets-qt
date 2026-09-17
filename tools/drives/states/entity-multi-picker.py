"""The Qt half of the multi picker's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/entity-multi-picker-<state>.js`. Every state the
single picker also has is handed to `tools/drives/states/entity-picker.py`, which this file loads
beside it, so one page's matrix is one file and the shared states cannot drift.

    QA_STATE=armed .venv/bin/python tools/qa.py --page entity-multi-picker \\
        --drive tools/drives/states/entity-multi-picker.py \\
        --shot shots/states/entity-multi-picker-armed.png

    armed     the token field with the caret on its last chip, wearing the ring
    overflow  the narrow summary control, whole chips then `+n`
    ticked    the list open on a multi picker whose rows are already ticked
"""
from __future__ import annotations

import os
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.widgets.picker_control import PickerControl

#: The states only a multi picker has. The rest are the single picker's.
OWN: tuple[str, ...] = ("armed", "overflow", "ticked")

#: The sibling drive holding the states both pickers share.
SHARED = Path(__file__).resolve().parent / "entity-picker.py"


def shared_drive():
    """The `drive` of the single picker's state file, loaded the way qa.py loads a drive."""
    namespace: dict = {"__name__": "sg_qa_shared_states", "__file__": str(SHARED)}
    exec(compile(SHARED.read_text(encoding="utf-8"), str(SHARED), "exec"), namespace)
    return namespace["drive"]


def state_name() -> str:
    return os.environ.get("QA_STATE", "rest").strip().lower()


def controls(find) -> list:
    return [
        control
        for control in find(PickerControl, all=True)
        if not control.disabled and not control.readonly and control.isVisible()
    ]


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    state = state_name()
    if state not in OWN:
        return shared_drive()(page, wait, find, prefs)

    found = controls(find)
    if state == "armed":
        tokens = next(
            (c for c in found if c.multiple and c.chip_row and c.inline and len(c.labels) > 1),
            None,
        )
        if tokens is None:
            return {"verdict": "FAIL no token field with chips to arm"}
        caret = tokens.caret()
        caret.setFocus()
        QTest.keyClick(caret, Qt.Key.Key_Backspace)
        wait(300)
        return {
            "verdict": "PASS armed",
            "state": state,
            "armed": tokens.armed,
            "chips": len(tokens.chips()),
        }

    if state == "overflow":
        narrow = next(
            (c for c in found if c.summary == "ellipsis" and c.overflow_pill().count > 0), None
        )
        if narrow is None:
            return {"verdict": "FAIL no narrow summary control with chips to hide"}
        wait(200)
        return {
            "verdict": "PASS overflow",
            "state": state,
            "shown": sum(1 for chip in narrow.chips() if chip.isVisibleTo(narrow)),
            "pill": narrow.overflow_pill().count,
            "height": narrow.height(),
        }

    multi = next((c for c in found if c.multiple and c.keys), None)
    if multi is None:
        return {"verdict": "FAIL no multi picker holding a value"}
    multi.set_open(True)
    wait(1800)
    return {
        "verdict": "PASS ticked",
        "state": state,
        "rows": multi.list_surface().row_count(),
        "ticked": len(multi.keys),
    }
