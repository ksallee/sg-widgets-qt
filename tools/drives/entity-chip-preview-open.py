"""The state matrix: a chip's hover card, open.

    .venv/bin/python tools/qa.py --page entity-chip \
      --drive tools/drives/entity-chip-preview-open.py --shot /tmp/entity-chip-preview-open.png

The twin of `tools/drives/upstream/entity-chip-preview-open.js`. The pointer is put on the first
chip that carries a preview and the card is given its own delay. Upstream the card holds an
EntityCard; here it holds what `set_preview_builder` was given, and the page's own stand-in until
that widget lands, which is the difference the shot shows.
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.widgets.entity_chip import EntityChip

#: How long the card is given past its own delay.
GRACE_MS = 600


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    chips = [chip for chip in find(EntityChip, all=True) if chip.hover_card is not None]
    if not chips:
        return {"verdict": "FAIL the page drew no chip with a preview"}
    chip = chips[0]
    card = chip.hover_card
    where = QtCore.QPointF(chip.rect().center())
    QtWidgets.QApplication.sendEvent(chip, QtGui.QEnterEvent(where, where, where))
    wait(card._open_timer.interval() + GRACE_MS)
    return {
        "verdict": (
            "PASS the card is open on the chip"
            if card.is_open
            else "FAIL no card opened on the chip"
        ),
        "seen": {"row": f"{chip.entity.type} {chip.entity.id}", "fields": chip.preview},
    }
