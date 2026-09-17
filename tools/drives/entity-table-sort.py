"""The toolbar's sort picker, driven the way a reader drives it.

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/entity-table-sort.py
    .venv/bin/python tools/qa.py --page entity-table --headed --drive tools/drives/entity-table-sort.py

The trigger is pressed, the field picker inside the panel is opened, and a field is taken with
the keyboard once and with a press once. A picker inside a popover is the interesting part: the
press lands in a window of its own standing over the panel, and the panel has to survive it.
The verdict reads the picker's own keys, the table's sort, the first row, and the mark the
header draws.

The list only offers the columns the table shows, which is what upstream's
`paths={columns.map((column) => column.path)}` hands it, so the hidden ones are checked too.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget, wait_for  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

#: The columns the demo opens on, and the two it can show but does not.
SHOWN = ("code", "entity", "sg_status_list", "image", "description", "user")
HIDDEN = ("created_at", "updated_at")


def click(widget, point=None) -> None:
    QTest.mouseClick(
        widget,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        widget.rect().center() if point is None else point,
    )


def settled(table) -> bool:
    return table.control.snapshot().status in ("ready", "error")


def codes(table) -> list[str]:
    """The `code` of every row on the page, in the order the table draws them."""
    from sg_widgets_core.collection import cell_value

    return [
        str(cell_value(line.row, "code") or "")
        for line in table.model.lines
        if line.kind == "row"
    ]


def first_code(table) -> str:
    page = codes(table)
    return page[0] if page else ""


def offered(picker) -> list[str]:
    """The paths the field list is showing, which is what `offers` let through."""
    return [row.path for row in picker.field_picker()._model.rows]


def open_list(picker, wait) -> bool:
    """The panel open, its field picker open, and a row in its list."""
    if not picker.open:
        click(picker.trigger())
        wait(300)
    if not picker.open:
        return False
    control = picker.field_picker().control
    if not control.is_open:
        click(control)
    view = control.list_surface()
    return wait_for(lambda: view.model().rowCount() > 0, wait, 8000) and picker.open


def mark(table) -> tuple[str, str]:
    """The column the header marks, and the way the arrow points."""
    header = table._header
    section = header.sortIndicatorSection()
    column = table.model.column_at(section)
    order = header.sortIndicatorOrder()
    way = "desc" if order == QtCore.Qt.SortOrder.DescendingOrder else "asc"
    return ("" if column is None or section < 0 else column.path), way


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-table")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = holder.table
    picker = holder._sort
    if picker is None:
        return {"verdict": "FAIL the toolbar carries no sort picker", "notes": notes}
    if not wait_for(lambda: settled(table) and table.control.rows, wait):
        return {"verdict": "FAIL the table drew no row", "notes": notes}
    images_settled(wait)
    before = first_code(table)
    notes.append(f"first row before any sort: {before}")

    # The list a toolbar's picker offers is the columns its table shows, never every column
    # the demo could show.
    if not open_list(picker, wait):
        return {"verdict": "FAIL the panel did not open with its field list", "notes": notes}
    paths = offered(picker)
    notes.append(f"offered: {paths}")
    if any(path in paths for path in HIDDEN):
        return {
            "verdict": f"FAIL the list offers a column the table does not show: {paths}",
            "notes": notes,
        }
    if "code" not in paths:
        return {"verdict": f'FAIL the list does not offer "code": {paths}', "notes": notes}

    # The first key is taken with a press, which lands in the field picker's own popup: a
    # window of its own standing over the panel. A press there must not read as a press
    # outside the panel, which would shut the panel before the row was ever taken.
    fired: list = []
    picker.sort_changed.connect(fired.append)
    view = picker.field_picker().control.list_surface()
    rows = picker.field_picker()._model.rows
    at = next((i for i, one in enumerate(rows) if one.path == "code"), 0)
    click(view.viewport(), view.visualRect(view.model().index(at, 0)).center())
    wait(400)
    if not picker.open:
        return {"verdict": "FAIL the press in the field list dismissed the panel", "notes": notes}
    if [key.field for key in picker.value] != ["code"]:
        return {"verdict": f"FAIL the press left the picker holding {picker.value}", "notes": notes}
    if len(picker.key_rows().rows()) != 1:
        return {"verdict": "FAIL the panel drew no key row for the press", "notes": notes}
    notes.append("a press added code; the panel stayed open and drew its key row")

    # The demo hands the keys to the table, so the page is read again, sorted.
    if not wait_for(
        lambda: settled(table)
        and [spec.path for spec in table.sort] == ["code"]
        and codes(table)
        and codes(table) == sorted(codes(table)),
        wait,
    ):
        return {
            "verdict": f"FAIL the page is not in code order: {codes(table)[:4]}",
            "notes": notes,
        }
    ascending = codes(table)
    notes.append(f"code ascending: {ascending[:3]} … over {len(ascending)} rows")
    if mark(table) != ("code", "asc"):
        return {"verdict": f"FAIL the header marks {mark(table)}, expected code ascending", "notes": notes}
    notes.append(f"the header marks {mark(table)}")

    # The key row's own toggle turns it over, and the rows and the mark follow. The press is
    # on the descending half of the pair, which is the gesture, not a prop write.
    click(picker.key_rows().rows()[0].direction().toggles()[1])
    if not wait_for(
        lambda: settled(table)
        and codes(table)
        and codes(table) == sorted(codes(table), reverse=True)
        and codes(table)[0] != ascending[0],
        wait,
    ):
        return {
            "verdict": f"FAIL the rows did not turn over on a descending key: {codes(table)[:4]}",
            "notes": notes,
        }
    if mark(table) != ("code", "desc"):
        return {"verdict": f"FAIL the header marks {mark(table)} after a descending key", "notes": notes}
    notes.append(f"descending: {ascending[0]} -> {codes(table)[0]}, the header marks {mark(table)}")
    if before == ascending[0] and before == codes(table)[0]:
        return {"verdict": "FAIL the first row never moved", "notes": notes}

    # And a second key taken with the keyboard: Down to a row, Enter to take it. The panel
    # stays open for it, which is what a list of ordered keys is for.
    if not open_list(picker, wait):
        return {"verdict": "FAIL the field list did not reopen", "notes": notes}
    caret = picker.field_picker().control.caret()
    QTest.keyClick(caret, QtCore.Qt.Key.Key_Down)
    wait(150)
    QTest.keyClick(caret, QtCore.Qt.Key.Key_Return)
    wait(300)
    if not picker.open:
        return {"verdict": "FAIL the panel closed when the key was taken", "notes": notes}
    if len(picker.value) != 2 or picker.value[0].field != "code":
        return {"verdict": f"FAIL Enter left the picker holding {picker.value}", "notes": notes}
    if len(picker.key_rows().rows()) != 2:
        return {
            "verdict": f"FAIL the panel drew {len(picker.key_rows().rows())} key rows, expected 2",
            "notes": notes,
        }
    notes.append(f"Enter added {picker.value[1].field} under it; two key rows drawn")
    notes.append(f"sort_changed fired {len(fired)} times, the picker reads {picker.sort!r}")

    return {
        "verdict": "PASS a key taken by key and by press, the rows re-read, the header marked",
        "notes": notes,
    }
