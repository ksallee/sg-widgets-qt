"""sort-picker: add a key, turn it round, move it, take it off, and read the rows re-order.

    .venv/bin/python tools/qa.py --page sort-picker --drive tools/drives/walk/sort-picker.py

The trigger opens a panel holding one row a key: a grip, the field's name, ascending against
descending, and a cross, with a field picker under them to add another. The walk does each of
those and after every act reads the sort string the demo prints and the rows it re-reads under it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, scroll_to, set_view, wait_for  # noqa: E402
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_core.filter_ux import to_sort_string  # noqa: E402


def rows_of(picker) -> list:
    """The key rows the panel draws, in the order they sort in."""
    return picker.key_rows().rows()


def fields_of(picker) -> list:
    return [one.field for one in picker.value]


def part(row, name: str) -> Any:
    for one in row.findChildren(QtWidgets.QWidget):
        if one.objectName() == name:
            return one
    return None


def settled(results, wait, ms: int = 20000):
    wait_for(lambda: results.count.kind != "counting", wait, ms)
    return results.count


def first_names(results, wait, ms: int = 20000) -> list:
    """The names of the rows the order answered, which is what a reader reads under the picker."""
    wait_for(lambda: bool(results.rows()), wait, ms)
    out = []
    for row in results.rows()[:6]:
        values = getattr(row, "values", {})
        out.append(str(values.get("code") or values.get("name") or row.id))
    return out


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("sort-picker-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no sort-picker demo"}
    wait_for(lambda: demo.demo_ready, wait, 25000)
    picker = demo.picker

    # --- the two keys the page opens on ------------------------------------------------------
    walk.same("the demo opens on two keys", ["sg_status_list", "code"], fields_of(picker))
    walk.same("the string under it reads them in order", "sg_status_list,-code", picker.sort)
    walk.same("the block prints that string", picker.sort, demo.wire.toPlainText())
    opening = first_names(demo.results, wait)
    walk.check("the rows under it answered", len(opening) > 0, "> 0", opening)

    click(picker.trigger())
    wait(600)
    walk.check("the trigger opens the panel", picker.open, True, picker.open)
    walk.check("the panel stands on a window of its own", popups() != [], "a popover", popups())
    walk.same("the panel draws a row a key", 2, len(rows_of(picker)))

    # --- a key turned round -------------------------------------------------------------------
    direction = part(rows_of(picker)[0], "sort-direction")
    walk.check("the first key carries ascending and descending", direction is not None, True, direction)
    click(direction.toggles()[1])
    wait(700)
    walk.same("pressing descending turns the key round", "desc", picker.value[0].direction)
    walk.same("the string follows the turn", "-sg_status_list,-code", picker.sort)
    walk.same("the block follows it", picker.sort, demo.wire.toPlainText())
    turned = first_names(demo.results, wait)
    walk.check(
        "the rows under it are read again in the new order",
        turned != opening,
        f"not {opening}",
        turned,
    )
    click(part(rows_of(picker)[0], "sort-direction").toggles()[0])
    wait(700)
    walk.same("pressing ascending turns it back", "asc", picker.value[0].direction)
    settled(demo.results, wait)

    # --- a key moved ------------------------------------------------------------------------------
    held = fields_of(picker)
    grip = rows_of(picker)[0].grip()
    grip.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(grip, QtCore.Qt.Key.Key_Down, QtCore.Qt.KeyboardModifier.AltModifier)
    wait(700)
    walk.same("Alt and an arrow move the key down one place", [held[1], held[0]], fields_of(picker))
    walk.same("the string follows the move", to_sort_string(picker.value), picker.sort)
    walk.check(
        "the picker says where the key landed",
        "2 of 2" in picker.announcement,
        "position 2 of 2",
        picker.announcement,
    )
    settled(demo.results, wait)
    grip = rows_of(picker)[1].grip()
    grip.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(grip, QtCore.Qt.Key.Key_Up, QtCore.Qt.KeyboardModifier.AltModifier)
    wait(700)
    walk.same("Alt and the other arrow move it back", held, fields_of(picker))
    settled(demo.results, wait)

    # --- a key added ---------------------------------------------------------------------------------
    chooser = picker.field_picker()
    walk.check("the panel offers a field picker to add a key", chooser is not None, True, chooser)
    added = "created_at"
    picker.add(added)
    wait(800)
    walk.same("the picked field joins the keys", [*held, added], fields_of(picker))
    walk.same("a key added is ascending", "asc", picker.value[-1].direction)
    walk.same("the string carries the new key", to_sort_string(picker.value), picker.sort)
    walk.same("the block carries it too", picker.sort, demo.wire.toPlainText())
    settled(demo.results, wait)
    walk.same("the panel drew a row for it", 3, len(rows_of(picker)))

    # --- a key taken off --------------------------------------------------------------------------------
    cross = part(rows_of(picker)[-1], "sort-remove")
    walk.check("each key carries a cross", cross is not None, True, cross)
    click(cross)
    wait(800)
    walk.same("the cross takes that key off", held, fields_of(picker))
    walk.same("the panel drew one row fewer", 2, len(rows_of(picker)))
    settled(demo.results, wait)

    # --- every key taken off ------------------------------------------------------------------------------
    while picker.value:
        click(part(rows_of(picker)[0], "sort-remove"))
        wait(600)
    walk.same("the last cross empties the panel", [], fields_of(picker))
    walk.same("the string reads as nothing", "", picker.sort)
    walk.same("the block says so", "(none)", demo.wire.toPlainText())
    walk.check(
        "the empty panel says there is no order",
        picker.key_rows().findChild(QtWidgets.QWidget, "sort-empty") is not None,
        "a line",
        None,
    )
    settled(demo.results, wait)

    picker.add(held[0])
    wait(800)
    walk.same("a key added to an empty panel stands alone", [held[0]], fields_of(picker))
    settled(demo.results, wait)

    picker.trigger().setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    key(picker.trigger(), QtCore.Qt.Key.Key_Escape)
    wait(600)
    walk.check("Escape closes the panel", not picker.open, False, picker.open)
    walk.same("nothing was left standing over the page", [], popups())

    # --- the view controls ------------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("sort-picker-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready, wait, 25000)
        walk.same("header: the trigger wears the size step", "lg", again.picker.size)
        walk.same("header: the sizes section keeps the steps it named", "sm", find("sort-picker-sm").size)
        rebuilt = again.picker
        scroll_to(page, rebuilt, wait)
        click(rebuilt.trigger())
        wait(600)
        walk.check("header: the rebuilt trigger still opens", rebuilt.open, True, rebuilt.open)
        click(part(rows_of(rebuilt)[0], "sort-direction").toggles()[1])
        wait(700)
        walk.same("header: the rebuilt panel still turns a key round", "desc", rebuilt.value[0].direction)
        rebuilt.trigger().setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        key(rebuilt.trigger(), QtCore.Qt.Key.Key_Escape)
        wait(600)
        walk.check("header: Escape closes the rebuilt panel", not rebuilt.open, False, rebuilt.open)
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS a key turns round, moves by its grip, is added and taken off, the panel says when"
        " it is empty, and the sort string and the rows under the picker follow every act"
    )
