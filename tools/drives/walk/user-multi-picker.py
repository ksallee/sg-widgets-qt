"""user-multi-picker: tick several people, walk the chips, and read the summary modes.

    .venv/bin/python tools/qa.py --page user-multi-picker \
        --drive tools/drives/walk/user-multi-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    case_widget,
    click,
    demo_widget,
    key,
    open_and_type,
    orphans,
    outside_click,
    scroll_to,
    walk_multi,
    wear,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.widgets.user_multi_picker import UserMultiPicker  # noqa: E402

NAME = "ada"


def picker_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(UserMultiPicker) if one.isVisible()]
    return found[index] if index < len(found) else None


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(UserMultiPicker) if one.isVisible()]
    return found[0] if found else None


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- several people at once -------------------------------------------------------------
    many = picker_in(page, "multi")
    walk_multi(walk, page, many, wait, NAME, "several people")

    # --- a token field: Backspace walks the chips ----------------------------------------------
    tokens = picker_in(page, "tokens")
    scroll_to(page, tokens, wait)
    control = tokens.control
    walk.same("tokens: the demo opens on three chips", 3, len(control.chips()))
    control.caret().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    key(control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(150)
    walk.same("tokens: the first Backspace arms the last chip", 2, control.armed)
    key(control.caret(), QtCore.Qt.Key.Key_Left)
    wait(100)
    walk.same("tokens: Left walks to the chip before it", 1, control.armed)
    key(control.caret(), QtCore.Qt.Key.Key_Right)
    wait(100)
    walk.same("tokens: Right walks back", 2, control.armed)
    held = len(tokens.value)
    key(control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(250)
    walk.same("tokens: Backspace takes the armed chip away", held - 1, len(tokens.value))
    key(control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(150)

    # --- people only, inactive included ------------------------------------------------------------
    people = picker_in(page, "people-only")
    scroll_to(page, people, wait)
    open_and_type(people, wait, "")
    names = [row.name for row in people.state.rows]
    walk.check(
        "people only: no script user is offered",
        all(row.type == "HumanUser" for row in people.state.rows),
        "HumanUser only",
        sorted({row.type for row in people.state.rows}),
    )
    walk.check(
        "people only: the inactive are offered all the same",
        "Bo Chen" in names,
        "Bo Chen",
        names,
    )
    outside_click(page, wait)

    # --- bare references, resolved on the way in -------------------------------------------------------
    bare = picker_in(page, "hydrate")
    scroll_to(page, bare, wait)
    labels = list(bare.control.labels)
    walk.same("hydrate: both references are held", 2, len(labels))
    walk.check(
        "hydrate: both resolved to a name",
        labels == ["Cleo Dias", "Farid Nasser"],
        ["Cleo Dias", "Farid Nasser"],
        labels,
    )

    # --- what the control shows for five selected, wide and narrow ----------------------------------------
    wide = picker_named(page, "chips")
    narrow = picker_named(page, "ellipsis-narrow")
    counted = picker_named(page, "count")
    capped = picker_named(page, "max")
    walk.check(
        "summary: every summary example is on the page",
        all(one is not None for one in (wide, narrow, counted, capped)),
        "four controls",
        [one is not None for one in (wide, narrow, counted, capped)],
    )
    if wide is not None:
        scroll_to(page, wide, wait)
        walk.same("summary: chips draws one chip a value", 5, len(wide.control.chips()))
    if narrow is not None:
        drawn = [chip for chip in narrow.control.chips() if chip.isVisible()]
        walk.check(
            "summary: ellipsis cuts the row and counts the rest",
            0 < len(drawn) < 5 and narrow.control.overflow_pill().isVisible(),
            "whole chips and a +n pill",
            (len(drawn), narrow.control.overflow_pill().count),
        )
    if counted is not None:
        walk.same("summary: count draws no chips at all", 0, len(counted.control.chips()))
        walk.check(
            "summary: count says how many are selected",
            "5" in (counted.control._count_label or ""),
            "a line counting five",
            counted.control._count_label,
        )
    if capped is not None:
        drawn = [chip for chip in capped.control.chips() if chip.isVisible()]
        walk.check("summary: a capped chip row stops at two", len(drawn) <= 2, "<= 2", len(drawn))
        walk.check(
            "summary: the rest is counted by a pill",
            capped.control.overflow_pill().isVisible(),
            True,
            False,
        )
        # The pill opens the list, which is the way to see what it hides.
        click(capped.control.overflow_pill())
        wait(300)
        walk.check("summary: the pill opens the list", capped.control.is_open, True, False)
        outside_click(page, wait)

    # --- sizes, then disabled, read-only, invalid ----------------------------------------------------------
    states = case_widget(page, "states")
    inert = [one for one in states.findChildren(UserMultiPicker) if one.isVisible()]
    walk.same("states: six controls stand in the example", 6, len(inert))
    if len(inert) == 6:
        scroll_to(page, inert[0], wait)
        walk.same(
            "states: the three heights are sm, md and lg",
            ["sm", "md", "lg"],
            [one.control.size for one in inert[:3]],
        )
        click(inert[3].control)
        wait(150)
        walk.check("states: the disabled picker does not open", not inert[3].control.is_open, False, True)
        click(inert[4].control)
        wait(150)
        walk.check("states: the read-only picker does not open", not inert[4].control.is_open, False, True)
        walk.check(
            "states: a read-only chip carries no cross",
            not any(getattr(chip, "removable", False) for chip in inert[4].control.chips()),
            "no cross",
            [getattr(chip, "removable", None) for chip in inert[4].control.chips()],
        )
        walk.check("states: the invalid picker is marked invalid", inert[5].control.invalid, True, False)

    # --- the header ------------------------------------------------------------------------------------------
    scroll_to(page, many, wait)
    click(many.control)
    wait(200)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", many.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = picker_in(page, "multi")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        found = open_and_type(rebuilt, wait, NAME)
        walk.check("header: the rebuilt picker still searches", found > 0, "> 0", found)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
