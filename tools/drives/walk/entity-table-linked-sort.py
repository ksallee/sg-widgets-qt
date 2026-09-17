"""entity-table-linked-sort: the toolbar offers the columns it shows, a linked one included.

The sort control's field list is the table's own columns, flat: no descending and no
breadcrumb. The linked column is taken as a key and the page comes back in that order.

The port of `tools/drive/entity-table-linked-sort.js`.

    .venv/bin/python tools/qa.py --headed --page entity-table --drive tools/drives/walk/entity-table-linked-sort.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _walk import Walk, press, settled, stage, wait_until  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

#: The column the table shows through a link, which the nested list would have to walk to.
LINKED = "entity.Shot.sg_turnover_date"


def column(table) -> list[str]:
    """The linked column of every row on the page, in the order the table draws them."""
    from sg_widgets_core.collection import cell_value

    return [
        str(cell_value(line.row, LINKED) or "")
        for line in table.model.lines
        if line.kind == "row"
    ]


def open_list(picker, wait) -> bool:
    """The panel open, its field picker open, and a row in its list."""
    if not picker.open:
        press(picker.trigger())
        wait(300)
    if not picker.open:
        return False
    control = picker.field_picker().control
    if not control.is_open:
        press(control)
    return wait_until(lambda: control.list_surface().model().rowCount() > 0, wait, 8000)


def labels_of(picker) -> list[str]:
    """What the flat list is showing, read as a reader reads it."""
    return [row.display_name for row in picker.field_picker().rows_model.rows]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk("entity-table-linked-sort")
    holder = stage(page, "entity-table")
    if not walk.check("the page built its table demo", holder is not None):
        return walk.verdict("nothing to walk")
    table = holder.table
    picker = holder._sort  # noqa: SLF001
    if not walk.check("the toolbar carries a sort control", picker is not None):
        return walk.verdict("nothing to walk")

    walk.check(
        "the table draws its rows",
        wait_until(lambda: settled(table.control, wait) and bool(table.control.rows), wait),
        len(table.control.rows),
    )
    shown = [one.path for one in table.columns]
    walk.check("the table shows the linked column", LINKED in shown, shown)

    # --- the list the toolbar offers ---------------------------------------------------
    if not walk.check("the panel opens with its field list", open_list(picker, wait)):
        return walk.verdict("the field list never opened")
    inner = picker.field_picker()
    offered = [row.path for row in inner.rows_model.rows]
    walk.check("the list is the columns the table shows", offered == shown, offered)
    walk.check(
        "the linked column is on the list, named through its link",
        any("Turnover Date" in label for label in labels_of(picker)),
        labels_of(picker),
    )
    walk.check(
        "the list is flat: no row descends",
        all(not row.traversable for row in inner.rows_model.rows),
        [row.path for row in inner.rows_model.rows if row.traversable],
    )
    walk.check(
        "the list is flat: no breadcrumb",
        not inner.levels.deep and not inner.breadcrumb.isVisible(),
        (inner.levels.deep, inner.breadcrumb.isVisible()),
    )

    # --- the linked column becomes a key ------------------------------------------------
    at = next((i for i, row in enumerate(inner.rows_model.rows) if row.path == LINKED), -1)
    if not walk.check("the linked row is there to take", at >= 0, at):
        return walk.verdict("the linked column was never offered")
    # The press lands in the field list's own popup, a window standing over the panel: the
    # panel has to survive it, which is the interesting part of a picker inside a popover.
    view = inner.control.list_surface()
    index = view.model().index(at, 0)
    view.scrollTo(index, view.ScrollHint.EnsureVisible)
    QTest.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        view.visualRect(index).center(),
    )
    wait(400)
    keys = [key.field for key in picker.value]
    walk.check("the press takes the linked column as a key", keys == [LINKED], keys)
    walk.check("the press left the panel open", picker.open, picker.open)
    walk.check(
        "the key it just took is off the list",
        LINKED not in [row.path for row in inner.rows_model.rows],
        [row.path for row in inner.rows_model.rows],
    )

    # --- the page comes back in that order ----------------------------------------------
    walk.check(
        "the table is read again on the linked key",
        wait_until(
            lambda: settled(table.control, wait)
            and [spec.path for spec in table.sort] == [LINKED],
            wait,
        ),
        [spec.path for spec in table.sort],
    )
    dates = [text for text in column(table) if text]
    walk.check(
        "the rows come back in that column's order",
        len(dates) > 1 and dates == sorted(dates),
        dates[:4],
    )
    return walk.verdict("the toolbar sorted the table on a linked column")
