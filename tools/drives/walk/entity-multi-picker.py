"""entity-multi-picker: tick several shots, walk the chips, page the list, arm a read to fail.

    .venv/bin/python tools/qa.py --page entity-multi-picker \
        --drive tools/drives/walk/entity-multi-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    case_widget,
    check_ink,
    click,
    key,
    open_and_type,
    orphans,
    outside_click,
    scroll_to,
    type_into,
    wait_for,
    walk_multi,
    wear,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.entity_multi_picker import EntityMultiPicker  # noqa: E402

QUERY = "sh0"


def picker_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(EntityMultiPicker) if one.isVisible()]
    return found[index] if index < len(found) else None


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- several shots ---------------------------------------------------------------------
    many = picker_in(page, "multi")
    walk_multi(walk, page, many, wait, QUERY, "several")

    # --- a token field: Backspace walks the chips -------------------------------------------
    tokens = picker_in(page, "tokens")
    scroll_to(page, tokens, wait)
    walk.same("tokens: the demo opens on three chips", 3, len(tokens.control.chips()))
    control = tokens.control
    control.caret().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    key(control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(150)
    walk.same("tokens: the first Backspace arms the last chip", 2, control.armed)
    key(control.caret(), QtCore.Qt.Key.Key_Left)
    wait(100)
    walk.same("tokens: Left walks to the chip before it", 1, control.armed)
    key(control.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(250)
    walk.same("tokens: Backspace takes the armed chip away", 2, len(tokens.value))
    key(control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(150)

    # --- status on the right of every row ----------------------------------------------------
    second = picker_in(page, "status-secondary")
    scroll_to(page, second, wait)
    open_and_type(second, wait, QUERY)
    surface = second.control.list_surface()
    wait_for(lambda: callable(surface.model().index(0, 0).data(Roles.PAINTER)), wait)
    index = surface.model().index(0, 0)
    walk.check(
        "status secondary: the row draws a status badge on the right",
        callable(index.data(Roles.PAINTER)),
        "a status painter",
        (index.data(Roles.SECONDARY), index.data(Roles.PAINTER)),
    )
    outside_click(page, wait)

    # --- three types in one list --------------------------------------------------------------
    kinds = picker_in(page, "multi-type")
    scroll_to(page, kinds, wait)
    found = open_and_type(kinds, wait, "sh")
    walk.check("three types: the query answers rows", found > 0, "> 0", found)
    types = {row.type for row in kinds.state.rows}
    walk.check("three types: more than one type is offered", len(types) > 1, "> 1", sorted(types))
    index = kinds.control.list_surface().model().index(0, 0)
    walk.check(
        "three types: the type is drawn on the right",
        index.data(Roles.SECONDARY) in types,
        "a type",
        index.data(Roles.SECONDARY),
    )
    outside_click(page, wait)

    # --- the id, rendered by the caller --------------------------------------------------------
    own = picker_in(page, "custom-secondary")
    scroll_to(page, own, wait)
    open_and_type(own, wait, QUERY)
    secondary = own.control.list_surface().model().index(0, 0).data(Roles.SECONDARY)
    walk.check(
        "custom secondary: the caller's own text is drawn",
        isinstance(secondary, str) and secondary.startswith("#"),
        "#<id>",
        secondary,
    )
    outside_click(page, wait)

    # --- bare references, resolved on the way in -------------------------------------------------
    bare = picker_in(page, "hydrate")
    scroll_to(page, bare, wait)
    labels = list(bare.control.labels)
    walk.same("hydrate: both references are held", 2, len(labels))
    walk.check(
        "hydrate: both resolved to a name",
        all(label and not label.startswith(("Shot ", "Asset ")) for label in labels),
        "two names",
        labels,
    )

    # --- two shots excluded from the results ------------------------------------------------------
    kept = picker_in(page, "exclude")
    scroll_to(page, kept, wait)
    found = open_and_type(kept, wait, "sh010")
    walk.check("exclude: the query answers rows", found > 0, "> 0", found)
    walk.check(
        "exclude: neither excluded shot is offered",
        all(row.id not in (862, 863) for row in kept.state.rows),
        "neither 862 nor 863",
        [row.id for row in kept.state.rows],
    )
    outside_click(page, wait)

    # --- five a page, with a load more row -----------------------------------------------------------
    paged = picker_in(page, "more")
    scroll_to(page, paged, wait)
    found = open_and_type(paged, wait, QUERY)
    walk.same("paging: a page is five rows", 5, found)
    surface = paged.control.list_surface()
    walk.check("paging: a load-more row stands under them", surface.load_more_visible(), True, False)
    held = len(paged.state.rows)
    surface.set_highlight(surface.row_count() - 1)
    key(paged.control.caret(), QtCore.Qt.Key.Key_Return)
    wait_for(lambda: not paged.state.loading and len(paged.state.rows) > held, wait)
    walk.check(
        "paging: Enter on the load-more row lands a page",
        len(paged.state.rows) > held,
        f"> {held}",
        len(paged.state.rows),
    )
    walk.check("paging: paging is not a pick", paged.control.is_open, True, False)
    outside_click(page, wait)

    # --- a read armed to fail --------------------------------------------------------------------------
    broken = picker_in(page, "error")
    scroll_to(page, broken, wait)
    arm = find("arm-failure")
    walk.check("error: the demo offers the arming control", arm is not None, True, arm)
    if arm is not None:
        click(arm)
        wait(100)
        click(broken.control)
        wait(150)
        type_into(broken.control.caret(), "sha", wait)
        wait_for(lambda: broken.state.error is not None, wait, 4000)
        walk.check(
            "error: the armed failure reaches the control",
            broken.state.error is not None,
            "an error",
            broken.state.error,
        )
        walk.same("error: the list draws its error line", "error", broken.control.state_line().state)
        outside_click(page, wait)

    # --- what the control shows for five selected, wide and narrow --------------------------------------
    summary = case_widget(page, "summary")
    shown = [one for one in summary.findChildren(EntityMultiPicker) if one.isVisible()]
    walk.same("summary: seven controls stand in the example", 7, len(shown))
    if len(shown) == 7:
        # chips wide, chips narrow, ellipsis wide, ellipsis narrow, count wide, count narrow, capped.
        scroll_to(page, shown[0], wait)
        walk.same("summary: chips draws one chip a value", 5, len(shown[0].control.chips()))
        narrow = shown[3]
        drawn = [chip for chip in narrow.control.chips() if chip.isVisible()]
        walk.check(
            "summary: ellipsis cuts the row at 320 and counts the rest",
            0 < len(drawn) < 5 and narrow.control.overflow_pill().isVisible(),
            "whole chips and a +n pill",
            (len(drawn), narrow.control.overflow_pill().count),
        )
        counted = shown[4]
        walk.same("summary: count draws no chips at all", 0, len(counted.control.chips()))
        walk.check(
            "summary: count says how many are selected",
            "5" in (counted.control._count_label or ""),
            "a line counting five",
            counted.control._count_label,
        )
        capped = shown[6]
        drawn = [chip for chip in capped.control.chips() if chip.isVisible()]
        walk.check(
            "summary: a capped chip row stops at its maximum",
            len(drawn) <= 2,
            "<= 2 drawn",
            len(drawn),
        )
        pill = capped.control.overflow_pill()
        walk.check("summary: the rest is counted by a pill", pill.isVisible() and pill.count > 0, "+n", pill.count)

    # --- disabled, read-only, invalid ---------------------------------------------------------------------
    states = case_widget(page, "states")
    inert = [one for one in states.findChildren(EntityMultiPicker) if one.isVisible()]
    walk.same("states: three controls stand in the example", 3, len(inert))
    if len(inert) == 3:
        scroll_to(page, inert[0], wait)
        click(inert[0].control)
        wait(150)
        walk.check("states: the disabled picker does not open", not inert[0].control.is_open, False, True)
        click(inert[1].control)
        wait(150)
        walk.check("states: the read-only picker does not open", not inert[1].control.is_open, False, True)
        walk.check("states: the invalid picker is marked invalid", inert[2].control.invalid, True, False)
        walk.check(
            "states: a read-only chip carries no cross",
            not any(getattr(chip, "removable", False) for chip in inert[1].control.chips()),
            "no cross",
            [getattr(chip, "removable", None) for chip in inert[1].control.chips()],
        )

    # --- the header ------------------------------------------------------------------------------------------
    scroll_to(page, many, wait)
    click(many.control)
    wait(200)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", many.control.is_open, True, False)
    # The list, its chips and the box the query is typed into, in the theme this class of defect
    # shows in: a field holding the application's ink is black on the popover's surface.
    check_ink(walk)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1400)
    rebuilt = picker_in(page, "multi")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        found = open_and_type(rebuilt, wait, QUERY)
        walk.check("header: the rebuilt picker still searches", found > 0, "> 0", found)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1400)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
