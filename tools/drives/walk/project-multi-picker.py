"""project-multi-picker: tick projects, walk the chips, and read the summary modes.

    .venv/bin/python tools/qa.py --page project-multi-picker \
        --drive tools/drives/walk/project-multi-picker.py
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

from sg_widgets_qt.widgets.project_multi_picker import ProjectMultiPicker  # noqa: E402

QUERY = "har"


def picker_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(ProjectMultiPicker) if one.isVisible()]
    return found[index] if index < len(found) else None


def picker_named(page, name: str):
    holder = demo_widget(page, name)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(ProjectMultiPicker) if one.isVisible()]
    return found[0] if found else None


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    many = picker_in(page, "multi")
    walk_multi(walk, page, many, wait, QUERY, "several projects")

    # --- a token field: Backspace walks the chips ---------------------------------------------
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
    held = len(tokens.value)
    key(control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(250)
    walk.same("tokens: Backspace takes the armed chip away", held - 1, len(tokens.value))
    key(control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(150)

    # --- archived projects included --------------------------------------------------------------
    archived = picker_in(page, "archived")
    scroll_to(page, archived, wait)
    found = open_and_type(archived, wait, "")
    walk.check("archived: the list answers rows", found > 0, "> 0", found)
    outside_click(page, wait)

    # --- bare references, resolved on the way in -------------------------------------------------
    bare = picker_in(page, "hydrate")
    scroll_to(page, bare, wait)
    labels = list(bare.control.labels)
    walk.check(
        "hydrate: the bare reference resolved to a name",
        labels == ["Harbour Lights"],
        ["Harbour Lights"],
        labels,
    )

    # --- what the control shows, wide and narrow ---------------------------------------------------
    wide = picker_named(page, "chips")
    counted = picker_named(page, "count")
    capped = picker_named(page, "max")
    walk.check(
        "summary: every summary example is on the page",
        all(one is not None for one in (wide, counted, capped)),
        "three controls",
        [one is not None for one in (wide, counted, capped)],
    )
    if wide is not None:
        scroll_to(page, wide, wait)
        walk.same("summary: chips draws one chip a value", 3, len(wide.control.chips()))
    if counted is not None:
        walk.same("summary: count draws no chips at all", 0, len(counted.control.chips()))
        walk.check(
            "summary: count says how many are selected",
            "3" in (counted.control._count_label or ""),
            "a line counting three",
            counted.control._count_label,
        )
    if capped is not None:
        drawn = [chip for chip in capped.control.chips() if chip.isVisible()]
        walk.check("summary: a capped chip row stops at two", len(drawn) <= 2, "<= 2", len(drawn))
        pill = capped.control.overflow_pill()
        walk.check("summary: the rest is counted by a pill", pill.isVisible() and pill.count == 1, "+1", pill.count)
        click(pill)
        wait(300)
        walk.check("summary: the pill opens the list", capped.control.is_open, True, False)
        outside_click(page, wait)

    # --- sizes, then disabled, read-only, invalid ---------------------------------------------------
    states = case_widget(page, "states")
    inert = [one for one in states.findChildren(ProjectMultiPicker) if one.isVisible()]
    walk.same("states: six controls stand in the example", 6, len(inert))
    if len(inert) == 6:
        scroll_to(page, inert[0], wait)
        walk.same(
            "states: the three heights are sm, md and lg",
            ["sm", "md", "lg"],
            [held.control.size for held in inert[:3]],
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

    # --- the header ------------------------------------------------------------------------------------
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
        found = open_and_type(rebuilt, wait, QUERY)
        walk.check("header: the rebuilt picker still searches", found > 0, "> 0", found)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
