"""status-multi-picker: tick statuses, take them off, and read the summary and badge modes.

    .venv/bin/python tools/qa.py --page status-multi-picker \
        --drive tools/drives/walk/status-multi-picker.py
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
    wait_for,
    wear,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.status_multi_picker import StatusMultiPicker  # noqa: E402


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(StatusMultiPicker) if one.isVisible()]
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

    # --- Version, in two projects -----------------------------------------------------------
    here = picker_named(page, "p70")
    there = picker_named(page, "p71")
    scroll_to(page, here, wait)
    walk.same("project 70: the demo opens on two statuses", ["ip", "apr"], list(here.value))
    open_list(here, wait)
    walk.check("project 70: a click opens the list", here.control.is_open, True, False)

    held = list(here.value)
    walk.check("project 70: a row is ticked with the mouse", click_row(here.control.list_surface(), 0), True, False)
    wait(300)
    walk.check(
        "project 70: the tick moves the value",
        list(here.value) != held,
        f"not {held}",
        list(here.value),
    )
    walk.check("project 70: a tick keeps the list open", here.control.is_open, True, False)
    held = list(here.value)
    key(here.control.caret(), QtCore.Qt.Key.Key_Down)
    key(here.control.caret(), QtCore.Qt.Key.Key_Return)
    wait(300)
    walk.check(
        "project 70: Enter ticks the armed row",
        list(here.value) != held,
        f"not {held}",
        list(here.value),
    )
    key(here.control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("project 70: Escape closes the list", not here.control.is_open, False, True)

    if here.value:
        held = list(here.value)
        took = click_chip_cross(here.control.chips()[0])
        walk.check("project 70: the first badge carries a cross", took, True, took)
        wait(250)
        walk.same("project 70: the cross takes that status off", len(held) - 1, len(here.value))

    if here.value:
        held = list(here.value)
        here.control.caret().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        key(here.control.caret(), QtCore.Qt.Key.Key_Backspace)
        wait(100)
        key(here.control.caret(), QtCore.Qt.Key.Key_Backspace)
        wait(250)
        walk.same("project 70: Backspace takes the last one off", len(held) - 1, len(here.value))

    if here.value:
        click(here.control.clear_control())
        wait(250)
        walk.same("project 70: the clear control empties the value", 0, len(here.value))

    scroll_to(page, there, wait)
    open_list(there, wait)
    walk.check(
        "project 71: it offers codes of its own",
        set(codes_of(there)) != set(codes_of(here)),
        "a different set",
        (codes_of(here), codes_of(there)),
    )
    outside_click(page, wait)

    # --- the statuses both projects offer ------------------------------------------------------
    both = picker_named(page, "both")
    line = line_of(page, "both")
    scroll_to(page, both, wait)
    open_list(both, wait)
    walk.check(
        "both: only what both projects offer is listed",
        set(codes_of(both)) <= set(codes_of(here)),
        "a subset",
        sorted(set(codes_of(both))),
    )
    walk.check("both: a row is ticked with the mouse", click_row(both.control.list_surface(), 0), True, False)
    wait(300)
    walk.check(
        "both: the tick reaches the readout",
        line is not None and line.text() not in ("", "—"),
        "the codes",
        line.text() if line else None,
    )
    outside_click(page, wait)

    # --- a mandatory field, which offers no clear ------------------------------------------------
    mandatory = picker_named(page, "mandatory")
    scroll_to(page, mandatory, wait)
    walk.check(
        "mandatory: no clear control is drawn",
        not mandatory.control.clear_control().isVisible(),
        False,
        True,
    )

    # --- a code the field does not carry ------------------------------------------------------------
    unknown = picker_named(page, "unknown")
    scroll_to(page, unknown, wait)
    walk.check(
        "unknown code: the control still holds it",
        "zz_retired" in list(unknown.value),
        "zz_retired",
        list(unknown.value),
    )

    # --- rows without the code, and a secondary of the caller's own ------------------------------------
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
        "own secondary: the caller's own text is drawn on the right",
        any(bool(text) for text in seen),
        "a secondary",
        seen,
    )
    outside_click(page, wait)

    # --- what the closed trigger shows for five selected ------------------------------------------------
    wide = picker_named(page, "summary-chips-5")
    narrow = picker_named(page, "summary-ellipsis-narrow")
    counted = picker_named(page, "summary-count-5")
    capped = picker_named(page, "max-one")
    if wide is not None:
        scroll_to(page, wide, wait)
        walk.same("summary: chips draws one badge a value", 5, len(wide.control.chips()))
    if narrow is not None:
        drawn = [chip for chip in narrow.control.chips() if chip.isVisible()]
        walk.check(
            "summary: ellipsis cuts the row at 320 and counts the rest",
            0 < len(drawn) < 5 and narrow.control.overflow_pill().isVisible(),
            "whole badges and a +n pill",
            (len(drawn), narrow.control.overflow_pill().count),
        )
    if counted is not None:
        walk.same("summary: count draws no badges at all", 0, len(counted.control.chips()))
        walk.check(
            "summary: count says how many are selected",
            "5" in (counted.control._count_label or ""),
            "a line counting five",
            counted.control._count_label,
        )
    if capped is not None:
        scroll_to(page, capped, wait)
        drawn = [chip for chip in capped.control.chips() if chip.isVisible()]
        walk.same("capped: one badge at most is drawn", 1, len(drawn))
        pill = capped.control.overflow_pill()
        walk.check("capped: the other is counted by a +1", pill.isVisible() and pill.count == 1, "+1", pill.count)
        click(pill)
        wait(300)
        walk.check("capped: the pill opens the list", capped.control.is_open, True, False)
        outside_click(page, wait)

    # --- what one badge is drawn as ------------------------------------------------------------------------
    icons = picker_named(page, "badge-icon-5")
    text = picker_named(page, "badge-text-5")
    if icons is not None and text is not None:
        scroll_to(page, icons, wait)
        walk.check(
            "badges: an icon badge is narrower than a text one",
            icons.control.chips()[0].sizeHint().width() < text.control.chips()[0].sizeHint().width(),
            "narrower",
            (icons.control.chips()[0].sizeHint().width(), text.control.chips()[0].sizeHint().width()),
        )

    # --- the header ---------------------------------------------------------------------------------------
    scroll_to(page, here, wait)
    open_list(here, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", here.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1600)
    rebuilt = picker_named(page, "p70")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        open_list(rebuilt, wait)
        walk.check("header: the rebuilt picker still lists", len(codes_of(rebuilt)) > 0, "> 0", codes_of(rebuilt))
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1600)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
