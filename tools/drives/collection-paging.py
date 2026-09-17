"""The port of `~/dev/sg-widgets/tools/drives/collection-paging.js`.

The three paging modes on the table demo: the scroller appends a page and says so with a loading
row, ArrowDown on the last row appends one and keeps the cursor, and a group that spans a page
boundary stays one group.

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/collection-paging.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget, wait_for  # noqa: E402
from qtpy import QtCore, QtGui  # noqa: E402

PAGE_SIZE = 25


def settled(table) -> bool:
    return table.control.snapshot().status in ("ready", "error")


def last_row_line(table) -> int:
    return max(i for i, line in enumerate(table.model.lines) if line.kind == "row")


def key(table, code) -> None:
    table.on_body_key(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), QtCore.Qt.KeyboardModifier.NoModifier)
    )


def group_counts(table) -> dict:
    return {group.key: len(group.rows) for group in table.model.groups}


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-table")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = holder.table
    if not wait_for(lambda: settled(table) and table.control.rows, wait):
        return {"verdict": "FAIL the table drew no row", "notes": notes}
    images_settled(wait)
    if table.control.pager.range_label != f"1 to {PAGE_SIZE} of 320":
        return {
            "verdict": f'FAIL it opened on "{table.control.pager.range_label}"',
            "notes": notes,
        }
    notes.append(f'pages reads "{table.control.pager.range_label}"')

    # --- scroll -------------------------------------------------------------------------
    holder._paging["scroll"].set_checked(True)
    if not wait_for(lambda: settled(table) and table.control.bottom() == "sentinel", wait):
        return {"verdict": f"FAIL scroll draws {table.control.bottom()!r}", "notes": notes}
    wait(400)
    if table.footer._pager_box.isVisible():
        return {"verdict": "FAIL the pager stayed up in scroll mode", "notes": notes}
    before = len(table.control.rows)
    seen_loading = []
    table.control.changed.connect(
        lambda: seen_loading.append(1) if table.control.bottom() == "loading" else None
    )
    table.control.on_last_visible(before - 1)
    if not wait_for(lambda: len(table.control.rows) > before, wait):
        return {"verdict": "FAIL scrolling to the end loaded no page", "notes": notes}
    if len(table.control.rows) != before + PAGE_SIZE:
        return {
            "verdict": f"FAIL scrolling left {len(table.control.rows)} rows, expected {before + PAGE_SIZE}",
            "notes": notes,
        }
    if table.control.bottom() == "loading":
        return {"verdict": "FAIL the loading row stayed up after the page landed", "notes": notes}
    notes.append(
        f"the scroller added {PAGE_SIZE} rows, "
        f"loading row {'seen and gone' if seen_loading else 'not drawn'}, "
        f'"{table.control.pager.loaded_label}"'
    )

    # --- more, from the keyboard --------------------------------------------------------
    holder._paging["more"].set_checked(True)
    if not wait_for(lambda: settled(table) and table.control.bottom() == "more", wait):
        return {"verdict": f"FAIL more draws {table.control.bottom()!r}", "notes": notes}
    held = len(table.control.rows)
    last = last_row_line(table)
    column = table.model.column_index_of("description")
    table.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    # The table keeps its own cell cursor, so it is put on the last row the way a press
    # would put it, not through the view's selection model.
    table._focus_row(held - 1, column)
    wait(150)
    del last
    cursor_before = table.control.active
    key(table, QtCore.Qt.Key.Key_Down)
    # Until the page lands the cursor is where it started; after it lands, on the first row
    # of the page. Nowhere else, at any moment in between.
    strayed = ""
    for _ in range(200):
        at = table.control.active
        if at not in (cursor_before, held):
            strayed = str(at)
            break
        if len(table.control.rows) > held:
            break
        wait(20)
    if strayed:
        return {"verdict": f"FAIL the cursor moved to {strayed} rather than holding it", "notes": notes}
    if not wait_for(lambda: len(table.control.rows) > held, wait):
        return {"verdict": "FAIL ArrowDown on the last row loaded no page", "notes": notes}
    wait(400)
    if table.control.active != held:
        return {
            "verdict": f"FAIL the cursor landed on {table.control.active}, expected {held}",
            "notes": notes,
        }
    if table.cursor_index().column() != column:
        return {"verdict": "FAIL the cursor left the column it started in", "notes": notes}
    notes.append(
        f"ArrowDown added {len(table.control.rows) - held} rows and landed on row {table.control.active}"
    )

    # --- groups across a page boundary ---------------------------------------------------
    holder._grouped.set_checked(True)
    if not wait_for(
        lambda: settled(table)
        and table.model.groups
        and table.control.sort
        and table.control.sort[0].path == "sg_status_list",
        wait,
    ):
        return {"verdict": "FAIL grouping drew no heading", "notes": notes}
    wait(400)
    opening = group_counts(table)
    rows_before = len(table.control.rows)
    notes.append(f"{len(opening)} groups over {rows_before} rows")
    table.control.load_more()
    if not wait_for(lambda: settled(table) and len(table.control.rows) > rows_before, wait):
        return {"verdict": "FAIL the load-more row loaded no page", "notes": notes}
    wait(400)
    after = group_counts(table)
    if len(after) != len(set(after)):
        return {"verdict": "FAIL a page opened a second group of the same key", "notes": notes}
    missing = [key_ for key_ in opening if key_ not in after]
    if missing:
        return {"verdict": f"FAIL lost the group {missing[0]!r} over a page boundary", "notes": notes}
    counted = sum(after.values())
    if counted != len(table.control.rows):
        return {
            "verdict": f"FAIL the groups state {counted} rows against {len(table.control.rows)} loaded",
            "notes": notes,
        }
    grown = [key_ for key_, count in after.items() if key_ in opening and count > opening[key_]]
    if not grown:
        return {"verdict": "FAIL no group grew over the page boundary", "notes": notes}
    notes.append(
        f"{len(after)} groups over {len(table.control.rows)} rows, {grown[0]!r} grew across the boundary"
    )

    return {
        "verdict": "PASS the scroller, ArrowDown and a grouped table all append a page",
        "notes": notes,
    }
