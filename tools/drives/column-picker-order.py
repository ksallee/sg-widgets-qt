"""column-picker: what the widget emits when the order moves, and when it does not.

The port of the column-picker half of `~/dev/sg-widgets/packages/core/src/sortable.ts`'s own
contract, read against the demo. Upstream emits `onOrderChange` once per keyboard step and once
per pointer gesture, from `endDrag`, and never from a cancel.

    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/column-picker-order.py
    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/column-picker-order.py --qt5

Four readings:

    keyboard   Space picks a row up, an arrow moves it, and one new order is emitted per step
    drag       a press on the grip, a move past four pixels and a release emit the order once
    cancel     Escape during a drag puts the row back and emits nothing
    remove     a press on the cross drops the row and emits the rest
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtCore import QPoint, Qt
from qtpy.QtTest import QTest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import press, until  # noqa: E402

#: How far past the four-pixel threshold the drag travels before it is read as one.
NUDGE = 8


class Heard:
    """Every order the widget emitted, in the order it emitted them."""

    def __init__(self, picker) -> None:
        self.orders: list[list[str]] = []
        picker.value_changed.connect(lambda value: self.orders.append(list(value)))

    def take(self) -> list[list[str]]:
        found = list(self.orders)
        self.orders = []
        return found


def row_point(chosen, row: int, x: int = 12) -> QPoint:
    rect = chosen.visualRect(chosen.model().index(row, 0))
    return QPoint(rect.left() + x, rect.center().y())


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    failures: list[str] = []
    seen: dict = {}

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    picker = find("column-picker-columns")
    if picker is None:
        return {"verdict": "FAIL no column picker on this page"}
    chosen = picker.chosen_list
    if not until(lambda: chosen.model().rowCount() >= 3, wait, 8000):
        return {"verdict": "FAIL the chosen list never filled"}
    wait(300)
    heard = Heard(picker)
    start = list(picker.value)

    # 1. The keyboard: one order per step, as upstream's `onKeyDown` emits.
    chosen.setFocus(Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(0)
    press(chosen, Qt.Key.Key_Space)
    press(chosen, Qt.Key.Key_Down)
    press(chosen, Qt.Key.Key_Space)
    wait(200)
    steps = heard.take()
    seen["keyboard"] = {"emitted": len(steps), "order": picker.value, "was": start}
    if len(steps) != 1:
        note("keyboard", f"one arrow emitted {len(steps)} orders")
    elif steps[-1] != [start[1], start[0], start[2]]:
        note("keyboard", f"the arrow emitted {steps[-1]}")
    if picker.value != chosen.paths:
        note("keyboard", "the widget's value and its list disagree")

    # 2. The pointer: a press on the grip, a move past four pixels, a release. One order, on
    #    the release, which is what upstream's `endDrag` does.
    before = list(picker.value)
    grip = row_point(chosen, 2)
    QTest.mousePress(
        chosen.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip
    )
    QTest.mouseMove(chosen.viewport(), QPoint(grip.x(), grip.y() - NUDGE))
    QTest.mouseMove(chosen.viewport(), row_point(chosen, 0))
    mid = heard.take()
    carrying = chosen.carrying
    QTest.mouseRelease(
        chosen.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        row_point(chosen, 0),
    )
    wait(200)
    after = heard.take()
    seen["drag"] = {
        "carried": carrying or "",
        "during": len(mid),
        "on_release": len(after),
        "order": picker.value,
        "was": before,
    }
    if not carrying:
        note("drag", "the press on the grip carried nothing")
    if mid:
        note("drag", f"{len(mid)} orders were emitted before the release")
    if len(after) != 1:
        note("drag", f"the release emitted {len(after)} orders")
    elif after[-1] == before:
        note("drag", "the release emitted the order it started from")
    if picker.value != chosen.paths:
        note("drag", "the widget's value and its list disagree")

    # 3. Escape during a drag puts the row back and emits nothing at all.
    held = list(picker.value)
    grip = row_point(chosen, 0)
    QTest.mousePress(
        chosen.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip
    )
    QTest.mouseMove(chosen.viewport(), QPoint(grip.x(), grip.y() + NUDGE))
    QTest.mouseMove(chosen.viewport(), row_point(chosen, 2))
    press(chosen, Qt.Key.Key_Escape)
    wait(200)
    cancelled = heard.take()
    seen["cancel"] = {"emitted": len(cancelled), "order": picker.value, "was": held}
    if cancelled:
        note("cancel", f"a cancelled drag emitted {len(cancelled)} orders")
    if picker.value != held or chosen.paths != held:
        note("cancel", f"a cancelled drag left {chosen.paths}")
    QTest.mouseRelease(
        chosen.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip
    )
    heard.take()

    # 4. The cross drops the row and the rest is emitted.
    kept = list(picker.value)
    rect = chosen.visualRect(chosen.model().index(0, 0))
    QTest.mouseClick(
        chosen.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(rect.right() - 8, rect.center().y()),
    )
    wait(200)
    removed = heard.take()
    seen["remove"] = {"emitted": len(removed), "order": picker.value, "was": kept}
    if len(removed) != 1 or picker.value != kept[1:]:
        note("remove", f"the cross emitted {removed}")

    return {
        "verdict": (
            "PASS a keyboard step emits one order, a drag emits one on the release and none"
            " before it, a cancelled drag emits none, and the cross emits the rest"
            if not failures
            else "FAIL " + "; ".join(failures[:6])
        ),
        "failures": failures,
        "seen": seen,
    }
