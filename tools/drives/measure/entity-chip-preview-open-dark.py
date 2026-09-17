"""The entity chip's hover card, open, measured against the upstream DOM walk.

The state twin of `tools/drives/upstream/measure/entity-chip-preview-open.js`. The pointer goes
on the first chip that carries a preview and the card is given its own delay before the popover
and the page under it are both measured.
"""
from __future__ import annotations

import os
import sys

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.widgets.entity_chip import EntityChip

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _leaves import measure_page, measure_popups  # noqa: E402

#: How long the card is given past its own delay.
GRACE_MS = 600


def drive(page, wait, find, prefs) -> dict:
    chips = [chip for chip in find(EntityChip, all=True) if chip.hover_card is not None]
    if not chips:
        return {"verdict": "FAIL the page drew no chip with a preview"}
    chip = chips[0]
    card = chip.hover_card
    where = QtCore.QPointF(chip.rect().center())
    QtWidgets.QApplication.sendEvent(chip, QtGui.QEnterEvent(where, where, where))
    wait(card._open_timer.interval() + GRACE_MS)
    out = measure_page(page)
    out["popups"] = measure_popups()
    out["verdict"] = "PASS the card is open" if card.is_open else "FAIL no card opened"
    return out
