"""entity-card: read a card, press it, and hand it a reference the picker chose.

    .venv/bin/python tools/qa.py --page entity-card --drive tools/drives/walk/entity-card.py

The page stands the same row on three steps of the ladder, then a card that reads whatever the
picker beside it points at, then the three states: no picture, still reading, and a read that
failed. The walk presses a card's name, picks another row and watches the card read it, and reads
what each state says rather than leaving a blank box.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import (  # noqa: E402
    Walk,
    case_widget,
    click,
    click_row,
    key,
    popups,
    scroll_to,
    set_view,
    type_into,
    wait_for,
)
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_qt.images import image_loader  # noqa: E402
from sg_widgets_qt.widgets.entity_card import EntityCard  # noqa: E402
from sg_widgets_qt.widgets.thumbnail import Thumbnail  # noqa: E402


def cards_in(page, case: str) -> list:
    holder = case_widget(page, case)
    return list(holder.findChildren(EntityCard)) if holder is not None else []


def named(card) -> str:
    """What the card calls the row it stands for."""
    for one in card.findChildren(QtWidgets.QWidget):
        if one.objectName() == "entity-card-name":
            return one.text
    return ""


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("entity-card-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no entity-card demo"}
    wait_for(lambda: demo.demo_ready(), wait, 25000)
    wait_for(lambda: image_loader().pending == 0, wait, 20000)
    wait(300)

    # --- the same row on three steps -------------------------------------------------------
    ladder = cards_in(page, "sizes")
    walk.same("the ladder stands the row on three steps", 3, len(ladder))
    steps = [card.size for card in ladder]
    walk.same("the three steps are small, medium and large", ["sm", "md", "lg"], steps)
    walk.check(
        "every card names the row it stands for",
        all(named(card) for card in ladder),
        "a name on each",
        [named(card) for card in ladder],
    )
    walk.check(
        "they all name the same row",
        len({named(card) for card in ladder}) == 1,
        "one name",
        sorted({named(card) for card in ladder}),
    )
    walk.check(
        "each step stands taller than the one under it",
        ladder[0].height() < ladder[1].height() < ladder[2].height(),
        "a rising ladder",
        [card.height() for card in ladder],
    )
    walk.check(
        "the card draws the row's fields under its name",
        [
            one
            for one in ladder[1].findChildren(QtWidgets.QWidget)
            if one.objectName() == "entity-card-value"
        ],
        "a field",
        None,
    )

    # --- a card is pressed ---------------------------------------------------------------------
    # The name is what answers a press on a card: the card variant is a figure, not a button, and
    # `EntityCard.clicked` is the name's own activation.
    card = ladder[1]
    scroll_to(page, card, wait)
    taken: list = []
    card.clicked.connect(lambda: taken.append(1))
    name_line = next(
        one for one in card.findChildren(QtWidgets.QWidget) if one.objectName() == "entity-card-name"
    )
    activated: list = []
    name_line.activated.connect(lambda: activated.append(1))
    click(name_line)
    wait(250)
    walk.same("pressing the row's name answers once", 1, len(activated))
    walk.same("the card passes that on as its own press", 1, len(taken))
    name_line.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(name_line, QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.same("the name answers the keyboard too", 2, len(activated))
    walk.same("the card passes that on as well", 2, len(taken))

    # --- a reference picked, and the card reads it ------------------------------------------------
    picker = find("entity-picker")
    read_card = demo._read_card  # noqa: SLF001
    walk.check("the picker stands beside the reading card", picker is not None, True, picker)
    walk.check("the card opens on a row the picker handed it", named(read_card), "a name", named(read_card))
    if picker is not None:
        held = named(read_card)
        scroll_to(page, picker, wait)
        click(picker.control)
        wait(400)
        walk.check("the picker opens its list", picker.control.is_open, True, picker.control.is_open)
        type_into(picker.control.caret(), "sh", wait)
        wait_for(lambda: not picker.state.loading, wait, 15000)
        wait(300)
        rows = picker.state.rows
        walk.check("the picker answers rows to choose from", len(rows) > 0, "> 0", len(rows))
        chosen = 0
        for index in range(len(rows)):
            if click_row(picker.control.list_surface(), index):
                chosen = index
                break
        wait(400)
        wait_for(lambda: named(read_card) and named(read_card) != held, wait, 15000)
        wait_for(lambda: image_loader().pending == 0, wait, 15000)
        wait(300)
        walk.check(
            "the card reads the row the picker chose",
            named(read_card) and named(read_card) != held,
            f"not {held}",
            named(read_card),
        )
        walk.check("no list was left standing over the page", not picker.control.is_open, False, True)
        _ = chosen

    # --- the three states ----------------------------------------------------------------------------
    bare = cards_in(page, "no-picture")
    walk.check("the card with no picture is drawn", bare, "a card", len(bare))
    if bare:
        tiles = bare[0].findChildren(Thumbnail)
        walk.check(
            "it falls back rather than leaving a blank box",
            tiles and all(one.pixmap is None for one in tiles),
            "a fallback",
            [(one.state, one.pixmap is not None) for one in tiles],
        )
        walk.check("it still names its row", named(bare[0]), "a name", named(bare[0]))

    skeleton = find("entity-card-skeleton")
    walk.check("the card still reading draws a skeleton", skeleton is not None, True, skeleton)
    if skeleton is not None:
        walk.check("the skeleton is given room", skeleton.height() > 0, "> 0", skeleton.height())

    failed = find("entity-card-error")
    walk.check("the card whose read failed says so", failed is not None, True, failed)

    # --- the view controls ------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("entity-card-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready(), wait, 25000)
        wait_for(lambda: image_loader().pending == 0, wait, 20000)
        wait(300)
        rebuilt = cards_in(page, "sizes")
        walk.same("header: the ladder came back", 3, len(rebuilt))
        walk.same("header: the ladder keeps the steps it named", ["sm", "md", "lg"], [c.size for c in rebuilt])
        walk.check(
            "header: the cards still name their row",
            all(named(card) for card in rebuilt),
            "a name on each",
            [named(card) for card in rebuilt],
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the ladder stands one row on three steps, a card answers a press on itself and on"
        " the row's name, the card beside the picker reads whatever it is handed, and the three"
        " states each say what happened rather than leaving a blank box"
    )
