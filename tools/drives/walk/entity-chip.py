"""entity-chip: press a chip, press its cross, and rest on one for its card.

    .venv/bin/python tools/qa.py --page entity-chip --drive tools/drives/walk/entity-chip.py

The page holds chips in four sizes and three variants, a glyph for every type, a chip with no name,
one that is a link and one that is a button, three that carry a cross, and three that open a hover
card read through the context. The walk presses what is pressable, takes the crosses one by one
until the demo offers to put them back, and rests on a chip until its card comes up and leaves it
again. A chip addressed at a site is read but never pressed: its row lives outside this window.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import (  # noqa: E402
    Walk,
    case_widget,
    click,
    click_chip_cross,
    hover,
    key,
    popups,
    scroll_to,
    set_view,
    unhover,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.widgets.entity_chip import EntityChip  # noqa: E402


def chips_in(page, case: str) -> list:
    """The chips of one example."""
    holder = case_widget(page, case)
    return list(holder.findChildren(EntityChip)) if holder is not None else []


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    wait(500)
    demo = find("entity-chip-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no entity-chip demo"}

    # --- the glyph for every type -----------------------------------------------------------
    glyphs = chips_in(page, "glyphs")
    walk.check("glyphs: a chip stands for every type", len(glyphs) >= 10, ">= 10", len(glyphs))
    walk.check(
        "glyphs: every chip names its row",
        all(chip.label for chip in glyphs),
        "a name on each",
        [chip.label for chip in glyphs if not chip.label],
    )

    # --- the three chips that are not plain ---------------------------------------------------
    bare = chips_in(page, "bare")
    walk.same("bare: the example holds three chips", 3, len(bare))
    unnamed, linked, button = bare
    walk.same("bare: a row with no name reads as its type and id", "Version #17055", unnamed.label)
    walk.check("bare: a row with no name is not pressable", not unnamed.interactive, False, unnamed.interactive)
    walk.check("bare: the link chip carries an address", bool(linked.href), True, linked.href)

    taken: list = []
    button.clicked.connect(lambda: taken.append(1))
    scroll_to(page, button, wait)
    click(button)
    wait(250)
    walk.same("bare: pressing the button chip answers once", 1, len(taken))
    button.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(button, QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.same("bare: Enter on the button chip answers too", 2, len(taken))

    # --- the crosses --------------------------------------------------------------------------
    removable = chips_in(page, "removable")
    walk.same("removable: the example opens on three chips", 3, len(removable))
    scroll_to(page, removable[0], wait)
    named = removable[0].label
    walk.check("removable: the first chip carries a cross", click_chip_cross(removable[0]), True, False)
    wait(400)
    left = chips_in(page, "removable")
    walk.same("removable: the cross takes that chip", 2, len(left))
    walk.check(
        "removable: it is the pressed chip that went",
        named not in [chip.label for chip in left],
        f"no {named}",
        [chip.label for chip in left],
    )

    # The keyboard takes one too: Delete on a focused chip is the same act.
    left[0].setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(left[0], QtCore.Qt.Key.Key_Delete)
    wait(400)
    walk.same("removable: Delete takes a chip from the keyboard", 1, len(chips_in(page, "removable")))

    click_chip_cross(chips_in(page, "removable")[0])
    wait(400)
    walk.same("removable: the last cross empties the example", 0, len(chips_in(page, "removable")))
    back = find("put-them-back")
    walk.check("removable: the demo offers to put them back", back is not None, True, back)
    if back is not None:
        click(back)
        wait(400)
        walk.same("removable: pressing it puts all three back", 3, len(chips_in(page, "removable")))

    # --- the hover card -----------------------------------------------------------------------
    cards = chips_in(page, "hover-card")
    walk.check("hover: the read answered chips to rest on", len(cards) > 0, "> 0", len(cards))
    if cards:
        chip = cards[0]
        scroll_to(page, chip, wait)
        card = chip.hover_card
        walk.check("hover: the chip carries a card", card is not None, True, card)
        hover(chip, wait, 900)
        walk.check("hover: resting on the chip opens the card", card.is_open, True, card.is_open)
        walk.check("hover: the card stands on a window of its own", popups() != [], "a popover", popups())
        unhover(chip, wait, 900)
        walk.check("hover: leaving the chip closes the card", not card.is_open, False, card.is_open)
        walk.same("hover: nothing was left standing over the page", [], popups())

    # --- the chips with a thumbnail ---------------------------------------------------------------
    thumbs = chips_in(page, "thumbnail")
    walk.check("thumbnail: the read answered chips with a picture", len(thumbs) > 0, "> 0", len(thumbs))
    walk.check(
        "thumbnail: each names the row it points at",
        all(chip.label for chip in thumbs),
        "a name on each",
        [chip.label for chip in thumbs],
    )

    # --- the view controls ---------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("entity-chip-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    wait(600)
    rebuilt = chips_in(page, "removable")
    walk.check("header: the crosses came back with it", len(rebuilt) == 3, 3, len(rebuilt))
    if rebuilt:
        scroll_to(page, rebuilt[0], wait)
        click_chip_cross(rebuilt[0])
        wait(400)
        walk.same("header: a rebuilt cross still takes its chip", 2, len(chips_in(page, "removable")))
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS a pressable chip answers the mouse and the keyboard, a cross takes its own chip and"
        " the demo puts them back, resting on a chip opens its card and leaving closes it, and the"
        " page follows the view controls"
    )
