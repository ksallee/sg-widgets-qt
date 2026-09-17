"""picker-control: every shape on the page, used the way its caption invites.

    .venv/bin/python tools/qa.py --page picker-control \
        --drive tools/drives/walk/picker-control.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    case_widget,
    click,
    click_chip_cross,
    click_row,
    key,
    outside_click,
    scroll_to,
    type_into,
    wear,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.widgets.picker_control import PickerControl  # noqa: E402


def control_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(PickerControl) if one.isVisible()]
    return found[index] if index < len(found) else None


def caret_of(control):
    """The input a person types into: the control's own, or the popup's search box."""
    return control.caret()


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- single, inline: the caret sits beside the chip ---------------------------------
    one = control_in(page, "inline")
    scroll_to(page, one, wait)
    click(one)
    wait(200)
    walk.check("inline: a click opens the list", one.is_open, True, one.is_open)
    surface = one.list_surface()
    walk.check("inline: every department is offered", surface.row_count() == 8, 8, surface.row_count())

    type_into(one.caret(), "light", wait)
    wait(200)
    walk.same("inline: typing filters to one row", 1, surface.row_count())
    walk.same("inline: the query reached the demo", "light", one.query)

    key(one.caret(), QtCore.Qt.Key.Key_Down)
    key(one.caret(), QtCore.Qt.Key.Key_Return)
    wait(200)
    walk.same("inline: Enter picks the armed row", ["light"], list(one.keys))
    walk.same("inline: the value reads Lighting", ["Lighting"], list(one.labels))
    walk.check("inline: a single pick closes the list", not one.is_open, False, one.is_open)

    click(one.clear_control())
    wait(150)
    walk.same("inline: the clear control empties the value", [], list(one.keys))

    click(one)
    wait(150)
    key(one.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("inline: Escape closes the list", not one.is_open, False, one.is_open)

    click(one)
    wait(150)
    outside_click(page, wait)
    walk.check("inline: a press outside closes the list", not one.is_open, False, one.is_open)

    # --- single, summary: the value reads as plain text ---------------------------------
    text = control_in(page, "text")
    scroll_to(page, text, wait)
    walk.same("summary: the demo opens on Compositing", ["Compositing"], list(text.labels))
    click(text)
    wait(250)
    walk.check("summary: a click opens the list", text.is_open, True, text.is_open)
    walk.check("summary: the search row moved into the popup", text.search_row().isVisible(), True, False)
    caret = caret_of(text)
    type_into(caret, "anim", wait)
    wait(200)
    walk.same("summary: the popup's search box filters", 1, text.list_surface().row_count())
    walk.check("summary: the row is picked with the mouse", click_row(text.list_surface(), 0), True, False)
    wait(250)
    walk.same("summary: the pick replaces the value", ["anim"], list(text.keys))
    walk.check("summary: the pick closes the list", not text.is_open, False, text.is_open)

    # --- several, inline: a token field -------------------------------------------------
    tokens = control_in(page, "tokens")
    scroll_to(page, tokens, wait)
    walk.same("tokens: the demo opens on two chips", 2, len(tokens.chips()))
    click(tokens)
    wait(250)
    walk.check("tokens: a click opens the list", tokens.is_open, True, tokens.is_open)
    walk.check("tokens: a row is ticked with the mouse", click_row(tokens.list_surface(), 0), True, False)
    wait(250)
    walk.same("tokens: the pick adds a third key", 3, len(tokens.keys))
    walk.check("tokens: a multi pick keeps the list open", tokens.is_open, True, tokens.is_open)
    walk.same("tokens: a third chip is drawn", 3, len(tokens.chips()))

    before = list(tokens.keys)
    took = click_chip_cross(tokens.chips()[0])
    walk.check("tokens: the first chip carries a cross", took, True, took)
    wait(200)
    walk.same("tokens: the cross removes that chip", before[1:], list(tokens.keys))

    key(tokens.caret(), QtCore.Qt.Key.Key_Escape)
    wait(150)
    left = list(tokens.keys)
    tokens.caret().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    key(tokens.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(100)
    key(tokens.caret(), QtCore.Qt.Key.Key_Backspace)
    wait(200)
    walk.same("tokens: Backspace on an empty query removes the last chip", left[:-1], list(tokens.keys))

    # --- several, summary ---------------------------------------------------------------
    summary = control_in(page, "summary")
    scroll_to(page, summary, wait)
    click(summary)
    wait(250)
    walk.check("summary picker: a click opens the list", summary.is_open, True, summary.is_open)
    held = len(summary.keys)
    walk.check("summary picker: a row is ticked", click_row(summary.list_surface(), 3), True, False)
    wait(250)
    walk.check(
        "summary picker: the tick moved the value",
        len(summary.keys) != held,
        f"not {held}",
        len(summary.keys),
    )
    outside_click(page, wait)
    walk.check("summary picker: a press outside closes it", not summary.is_open, False, summary.is_open)

    # --- eight selected in 320: whole chips, then a +n pill -----------------------------
    crowd = control_in(page, "overflow")
    scroll_to(page, crowd, wait)
    pill = crowd.overflow_pill()
    walk.check("overflow: a +n pill stands after the chips", pill is not None and pill.isVisible(), True, pill)
    if pill is not None and pill.isVisible():
        walk.check("overflow: the pill counts what it hides", pill.count > 0, "> 0", pill.count)
        click(pill)
        wait(250)
        walk.check("overflow: the pill opens the list", crowd.is_open, True, crowd.is_open)
        outside_click(page, wait)

    # --- a fixed set: no search row -----------------------------------------------------
    fixed = control_in(page, "fixed")
    scroll_to(page, fixed, wait)
    click(fixed)
    wait(250)
    walk.check("fixed: a click opens the list", fixed.is_open, True, fixed.is_open)
    walk.check(
        "fixed: no search row is drawn",
        not fixed.search_row().isVisible(),
        False,
        fixed.search_row().isVisible(),
    )
    key(fixed, QtCore.Qt.Key.Key_Down)
    key(fixed, QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.same("fixed: Enter picks from the keyboard", 1, len(fixed.keys))
    walk.check("fixed: the pick closes the list", not fixed.is_open, False, fixed.is_open)

    # --- disabled, read-only and invalid ------------------------------------------------
    disabled = control_in(page, "states", 0)
    readonly = control_in(page, "states", 1)
    invalid = control_in(page, "states", 2)
    scroll_to(page, disabled, wait)
    click(disabled)
    wait(150)
    walk.check("states: the disabled control does not open", not disabled.is_open, False, disabled.is_open)
    click(readonly)
    wait(150)
    walk.check("states: the read-only control does not open", not readonly.is_open, False, readonly.is_open)
    walk.check("states: the invalid control is marked invalid", invalid.invalid, True, invalid.invalid)

    # --- a row and a chip of the caller's own -------------------------------------------
    custom = control_in(page, "custom")
    scroll_to(page, custom, wait)
    click(custom)
    wait(250)
    from sg_widgets_qt.primitives.roles import Roles

    index = custom.list_surface().model().index(0, 0)
    walk.check(
        "custom: the row carries the demo's own sub-label",
        bool(index.data(Roles.SUB_LABEL)),
        "a lead",
        index.data(Roles.SUB_LABEL),
    )
    outside_click(page, wait)

    # --- the header -----------------------------------------------------------------------
    click(one)
    wait(150)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", one.is_open, True, one.is_open)
    walk.same("header: the page wears dark", "dark", prefs.theme)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=700)
    again = control_in(page, "inline")
    walk.check("header: the demo survives a rebuild", again is not None, True, again)
    if again is not None:
        walk.same("header: the controls wear the size step", "lg", again.size)
        click(again)
        wait(250)
        walk.check("header: the rebuilt control still opens", again.is_open, True, again.is_open)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=700)

    return walk.result()
