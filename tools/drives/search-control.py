"""The base every search widget wears: the pause, the ticket, the page and the four views.

The port of `~/dev/sg-widgets/tools/drives/search-control.js`, with the clauses that drive
names read off the widget rather than off the DOM, plus the gap the GUI thread left while a
read was in flight.

    .venv/bin/python tools/qa.py --page search-control --drive tools/drives/search-control.py
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, QObject, Qt, QTimer
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QApplication

#: The demo's read waits this long before it answers, and the base pauses 250ms before asking.
PAUSE_MS = 300

#: No event-loop iteration may take longer than this while a read is in flight.
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
    """One key, delivered to the widget itself, so a headless run needs no focus."""
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))


def settle(control, wait, ms: int = 6000) -> None:
    """Spin until the read in flight has answered or failed."""
    deadline = time.monotonic() + ms / 1000.0
    while control.loading and time.monotonic() < deadline:
        wait(25)


def counted(load, box: dict):
    """The read, with a tally of how many times it was actually called."""

    def counting(request):
        box["reads"] = box.get("reads", 0) + 1
        return load(request)

    return counting


def drive(page, wait, find, prefs) -> dict:
    bad: list[str] = []
    notes: list[str] = []
    watch = LoopWatch()
    watch.start()

    search = find("search-control-query")
    listed = find("search-control-bare")
    failing = find("search-control-error")
    if search is None or listed is None or failing is None:
        watch.stop()
        return {"verdict": "FAIL the three cases of the page are not all there"}
    box = search.input()
    reads: dict = {}
    search.set_load(counted(search.load, reads))
    settle(search, wait)
    reads.clear()

    # 1. Two keystrokes inside the pause cost one read, and the skeletons stand in meanwhile.
    box.setText("a")
    wait(60)
    box.setText("an")
    wait(120)
    if search.view != "loading":
        bad.append(f"the list is {search.view!r} while the pause runs, wanted loading")
    if not search.findChild(type(search._skeleton)).isVisible():  # noqa: SLF001
        bad.append("no skeletons while the read is in flight")
    spinners = [w for w in page.findChildren(QObject) if "spinner" in w.objectName().lower()]
    if spinners:
        bad.append(f"{len(spinners)} spinner(s) inside the first {PAUSE_MS}ms")
    settle(search, wait)
    if reads.get("reads") != 1:
        bad.append(f"two keystrokes inside the pause cost {reads.get('reads')} reads, wanted 1")
    notes.append(f"two keystrokes cost {reads.get('reads')} read")

    # 2. A query started before the first answers drops the first answer.
    reads.clear()
    landings = {"n": 0}
    search.rows_changed.connect(lambda: landings.__setitem__("n", landings["n"] + 1))
    box.setText("a")
    search.flush()
    wait(80)  # The first read is in flight and has not answered yet.
    box.setText("an")
    search.flush()
    settle(search, wait)
    wait(400)
    if landings["n"] != 1:
        bad.append(f"{landings['n']} answers landed, wanted 1: the first was not dropped")
    if search.query != "an":
        bad.append(f"the box holds {search.query!r} after the second query")
    notes.append(f"{reads.get('reads')} reads, {landings['n']} answer landed")

    # 3. A full page draws a load-more row, and the next page lands under the rows.
    first = len(search.items)
    surface = search.list_surface()
    if not search.has_more:
        bad.append("a full page said there was no further page")
    search.load_more()
    settle(search, wait)
    if len(search.items) <= first:
        bad.append(f"load more left {len(search.items)} rows, wanted more than {first}")
    notes.append(f"page of {first}, {len(search.items)} after load more")

    # 4. Down keeps the highlight in view and the last row holds.
    surface.set_highlight(0)
    seen = []
    for _ in range(len(search.items) + 6):
        press(box, Qt.Key.Key_Down)
        wait(10)
        seen.append(surface.highlighted())
    last = seen[-1]
    if last != max(seen):
        bad.append(f"Down wrapped: the highlight ended at {last} after reaching {max(seen)}")
    rect = surface.visualRect(surface.model().index(last, 0))
    if not surface.viewport().rect().intersects(rect):
        bad.append("the highlighted row is out of view")
    notes.append(f"Down walked to row {last} and held")

    # 5. Enter takes the row and the demo reads what was emitted.
    surface.set_highlight(0)
    picked = {"row": -1}
    search.activated.connect(lambda row: picked.__setitem__("row", row))
    press(box, Qt.Key.Key_Return)
    wait(60)
    if picked["row"] != 0:
        bad.append(f"Enter emitted row {picked['row']}, wanted 0")
    line = find("demo-picked")
    if line is not None and not line.text().strip():
        bad.append("the demo read nothing off the pick")
    notes.append(f"Enter emitted row {picked['row']} as {line.text() if line else ''!r}")

    # 6. A query matching nothing is the empty line.
    box.setText("zzzzz")
    search.flush()
    settle(search, wait)
    if search.view != "empty":
        bad.append(f"a query matching nothing drew {search.view!r}")

    # 7. Escape clears the query and the rows; a second one is the shell's.
    box.setText("a")
    search.flush()
    settle(search, wait)
    dismissed = {"n": 0}
    search.dismissed.connect(lambda: dismissed.__setitem__("n", dismissed["n"] + 1))
    press(box, Qt.Key.Key_Escape)
    wait(80)
    if search.query != "" or len(search.items) != 0:
        bad.append(f"Escape left {search.query!r} and {len(search.items)} rows")
    if dismissed["n"] != 0:
        bad.append("Escape on a query reached the shell")
    press(box, Qt.Key.Key_Escape)
    wait(80)
    if dismissed["n"] != 1:
        bad.append(f"a second Escape raised {dismissed['n']} dismissals, wanted 1")

    # 8. The bare shell reads once with no search row, and a failed read is the error line.
    if listed.input() is not None:
        bad.append("the bare shell drew a search row")
    if listed.view != "rows" or not listed.items:
        bad.append(f"the bare shell drew {listed.view!r} with {len(listed.items)} rows")
    if failing.view != "error" or not failing.failure:
        bad.append(f"the failed read drew {failing.view!r}")
    notes.append(f"bare shell {len(listed.items)} rows; error line {failing.failure!r}")

    watch.stop()
    if watch.worst > GAP_LIMIT_MS:
        bad.append(f"the GUI thread stalled {watch.worst:.0f}ms, over {GAP_LIMIT_MS}ms")
    return {
        "verdict": (
            "PASS the base debounced one read, dropped the stale answer, paged, held the last "
            "row, picked, emptied, cleared on Escape, listed without a query and reported a "
            f"failed read, with no event-loop gap over {GAP_LIMIT_MS}ms"
            if not bad
            else "FAIL " + "; ".join(bad)
        ),
        "notes": notes,
        "max_gap_ms": round(watch.worst, 1),
    }
