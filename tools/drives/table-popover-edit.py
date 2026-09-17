"""The port of `~/dev/sg-widgets/tools/drives/table-popover-edit.js`, with the write contract.

A text cell edits in a popover and a status cell in one too; Escape closes the next one and
leaves the value alone; a commit goes through `context.client.update` on a worker and the row
is read back whole (024_read_after_write); a refused write says why on the cell and keeps the
value the row still holds.

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/table-popover-edit.py
"""
from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget, wait_for  # noqa: E402

from sg_widgets_core.collection import cell_value  # noqa: E402

TYPED = "popover edit by qa"


def settled(table) -> bool:
    return table.control.snapshot().status in ("ready", "error")


def first_line(table) -> int:
    return next(i for i, line in enumerate(table.model.lines) if line.kind == "row")


def cell(table, path: str):
    return table.model.index(first_line(table), table.model.column_index_of(path))


def text_of(table, path: str) -> str:
    return str(cell_value(table.model.lines[first_line(table)].row, path) or "")


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-table")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = holder.table
    if not wait_for(lambda: settled(table) and table.control.rows, wait):
        return {"verdict": "FAIL the table drew no row", "notes": notes}
    images_settled(wait)

    # A text cell opens the editor in a popover, not in the cell.
    index = cell(table, "description")
    column = table.model.column_at(index.column())
    if table.placement_for(column) != "popover":
        return {"verdict": f"FAIL the description opens {table.placement_for(column)!r}", "notes": notes}
    table.on_cell_activated(index)
    if not wait_for(lambda: table._editing is not None, wait, 5000):
        return {"verdict": "FAIL no editor opened on the description cell", "notes": notes}
    editor = table.view.indexWidget(index)
    if editor is None:
        return {"verdict": "FAIL the editor is not on the cell", "notes": notes}
    notes.append(f"the editor opened as {editor.objectName()!r} in {table.placement_for(column)}")

    # The write runs off the GUI thread and the row is read back whole.
    gui = threading.current_thread().ident
    on_thread: list = []
    real = table.context.client.update

    def watched(entity_type, entity_id, patch, *rest, **kwargs):
        on_thread.append(threading.current_thread().ident)
        return real(entity_type, entity_id, patch, *rest, **kwargs)

    table.context.client.update = watched
    before_values = dict(table.model.lines[first_line(table)].row.values)
    held = table._editing
    table.commit(held[0], column, TYPED)
    if not wait_for(lambda: text_of(table, "description") == TYPED, wait, 10000):
        return {"verdict": f'FAIL the cell reads "{text_of(table, "description")}"', "notes": notes}
    if not on_thread or gui in on_thread:
        return {"verdict": "FAIL the write ran on the GUI thread", "notes": notes}
    after_values = dict(table.model.lines[first_line(table)].row.values)
    kept = [key for key in before_values if key not in after_values]
    if kept:
        return {"verdict": f"FAIL the row came back short of {kept}", "notes": notes}
    notes.append(
        f"the write ran off the GUI thread and the row came back with {len(after_values)} fields"
    )

    # Escape closes the next one and leaves the value where it was.
    table.on_cell_activated(cell(table, "description"))
    if not wait_for(lambda: table._editing is not None, wait, 5000):
        return {"verdict": "FAIL the editor did not open again", "notes": notes}
    table.close_editor()
    wait(300)
    if text_of(table, "description") != TYPED:
        return {"verdict": f'FAIL Escape left the cell reading "{text_of(table, "description")}"', "notes": notes}
    notes.append("Escape left the committed value alone")

    # A status cell opens its picker in a popover too.
    status = cell(table, "sg_status_list")
    if table.placement_for(table.model.column_at(status.column())) != "popover":
        return {"verdict": "FAIL the status cell does not open a popover", "notes": notes}
    table.on_cell_activated(status)
    if not wait_for(lambda: table._editing is not None, wait, 5000):
        return {"verdict": "FAIL no editor opened on the status cell", "notes": notes}
    table.close_editor()
    wait(200)
    notes.append("the status cell opened its own editor in a popover")

    # A refused write says why on the cell and keeps the value the row still holds.
    def refuse(*_args, **_kwargs):
        raise RuntimeError("403 Forbidden: qa refused this write")

    table.context.client.update = refuse
    kept_value = text_of(table, "description")
    table.on_cell_activated(cell(table, "description"))
    if not wait_for(lambda: table._editing is not None, wait, 5000):
        return {"verdict": "FAIL the editor did not open for the refused write", "notes": notes}
    held = table._editing
    table.commit(held[0], column, kept_value + " refused")
    if not wait_for(lambda: table.cell_error(held[0], "description"), wait, 10000):
        return {"verdict": "FAIL the refused write said nothing on the cell", "notes": notes}
    if text_of(table, "description") != kept_value:
        return {"verdict": "FAIL the refused write was kept on the row", "notes": notes}
    notes.append(f"the refused write reads {table.cell_error(held[0], 'description')!r} and kept the value")

    return {
        "verdict": (
            "PASS a text cell and a status cell both edit in a popover, a commit writes off the "
            "GUI thread and re-reads the row, and a refused write says why and keeps the value"
        ),
        "notes": notes,
    }
