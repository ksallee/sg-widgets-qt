"""The GUI thread while a picker reads: nothing blocks it, and no picture holds up a query.

`docs/design-rules.md`: widgets never block the GUI thread. Reads run through
`sg_widgets_qt.workers`, and a picker's pictures read on a pool of their own so a page of rows
with thumbnails cannot hold every thread while the next query waits behind them.

    .venv/bin/python tools/qa.py --page entity-picker --drive tools/drives/picker-thread.py
    .venv/bin/python tools/qa.py --page entity-multi-picker --drive tools/drives/picker-thread.py --qt5

Two measurements, both taken while a read is in flight and the mock's thumbnails — which are
real http urls — are being fetched:

    the longest gap between two turns of the event loop, against `BUDGET_MS`
    the wait from the last keystroke to the rows that answer it, against the mock's own latency
      plus `ANSWER_SLACK_MS`
"""
from __future__ import annotations

import time

from qtpy.QtCore import QObject, Qt, QTimer
from qtpy.QtTest import QTest

from sg_widgets_qt.showcase.context import MOCK_LATENCY_MS
from sg_widgets_qt.widgets.picker_control import PickerControl

#: No turn of the loop may take longer than this while a picker is reading.
BUDGET_MS = 50.0

#: What an answer may take on top of the mock's own latency.
ANSWER_SLACK_MS = 100.0


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


def pickers_of(find) -> list:
    from sg_widgets_qt.widgets.entity_picker import EntitySearchPicker

    return [
        picker
        for picker in find(EntitySearchPicker, all=True)
        if not picker.disabled and not picker.readonly
    ]


def wait_for(read, wait, ms: int) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(20)
        if read():
            return True
    return False


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(400)
    failures: list = []

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    beat = Heartbeat(page)
    pickers = pickers_of(find)
    controls = [
        control
        for control in find(PickerControl, all=True)
        if not control.disabled and not control.readonly and control.row_model() is not None
    ]
    if not controls:
        return {"verdict": f"FAIL {page.data_name}: nothing on the page reads"}

    # 1. A read with a page of pictures behind it, with the loop timed all the way through.
    control = controls[0]
    beat.start()
    control.set_open(True)
    wait_for(lambda: control.list_surface().row_count() > 0, wait, 8000)
    # The rows are drawn; their pictures are still arriving. Keep turning the loop over them.
    wait(1500)
    beat.stop()
    opening = {"turns": len(beat.gaps), "worst_ms": round(beat.worst, 1)}
    if beat.worst > BUDGET_MS:
        note("loop", f"a turn of the loop took {beat.worst:.0f}ms while the list was reading")
    if len(beat.gaps) < 20:
        note("loop", f"the loop turned {len(beat.gaps)} times, too few to measure")

    # 2. The loop again while the page the load-more row asks for lands.
    beat.start()
    surface = control.list_surface()
    if surface.load_more_visible():
        before = surface.row_count()
        surface.activate(surface.row_count() - 1)
        wait_for(lambda: surface.row_count() != before, wait, 8000)
        wait(600)
    beat.stop()
    paging = {"turns": len(beat.gaps), "worst_ms": round(beat.worst, 1)}
    if beat.worst > BUDGET_MS:
        note("loop", f"a turn of the loop took {beat.worst:.0f}ms while a page was landing")

    # 3. A query, timed from the last keystroke, with the picture reads still in flight.
    picker = next((p for p in pickers if p.control is control), None)
    if picker is None:
        control.set_open(False)
        return _answer(page, failures, {"opening": opening, "paging": paging})
    held = picker.debounce_ms
    picker.set_debounce_ms(0)
    caret = control.caret()
    caret.setFocus()
    started = time.monotonic()
    QTest.keyClicks(caret, "sh01")
    # The read is in flight from the last keystroke: the loop is timed over the wait, not over
    # the driver's own synthetic key injection.
    beat.start()
    landed = wait_for(lambda: picker.state.query == "sh01" and not picker.state.loading, wait, 8000)
    took = (time.monotonic() - started) * 1000.0
    beat.stop()
    picker.set_debounce_ms(held)
    budget = MOCK_LATENCY_MS + ANSWER_SLACK_MS
    query = {
        "answered": landed,
        "took_ms": round(took, 1),
        "budget_ms": budget,
        "worst_ms": round(beat.worst, 1),
        "pictures": len(control.list_surface().source_model().rows),
    }
    if not landed:
        note("answer", "the query was never answered")
    elif took > budget:
        note(
            "answer",
            f"the answer took {took:.0f}ms against the mock's {MOCK_LATENCY_MS}ms"
            f" plus {ANSWER_SLACK_MS:.0f}ms",
        )
    if beat.worst > BUDGET_MS:
        note("loop", f"a turn of the loop took {beat.worst:.0f}ms while the query was in flight")

    control.set_open(False)
    wait(200)
    QTest.keyClick(caret, Qt.Key.Key_Escape)
    return _answer(page, failures, {"opening": opening, "query": query, "paging": paging})


def _answer(page, failures: list, seen: dict) -> dict:
    return {
        "verdict": (
            f"PASS the GUI thread on {page.data_name} never stalled past {BUDGET_MS:.0f}ms and"
            " no picture held up a query"
            if not failures
            else "FAIL " + "; ".join(failures[:8])
        ),
        "failures": failures,
        "seen": seen,
    }
