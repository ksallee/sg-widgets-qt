"""The widest condition row inside the dialog, against the same one-line baseline.

The port of `~/dev/sg-widgets/tools/drives/filter-dialog-stress.js`.

    .venv/bin/python tools/qa.py --page filter-dialog --viewport 1400x1000 \\
        --drive tools/drives/filter-dialog-stress.py

The dialog takes `min(96vw, 64rem)` upstream, which is 1024 where it fits, so the editor inside
it has about the 1000px the stress table measures on the page. `date_time between` is the widest
combination the editor can draw and is what this checks: the row is no taller inside the dialog
than the `Version Name is` row beside it. Nothing here reaches the demo's filter — the run ends
on Cancel.
"""
from __future__ import annotations

import time

from sg_widgets_core.filter import condition, group
from sg_widgets_qt.widgets.filter_dialog import DIALOG_WIDTH, FilterDialog

#: The editor inside the dialog never has less than this to draw a row in.
EDITOR_FLOOR = 900


def wait_for(read, wait, ms: int = 8000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    launcher = find("filter-dialog-applied")
    if not isinstance(launcher, FilterDialog):
        every = find(FilterDialog, all=True)
        launcher = every[0] if every else None
    if launcher is None:
        return {"verdict": "FAIL the page has no launcher"}

    launcher.set_open(True)
    wait_for(lambda: launcher.editor() is not None, wait, 8000)
    wait(600)
    editor = launcher.editor()
    dialog = launcher.dialog()
    if editor is None or dialog is None:
        return {"verdict": "FAIL the dialog opened with no editor in it"}
    wait_for(lambda: editor.fields(), wait, 8000)

    # Two rows: the one-line baseline and the widest date_time the editor can draw.
    editor.set_value(
        group(
            "and",
            [
                condition("code", "is", ""),
                condition("created_at", "between", [None, None]),
            ],
        )
    )
    wait(600)
    rows = editor.rows()
    if len(rows) != 2:
        launcher.cancel()
        return {"verdict": f"FAIL the dialog drew {len(rows)} rows, wanted 2"}

    width = dialog.width()
    inner = editor.width()
    baseline = rows[0].height()
    between = rows[1].height()

    launcher.cancel()
    wait(300)

    failures: list[str] = []
    if inner < EDITOR_FLOOR:
        failures.append(f"the editor has {inner}px, under the {EDITOR_FLOOR}px floor")
    if between != baseline:
        failures.append(
            f"date_time between is {between}px on a {baseline}px baseline"
        )
    if width > DIALOG_WIDTH:
        failures.append(f"the dialog took {width}px, over the {DIALOG_WIDTH}px cap")

    return {
        "verdict": (
            f"PASS dialog {width}px, editor {inner}px, date_time between {between}px on a"
            f" {baseline}px baseline"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "dialog": width,
        "editor": inner,
        "baseline": baseline,
        "between": between,
    }
