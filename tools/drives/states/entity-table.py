"""The entity table's state matrix, one state per `QA_STATE`.

The upstream half of each state is `tools/drives/upstream/entity-table-<state>.js`, run against
`/widgets/entity-table/`; the states the upstream demo has no case for (`empty`, `loading`,
`error`, `failed`) are this port's own and say so below.

    QA_STATE=grouped .venv/bin/python tools/qa.py --page entity-table \\
        --drive tools/drives/states/entity-table.py --shot shots/states/entity-table-grouped.png

    pages         the first page of 25, the footer reading the range
    more          the set walked with a load-more row
    scroll        the set walked by the scroller, with the sentinel
    sorted        sorted by a header, the mark on that column
    row-selected  one row taken
    all-selected  every loaded row taken, the header box full
    tri-state     every row but one taken, the header box mixed
    hovered       the pointer on a row, and on a sortable header
    popover-edit  a description cell editing in a popover
    inline-edit   the same cell editing in the cell
    committed     an edit written back, the cell reading the new value
    failed        a refused write, the old value kept and the reason on the cell
    grouped       grouped by status, every heading open
    group-collapsed  the first heading shut
    collapsed-all    every heading shut, and the mode that holds over a page
    compact       the row padding halved
    columns-open  the column picker open in the toolbar
    sort-open     the sort picker open in the toolbar
    empty         a filter no row answers
    loading       the first read still in flight
    error         a read that failed, with its retry
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _collection_states import (  # noqa: E402
    click,
    frame,
    images_settled,
    stage_widget,
    state_name,
    wait_for,
)
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_core.client import EntityRef  # noqa: E402
from sg_widgets_core.collection_state import collapse_all  # noqa: E402
from sg_widgets_core.filter import condition  # noqa: E402

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = (
    "pages",
    "more",
    "scroll",
    "sorted",
    "row-selected",
    "all-selected",
    "tri-state",
    "hovered",
    "popover-edit",
    "inline-edit",
    "committed",
    "failed",
    "grouped",
    "group-collapsed",
    "collapsed-all",
    "compact",
    "columns-open",
    "sort-open",
    "empty",
    "loading",
    "error",
)

#: What a cell edited by this drive is left reading.
TYPED = "edited in place by qa"


def demo(page):
    return stage_widget(page, "entity-table")


def rows_of(table) -> list:
    return list(table.control.rows)


def settled(table) -> bool:
    return table.control.snapshot().status in ("ready", "error")


def described(table) -> dict:
    control = table.control
    pager = control.pager
    return {
        "rows": len(control.rows),
        "columns": [column.path for column in table.columns],
        "range": pager.range_label,
        "loaded": pager.loaded_label,
        "page": pager.page,
        "page_count": pager.page_count,
        "bottom": control.bottom(),
        "view": control.view(len(control.rows)),
        "selection": len(table.selection),
        "sort": [(spec.path, spec.descending) for spec in control.sort],
        "group_by": table.group_by,
        "density": table.density,
        "paging": table.paging,
    }


def first_row_line(table) -> int:
    for at, line in enumerate(table.model.lines):
        if line.kind == "row":
            return at
    return -1


def column_at(table, path: str) -> int:
    for at, column in enumerate(table.columns):
        if column.path == path:
            return at
    return -1


def cell(table, path: str, line: int = -1) -> QtCore.QModelIndex:
    row = first_row_line(table) if line < 0 else line
    return table.model.index(row, column_at(table, path))


def editor_open(table) -> bool:
    return table.findChild(QtWidgets.QWidget, "entity-table-editor") is not None or bool(
        [w for w in QtWidgets.QApplication.topLevelWidgets() if w.isVisible() and w.width() > 1]
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    state = state_name(STATES, "pages")
    wait(200)
    holder = demo(page)
    if holder is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = holder.table
    if not wait_for(lambda: settled(table) and rows_of(table), wait):
        return {"verdict": f"FAIL the first page never landed: {described(table)}"}
    images_settled(wait)
    frame(page, wait, "entity-table")

    answer = _reach(state, page, wait, holder, table)
    if answer is not None:
        return answer
    wait(300)
    return {"verdict": f"PASS {state}", "state": state, "table": described(table)}


def _reach(state, page, wait, holder, table):  # noqa: C901
    """Put the page in `state`, or answer a FAIL saying why it could not."""
    if state == "pages":
        if table.control.pager.range_label != "1 to 25 of 320":
            return {"verdict": f"FAIL the range reads {table.control.pager.range_label!r}"}
        return None

    if state in ("more", "scroll"):
        holder._paging[state].set_checked(True)
        wait(400)
        wait_for(lambda: settled(table), wait)
        wanted = "more" if state == "more" else "sentinel"
        if table.control.bottom() != wanted:
            return {"verdict": f"FAIL {state} draws {table.control.bottom()!r} under the rows"}
        return None

    if state == "sorted":
        before = table.control.rows[0].id
        table.toggle_sort("code")
        wait_for(lambda: settled(table) and table.control.rows[0].id != before, wait)
        if not table.control.sort or table.control.sort[0].path != "code":
            return {"verdict": f"FAIL the sort reads {table.control.sort}"}
        return None

    if state in ("row-selected", "all-selected", "tri-state"):
        table.control.toggle_all(True)
        if state == "row-selected":
            first = table.control.rows[0]
            table.control.set_selection([EntityRef(type=first.type, id=first.id)])
        if state == "tri-state":
            table.control.toggle(table.control.rows[0])
        wait(200)
        picked = len(table.selection)
        loaded = len(table.control.rows)
        wanted = {"row-selected": 1, "all-selected": loaded, "tri-state": loaded - 1}[state]
        if picked != wanted:
            return {"verdict": f"FAIL {state} took {picked} rows of {loaded}, expected {wanted}"}
        return None

    if state == "hovered":
        index = cell(table, "code")
        rect = table.view.visualRect(index)
        QtWidgets.QApplication.sendEvent(
            table.view.viewport(),
            QtGui_mouse_move(rect.center()),
        )
        wait(250)
        if table.view.hovered_row() != index.row():
            return {"verdict": "FAIL the pointer did not light a row"}
        return None

    if state in ("popover-edit", "inline-edit", "committed", "failed"):
        return _edit(state, wait, holder, table)

    if state in ("grouped", "group-collapsed", "collapsed-all"):
        holder._grouped.set_checked(True)
        wait(400)
        if not wait_for(lambda: settled(table) and table.model.groups, wait):
            return {"verdict": "FAIL grouping drew no heading"}
        if state == "group-collapsed":
            table._toggle_group(table.model.groups[0].key)
            wait(200)
        if state == "collapsed-all":
            table.set_collapsed(collapse_all())
            wait(200)
            if table.model.rowCount() != len(table.model.groups):
                return {"verdict": "FAIL Collapse all left rows on the table"}
        return None

    if state == "compact":
        holder._compact.set_checked(True)
        wait(300)
        if table.density != "compact":
            return {"verdict": f"FAIL the density reads {table.density!r}"}
        return None

    if state == "columns-open":
        holder._columns_toggle.set_checked(True)
        wait(400)
        if not holder._picker.isVisible():
            return {"verdict": "FAIL the column picker stayed shut"}
        return None

    if state == "sort-open":
        if holder._sort is None:
            return {"verdict": "FAIL the toolbar carries no sort picker"}
        click(holder._sort)
        wait(500)
        if not holder._sort.open:
            return {"verdict": "FAIL the sort picker stayed shut"}
        return None

    if state in ("empty", "loading", "error"):
        return _state_block(state, wait, table)

    return {"verdict": f"FAIL the drive has no {state}"}


def _edit(state, wait, holder, table):
    """Open a cell's editor, and for the two write states let the write land or fail."""
    if state == "inline-edit":
        holder._placement["inline"].set_checked(True)
        wait(300)
    if state == "failed":
        _refuse_writes(table)
    index = cell(table, "description")
    table.on_cell_activated(index)
    if not wait_for(lambda: table._editing is not None, wait, 4000):
        return {"verdict": f"FAIL {state} opened no editor on the description cell"}
    if state in ("popover-edit", "inline-edit"):
        placement = table.placement_for(table.columns[index.column()])
        wanted = "popover" if state == "popover-edit" else "inline"
        if placement != wanted:
            return {"verdict": f"FAIL {state} opened {placement!r}"}
        return None

    held = table._editing
    column = next(c for c in table.columns if c.path == held[1])
    table.commit(held[0], column, TYPED)
    if state == "committed":
        if not wait_for(lambda: _cell_text(table, index) == TYPED, wait, 8000):
            return {"verdict": f"FAIL the cell reads {_cell_text(table, index)!r}, not {TYPED!r}"}
        return None
    if not wait_for(lambda: table.cell_error(*_key_of(table, index)), wait, 8000):
        return {"verdict": "FAIL the refused write said nothing on the cell"}
    if _cell_text(table, index) == TYPED:
        return {"verdict": "FAIL the refused write was kept on the row"}
    return None


def _key_of(table, index):
    line = table.model.lines[index.row()]
    return table.control.row_id(line.row), table.columns[index.column()].path


def _cell_text(table, index) -> str:
    from sg_widgets_core.collection import cell_value

    line = table.model.lines[index.row()]
    return str(cell_value(line.row, table.columns[index.column()].path) or "")


def _refuse_writes(table) -> None:
    """Make the next write answer 403, which is what an armed failure does upstream."""
    client = table.context.client

    def refuse(*_args, **_kwargs):
        raise RuntimeError("403 Forbidden: qa refused this write")

    client.update = refuse  # type: ignore[assignment]


def _state_block(state, wait, table):
    if state == "empty":
        table.set_filters(condition("code", "is", "no such version"))
        wait_for(lambda: table.control.view(len(table.control.rows)) == "empty", wait)
        if table.control.view(len(table.control.rows)) != "empty":
            return {"verdict": "FAIL the empty filter still drew rows"}
        return None
    if state == "loading":
        table.set_filters(condition("code", "contains", "sh0"))
        wait(60)
        if table.control.snapshot().status != "loading":
            return {"verdict": "FAIL the read was over before the shot"}
        return None
    _break_reads(table)
    table.set_filters(condition("code", "contains", "sh01"))
    wait_for(lambda: table.control.snapshot().status == "error", wait)
    if table.control.snapshot().status != "error":
        return {"verdict": "FAIL the read did not fail"}
    return None


def _break_reads(table) -> None:
    client = table.context.client

    def fail(*_args, **_kwargs):
        raise RuntimeError("503 Service Unavailable: qa broke this read")

    client.search = fail  # type: ignore[assignment]


def QtGui_mouse_move(point):  # noqa: N802
    """A move event at `point`, spelled once so the hover state has one source."""
    from qtpy import QtGui

    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(point),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
