"""entity-type-multi-picker: tick several types, take them off, and read the summary modes.

    .venv/bin/python tools/qa.py --page entity-type-multi-picker \
        --drive tools/drives/walk/entity-type-multi-picker.py
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
    readouts,
    scroll_to,
    type_into,
    wear,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.entity_type_multi_picker import EntityTypeMultiPicker  # noqa: E402

PRODUCTION = ["Project", "Sequence", "Shot", "Asset", "Version", "Task"]


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(EntityTypeMultiPicker) if one.isVisible()]
    return found[0] if found else None


def line_named(page, name: str):
    holder = demo_widget(page, name)
    found = readouts(holder) if holder is not None else []
    return found[0] if found else None


def open_list(picker, wait) -> None:
    if not picker.control.is_open:
        click(picker.control)
        wait(250)


def labels_of(picker) -> list:
    model = picker.control.list_surface().model()
    return [model.index(row, 0).data(Roles.LABEL) for row in range(model.rowCount())]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- the deny list -------------------------------------------------------------------------
    many = picker_named(page, "multi")
    line = line_named(page, "multi")
    scroll_to(page, many, wait)
    walk.same("deny list: the demo opens on Version", ["Version"], list(many.value))
    open_list(many, wait)
    walk.check("deny list: a click opens the list", many.control.is_open, True, False)
    offered = labels_of(many)
    walk.check(
        "deny list: neither user type is offered",
        "Person" not in offered and "Script" not in offered,
        "no user type",
        offered,
    )

    walk.check("deny list: a row is ticked with the mouse", click_row(many.control.list_surface(), 0), True, False)
    wait(300)
    walk.same("deny list: the tick adds a type", 2, len(many.value))
    walk.check("deny list: a tick keeps the list open", many.control.is_open, True, False)
    walk.check("deny list: the readout follows", line is not None and line.text().count(",") == 1, "two codes", line.text() if line else None)

    walk.check("deny list: the same row again unticks it", click_row(many.control.list_surface(), 0), True, False)
    wait(300)
    walk.same("deny list: the second click takes it off", 1, len(many.value))

    surface = many.control.list_surface()
    surface.set_highlight(2)
    seat = surface.highlighted()
    key(many.control.caret(), QtCore.Qt.Key.Key_Return)
    wait(300)
    walk.same("deny list: Enter ticks the armed row", 2, len(many.value))
    walk.same("deny list: the cursor stays on the row it took", seat, surface.highlighted())

    type_into(many.control.caret(), "ver", wait)
    wait(300)
    walk.check(
        "deny list: the query cuts the list down",
        labels_of(many) and all("ver" in label.lower() for label in labels_of(many)),
        "only what matches",
        labels_of(many),
    )

    key(many.control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("deny list: Escape closes the list", not many.control.is_open, False, True)

    held = list(many.value)
    took = click_chip_cross(many.control.chips()[0])
    walk.check("deny list: the first chip carries a cross", took, True, took)
    wait(250)
    walk.same("deny list: the cross removes that type", len(held) - 1, len(many.value))

    held = list(many.value)
    many.control.caret().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    key(many.control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(100)
    key(many.control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(250)
    walk.same("deny list: Backspace takes the last chip off", len(held) - 1, len(many.value))

    # --- what the control shows for six selected, wide and narrow ---------------------------------
    wide = picker_named(page, "chips")
    narrow = picker_named(page, "ellipsis-narrow")
    counted = picker_named(page, "count")
    if wide is not None:
        scroll_to(page, wide, wait)
        walk.same("summary: chips draws one chip a type", 6, len(wide.control.chips()))
    if narrow is not None:
        drawn = [chip for chip in narrow.control.chips() if chip.isVisible()]
        walk.check(
            "summary: ellipsis cuts the row at 20rem and counts the rest",
            0 < len(drawn) < 6 and narrow.control.overflow_pill().isVisible(),
            "whole chips and a +n pill",
            (len(drawn), narrow.control.overflow_pill().count),
        )
        click(narrow.control.overflow_pill())
        wait(300)
        walk.check("summary: the pill opens the list", narrow.control.is_open, True, False)
        outside_click(page, wait)
    if counted is not None:
        walk.same("summary: count draws no chips at all", 0, len(counted.control.chips()))
        walk.check(
            "summary: count says how many are selected",
            "6" in (counted.control._count_label or ""),
            "a line counting six",
            counted.control._count_label,
        )

    # --- sizes, read-only and invalid ----------------------------------------------------------------
    everyone = [one for one in page.findChildren(EntityTypeMultiPicker) if one.isVisible()]
    small = [one for one in everyone if one.control.size == "sm"]
    large = [one for one in everyone if one.control.size == "lg"]
    walk.check("sizes: a small and a large control stand in the example", bool(small and large), "both", (len(small), len(large)))
    readonly = [one for one in everyone if one.control.readonly]
    disabled = [one for one in everyone if one.control.disabled]
    invalid = [one for one in everyone if one.control.invalid]
    walk.check(
        "states: one read-only, one disabled and one invalid",
        bool(readonly and disabled and invalid),
        "one each",
        (len(readonly), len(disabled), len(invalid)),
    )
    if readonly:
        scroll_to(page, readonly[0], wait)
        click(readonly[0].control)
        wait(150)
        walk.check("states: the read-only control does not open", not readonly[0].control.is_open, False, True)
        walk.check(
            "states: a read-only chip carries no cross",
            not any(getattr(chip, "removable", False) for chip in readonly[0].control.chips()),
            "no cross",
            [getattr(chip, "removable", None) for chip in readonly[0].control.chips()],
        )
    if disabled:
        click(disabled[0].control)
        wait(150)
        walk.check("states: the disabled control does not open", not disabled[0].control.is_open, False, True)

    # --- the header -----------------------------------------------------------------------------------
    scroll_to(page, many, wait)
    open_list(many, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", many.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = picker_named(page, "multi")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        open_list(rebuilt, wait)
        walk.check("header: the rebuilt picker still lists", len(labels_of(rebuilt)) > 0, "> 0", len(labels_of(rebuilt)))
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
