"""The shared row on the picker-control page, and the gap the GUI thread leaves there.

The picker-row half of `~/dev/sg-widgets/tools/drives/row-anatomy.js`. Nothing on this page
reads a site, so the loop watch here measures the gap while a popup opens and the arrows walk
its list rather than while a read is in flight.

    .venv/bin/python tools/qa.py --page picker-control --drive tools/drives/picker-row.py
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, QObject, Qt, QTimer
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.picker_control import PickerControl

#: No event-loop iteration may take longer than this.
GAP_LIMIT_MS = 50


class LoopWatch(QObject):
    """A 10ms tick that records the longest gap between two turns of the event loop."""

    def __init__(self) -> None:
        super().__init__()
        self.worst = 0.0
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._last = time.monotonic()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = time.monotonic()
        self.worst = max(self.worst, (now - self._last) * 1000.0)
        self._last = now


def press(widget, key: int) -> None:
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))


def drive(page, wait, find, prefs) -> dict:
    bad: list[str] = []
    notes: list[str] = []
    watch = LoopWatch()
    watch.start()

    pickers = find(PickerControl, all=True) or []
    if not pickers:
        watch.stop()
        return {"verdict": "FAIL no picker on the page"}

    picker = pickers[0]
    picker.set_open(True)
    wait(300)
    surface = picker.list_surface() if hasattr(picker, "list_surface") else None
    model = surface.source_model() if surface is not None else None
    if model is None or model.rowCount() == 0:
        bad.append("the picker's list drew no rows")
    else:
        where = model.index(0, 0)
        label = model.data(where, Roles.LABEL) or model.data(where, Qt.ItemDataRole.DisplayRole)
        if not label:
            bad.append("the first option has no label")
        runs = model.data(where, Roles.RUNS)
        glyph = model.data(where, Roles.GLYPH)
        pixmap = model.data(where, Roles.PIXMAP)
        sub = model.data(where, Roles.SUB_LABEL)
        secondary = model.data(where, Roles.SECONDARY)
        if not (glyph or pixmap):
            notes.append("the options here carry no leading picture, which this demo's set has none of")
        notes.append(
            f"first option {str(label)!r}: runs {bool(runs)}, sub {str(sub or '')!r}, "
            f"secondary {str(secondary or '')!r}"
        )
        # The arrows walk the list and the last row holds.
        surface.set_highlight(0)
        landed = []
        for _ in range(model.rowCount() + 4):
            press(picker, Qt.Key.Key_Down)
            wait(8)
            landed.append(surface.highlighted())
        if landed and landed[-1] != max(landed):
            bad.append("Down wrapped past the last option")
        notes.append(f"Down walked to option {landed[-1] if landed else -1} and held")
    picker.set_open(False)
    wait(200)

    watch.stop()
    if watch.worst > GAP_LIMIT_MS:
        bad.append(f"the GUI thread stalled {watch.worst:.0f}ms, over {GAP_LIMIT_MS}ms")
    return {
        "verdict": (
            f"PASS the shared row drew its parts and no event-loop gap passed {GAP_LIMIT_MS}ms"
            if not bad
            else "FAIL " + "; ".join(bad)
        ),
        "notes": notes,
        "max_gap_ms": round(watch.worst, 1),
    }
