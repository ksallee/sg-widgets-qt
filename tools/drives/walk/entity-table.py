"""The entity-table page, walked the way a reader walks it.

The select-all box and the row boxes against the count line, the column picker's add, remove,
reorder and close, the page size and the arrows, the popover and the inline editor committing
and cancelling, the cursor and Space, grouping with its collapse and expand, compact, the three
paging modes and the wheel at the bottom edge.

The header's own sort mark is left to `tools/drives/sort-picker-order.py` and to the drive of
the sort control beside it.

    .venv/bin/python tools/qa.py --headed --page entity-table --drive tools/drives/walk/entity-table.py

A popup dismissing, the focus and the wheel's owner are what a real window decides, so
this drive is run headed; offscreen is for the unit tests.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _walk import Walk, press, settled, stage, wait_until, wheel  # noqa: E402
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

Qt = QtCore.Qt

TOTAL = 320
PAGE_SIZE = 25

#: What the walk types into a description cell, and what it must read after a cancel.
TYPED = "walked by qa"


def tops() -> list[str]:
    return [
        w.objectName() or type(w).__name__
        for w in QtWidgets.QApplication.topLevelWidgets()
        if w.isVisible() and w.objectName() != "showcase"
    ]


def first_row_line(table) -> int:
    return next(i for i, line in enumerate(table.model.lines) if line.kind == "row")


def cell(table, path: str):
    return table.model.index(first_row_line(table), table.model.column_index_of(path))


def text_at(table, path: str) -> str:
    from sg_widgets_core.collection import cell_value

    return str(cell_value(table.model.lines[first_row_line(table)].row, path) or "")


def head_press(table, column: int) -> None:
    header = table._header
    point = QtCore.QPoint(
        header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
        header.height() // 2,
    )
    QTest.mouseClick(
        header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )


def body_key(table, code) -> None:
    table.view.keyPressEvent(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), Qt.KeyboardModifier.NoModifier)
    )


def escape(widget) -> None:
    QtWidgets.QApplication.sendEvent(
        widget,
        QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress, int(Qt.Key.Key_Escape), Qt.KeyboardModifier.NoModifier
        ),
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0915
    walk = Walk("entity-table")
    demo = stage(page, "entity-table")
    if demo is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = demo.table
    control = table.control
    if not wait_until(lambda: demo.demo_ready, wait, 30000):
        return {"verdict": "FAIL the table drew no row"}
    settled(control, wait)

    # --- the boxes and the count line ---------------------------------------------------
    head_press(table, 0)
    wait(250)
    walk.check(
        "the header's box takes every loaded row",
        len(table.selection) == len(control.rows) and demo._count.text().startswith(str(PAGE_SIZE)),
        demo._count.text(),
    )
    walk.check(
        "and the box draws itself full",
        table._header._all,
        table._header._all,
    )
    head_press(table, 0)
    wait(250)
    walk.check(
        "pressing it again drops them all",
        not table.selection and demo._count.text() == "0 selected",
        demo._count.text(),
    )
    box = table.view.visualRect(table.model.index(first_row_line(table), 0))
    QTest.mouseClick(
        table.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, box.center()
    )
    wait(250)
    walk.check(
        "a row box takes one row",
        len(table.selection) == 1 and demo._count.text() == "1 selected",
        demo._count.text(),
    )
    walk.check(
        "and the header's box goes partial",
        table._header._some and not table._header._all,
        f"all {table._header._all}, some {table._header._some}",
    )
    head_press(table, 0)
    wait(250)
    head_press(table, 0)
    wait(250)

    # --- the column picker --------------------------------------------------------------
    toggle = find("columns-toggle")
    press(toggle)
    wait(300)
    walk.check("the Columns toggle opens the picker", demo._picker.isVisible())
    chosen = demo._picker.chosen_list
    opening = [column.path for column in table.columns]
    chosen.setFocus(Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(opening.index("user"))
    QTest.keyClick(chosen, Qt.Key.Key_Delete)
    wait_until(lambda: [c.path for c in table.columns] != opening, wait, 10000)
    wait(300)
    walk.check(
        "Delete on a chosen column takes it off the table",
        "user" not in [column.path for column in table.columns],
        [column.path for column in table.columns],
    )
    held = [column.path for column in table.columns]
    chosen.setFocus(Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(2)
    QTest.keyClick(chosen, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    wait_until(lambda: [c.path for c in table.columns] == list(demo._picker.value), wait, 10000)
    wait(300)
    moved = [column.path for column in table.columns]
    walk.check(
        "Alt with an arrow moves a column and the header follows",
        moved != held and moved == list(demo._picker.value),
        moved,
    )
    # The field picker's pick is what the popup emits when a field is taken from the list.
    demo._picker.field_picker.value_changed.emit("user")
    wait_until(lambda: "user" in [c.path for c in table.columns], wait, 10000)
    wait(300)
    walk.check(
        "picking a field adds the column back, at the end",
        [c.path for c in table.columns] == [*moved, "user"],
        [c.path for c in table.columns],
    )
    press(toggle)
    wait(200)
    walk.check("the toggle shuts the picker", not demo._picker.isVisible())

    # --- the filter bar's facets ---------------------------------------------------------
    facets = demo._filters
    walk.check(
        "the filter bar offers the status pill",
        facets.pill("sg_status_list") is not None,
        list(facets.pills().keys()),
    )
    values = facets.facet_list("sg_status_list")
    walk.check("and the facet counted its values", bool(values and values.values))

    # --- the footer ----------------------------------------------------------------------
    walk.check(
        "the footer reads the first page",
        control.pager.range_label == f"1 to {PAGE_SIZE} of {TOTAL}",
        control.pager.range_label,
    )
    select = table.footer._size_select
    select.open()
    wait(250)
    QTest.keyClick(select, Qt.Key.Key_Down)
    QTest.keyClick(select, Qt.Key.Key_Return)
    settled(control, wait)
    wait(200)
    walk.check(
        "the page size select reopens the set",
        control.pager.range_label == f"1 to 50 of {TOTAL}",
        control.pager.range_label,
    )
    press(table.footer._next)
    settled(control, wait)
    wait(200)
    walk.check(
        "the next arrow pages forward",
        control.pager.range_label == f"51 to 100 of {TOTAL}",
        control.pager.range_label,
    )
    press(table.footer._previous)
    settled(control, wait)
    wait(200)
    walk.check(
        "the previous arrow pages back",
        control.pager.range_label == f"1 to 50 of {TOTAL}",
        control.pager.range_label,
    )

    # --- the editors ----------------------------------------------------------------------
    for placement in ("popover", "inline"):
        press(find(f"placement-{placement}"))
        wait(250)
        walk.check(f"the {placement} toggle moves the editor", table.editor_placement == placement)
        before = text_at(table, "description")
        index = cell(table, "description")
        rect = table.view.visualRect(index)
        QTest.mouseDClick(
            table.view.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            rect.center(),
        )
        wait(500)
        walk.check(
            f"a double-click opens the {placement} editor",
            table._editing is not None,
            tops() or "in the cell",
        )
        editor = table.view.indexWidget(cell(table, "description"))
        if not walk.check(
            f"the {placement} editor stands on the cell it was opened on", editor is not None
        ):
            return walk.verdict("")
        escape(editor)
        wait(600)
        walk.check(
            f"Escape cancels the {placement} editor and keeps the value",
            table._editing is None and text_at(table, "description") == before,
            f"{text_at(table, 'description')!r}",
        )
        walk.check(f"and leaves no {placement} popup standing", not tops(), tops())

        table.on_cell_activated(cell(table, "description"))
        wait(500)
        walk.check(f"the {placement} editor opens again", table._editing is not None)
        QTest.mouseClick(
            table.view.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QtCore.QPoint(5, table.view.viewport().rect().bottom() - 5),
        )
        settled(control, wait)
        wait(600)
        walk.check(
            f"a press outside the {placement} editor closes it and leaves nothing standing",
            table._editing is None and not tops(),
            tops(),
        )

        table.view.setFocus(Qt.FocusReason.TabFocusReason)
        table._focus_row(0, table.model.column_index_of("description"))
        wait(150)
        body_key(table, Qt.Key.Key_Return)
        wait(500)
        walk.check(f"Enter opens the {placement} editor", table._editing is not None)
        key, path = table._editing
        column = next(one for one in table.columns if one.path == path)
        table.commit(key, column, TYPED)
        wait_until(lambda: text_at(table, "description") == TYPED, wait, 10000)
        wait(300)
        walk.check(
            f"and the {placement} editor writes the cell",
            text_at(table, "description") == TYPED,
            text_at(table, "description"),
        )
        table.commit(key, column, before)
        wait_until(lambda kept=before: text_at(table, "description") == kept, wait, 10000)

    # --- the cursor -------------------------------------------------------------------------
    press(find("placement-popover"))
    wait(200)
    table.view.setFocus(Qt.FocusReason.TabFocusReason)
    table._focus_row(0, 1)
    body_key(table, Qt.Key.Key_Down)
    body_key(table, Qt.Key.Key_Down)
    body_key(table, Qt.Key.Key_Up)
    wait(200)
    walk.check(
        "the arrows walk the cursor down the same column",
        table.model.row_index_of_line(table.cursor_index().row()) == 1
        and table.cursor_index().column() == 1,
        table.model.row_index_of_line(table.cursor_index().row()),
    )
    taken = len(table.selection)
    body_key(table, Qt.Key.Key_Space)
    wait(200)
    walk.check(
        "Space takes the row under the cursor",
        len(table.selection) == taken + 1,
        demo._count.text(),
    )
    body_key(table, Qt.Key.Key_Space)
    wait(200)

    # --- grouping ------------------------------------------------------------------------
    press(find("group-by-status"))
    settled(control, wait)
    wait(500)
    walk.check("grouping by status draws headings", bool(table.model.groups), len(table.model.groups))
    walk.check(
        "and the collapse and expand buttons wake up",
        find("collapse-all").isEnabled() and find("expand-all").isEnabled(),
    )
    lines = table.model.rowCount()
    press(find("collapse-all"))
    wait(300)
    walk.check(
        "Collapse all leaves the headings alone",
        table.model.rowCount() == len(table.model.groups),
        f"{lines} -> {table.model.rowCount()} lines",
    )
    press(find("expand-all"))
    wait(300)
    walk.check("Expand all puts the rows back", table.model.rowCount() == lines, table.model.rowCount())
    heading = next(i for i, line in enumerate(table.model.lines) if line.kind == "heading")
    rect = table.view.visualRect(table.model.index(heading, 0))
    QTest.mouseClick(
        table.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center()
    )
    wait(300)
    walk.check(
        "a press on one heading shuts that group alone",
        0 < table.model.rowCount() < lines,
        f"{lines} -> {table.model.rowCount()} lines",
    )
    press(find("group-by-status"))
    settled(control, wait)
    wait(300)
    walk.check("ungrouping puts the flat list back", not table.model.groups)

    # --- compact -------------------------------------------------------------------------
    press(find("compact"))
    wait(250)
    walk.check("Compact halves the row padding", table.density == "compact", table.density)
    press(find("compact"))
    wait(250)
    walk.check("and stands back up", table.density == "default", table.density)

    # --- the paging modes and the wheel ---------------------------------------------------
    press(find("paging-more"))
    settled(control, wait)
    wait(300)
    walk.check(
        "load more draws its own row and no pager",
        control.bottom() == "more" and not table.footer._pager_box.isVisible(),
        control.pager.loaded_label,
    )
    held_rows = len(control.rows)
    table._bottom.more_requested.emit()
    settled(control, wait)
    wait(300)
    walk.check(
        "the load-more row appends a page",
        len(control.rows) > held_rows,
        f"{held_rows} -> {len(control.rows)}",
    )
    bar = table.view.verticalScrollBar()
    bar.setValue(bar.maximum())
    wait(100)
    kept = [wheel(table.view) for _ in range(3)]
    walk.check("a gesture at the bottom stays on the table", all(kept[1:]), kept)

    press(find("paging-scroll"))
    settled(control, wait)
    wait(300)
    walk.check("scroll draws the sentinel", control.bottom() == "sentinel", control.bottom())
    held_rows = len(control.rows)
    control.on_last_visible(len(control.rows) - 1)
    settled(control, wait)
    wait(300)
    walk.check(
        "reaching the end appends a page",
        len(control.rows) > held_rows,
        f"{held_rows} -> {len(control.rows)}",
    )
    press(find("paging-pages"))
    settled(control, wait)
    wait(300)
    walk.check(
        "the pager comes back",
        table.footer._pager_box.isVisible() and control.pager.range_label.endswith(str(TOTAL)),
        control.pager.range_label,
    )

    # --- the view controls -----------------------------------------------------------------
    press(toggle)
    wait(200)
    for name, value in (("theme", "dark"), ("size", "lg"), ("density", "compact"), ("motion", "reduced")):
        prefs.set(name, value)
        wait(120)
    wait(300)
    walk.check(
        "the header's view controls leave the page standing, with the picker open",
        control.snapshot().status in ("ready", "error") and bool(control.rows),
        f"{len(control.rows)} rows, {control.pager.range_label}",
    )
    return walk.verdict("the boxes, the picker, the footer, the editors, grouping and paging")
