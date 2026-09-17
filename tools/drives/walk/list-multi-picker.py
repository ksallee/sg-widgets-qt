"""list-multi-picker: tick several values of a list field, and read the strings stored under it.

    .venv/bin/python tools/qa.py --page list-multi-picker \
        --drive tools/drives/walk/list-multi-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click,
    click_chip_cross,
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
from sg_widgets_qt.widgets.list_multi_picker import ListMultiPicker  # noqa: E402


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(ListMultiPicker) if one.isVisible()]
    return found[0] if found else None


def line_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    for widget in holder.findChildren(QtWidgets.QWidget):
        if widget.parent() is holder and hasattr(widget, "text") and not isinstance(widget, ListMultiPicker):
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

    # --- the valid values ---------------------------------------------------------------------
    values = picker_named(page, "values")
    line = line_named(page, "values")
    scroll_to(page, values, wait)
    walk.same("valid values: the demo opens on Type A", ["Type A"], list(values.value))
    walk.check(
        "valid values: the stored strings are under it",
        line is not None and line.text() == '["Type A"]',
        '["Type A"]',
        line.text() if line else None,
    )
    open_list(values, wait)
    walk.same("valid values: the field's own set is offered", ["Type A", "Type B", "Type C"], labels_of(values))
    walk.check("valid values: a row is ticked with the mouse", click_row(values.control.list_surface(), 1), True, False)
    wait(300)
    walk.same("valid values: the tick adds the value", ["Type A", "Type B"], list(values.value))
    walk.check("valid values: a tick keeps the list open", values.control.is_open, True, False)
    walk.same("valid values: the readout follows", '["Type A","Type B"]', line.text())

    walk.check("valid values: the same row again unticks it", click_row(values.control.list_surface(), 1), True, False)
    wait(300)
    walk.same("valid values: the second click takes it off", ["Type A"], list(values.value))

    # The summary trigger takes the keys itself: it has no caret of its own on the page.
    surface = values.control.list_surface()
    surface.set_highlight(2)
    seat = surface.highlighted()
    key(values.control, QtCore.Qt.Key.Key_Return)
    wait(300)
    walk.same("valid values: Enter ticks the armed row", 2, len(values.value))
    walk.same("valid values: the cursor stays on the row it took", seat, surface.highlighted())
    key(values.control, QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("valid values: Escape closes the list", not values.control.is_open, False, True)

    held = list(values.value)
    chips = values.control.chips()
    walk.check("valid values: a chip a value stands in the trigger", len(chips) == len(held), len(held), len(chips))
    if chips:
        took = click_chip_cross(chips[0])
        walk.check("valid values: the first chip carries a cross", took, True, took)
        wait(250)
        walk.same("valid values: the cross removes that value", len(held) - 1, len(values.value))

    if values.value:
        click(values.control.clear_control())
        wait(250)
        walk.same("valid values: the clear control empties the value", 0, len(values.value))
        walk.same("valid values: the readout says so", "[]", line.text())

    # --- the display values ------------------------------------------------------------------------
    labels = picker_named(page, "labels")
    line = line_named(page, "labels")
    scroll_to(page, labels, wait)
    walk.same("display values: the demo opens on two", ["VFX", "2D"], list(labels.value))
    open_list(labels, wait)
    shown = labels_of(labels)
    walk.check(
        "display values: the display value is what a row reads",
        "Two D" in shown and "Lookdev" in shown,
        "Two D and Lookdev",
        shown,
    )
    row = shown.index("Lookdev") if "Lookdev" in shown else 0
    walk.check("display values: that row is ticked", click_row(labels.control.list_surface(), row), True, False)
    wait(300)
    walk.check(
        "display values: the stored string is the raw one",
        "Look Dev" in list(labels.value),
        "Look Dev",
        list(labels.value),
    )
    walk.check(
        "display values: the readout says the stored strings",
        "Look Dev" in line.text(),
        "Look Dev",
        line.text(),
    )
    outside_click(page, wait)

    # --- a project's hidden values removed ---------------------------------------------------------------
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

    # --- a search box ---------------------------------------------------------------------------------------
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
    walk.check("searchable: the matched row is ticked", click_row(searchable.control.list_surface(), 0), True, False)
    wait(300)
    walk.same("searchable: the tick is stored", ["Full CG"], list(searchable.value))
    outside_click(page, wait)

    # --- a mandatory field, which offers no clear ---------------------------------------------------------------
    mandatory = picker_named(page, "mandatory")
    scroll_to(page, mandatory, wait)
    walk.check(
        "mandatory: no clear control is drawn",
        not mandatory.control.clear_control().isVisible(),
        False,
        True,
    )

    # --- disabled -------------------------------------------------------------------------------------------------
    disabled = picker_named(page, "disabled")
    scroll_to(page, disabled, wait)
    click(disabled.control)
    wait(200)
    walk.check("disabled: the control does not open", not disabled.control.is_open, False, True)
    walk.same("disabled: its value is untouched", ["Type B"], list(disabled.value))

    # --- the header -----------------------------------------------------------------------------------------------
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
