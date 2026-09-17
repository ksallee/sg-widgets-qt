"""The card: the paths it labels, the one status it draws, what a pick costs, and its signals.

    .venv/bin/python tools/qa.py --page entity-card --drive tools/drives/entity-card.py
    .venv/bin/python tools/qa.py --page entity-card --drive tools/drives/entity-card.py --qt5

The port of `~/dev/sg-widgets/tools/drives/entity-card.js` and `entity-card-one-status.js`, with
the tile clauses left to EntityGrid's own drive. The upstream pair reads the DOM; here a card is a
tree of painted widgets, so the same claims are read off its properties:

    every card from the held row is named and carries the dotted label `Link › Shot › Sequence`
    every card draws one status, in its header, and no Status row in the grid beside it
    a pick hands the card a type and an id, and the card reads the row itself
    a second card on a row already read costs no further search (probe: the context's cache)
    the name emits `clicked` and addresses the row's own page, and never opens one here
    a row no site has shows the error line with what the read said

Nothing here follows a link: the drive takes the `https` handler for the length of the run.
"""
from __future__ import annotations

import time

from qtpy import QtCore, QtGui

from sg_widgets_core.filter import EntityRef
from sg_widgets_qt.images import image_loader
from sg_widgets_qt.widgets.entity_card import EntityCard

#: The label a path through a link that accepts several types is given (probe 059).
DOTTED = "Link › Shot › Sequence"

#: The field the demo names that the header already draws, so the grid must not draw it twice.
STATUS_PATH = "sg_status_list"


class _Caught(QtCore.QObject):
    """Takes the `https` handler, so an activated name opens nothing."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    @QtCore.Slot(QtCore.QUrl)
    def handle(self, url: QtCore.QUrl) -> None:
        self.urls.append(url.toString())


def wait_for(read, wait, ms: int = 12000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def case_of(card) -> str:
    walk = card.parentWidget()
    for _ in range(8):
        if walk is None:
            return ""
        if walk.objectName().startswith("case-"):
            return walk.objectName()
        walk = walk.parentWidget()
    return ""


def cards(find) -> list:
    return [card for card in find(EntityCard, all=True) if card.isVisible()]


def searches(page) -> int:
    """How many searches the demos on this page have cost so far."""
    context = page.context
    return int(context.reads.get("search", 0)) if context is not None else 0


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(400)
    failures: list[str] = []
    seen: dict = {}

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    caught = _Caught()
    QtGui.QDesktopServices.setUrlHandler("https", caught, "handle")
    try:
        wait_for(
            lambda: bool(cards(find))
            and all(not card.loading or case_of(card) == "case-loading" for card in cards(find)),
            wait,
        )
        wait_for(lambda: image_loader().pending == 0, wait, 8000)
        held = [card for card in cards(find) if case_of(card) == "case-sizes"]
        seen["cards"] = len(cards(find))
        seen["from_a_row"] = len(held)
        if len(held) != 3:
            note("sizes", f"the demo drew {len(held)} cards from the held row, wanted 3")

        # 1. Every card is named, and the dotted path is labelled through the schema.
        for card in held:
            if not card.name:
                note("name", f"a {card.size} card is unnamed")
            labels = [column.label for column in (card.model.columns if card.model else [])]
            if DOTTED not in labels:
                note("labels", f"a {card.size} card labels {labels}, with no {DOTTED!r}")
        seen["labels"] = [c.label for c in (held[0].model.columns if held and held[0].model else [])]

        # 2. One status, in the header, and no Status row in the grid beside it.
        for card in held:
            model = card.model
            if model is None or model.status is None:
                note("status", f"a {card.size} card read no status for its header")
                continue
            drawn = [
                column.path
                for column in model.columns
                if column.path.rsplit(".", 1)[-1] == STATUS_PATH
            ]
            if drawn:
                note("status", f"a {card.size} card draws {drawn} in the grid beside its badge")
        seen["header_status"] = held[0].model.status.code if held and held[0].model and held[0].model.status else ""

        # 3. A pick hands the card a type and an id: the card reads the row itself.
        picked = [card for card in cards(find) if case_of(card) == "case-reference"]
        if not picked:
            note("reference", "the demo drew no card reading a picked reference")
        else:
            card = picked[0]
            before = searches(page)
            card.set_entity(EntityRef(type=card.model.entity.type, id=card.model.entity.id) if card.model else None)
            wait_for(lambda: not card.loading, wait)
            again = searches(page)
            seen["reread"] = {"searches_before": before, "searches_after": again, "name": card.name}
            if card.loading or not card.name:
                note("reference", "a reference the card already read never came back")
            # The read goes through the context's cache, so the same row costs nothing twice.
            if again > before:
                note(
                    "cache",
                    f"reading a row the page already holds cost {again - before} more searches",
                )

        # 4. The name emits `clicked` and addresses the row's own page.
        card = held[0] if held else None
        if card is not None:
            name = card.findChild(QtCore.QObject, "entity-card-name")
            fired: list[int] = []
            card.clicked.connect(lambda: fired.append(1))
            if name is None:
                note("clicked", "the card drew no name to activate")
            else:
                name._activate()
                wait(200)
                seen["clicked"] = {"fired": len(fired), "url": card.url, "opened": list(caught.urls)}
                if not fired:
                    note("clicked", "activating the name emitted no clicked")
                if card.url and "/detail/" not in card.url:
                    note("clicked", f"the name points at {card.url}, wanted a detail page")
                # The one link this run is allowed to open is the one it asked for.
                if card.url and caught.urls != [card.url]:
                    note("clicked", f"the name opened {caught.urls}, wanted [{card.url}]")
                if not card.url and caught.urls:
                    note("clicked", f"a card with no site opened {caught.urls}")
                caught.urls.clear()

        # 5. `selected_changed` carries the new state, and only on a change.
        if card is not None:
            reported: list[bool] = []
            card.selected_changed.connect(reported.append)
            card.set_selected(True)
            card.set_selected(True)
            card.set_selected(False)
            wait(100)
            seen["selected"] = reported
            if reported != [True, False]:
                note("selected", f"selected_changed reported {reported}, wanted [True, False]")

        # 6. A row no site has shows the error line with what the read said.
        broken = [one for one in cards(find) if case_of(one) == "case-error"]
        if not broken:
            note("error", "the demo drew no card on an unreadable row")
        else:
            said = broken[0].error or ""
            seen["error"] = said
            if not said:
                note("error", "the card on an unreadable row shows no error")
            elif "not readable" not in said:
                note("error", f"the error line says {said!r}, wanted upstream's wording")
            line = broken[0].findChild(QtCore.QObject, "entity-card-error")
            if line is None:
                note("error", "the failed card drew no state line")

        # 7. The skeleton stands while a read is out, and the picture-less card still reads.
        waiting = [one for one in cards(find) if case_of(one) == "case-loading"]
        bare = [one for one in cards(find) if case_of(one) == "case-no-picture"]
        seen["loading"] = [one.loading for one in waiting]
        seen["no_picture"] = [one.name for one in bare]
        if not waiting or not all(one.loading for one in waiting):
            note("loading", "the card whose read never answers is not behind its skeleton")
        if not bare or any(one.loading or not one.name for one in bare):
            note("no-picture", "the card on a row with no image never read it")

        if caught.urls:
            note("links", f"the drive opened {len(caught.urls)} links it never asked for")
    finally:
        QtGui.QDesktopServices.unsetUrlHandler("https")

    return {
        "verdict": (
            "PASS three cards from a row with the dotted label, one status each and none in the "
            "grid, a pick read through the cache, a name that emits clicked and points at the "
            "row's page, selected_changed on a change only, and the error line on an unreadable row"
            if not failures
            else "FAIL " + "; ".join(failures[:8])
        ),
        "failures": failures,
        "seen": seen,
    }
