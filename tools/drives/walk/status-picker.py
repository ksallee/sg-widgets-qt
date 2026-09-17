"""status-picker: pick a status, read what each project offers, and switch project under one.

    .venv/bin/python tools/qa.py --page status-picker \
        --drive tools/drives/walk/status-picker.py
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
    readouts,
    scroll_to,
    wait_for,
    wear,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.widgets.status_picker import StatusPicker  # noqa: E402


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(StatusPicker) if one.isVisible()]
    return found[0] if found else None


def line_of(page, name: str):
    holder = demo_widget(page, name)
    found = readouts(holder) if holder is not None else []
    return found[0] if found else None


def open_list(picker, wait) -> None:
    if not picker.control.is_open:
        click(picker.control)
        wait(250)
    wait_for(lambda: not picker.load.loading, wait)


def codes_of(picker) -> list:
    return [option.code for option in picker.options]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- Version, in two projects -------------------------------------------------------------
    here = picker_named(page, "p70")
    there = picker_named(page, "p71")
    scroll_to(page, here, wait)
    walk.same("project 70: the demo opens on ip", "ip", here.value)
    open_list(here, wait)
    walk.check("project 70: a click opens the list", here.control.is_open, True, False)
    walk.check("project 70: the project's codes are offered", len(codes_of(here)) > 0, "> 0", codes_of(here))
    walk.check("project 70: a row is picked with the mouse", click_row(here.control.list_surface(), 0), True, False)
    wait(300)
    walk.check("project 70: the pick lands on the control", here.value == codes_of(here)[0], codes_of(here)[0], here.value)
    walk.check("project 70: the pick closes the list", not here.control.is_open, False, True)
    walk.check(
        "project 70: the chip is a status badge",
        bool(here.control.chips()),
        "a badge",
        here.control.chips(),
    )
    click(here.control.clear_control())
    wait(250)
    walk.same("project 70: the clear control empties the value", None, here.value)

    scroll_to(page, there, wait)
    open_list(there, wait)
    walk.check(
        "project 71: it offers codes of its own",
        set(codes_of(there)) != set(codes_of(here)),
        "a different set",
        (codes_of(here), codes_of(there)),
    )
    key(there.control, QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("project 71: Escape closes the list", not there.control.is_open, False, True)

    # --- the statuses both projects offer -------------------------------------------------------
    both = picker_named(page, "both")
    line = line_of(page, "both")
    scroll_to(page, both, wait)
    open_list(both, wait)
    shared = set(codes_of(both))
    walk.check("both: only what both projects offer is listed", shared <= set(codes_of(here)), "a subset", sorted(shared))
    walk.check("both: a row is picked with the mouse", click_row(both.control.list_surface(), 0), True, False)
    wait(300)
    walk.check("both: the pick reaches the readout", line is not None and line.text() == both.value, both.value, line.text() if line else None)

    # --- Project, a plain list with no icons ------------------------------------------------------
    plain = picker_named(page, "project")
    scroll_to(page, plain, wait)
    walk.same("plain list: the demo opens on Active", "Active", plain.value)
    open_list(plain, wait)
    walk.check("plain list: the codes are offered", len(codes_of(plain)) > 0, "> 0", codes_of(plain))
    outside_click(page, wait)
    walk.check("plain list: a press outside closes it", not plain.control.is_open, False, True)

    # --- a mandatory field, which offers no clear --------------------------------------------------
    mandatory = picker_named(page, "mandatory")
    scroll_to(page, mandatory, wait)
    walk.check(
        "mandatory: no clear control is drawn",
        not mandatory.control.clear_control().isVisible(),
        False,
        True,
    )
    open_list(mandatory, wait)
    before = mandatory.value
    walk.check("mandatory: a row is picked", click_row(mandatory.control.list_surface(), 1), True, False)
    wait(300)
    walk.check("mandatory: the pick lands", mandatory.value != before, f"not {before}", mandatory.value)
    walk.check(
        "mandatory: the readout follows",
        (line_of(page, "mandatory").text() if line_of(page, "mandatory") else "") == mandatory.value,
        mandatory.value,
        line_of(page, "mandatory").text() if line_of(page, "mandatory") else None,
    )

    # --- a code the field does not carry --------------------------------------------------------------
    unknown = picker_named(page, "unknown")
    scroll_to(page, unknown, wait)
    walk.same("unknown code: the control still holds it", "zz_retired", unknown.value)
    walk.check(
        "unknown code: it is labelled as itself rather than dropped",
        bool(unknown.control.labels and unknown.control.labels[0]),
        "a label",
        list(unknown.control.labels),
    )

    # --- rows without the code, and a secondary of the caller's own --------------------------------------
    from sg_widgets_qt.primitives.roles import Roles

    plain_rows = picker_named(page, "no-code")
    scroll_to(page, plain_rows, wait)
    open_list(plain_rows, wait)
    index = plain_rows.control.list_surface().model().index(0, 0)
    walk.check("no code: the row draws no code", not index.data(Roles.CODE), "", index.data(Roles.CODE))
    outside_click(page, wait)

    own = picker_named(page, "own-secondary")
    scroll_to(page, own, wait)
    open_list(own, wait)
    model = own.control.list_surface().model()
    seen = [model.index(row, 0).data(Roles.SECONDARY) for row in range(model.rowCount())]
    walk.check(
        "own secondary: the caller's own stage is drawn on the right",
        any(text in ("Animation", "Review", "Delivery") for text in seen),
        "a pipeline stage",
        seen,
    )
    outside_click(page, wait)

    # --- switching project drops a status the new one hides -----------------------------------------------
    switching = picker_named(page, "switching")
    switch = find("switch-project")
    switch_line = line_of(page, "switching")
    scroll_to(page, switching, wait)
    walk.same("switching: the demo opens on part", "part", switching.value)
    walk.check("switching: the demo offers the switch", switch is not None, True, switch)
    if switch is not None:
        click(switch)
        wait_for(lambda: not switching.load.loading, wait)
        wait(400)
        walk.check(
            "switching: a status the new project hides is dropped",
            switching.value != "part",
            "not part",
            switching.value,
        )
        walk.check(
            "switching: the readout follows the drop",
            switch_line is not None and switch_line.text() == (switching.value or "—"),
            switching.value or "—",
            switch_line.text() if switch_line else None,
        )
        click(switch)
        wait_for(lambda: not switching.load.loading, wait)

    # --- the header -------------------------------------------------------------------------------------
    scroll_to(page, here, wait)
    open_list(here, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", here.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1400)
    rebuilt = picker_named(page, "p70")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        open_list(rebuilt, wait)
        walk.check("header: the rebuilt picker still lists", len(codes_of(rebuilt)) > 0, "> 0", codes_of(rebuilt))
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1400)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
