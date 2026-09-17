"""entity-table: one column pinned to the start, with the body scrolled under it.

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/entity-table-pinned.py \
        --shot shots/states/entity-table-pinned-light.png
    .venv/bin/python tools/qa.py --page entity-table --dark --drive tools/drives/entity-table-pinned.py \
        --shot shots/states/entity-table-pinned-dark.png

The state has no twin under `tools/drives/upstream/`: the upstream demo leaves `columnMenu` off,
so nothing on that page can pin a column.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget, wait_for  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    demo = stage_widget(page, "entity-table")
    if demo is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = demo.table
    if not wait_for(lambda: bool(table.control.rows), wait):
        return {"verdict": "FAIL the table drew no row"}
    images_settled(wait)

    table.set_column_menu(True)
    pinned = table.column_order[1]
    table.pin_column(pinned)
    wait(300)
    across = table.view.horizontalScrollBar()
    across.setValue(across.maximum())
    wait(400)
    if not table.frozen.isVisible():
        return {"verdict": "FAIL the frozen column is not on show"}
    if not table.body_scrolled():
        return {"verdict": "FAIL the body did not run under the frozen column"}
    return {
        "verdict": f"PASS {pinned} holds the start at x {table.frozen.x()}",
        "order": table.column_order,
        "pinned": table.pinned_columns,
        "scrolled": [across.value(), across.maximum()],
    }
