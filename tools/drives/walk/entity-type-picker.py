"""entity-type-picker: pick a type, search it, and read the code the demo stores under it.

    .venv/bin/python tools/qa.py --page entity-type-picker \
        --drive tools/drives/walk/entity-type-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    case_widget,
    click,
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
from sg_widgets_qt.widgets.entity_type_picker import EntityTypePicker  # noqa: E402

PRODUCTION = ["Project", "Sequence", "Shot", "Asset", "Version", "Task"]


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(EntityTypePicker) if one.isVisible()]
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


def codes_of(picker) -> list:
    model = picker.control.list_surface().model()
    return [model.index(row, 0).data(Roles.CODE) for row in range(model.rowCount())]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- the allow list -----------------------------------------------------------------------
    one = picker_named(page, "single")
    line = line_named(page, "single")
    scroll_to(page, one, wait)
    walk.same("allow list: the demo opens on Shot", "Shot", one.value)
    open_list(one, wait)
    walk.check("allow list: a click opens the list", one.control.is_open, True, False)
    walk.same("allow list: only the six production types are offered", 6, len(labels_of(one)))
    type_into(one.control.caret(), "ver", wait)
    wait(250)
    walk.check(
        "allow list: the query cuts the list down",
        labels_of(one) and all("ver" in one_label.lower() for one_label in labels_of(one)),
        "only what matches",
        labels_of(one),
    )
    walk.check("allow list: the matched row is picked", click_row(one.control.list_surface(), 0), True, False)
    wait(300)
    walk.same("allow list: the pick is stored as the type code", "Version", one.value)
    walk.check("allow list: the pick closes the list", not one.control.is_open, False, True)
    walk.same("allow list: the readout follows", "Version", line.text())

    click(one.control.clear_control())
    wait(250)
    walk.same("allow list: the clear control empties the value", None, one.value)
    walk.same("allow list: the readout says null", "null", line.text())

    open_list(one, wait)
    key(one.control.caret(), QtCore.Qt.Key.Key_Down)
    key(one.control.caret(), QtCore.Qt.Key.Key_Return)
    wait(300)
    walk.check("allow list: Enter picks the armed row", one.value is not None, "a type", one.value)
    open_list(one, wait)
    key(one.control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("allow list: Escape closes the list", not one.control.is_open, False, True)
    open_list(one, wait)
    outside_click(page, wait)
    walk.check("allow list: a press outside closes the list", not one.control.is_open, False, True)

    # --- the deny list ---------------------------------------------------------------------------
    deny = picker_named(page, "deny")
    scroll_to(page, deny, wait)
    open_list(deny, wait)
    offered = codes_of(deny)
    walk.check(
        "deny list: neither user type is offered",
        "HumanUser" not in offered and "ApiUser" not in offered,
        "no user type",
        offered,
    )
    walk.check(
        "deny list: everything else is",
        len(offered) > len(PRODUCTION),
        f"> {len(PRODUCTION)}",
        len(offered),
    )
    # The code is drawn only where it says something the display name does not: Step reads
    # "Pipeline Step", and its code stands beside it.
    walk.check(
        "deny list: a code that differs from the display name is drawn",
        "Step" in codes_of(deny),
        "Step",
        [code for code in codes_of(deny) if code],
    )
    outside_click(page, wait)

    # --- the code beside the display name, and without it ------------------------------------------
    codes = case_widget(page, "codes")
    pair = [one_picker for one_picker in codes.findChildren(EntityTypePicker) if one_picker.isVisible()]
    walk.same("codes: two controls stand in the example", 2, len(pair))
    if len(pair) == 2:
        scroll_to(page, pair[0], wait)
        open_list(pair[0], wait)
        # Every production type reads as its own code, so neither list draws one; the pair is
        # read on the prop the second one turns off instead.
        walk.check("codes: the first asks for the code", pair[0].show_code, True, pair[0].show_code)
        outside_click(page, wait)
        open_list(pair[1], wait)
        walk.check(
            "codes: the second draws none",
            not pair[1].show_code and not any(codes_of(pair[1])),
            "no code",
            codes_of(pair[1]),
        )
        outside_click(page, wait)

    # --- sizes, read-only and invalid ----------------------------------------------------------------
    everyone = [one_picker for one_picker in page.findChildren(EntityTypePicker) if one_picker.isVisible()]
    small = [one_picker for one_picker in everyone if one_picker.control.size == "sm"]
    large = [one_picker for one_picker in everyone if one_picker.control.size == "lg"]
    walk.check("sizes: a small and a large control stand in the example", bool(small and large), "both", (len(small), len(large)))
    readonly = [one_picker for one_picker in everyone if one_picker.control.readonly]
    disabled = [one_picker for one_picker in everyone if one_picker.control.disabled]
    invalid = [one_picker for one_picker in everyone if one_picker.control.invalid]
    walk.check("states: one read-only, one disabled and one invalid", bool(readonly and disabled and invalid), "one each", (len(readonly), len(disabled), len(invalid)))
    if readonly:
        scroll_to(page, readonly[0], wait)
        click(readonly[0].control)
        wait(150)
        walk.check("states: the read-only control does not open", not readonly[0].control.is_open, False, True)
    if disabled:
        click(disabled[0].control)
        wait(150)
        walk.check("states: the disabled control does not open", not disabled[0].control.is_open, False, True)

    # --- the header -----------------------------------------------------------------------------------
    scroll_to(page, one, wait)
    open_list(one, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", one.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = picker_named(page, "single")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        open_list(rebuilt, wait)
        walk.same("header: the rebuilt picker still lists", 6, len(labels_of(rebuilt)))
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
