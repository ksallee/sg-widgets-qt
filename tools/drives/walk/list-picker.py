"""list-picker: pick a value of a list field, and read the string the demo stores under it.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/walk/list-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click,
    click_row,
    demo_widget,
    key,
    orphans,
    outside_click,
    scroll_to,
    type_into,
    wear,
)
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.list_picker import ListPicker  # noqa: E402


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(ListPicker) if one.isVisible()]
    return found[0] if found else None


def line_named(page, name: str):
    """The stored string the demo writes under the control."""
    holder = demo_widget(page, name)
    if holder is None:
        return None
    for widget in holder.findChildren(QtWidgets.QWidget):
        if widget.parent() is holder and hasattr(widget, "text") and not isinstance(widget, ListPicker):
            return widget
    return None


def open_list(picker, wait) -> None:
    if not picker.control.is_open:
        click(picker.control)
        wait(250)


def labels_of(picker) -> list:
    model = picker.control.list_surface().model()
    return [model.index(row, 0).data(Roles.LABEL) for row in range(model.rowCount())]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- the valid values -------------------------------------------------------------------
    values = picker_named(page, "values")
    line = line_named(page, "values")
    scroll_to(page, values, wait)
    walk.same("valid values: the demo opens on Type A", "Type A", values.value)
    walk.check("valid values: the stored string is under it", line is not None and line.text() == '"Type A"', '"Type A"', line.text() if line else None)
    open_list(values, wait)
    walk.check("valid values: a click opens the list", values.control.is_open, True, False)
    walk.same("valid values: the field's own set is offered", ["Type A", "Type B", "Type C"], labels_of(values))
    walk.check("valid values: a row is picked with the mouse", click_row(values.control.list_surface(), 2), True, False)
    wait(300)
    walk.same("valid values: the pick is stored byte for byte", "Type C", values.value)
    walk.check("valid values: the pick closes the list", not values.control.is_open, False, True)
    walk.check("valid values: the readout follows", line.text() == '"Type C"', '"Type C"', line.text())

    click(values.control.clear_control())
    wait(250)
    walk.same("valid values: the clear control stores null", None, values.value)
    walk.same("valid values: the readout says null", "null", line.text())

    open_list(values, wait)
    key(values.control.caret(), QtCore.Qt.Key.Key_Down)
    key(values.control.caret(), QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.same("valid values: Enter picks the armed row", "Type A", values.value)

    open_list(values, wait)
    key(values.control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("valid values: Escape closes the list", not values.control.is_open, False, True)
    open_list(values, wait)
    outside_click(page, wait)
    walk.check("valid values: a press outside closes the list", not values.control.is_open, False, True)

    # --- the display values --------------------------------------------------------------------
    labels = picker_named(page, "labels")
    line = line_named(page, "labels")
    scroll_to(page, labels, wait)
    open_list(labels, wait)
    shown = labels_of(labels)
    walk.check(
        "display values: the display value is what a row reads",
        "Two D" in shown and "2D" not in shown,
        "Two D",
        shown,
    )
    row = shown.index("Two D")
    walk.check("display values: that row is picked", click_row(labels.control.list_surface(), row), True, False)
    wait(300)
    walk.same("display values: the stored string is the raw one", "2D", labels.value)
    walk.same("display values: the readout says the stored string", '"2D"', line.text())

    # --- a project's hidden values removed ----------------------------------------------------------
    scoped = picker_named(page, "project")
    scroll_to(page, scoped, wait)
    open_list(scoped, wait)
    shown = labels_of(scoped)
    walk.check(
        "project: the values that project hides are not offered",
        "Marketing" not in shown and "Trailer" not in shown,
        "no hidden value",
        shown,
    )
    outside_click(page, wait)

    # --- a search box -----------------------------------------------------------------------------------
    searchable = picker_named(page, "searchable")
    scroll_to(page, searchable, wait)
    open_list(searchable, wait)
    walk.check("searchable: a search row stands in the popup", searchable.control.search_row().isVisible(), True, False)
    type_into(searchable.control.caret(), "cg", wait)
    wait(250)
    shown = labels_of(searchable)
    walk.check(
        "searchable: the query cuts the list down",
        shown and all("cg" in one.lower() for one in shown),
        "only what matches",
        shown,
    )
    walk.check("searchable: the matched row is picked", click_row(searchable.control.list_surface(), 0), True, False)
    wait(300)
    walk.same("searchable: the pick is stored", "Full CG", searchable.value)

    # --- a mandatory field, which offers no clear ------------------------------------------------------------
    mandatory = picker_named(page, "mandatory")
    scroll_to(page, mandatory, wait)
    walk.check(
        "mandatory: no clear control is drawn",
        not mandatory.control.clear_control().isVisible(),
        False,
        True,
    )
    open_list(mandatory, wait)
    walk.check("mandatory: a row is picked", click_row(mandatory.control.list_surface(), 1), True, False)
    wait(300)
    walk.same("mandatory: the pick is stored", "Rig", mandatory.value)

    # --- disabled -------------------------------------------------------------------------------------------
    disabled = picker_named(page, "disabled")
    scroll_to(page, disabled, wait)
    click(disabled.control)
    wait(200)
    walk.check("disabled: the control does not open", not disabled.control.is_open, False, True)
    walk.same("disabled: its value is untouched", "Type B", disabled.value)

    # --- the header -------------------------------------------------------------------------------------------
    scroll_to(page, values, wait)
    open_list(values, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", values.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=900)
    rebuilt = picker_named(page, "values")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        open_list(rebuilt, wait)
        walk.same("header: the rebuilt picker still lists", 3, len(labels_of(rebuilt)))
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=900)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
