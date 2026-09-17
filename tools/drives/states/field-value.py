"""The Qt half of the field value's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/field-value-<state>.js` where upstream has one; the
demo there is one table of every data type with no density, no disabled and no delegate, so only
`rest` has a pair and the rest of the matrix is this port's own.

    QA_STATE=compact .venv/bin/python tools/qa.py --page field-value \\
        --drive tools/drives/states/field-value.py --shot shots/states/field-value-compact.png

    rest      the page as it settles: every data type, both faces
    compact   the collection density the toolbar holds set to compact, so chips drop a step
    disabled  every value inert, which is rule 5's 50%
    hover     the pointer on the first entity chip and on the url value
    preview   the hover card of a chip that carries a preview, open
    faces     no shot: the two faces rendered into one pixmap each and compared, value by value

`faces` is the claim the docs page makes — "both faces settle what to draw through one call, so a
cell and a widget never disagree about a value" — measured rather than asserted in prose: each
value is rendered twice into the same-sized image and the two images must be equal.
"""
from __future__ import annotations

import os
import time

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.widgets.entity_chip import EntityChip
from sg_widgets_qt.widgets.field_value import FieldValue, paint_field_value

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = ("rest", "compact", "disabled", "hover", "preview", "faces")

#: The box both faces are rendered into: wide enough for two chips, one row of a table high.
FACE_BOX = QtCore.QSize(320, 32)

#: How long the hover card is given past its own delay.
CARD_GRACE_MS = 600

#: What the card a chip previews is asked to show, where the demo names no preview of its own.
PREVIEW: tuple[str, ...] = ("code", "sg_status_list")


def state_name() -> str:
    wanted = os.environ.get("QA_STATE", "rest").strip().lower()
    return wanted if wanted in STATES else "rest"


def wait_for(read, wait, ms: int = 8000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def values(find) -> list:
    return [value for value in find(FieldValue, all=True) if value.isVisible()]


def demo_of(page):
    for stage in page.stages:
        found = stage.widget
        if found is not None and hasattr(found, "set_density"):
            return found
    return None


def render(widget: QtWidgets.QWidget, size: QtCore.QSize) -> QtGui.QImage:
    """The widget and everything under it, drawn into an image of `size`."""
    image = QtGui.QImage(size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    widget.render(
        image,
        QtCore.QPoint(0, 0),
        QtGui.QRegion(0, 0, size.width(), size.height()),
        QtWidgets.QWidget.RenderFlag.DrawChildren,
    )
    return image


def painted(value: FieldValue, size: QtCore.QSize) -> QtGui.QImage:
    """The same value through the delegate face, into an image of `size`."""
    image = QtGui.QImage(size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    paint_field_value(
        painter,
        QtCore.QRect(0, 0, size.width(), size.height()),
        value.value,
        value.data_type,
        value.options(),
    )
    painter.end()
    return image


def differing(left: QtGui.QImage, right: QtGui.QImage) -> int:
    """How many pixels the two faces disagree on."""
    if left == right:
        return 0
    return sum(
        1
        for y in range(left.height())
        for x in range(left.width())
        if left.pixel(x, y) != right.pixel(x, y)
    )


def compare_faces(page, wait, find) -> dict:
    """Every value on the page through both faces, at one size, pixel for pixel."""
    found = values(find)
    if not found:
        return {"verdict": "FAIL the page drew no field value"}
    off: list[str] = []
    seen: list[dict] = []
    for value in found:
        held = value.size()
        value.resize(FACE_BOX)
        wait(20)
        gap = differing(render(value, FACE_BOX), painted(value, FACE_BOX))
        value.resize(held)
        seen.append({"data_type": value.data_type, "kind": value.kind, "pixels": gap})
        if gap:
            off.append(f"{value.data_type} ({value.kind}) differs on {gap} pixels")
    wait(50)
    return {
        "verdict": (
            f"PASS the widget and the delegate face agree pixel for pixel on {len(seen)} values"
            if not off
            else "FAIL " + "; ".join(off[:8])
        ),
        "state": "faces",
        "values": seen,
    }


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    state = state_name()
    if state == "faces":
        return compare_faces(page, wait, find)

    found = values(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: the page drew no field value"}

    if state == "compact":
        prefs.set("density", "compact")
        wait_for(lambda: all(v.density == "compact" for v in values(find)), wait, 4000)
        wait(400)
        held = values(find)
        return {
            "verdict": (
                "PASS every value is compact"
                if held and all(v.density == "compact" for v in held)
                else "FAIL the toolbar's compact density never reached the values"
            ),
            "state": state,
            "values": len(held),
        }

    if state == "disabled":
        for value in found:
            value.setEnabled(False)
        wait(400)
        return {"verdict": "PASS every value is inert", "state": state, "values": len(found)}

    if state == "hover":
        chips = [chip for chip in find(EntityChip, all=True) if chip.isVisible()]
        linked = [value for value in found if value.url]
        if not chips:
            return {"verdict": "FAIL the page drew no chip to hover"}
        if not linked:
            return {"verdict": "FAIL the page drew no value that opens somewhere"}
        chips[0].set_hovered(True)
        linked[0].set_hovered(True)
        wait(400)
        return {
            "verdict": "PASS the pointer is on a chip and on a link",
            "state": state,
            "chip": f"{chips[0].entity.type} {chips[0].entity.id}" if chips[0].entity else "",
            "link": linked[0].url[:60],
        }

    if state == "preview":
        # The demo names no preview, as upstream's does not; the prop is the value's own, so the
        # drive arms it on the first linked value and then puts the pointer on its chip.
        for value in found:
            if value.kind in ("entity", "multi_entity"):
                value.set_preview(list(PREVIEW))
        wait(200)
        previewed = [
            chip
            for chip in find(EntityChip, all=True)
            if chip.isVisible() and chip.hover_card is not None
        ]
        if not previewed:
            return {"verdict": "FAIL no chip on the page carries a hover card"}
        chip = previewed[0]
        card = chip.hover_card
        where = QtCore.QPointF(chip.rect().center())
        QtWidgets.QApplication.sendEvent(chip, QtGui.QEnterEvent(where, where, where))
        wait(card._open_timer.interval() + CARD_GRACE_MS)
        return {
            "verdict": "PASS the chip's card is open" if card.is_open else "FAIL no card opened",
            "state": state,
            "delay_ms": card._open_timer.interval(),
        }

    return {
        "verdict": "PASS rest",
        "state": state,
        "values": len(found),
        "kinds": sorted({value.kind for value in found}),
    }
