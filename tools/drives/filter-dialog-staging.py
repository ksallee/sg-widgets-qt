"""Edits inside the dialog are staged: only Apply emits, Cancel drops them, Clear all empties.

    .venv/bin/python tools/qa.py --page filter-dialog --drive tools/drives/filter-dialog-staging.py
    .venv/bin/python tools/qa.py --page filter-dialog --drive tools/drives/filter-dialog-staging.py --qt5

What the docs page promises, clause by clause:

  * closed, the launcher reads the count of the conditions that would reach the API,
  * opening stages the applied tree afresh, so a cancelled edit leaves nothing behind,
  * Apply emits once on `changed` and once on `filters_changed`, with the staged tree, and
    the wire under the launcher is core's own `to_api3_hash` of it,
  * Cancel emits nothing and leaves the applied tree where it was,
  * Clear all emits an empty filter,
  * a tree of blank rows applies as no filter at all.
"""
from __future__ import annotations

import json
import time

from qtpy import QtWidgets

from sg_widgets_core.filter import condition, empty_filter, to_api3_hash
from sg_widgets_core.filter_ux import count_active_conditions
from sg_widgets_qt.widgets.filter_dialog import FilterDialog


def wait_for(read, wait, ms: int = 8000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def block_of(page):
    for one in page.findChildren(QtWidgets.QPlainTextEdit):
        if one.objectName() == "dialog-json":
            return one
    return None


def printed(block):
    text = block.toPlainText().strip()
    if not text or text == "null":
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(600)
    launcher = find("filter-dialog-applied")
    if not isinstance(launcher, FilterDialog):
        every = find(FilterDialog, all=True)
        launcher = every[1] if len(every) > 1 else (every[0] if every else None)
    block = block_of(page)
    if launcher is None or block is None:
        return {"verdict": "FAIL the page has no applied launcher with its serialised filter"}

    failures: list[str] = []
    seen: list = []
    also: list = []
    launcher.changed.connect(seen.append)
    launcher.filters_changed.connect(also.append)
    applied = launcher.value
    steps: list[dict] = []

    # Closed, the trigger carries the count and the label the docs page names.
    if launcher.active != count_active_conditions(applied):
        failures.append(f"the launcher reads {launcher.active}, core counts {count_active_conditions(applied)}")
    if launcher.launcher().text != "Edit filters":
        failures.append(f"the launcher reads {launcher.launcher().text!r} with filters applied")
    if launcher.launcher().count != str(launcher.active):
        failures.append(
            f"the trigger carries {launcher.launcher().count!r}, not the count {launcher.active}"
        )
    steps.append({"step": "closed", "count": launcher.active, "chip": launcher.launcher().count})

    # Cancel: an edit inside the dialog reaches nothing.
    launcher.set_open(True)
    wait_for(lambda: launcher.editor() is not None, wait, 6000)
    wait(400)
    editor = launcher.editor()
    if editor is None:
        return {"verdict": "FAIL the dialog opened with no editor in it"}
    editor.append([], condition("code", "contains", "zzz"))
    wait(300)
    launcher.cancel()
    wait(300)
    steps.append({"step": "cancelled", "emitted": len(seen), "count": launcher.active})
    if seen:
        failures.append(f"Cancel emitted {len(seen)} times")
    if launcher.value is not applied and to_api3_hash(launcher.value) != to_api3_hash(applied):
        failures.append("Cancel changed the applied tree")

    # Opening again stages the applied tree afresh, so the cancelled row is gone.
    launcher.set_open(True)
    wait_for(lambda: launcher.editor() is not None, wait, 6000)
    wait(400)
    editor = launcher.editor()
    staged = [c.path for c in editor.value.conditions]
    if "code" in staged:
        failures.append(f"the draft kept the cancelled row: {staged}")
    steps.append({"step": "reopened", "staged": staged})

    # Apply: one emission on each signal, and the wire under it is core's own.
    editor.append([], condition("code", "contains", "comp"))
    wait(300)
    want = to_api3_hash(editor.value)
    launcher.apply()
    wait(400)
    steps.append({"step": "applied", "emitted": len(seen), "count": launcher.active})
    if len(seen) != 1:
        failures.append(f"Apply emitted {len(seen)} times, wanted 1")
    if len(also) != len(seen):
        failures.append(f"filters_changed ran {len(also)} times to changed's {len(seen)}")
    if seen and to_api3_hash(seen[-1]) != want:
        failures.append("Apply carried a tree that is not the staged one")
    wait(300)
    if printed(block) != want:
        failures.append(f"the block reads {json.dumps(printed(block))[:120]}")
    if launcher.open:
        failures.append("Apply left the dialog open")

    # Clear all: an empty filter, once.
    before = len(seen)
    launcher.set_open(True)
    wait_for(lambda: launcher.editor() is not None, wait, 6000)
    wait(300)
    launcher.clear_all()
    wait(400)
    steps.append({"step": "cleared", "emitted": len(seen) - before, "count": launcher.active})
    if len(seen) - before != 1:
        failures.append(f"Clear all emitted {len(seen) - before} times, wanted 1")
    if launcher.active != 0:
        failures.append(f"Clear all left {launcher.active} conditions")
    if launcher.launcher().text != "Add filters":
        failures.append(f"the emptied launcher reads {launcher.launcher().text!r}")
    if launcher.launcher().count:
        failures.append("the emptied launcher still carries a count chip")

    # A tree of blank rows applies as no filter at all.
    before = len(seen)
    launcher.set_open(True)
    wait_for(lambda: launcher.editor() is not None, wait, 6000)
    wait(300)
    launcher.editor().append([], condition("", "is", ""))
    wait(300)
    launcher.apply()
    wait(400)
    steps.append({"step": "blank", "emitted": len(seen) - before, "count": launcher.active})
    if seen and to_api3_hash(seen[-1]) is not None:
        failures.append("a tree of blank rows applied as a filter")
    if launcher.active != 0:
        failures.append(f"a tree of blank rows counted {launcher.active}")
    if to_api3_hash(empty_filter()) is not None:
        failures.append("core's own empty filter serialises to something")

    return {
        "verdict": (
            "PASS the count reads core's, Cancel emits nothing and drops its edit, reopening"
            " stages the applied tree afresh, Apply emits once on both signals with the staged"
            " tree, Clear all emits an empty filter, and a tree of blank rows applies as none"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "steps": steps,
    }
