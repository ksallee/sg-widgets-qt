"""column-picker: add a column, drag it into order, move it from the keyboard, take it off.

    .venv/bin/python tools/qa.py --page column-picker \
        --drive tools/drives/walk/column-picker.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click,
    click_row,
    key,
    orphans,
    outside_click,
    scroll_to,
    type_into,
    wait_for,
    wear,
)
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402


def row_point(chosen, row: int, x: int = 12) -> QtCore.QPoint:
    """A point on the grip of a row, which is where a drag starts."""
    rect = chosen.visualRect(chosen.model().index(row, 0))
    return QtCore.QPoint(rect.left() + x, rect.center().y())


def drag_move(widget, point: QtCore.QPoint) -> None:
    """A move with the button still down, delivered the same way on Qt 5 and Qt 6."""
    where = QtCore.QPointF(float(point.x()), float(point.y()))
    QtWidgets.QApplication.sendEvent(
        widget,
        QtGui.QMouseEvent(
            QtGui.QMouseEvent.Type.MouseMove,
            where,
            where,
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
        ),
    )


def open_field_list(picker, wait) -> None:
    field = picker.field_picker
    if field is not None and not field.control.is_open:
        click(field.control)
        wait(250)
        wait_for(lambda: not field.levels.loading, wait)


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    columns = find("column-picker-columns")
    line = find("column-picker-columns-value")
    chosen = columns.chosen_list
    scroll_to(page, columns, wait)
    wait(400)

    walk.same("columns: the demo opens on three columns", 3, len(columns.value))
    walk.check(
        "columns: the chosen list draws one row a column",
        chosen.model().rowCount() == 3,
        3,
        chosen.model().rowCount(),
    )
    walk.check(
        "columns: a path behind a link reads as its friendly path",
        all("." not in chosen.rows_model.label_of(path) for path in chosen.paths),
        "friendly paths",
        [chosen.rows_model.label_of(path) for path in chosen.paths],
    )

    # --- pick a field, which appends it ------------------------------------------------------
    field = columns.field_picker
    walk.check("columns: the example carries a field picker", field is not None, True, field)
    open_field_list(columns, wait)
    walk.check("columns: a click opens the field list", field.control.is_open, True, False)
    type_into(field.control.caret(), "description", wait)
    wait(350)
    before = list(columns.value)
    walk.check("columns: a field is picked with the mouse", click_row(field.control.list_surface(), 0), True, False)
    wait(400)
    walk.check(
        "columns: the pick is appended to the columns",
        len(columns.value) == len(before) + 1,
        len(before) + 1,
        columns.value,
    )
    walk.check(
        "columns: the readout under the example follows",
        line.text() == "[" + ", ".join(columns.value) + "]",
        "[" + ", ".join(columns.value) + "]",
        line.text(),
    )
    walk.check(
        "columns: a column already chosen is off the list",
        all(one.path not in columns.value for one in field.levels.rows(field.control.query)),
        "none of the chosen",
        [one.path for one in field.levels.rows(field.control.query) if one.path in columns.value],
    )
    if field.control.is_open:
        outside_click(page, wait)

    # --- drag the list into order --------------------------------------------------------------
    wait(300)
    before = list(chosen.paths)
    start = row_point(chosen, 2)
    QTest.mousePress(
        chosen.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        start,
    )
    drag_move(chosen.viewport(), QtCore.QPoint(start.x(), start.y() - 8))
    drag_move(chosen.viewport(), row_point(chosen, 0))
    wait(200)
    walk.check("drag: the row is carried by its grip", bool(chosen.carrying), "a path", chosen.carrying)
    QTest.mouseRelease(
        chosen.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        row_point(chosen, 0),
    )
    wait(300)
    walk.check(
        "drag: the release leaves the order moved",
        chosen.paths != before and sorted(chosen.paths) == sorted(before),
        f"a reordering of {before}",
        chosen.paths,
    )
    walk.same("drag: the value follows the order", list(chosen.paths), list(columns.value))
    walk.check(
        "drag: the readout follows too",
        line.text() == "[" + ", ".join(columns.value) + "]",
        "[" + ", ".join(columns.value) + "]",
        line.text(),
    )
    walk.check("drag: nothing is left carried", not chosen.carrying, None, chosen.carrying)

    # --- drag a row two slots down, and watch it settle --------------------------------------------
    wait(400)
    before = list(chosen.paths)
    if len(before) >= 3:
        start = row_point(chosen, 0)
        target = row_point(chosen, 2)
        target = QtCore.QPoint(target.x(), target.y() + 4)
        QTest.mousePress(
            chosen.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            start,
        )
        drag_move(chosen.viewport(), QtCore.QPoint(start.x(), start.y() + 8))
        wait(80)
        walk.same("motion: the row under the pointer is lifted", 0, chosen.motion.lifted)
        drag_move(chosen.viewport(), target)
        wait(150)
        walk.check(
            "motion: the lifted row follows the pointer",
            chosen.offset_of(0) > 0,
            "> 0",
            chosen.offset_of(0),
        )
        walk.check(
            "motion: the rows it passes give way",
            chosen.offset_of(1) < 0 and chosen.offset_of(2) < 0,
            "both above their slots",
            (chosen.offset_of(1), chosen.offset_of(2)),
        )
        walk.same("motion: the order stands still until the drop", before, list(chosen.paths))
        heard = []
        chosen.reordered.connect(heard.append)
        QTest.mouseRelease(
            chosen.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            target,
        )
        started = time.monotonic()
        while chosen.motion.running and time.monotonic() - started < 1.0:
            wait(20)
        settled_in = time.monotonic() - started
        walk.same(
            "motion: the drop moves the row two slots",
            [*before[1:3], before[0], *before[3:]],
            list(chosen.paths),
        )
        walk.check("motion: the order is emitted once", len(heard) == 1, 1, len(heard))
        walk.same("motion: what was emitted is what the list holds", list(chosen.paths), heard[-1] if heard else None)
        walk.check(
            "motion: the settle ends inside 300ms",
            settled_in <= 0.35,
            "<= 0.3s",
            round(settled_in, 3),
        )
        walk.check(
            "motion: every row is back on its slot",
            all(abs(chosen.offset_of(row)) < 1 for row in range(len(chosen.paths))),
            "no offsets",
            {row: chosen.offset_of(row) for row in range(len(chosen.paths))},
        )
        walk.same("motion: nothing is left lifted", -1, chosen.motion.lifted)
        chosen.reordered.disconnect(heard.append)

    # --- move a row from the keyboard -----------------------------------------------------------
    before = list(chosen.paths)
    chosen.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(0)
    key(chosen, QtCore.Qt.Key.Key_Space)
    wait(150)
    walk.check("keyboard: Space picks the row up", chosen.carrying == before[0], before[0], chosen.carrying)
    key(chosen, QtCore.Qt.Key.Key_Down)
    wait(200)
    walk.check(
        "keyboard: Down moves it one place",
        chosen.paths.index(before[0]) == 1,
        1,
        chosen.paths.index(before[0]),
    )
    walk.check("keyboard: the move is announced", bool(columns.announcement), "a line", columns.announcement)
    key(chosen, QtCore.Qt.Key.Key_Space)
    wait(150)
    walk.check("keyboard: Space drops it", not chosen.carrying, None, chosen.carrying)
    walk.same("keyboard: the value follows the order", list(chosen.paths), list(columns.value))

    # Escape puts a row being carried back where it was.
    held = list(chosen.paths)
    chosen.set_highlight(0)
    key(chosen, QtCore.Qt.Key.Key_Space)
    key(chosen, QtCore.Qt.Key.Key_Down)
    wait(200)
    key(chosen, QtCore.Qt.Key.Key_Escape)
    wait(250)
    walk.same("keyboard: Escape puts the order back", held, list(chosen.paths))

    # --- take a column off ------------------------------------------------------------------------
    held = list(chosen.paths)
    chosen.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(0)
    key(chosen, QtCore.Qt.Key.Key_Delete)
    wait(300)
    walk.same("remove: Delete takes the row off", held[1:], list(chosen.paths))
    walk.same("remove: the value follows", held[1:], list(columns.value))

    # --- date-times only ----------------------------------------------------------------------------
    dates = find("column-picker-dates")
    scroll_to(page, dates, wait)
    wait(300)
    walk.same("dates: the demo opens on the one timestamp", 1, len(dates.value))
    open_field_list(dates, wait)
    offered = dates.field_picker.levels.rows(dates.field_picker.control.query)
    walk.check(
        "dates: only timestamps and links are offered",
        all(one.traversable or one.data_type == "date_time" for one in offered),
        "date_time and links",
        sorted({one.data_type for one in offered}),
    )
    outside_click(page, wait)

    # --- the dual layout -------------------------------------------------------------------------------
    dual = find("column-picker-dual")
    scroll_to(page, dual, wait)
    wait(300)
    walk.check("dual: the fields of the type stand on the left", dual.available is not None, True, None)
    walk.check("dual: the chosen paths stand on the right", dual.chosen_list.model().rowCount() == 2, 2, dual.chosen_list.model().rowCount())
    surface = dual.available.list_surface()
    wait_for(lambda: surface.row_count() > 0, wait)
    before = list(dual.value)
    walk.check("dual: a field on the left is picked", click_row(surface, 0), True, False)
    wait(350)
    walk.check(
        "dual: the pick crosses to the chosen list",
        len(dual.value) == len(before) + 1,
        len(before) + 1,
        dual.value,
    )

    # --- disabled and read-only ---------------------------------------------------------------------------
    disabled = find("column-picker-disabled")
    readonly = find("column-picker-readonly")
    scroll_to(page, disabled, wait)
    held = list(disabled.value)
    disabled.chosen_list.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    disabled.chosen_list.set_highlight(0)
    key(disabled.chosen_list, QtCore.Qt.Key.Key_Delete)
    wait(200)
    walk.same("disabled: the keyboard takes nothing off", held, list(disabled.value))
    scroll_to(page, readonly, wait)
    held = list(readonly.value)
    readonly.chosen_list.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    readonly.chosen_list.set_highlight(0)
    key(readonly.chosen_list, QtCore.Qt.Key.Key_Space)
    key(readonly.chosen_list, QtCore.Qt.Key.Key_Down)
    wait(200)
    walk.same("read-only: the keyboard moves nothing", held, list(readonly.value))
    walk.check("read-only: the chosen list alone is drawn", readonly.field_picker is None or not readonly.field_picker.isVisible(), "no field picker", readonly.field_picker)

    # --- the header -----------------------------------------------------------------------------------------
    scroll_to(page, columns, wait)
    open_field_list(columns, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", columns.field_picker.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1400)
    rebuilt = find("column-picker-columns")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.size)
        scroll_to(page, rebuilt, wait)
        open_field_list(rebuilt, wait)
        walk.check(
            "header: the rebuilt picker still lists fields",
            len(rebuilt.field_picker.levels.rows("")) > 0,
            "> 0",
            0,
        )
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1400)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
