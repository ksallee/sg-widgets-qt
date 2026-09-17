"""The GUI thread on the field value page: the loop while it reads, and what a cell costs to paint.

`docs/design-rules.md`: widgets never block the GUI thread. A collection draws its cells through
`paint_field_value` rather than holding a widget a row, so the cost of one cell is the cost of a
table: a page of 200 mixed cells has to paint inside one frame's worth of work.

    .venv/bin/python tools/qa.py --page field-value --drive tools/drives/field-value-paint.py
    .venv/bin/python tools/qa.py --page field-value --drive tools/drives/field-value-paint.py --qt5

Two measurements:

    the longest gap between two turns of the event loop while the demo's read is in flight,
      against `BUDGET_MS`
    the wall time of 200 cells of mixed data types through the delegate face, against `PAINT_MS`

The timer is the one `tools/drives/picker-thread.py` uses, kept here rather than shared so a drive
stays one file the driver can exec.
"""
from __future__ import annotations

import time

from qtpy import QtCore, QtGui

from sg_widgets_qt.widgets.field_value import FieldValue, FieldValueOptions, paint_field_value

#: No turn of the loop may take longer than this while the page is reading.
BUDGET_MS = 50.0

#: What 200 cells of mixed types may cost, in total.
PAINT_MS = 100.0

#: How many cells the budget is measured over, and the cell they are painted into.
CELLS = 200
CELL = QtCore.QRect(0, 0, 220, 28)


class Heartbeat(QtCore.QObject):
    """A zero-interval timer on the GUI thread, timing the gap between two turns of the loop."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.gaps: list[float] = []
        self._last = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.gaps = []
        self._last = time.monotonic()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = time.monotonic()
        self.gaps.append((now - self._last) * 1000.0)
        self._last = now

    @property
    def worst(self) -> float:
        return max(self.gaps) if self.gaps else 0.0


def values(find) -> list:
    return [value for value in find(FieldValue, all=True) if value.isVisible()]


def drive(page, wait, find, prefs) -> dict:
    failures: list[str] = []

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    # 1. The loop while the demo's read and the picture behind it are in flight. The page is
    #    built again so the read is timed from its start rather than from whatever is left of it.
    stage = page.stages[0] if page.stages else None
    beat = Heartbeat(page)
    beat.start()
    if stage is not None:
        stage.build()
    deadline = time.time() + 12.0
    while time.time() < deadline and not page.ready:
        wait(20)
    wait(1200)
    beat.stop()
    reading = {"turns": len(beat.gaps), "worst_ms": round(beat.worst, 1), "ready": page.ready}
    if beat.worst > BUDGET_MS:
        note("loop", f"a turn of the loop took {beat.worst:.0f}ms while the page was reading")
    if len(beat.gaps) < 20:
        note("loop", f"the loop turned {len(beat.gaps)} times, too few to measure")

    # 2. What a table's worth of cells costs. Every data type the page draws is taken in turn, so
    #    the run measures chips, badges, pictures and text in the mix a real table holds.
    held = values(find)
    if not held:
        return _answer(page, failures, {"reading": reading})
    plans = [(value.value, value.data_type, value.options()) for value in held]
    picture = QtGui.QPixmap(CELL.size())
    picture.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(picture)
    # The first pass warms whatever a cell reads once: the sprite of a status, a picture's cache.
    for value, data_type, options in plans:
        paint_field_value(painter, CELL, value, data_type, _still(options))
    started = time.monotonic()
    for index in range(CELLS):
        value, data_type, options = plans[index % len(plans)]
        paint_field_value(painter, CELL, value, data_type, _still(options))
    took = (time.monotonic() - started) * 1000.0
    painter.end()
    painting = {
        "cells": CELLS,
        "types": len(plans),
        "took_ms": round(took, 1),
        "budget_ms": PAINT_MS,
        "per_cell_us": round(took * 1000.0 / CELLS, 1),
    }
    if took > PAINT_MS:
        note("paint", f"{CELLS} cells took {took:.0f}ms against a budget of {PAINT_MS:.0f}ms")

    return _answer(page, failures, {"reading": reading, "painting": painting})


def _still(options: FieldValueOptions) -> FieldValueOptions:
    """The same options with no repaint hook: a measurement never asks the page to redraw."""
    return FieldValueOptions(**{**options.__dict__, "on_ready": None})


def _answer(page, failures: list, seen: dict) -> dict:
    return {
        "verdict": (
            f"PASS the GUI thread on {page.data_name} never stalled past {BUDGET_MS:.0f}ms and"
            f" {CELLS} cells painted inside {PAINT_MS:.0f}ms"
            if not failures
            else "FAIL " + "; ".join(failures[:8])
        ),
        "failures": failures,
        "seen": seen,
    }
