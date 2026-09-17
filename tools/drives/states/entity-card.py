"""The Qt half of the entity card's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/entity-card-loaded.js` for `loaded`; the other states
are this port's own, because the upstream demo carries a tile section where this one carries the
picture-less card, the skeleton and the failed read.

    QA_STATE=error .venv/bin/python tools/qa.py --page entity-card \\
        --drive tools/drives/states/entity-card.py --shot shots/states/entity-card-error.png

    loaded     every card read and every picture landed: the three sizes and the read reference
    sizes      the same, reported size by size, which is the ladder rule 3 pins
    no-picture the card whose row holds no image, so the thumbnail is the type's glyph
    loading    the card whose read never answers, so the skeleton stands
    error      the card on a row no site has, so the error line stands
    hover      the pointer on the first card's name, which underlines it
    selected   the card taken, which is what a collection sets on a tile
    clicked    the first card's name activated, so `clicked` has fired
"""
from __future__ import annotations

import os
import time

from qtpy import QtCore, QtGui

from sg_widgets_qt.widgets.entity_card import EntityCard

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = (
    "loaded",
    "sizes",
    "no-picture",
    "loading",
    "error",
    "hover",
    "selected",
    "clicked",
)

#: What each named case of the demo is called.
CASES: dict[str, str] = {
    "no-picture": "case-no-picture",
    "loading": "case-loading",
    "error": "case-error",
}


def state_name() -> str:
    wanted = os.environ.get("QA_STATE", "loaded").strip().lower()
    return wanted if wanted in STATES else "loaded"


def wait_for(read, wait, ms: int = 12000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def cards(find) -> list:
    return [card for card in find(EntityCard, all=True) if card.isVisible()]


def case_of(card) -> str:
    """The demo section a card stands in, by the object name its section carries."""
    walk = card.parentWidget()
    for _ in range(8):
        if walk is None:
            return ""
        name = walk.objectName()
        if name.startswith("case-"):
            return name
        walk = walk.parentWidget()
    return ""


def in_case(find, case: str) -> list:
    return [card for card in cards(find) if case_of(card) == case]


def settled(find) -> bool:
    """True once every card but the one whose read never answers holds a row or an error."""
    held = cards(find)
    return bool(held) and all(
        not card.loading or case_of(card) == "case-loading" for card in held
    )


def described(card) -> dict:
    model = card.model
    return {
        "case": case_of(card),
        "size": card.size,
        "name": card.name,
        "loading": card.loading,
        "error": card.error,
        "type_label": model.type_label if model is not None else "",
        "status": model.status.code if model is not None and model.status is not None else "",
        "columns": [column.label for column in model.columns] if model is not None else [],
        "values": [value.text for value in card.values],
    }


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(400)
    state = state_name()
    wait_for(lambda: settled(find), wait)
    # A picture is read after the row, so the shot waits for it the way upstream's does.
    from sg_widgets_qt.images import image_loader

    wait_for(lambda: image_loader().pending == 0, wait, 8000)
    wait(300)

    held = cards(find)
    if not held:
        return {"verdict": f"FAIL {page.data_name}: the page drew no card"}

    if state in CASES:
        case = CASES[state]
        found = in_case(find, case)
        if not found:
            return {"verdict": f"FAIL the page has no {case} card"}
        card = found[0]
        if state == "loading" and not card.loading:
            return {"verdict": "FAIL the loading card answered its read"}
        if state == "error" and not card.error:
            return {"verdict": "FAIL the card meant to fail read a row"}
        if state == "no-picture" and card.loading:
            return {"verdict": "FAIL the picture-less card never read its row"}
        return {"verdict": f"PASS {state}", "state": state, "card": described(card)}

    if state == "sizes":
        by_size = {card.size: described(card) for card in in_case(find, "case-sizes")}
        missing = [step for step in ("sm", "md", "lg") if step not in by_size]
        return {
            "verdict": (
                "PASS the card stands at all three sizes"
                if not missing
                else f"FAIL the page drew no {', '.join(missing)} card"
            ),
            "state": state,
            "sizes": by_size,
        }

    read = [card for card in held if not card.loading and card.error is None]
    if not read:
        return {"verdict": "FAIL no card on the page read a row"}
    card = read[0]

    if state == "hover":
        name = card.findChild(QtCore.QObject, "entity-card-name")
        if name is None:
            return {"verdict": "FAIL the card drew no name"}
        name.set_hovered(True)
        wait(400)
        return {"verdict": "PASS the pointer is on the card's name", "state": state, "name": card.name}

    if state == "selected":
        fired: list = []
        card.selected_changed.connect(fired.append)
        card.set_selected(True)
        wait(300)
        return {
            "verdict": (
                "PASS the card is taken and said so"
                if card.selected and fired == [True]
                else f"FAIL selected={card.selected} reported {fired}"
            ),
            "state": state,
        }

    if state == "clicked":
        name = card.findChild(QtCore.QObject, "entity-card-name")
        if name is None:
            return {"verdict": "FAIL the card drew no name"}
        fired: list = []
        card.clicked.connect(lambda: fired.append(1))
        caught = _Caught()
        QtGui.QDesktopServices.setUrlHandler("https", caught, "handle")
        try:
            name._activate()
            wait(300)
        finally:
            QtGui.QDesktopServices.unsetUrlHandler("https")
        return {
            "verdict": (
                "PASS the name emitted clicked and addressed the row's page"
                if fired and (not card.url or caught.urls)
                else f"FAIL clicked fired {len(fired)} times, opened {caught.urls}"
            ),
            "state": state,
            "url": card.url,
            "opened": caught.urls,
        }

    return {
        "verdict": f"PASS {len(held)} cards loaded",
        "state": state,
        "cards": [described(one) for one in held],
    }


class _Caught(QtCore.QObject):
    """Takes the `https` handler, so an activated name opens nothing."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    @QtCore.Slot(QtCore.QUrl)
    def handle(self, url: QtCore.QUrl) -> None:
        self.urls.append(url.toString())
