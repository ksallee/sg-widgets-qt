"""The GUI thread while the query widgets read: no turn of the loop over 50ms.

`docs/design-rules.md`: widgets never block the GUI thread. A facet tally is a `_summarize` per
facet or a page of rows (020_summarize), and a field list is the 48KB `GET /schema/<Type>/fields`
at about 330ms a type (probe 002). Neither may hold the loop while it is in flight.

    .venv/bin/python tools/qa.py --page filter-bar --drive tools/drives/query-thread.py
    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/query-thread.py --qt5
    .venv/bin/python tools/qa.py --page sort-picker --drive tools/drives/query-thread.py

The reading is the longest gap between two turns of a zero-interval timer, from the moment the
read is out to the moment it lands. A type the page has not read yet is asked for, so the schema
cache cannot answer from memory.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QObject, QTimer

#: No turn of the loop may take longer than this while a read is in flight.
BUDGET_MS = 50.0

#: A type none of the four demos opens on, so the read is a real one.
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


def bar_read(page, wait, find):
    """The bar's own tally, put out afresh on a type the page has not seen."""
    from sg_widgets_qt.widgets.filter_bar import FilterBar

    bars = [one for one in find(FilterBar, all=True) if not one.disabled]
    if not bars:
        return None
    bar = bars[0]
    wait_for(lambda: not bar.counting, wait, 20000)
    bar.set_entity_type(COLD_TYPE)
    bar.set_facets(["sg_status_list", "code"])
    return lambda: not bar.counting and bool(bar.field_of("sg_status_list"))


def editor_read(page, wait, find):
    """The editor's field list, on a type the page has not read."""
    from sg_widgets_qt.widgets.filter_editor import FilterEditor

    editors = [one for one in find(FilterEditor, all=True) if not one.disabled]
    if not editors:
        return None
    editor = editors[0]
    wait_for(lambda: editor.fields(), wait, 12000)
    editor.set_entity_type(COLD_TYPE)
    return lambda: bool(editor.fields())


def sort_read(page, wait, find):
    """The sort picker's field list, on a type the page has not read."""
    from sg_widgets_qt.widgets.sort_picker import SortPicker

    pickers = [one for one in find(SortPicker, all=True) if not one.disabled]
    if not pickers:
        return None
    picker = pickers[0]
    picker.set_open(True)
    # The popover is a window of its own: showing it is the platform's work, not a read's.
    wait(80)
    picker.set_entity_type(COLD_TYPE)
    return lambda: not picker.field_picker().levels.loading


def dialog_read(page, wait, find):
    """The editor behind the launcher, opened on a type the page has not read."""
    from sg_widgets_qt.widgets.filter_dialog import FilterDialog

    launchers = [one for one in find(FilterDialog, all=True) if not one.disabled]
    if not launchers:
        return None
    launcher = launchers[0]
    launcher.set_open(True)
    wait_for(lambda: launcher.editor() is not None, wait, 8000)
    editor = launcher.editor()
    if editor is None:
        return None
    wait_for(lambda: editor.fields(), wait, 12000)
    launcher.set_entity_type(COLD_TYPE)
    return lambda: bool(editor.fields())


#: One read per page, tried in turn: a page carries whichever of them it has.
READS = (bar_read, editor_read, sort_read, dialog_read)


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    beat = Heartbeat(page)
    landed = None
    which = ""
    for read in READS:
        landed = read(page, wait, find)
        if landed is not None:
            which = read.__name__
            break
    if landed is None:
        return {"verdict": f"FAIL nothing on {page.data_name} reads"}

    beat.start()
    answered = wait_for(landed, wait, 20000)
    # The rows are up; the widgets are still settling behind them. Keep turning the loop.
    wait(800)
    beat.stop()

    failures: list[str] = []
    if not answered:
        failures.append("the read never landed")
    if beat.worst > BUDGET_MS:
        failures.append(f"a turn of the loop took {beat.worst:.0f}ms while the read was out")
    if len(beat.gaps) < MIN_TURNS:
        failures.append(f"the loop turned {len(beat.gaps)} times, too few to measure")
    return {
        "verdict": (
            f"PASS the GUI thread on {page.data_name} never stalled past {BUDGET_MS:.0f}ms"
            f" while {which} was out"
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
