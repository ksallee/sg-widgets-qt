"""A two-letter query against the test site, read-only, on whichever search the page holds.

    .venv/bin/python tools/qa.py --page global-search --live --drive tools/drives/search-live.py

Nothing is named here: the drive counts rows and reports what the list drew, never a row's own
words, so a run says what the site answered without saying whose it is.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QObject, QTimer

#: No event-loop iteration may take longer than this while a read is in flight.
GAP_LIMIT_MS = 50

#: Two letters, and then three. The endpoint refuses a query under three characters (`query
#: text too short! must be 3 or more characters`), so the client answers the short one with a
#: name read per type; both queries are expected to draw rows, or empty, never the error line.
SHORT = "sh"
QUERY = "sh0"


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


def settle(control, wait, ms: int = 30000) -> None:
    deadline = time.monotonic() + ms / 1000.0
    while control.loading and time.monotonic() < deadline:
        wait(50)


def drive(page, wait, find, prefs) -> dict:
    watch = LoopWatch()
    watch.start()
    # The palette is unscoped; the inline case of that page is scoped to a project the live
    # run only knows when `--project` names one.
    widget = find("global-search-palette") or find("hierarchical-search")
    if widget is None:
        watch.stop()
        return {"verdict": "FAIL no search on this page"}
    control = widget.search_control()
    settle(control, wait)

    control.input().setText(SHORT)
    control.flush()
    settle(control, wait)
    wait(1000)
    short_view = control.view

    control.input().setText(QUERY)
    control.flush()
    settle(control, wait)
    wait(1500)
    watch.stop()
    bad = []
    if control.view not in ("rows", "empty"):
        bad.append(f"the list drew {control.view!r} against the site")
    if short_view not in ("rows", "empty"):
        bad.append(f"the two-letter query drew {short_view!r}, not a name read")
    if watch.worst > GAP_LIMIT_MS:
        bad.append(f"the GUI thread stalled {watch.worst:.0f}ms")
    return {
        "verdict": (
            f"PASS the site answered, the list drew {control.view!r}"
            if not bad
            else "FAIL " + "; ".join(bad)
        ),
        "two_letter_view": short_view,
        "view": control.view,
        "rows": len(control.items),
        "failure": (control.failure or "")[:120],
        "max_gap_ms": round(watch.worst, 1),
    }
