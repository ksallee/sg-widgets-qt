"""The port of `~/dev/sg-widgets/tools/drives/entity-table.js`.

Change the page size, walk to page 2, sort a header, see no column menu, edit a description in
a popover, then group by status and shut the first heading.

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/entity-table.py

The upstream drive reaches the demo through the DOM; here the same gestures go through the
widget's own API, which is what a caller has.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import click, images_settled, press_key, stage_widget, wait_for  # noqa: E402
from qtpy import QtCore  # noqa: E402

#: The set the mock answers on this page, and the page the demo opens at.
TOTAL = 320
PAGE_SIZE = 25

#: What the drive types into the description cell.
TYPED = "edited in place by qa"


def settled(table) -> bool:
    return table.control.snapshot().status in ("ready", "error")


def cell(table, path: str, line: int = 0):
    at = next(i for i, one in enumerate(table.model.lines) if one.kind == "row")
    return table.model.index(at + line, table.model.column_index_of(path))


def text_of(table, path: str) -> str:
    from sg_widgets_core.collection import cell_value

    at = next(i for i, one in enumerate(table.model.lines) if one.kind == "row")
    return str(cell_value(table.model.lines[at].row, path) or "")


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-table")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = holder.table
    if not wait_for(lambda: settled(table) and table.control.rows, wait):
        return {"verdict": "FAIL the table drew no row", "notes": notes}
    images_settled(wait)

    # The first page of 25, counted by one `summarize` call (020_summarize).
    if not wait_for(lambda: table.control.pager.range_label == f"1 to {PAGE_SIZE} of {TOTAL}", wait):
        return {
            "verdict": f'FAIL the range reads "{table.control.pager.range_label}"',
            "notes": notes,
        }
    notes.append(f'page 1 reads "{table.control.pager.range_label}" over {len(table.control.rows)} rows')

    # Page size: the select reopens the set at the first row. The list is opened and one
    # row taken, which is the gesture a reader makes, not a silent prop write.
    select = table.footer._size_select
    select.open()
    wait(250)
    press_key(select, QtCore.Qt.Key.Key_Down)
    press_key(select, QtCore.Qt.Key.Key_Return)
    wait(250)
    if not wait_for(lambda: table.control.pager.range_label == f"1 to 50 of {TOTAL}", wait):
        return {
            "verdict": f'FAIL after a page size of 50 the range reads "{table.control.pager.range_label}"',
            "notes": notes,
        }
    notes.append(f'page size 50 reads "{table.control.pager.range_label}" over {len(table.control.rows)} rows')

    # Page 2 of the same set, through the footer's own arrow.
    click(table.footer._next)
    if not wait_for(lambda: table.control.pager.range_label == f"51 to 100 of {TOTAL}", wait):
        return {
            "verdict": f'FAIL page 2 reads "{table.control.pager.range_label}"',
            "notes": notes,
        }
    notes.append(f'page 2 reads "{table.control.pager.range_label}"')

    # Sorting goes through the source, so the first row changes and the page reopens.
    before = text_of(table, "code")
    fired: list = []
    table.sort_changed.connect(fired.append)
    table.toggle_sort("code")
    wait_for(lambda: settled(table) and text_of(table, "code") != before, wait)
    after = text_of(table, "code")
    notes.append(f"first row: {before} -> {after}; sort_changed fired {len(fired)} times")
    if not after or after == before:
        return {"verdict": "FAIL the first row did not change after sorting", "notes": notes}
    if len(fired) != 1:
        return {"verdict": f"FAIL sort_changed fired {len(fired)} times, expected once", "notes": notes}

    # The column menu is opt-in and the demo leaves it off.
    if table.column_menu:
        return {"verdict": "FAIL the headers carry a column menu although it is off", "notes": notes}
    notes.append("no column menu on the headers")

    # A description cell opens the field editor in a popover, and Enter writes it back.
    index = cell(table, "description")
    if table.placement_for(table.model.column_at(index.column())) != "popover":
        return {"verdict": "FAIL the description does not edit in a popover", "notes": notes}
    table.on_cell_activated(index)
    if not wait_for(lambda: table._editing is not None, wait, 5000):
        return {"verdict": "FAIL no editor opened on the description cell", "notes": notes}
    held = table._editing
    column = next(one for one in table.columns if one.path == held[1])
    table.commit(held[0], column, TYPED)
    if not wait_for(lambda: text_of(table, "description") == TYPED, wait, 10000):
        return {
            "verdict": f'FAIL the cell reads "{text_of(table, "description")}", expected "{TYPED}"',
            "notes": notes,
        }
    notes.append(f"cell now: {text_of(table, 'description')}")

    # Grouping is over the loaded page, under the order the server produced.
    holder._grouped.set_checked(True)
    # Grouping puts the group path at the head of the sort, so the page is read again: the
    # counts are only worth reading once that read has landed.
    if not wait_for(
        lambda: settled(table)
        and table.model.groups
        and table.control.sort
        and table.control.sort[0].path == "sg_status_list",
        wait,
    ):
        return {"verdict": "FAIL grouping produced no headings", "notes": notes}
    wait(400)
    groups = table.model.groups
    stated = len(groups[0].rows)
    lines = table.model.rowCount()
    notes.append(f"group headings: {len(groups)}, the first states {stated}")
    table._toggle_group(groups[0].key)
    wait(300)
    if table.model.rowCount() != lines - stated:
        return {
            "verdict": f"FAIL collapsing left {table.model.rowCount()} lines, expected {lines - stated}",
            "notes": notes,
        }
    notes.append(f"collapsing the first heading hid {stated} rows")

    return {
        "verdict": "PASS page size, paging, sorting, no column menu, popover edit and grouping",
        "notes": notes,
    }
