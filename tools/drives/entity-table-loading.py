"""entity-table: a re-read, with the blank rows standing in for the rows they replace.

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/entity-table-loading.py
    .venv/bin/python tools/qa.py --page entity-table --dark --drive tools/drives/entity-table-loading.py

The stage is handed a slow context so the read is still in flight when the shot is taken. `--shot`
is no use here: the driver lets the reads in flight land before it grabs, and the blank rows are
gone by then, so the drive grabs the window itself and says where it put it. The verdict reads the
header, the count of blank rows and the body's room before and during the read: a re-read keeps the
box the rows stood in, so nothing under the table moves.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from pathlib import Path  # noqa: E402

from _collection_states import wait_for  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

#: How long the mock holds a read, so the shot lands while it is in flight.
LATENCY_MS = 1500


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.showcase.context import demo_context

    stage = page.stage("entity-table")
    if stage is None:
        return {"verdict": "FAIL the page carries no entity-table stage"}
    stage.set_context(demo_context(latency_ms=LATENCY_MS))
    ready = wait_for(
        lambda: getattr(stage.widget, "table", None) is not None
        and bool(stage.widget.table.control.rows)
        and len(stage.widget.table.columns) > 1,
        wait,
        30000,
    )
    if not ready:
        return {"verdict": "FAIL the slow context drew no row"}
    table = stage.widget.table
    held = table.view.height()
    header = table._header
    at = table.model.select_offset
    QTest.mouseClick(
        header.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(
            header.sectionViewportPosition(at) + header.sectionSize(at) // 2, header.height() // 2
        ),
    )
    wait(60)
    box = table.view.height() + table._skeleton.height()
    if table.control.snapshot().status != "loading":
        return {"verdict": "FAIL the read had already landed"}
    if not table._header.isVisible():
        return {"verdict": "FAIL the header left with the rows"}
    if box != held:
        return {"verdict": f"FAIL the box moved, {held} to {box}"}
    dark = getattr(prefs, "theme", "") == "dark"
    target = Path("shots") / "states" / f"entity-table-loading-{'dark' if dark else 'light'}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    page.window().grab().save(str(target))
    return {
        "verdict": f"PASS {table._skeleton.rows} blank rows under the header, the box still {box}",
        "columns": table.model.columnCount(),
        "bars": len(table._skeleton.blocks()),
        "shot": str(target),
    }
