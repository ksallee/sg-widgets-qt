"""The GUI thread while the wave's three pages read the schema: nothing blocks it.

`docs/design-rules.md`: widgets never block the GUI thread. `GET /schema/<Type>/fields` is 48KB
and about 330ms per type (probe 002), so a field list, a column list and a status editor all have
a real read behind them, and none of them may hold the loop while it is in flight.

    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/wave-thread.py
    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/wave-thread.py
    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/wave-thread.py --qt5

The reading is the longest gap between two turns of a zero-interval timer, taken from the moment
the read is out to the moment it lands, against `BUDGET_MS`. A type the page has not read yet is
asked for, so the schema cache cannot answer from memory.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QObject, QTimer

#: No turn of the loop may take longer than this while a schema read is in flight.
BUDGET_MS = 50.0

#: A type none of the three demos opens on, so the read is a real one.
COLD_TYPE = "Asset"

#: Too few turns to call a measurement one.
MIN_TURNS = 20


class Heartbeat(QObject):
    """A zero-interval timer on the GUI thread, timing the gap between two turns of the loop."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.gaps: list[float] = []
        self._last = 0.0
        self._timer = QTimer(self)
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


def wait_for(read, wait, ms: int) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(20)
        if read():
            return True
    return False


def field_read(page, wait, find):
    """The field picker's own schema read, put out on a type the page has not seen."""
    from sg_widgets_qt.widgets.field_picker import FieldPicker

    pickers = [one for one in find(FieldPicker, all=True) if not one.disabled and not one.readonly]
    if not pickers:
        return None
    picker = pickers[0]
    picker.control.set_open(True)
    # The popover is a window of its own: showing it is the platform's work, not a read's.
    wait(80)
    picker.set_entity_type(COLD_TYPE)
    return lambda: not picker.levels.loading


def column_read(page, wait, find):
    """The column picker's list, on a type the page has not read."""
    from sg_widgets_qt.widgets.column_picker import ColumnPicker

    pickers = [one for one in find(ColumnPicker, all=True) if not one.disabled and not one.readonly]
    if not pickers:
        return None
    picker = pickers[0]
    picker.set_entity_type(COLD_TYPE)
    return lambda: not picker.levels.loading


def editor_read(page, wait, find):
    """The status editor's read: the schema of its type and the Status table behind it."""
    from sg_widgets_qt.widgets.field_editor import FieldEditor

    editors = [one for one in find(FieldEditor, all=True) if one.kind == "status_list"]
    if not editors:
        return None
    editor = editors[0]
    editor.set_mode("edit")
    wait(20)
    control = editor.control
    if control is None:
        return None
    return lambda: not control.load.loading


#: One read per page, tried in turn: a page carries whichever of them it has.
READS = (field_read, column_read, editor_read)


def drive(page, wait, find, prefs) -> dict:
    wait(400)
    beat = Heartbeat(page)
    landed = None
    which = ""
    for read in READS:
        landed = read(page, wait, find)
        if landed is not None:
            which = read.__name__
            break
    if landed is None:
        return {"verdict": f"FAIL nothing on {page.data_name} reads the schema"}

    beat.start()
    answered = wait_for(landed, wait, 12000)
    # The rows are up; the widgets are still settling behind them. Keep turning the loop.
    wait(800)
    beat.stop()

    failures: list[str] = []
    if not answered:
        failures.append("the read never landed")
    if beat.worst > BUDGET_MS:
        failures.append(f"a turn of the loop took {beat.worst:.0f}ms while the schema was read")
    if len(beat.gaps) < MIN_TURNS:
        failures.append(f"the loop turned {len(beat.gaps)} times, too few to measure")
    return {
        "verdict": (
            f"PASS the GUI thread on {page.data_name} never stalled past {BUDGET_MS:.0f}ms while"
            " the schema was read"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "seen": {
            "read": which,
            "answered": answered,
            "turns": len(beat.gaps),
            "worst_ms": round(beat.worst, 1),
            "budget_ms": BUDGET_MS,
        },
    }
