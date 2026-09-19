"""The switch from light to dark: the window is repainted inside the budget.

The showcase never blocks the GUI thread (`CLAUDE.md`), and the theme switch is the one turn that
touches every widget at once. This times the whole switch on a heavy page, with two more pages
built behind it, which is the window a reader toggles after browsing.

    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/theme-switch.py
    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/theme-switch.py --qt5

The reading is taken twice, once each way, and the worse of the two is the verdict:

    blocked   the wall time of `prefs.set('theme', ...)`, the stretch the window answers nothing
    painted   from the same call to the last paint of the page settling

Behaviour is checked beside the clock: one `theme_bus.changed` for the switch, the visible page
and a page left hidden both wearing the new theme, and reduced motion carried with it.
"""
from __future__ import annotations

import time

from qtpy import QtCore, QtWidgets

from sg_widgets_qt.theme import theme_bus, theme_of

#: Neither switch may hold the GUI thread, or leave the page unpainted, longer than this. The
#: switch is one page's polish: the rail, the header and the page on show wear the new sheet, and
#: the pages and popovers behind them wear theirs when they are next opened.
BUDGET_MS = 350.0

#: Pages built behind the one on show, so the switch meets a window a reader has browsed.
WARM_PAGES = ("widgets/entity-table", "widgets/filter-bar")

#: How long a warmed page is given to settle before the next one is opened.
WARM_MS = 8000

#: No paint for this long means the page has settled.
QUIET_MS = 200

#: The longest a switch is followed before the reading is given up on.
SETTLE_MS = 6000


class Paints(QtCore.QObject):
    """When the widgets it watches last painted."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.count = 0
        self.last = 0.0

    def eventFilter(self, _watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.Paint:
            self.count += 1
            self.last = time.monotonic()
        return False


def watched(page: QtWidgets.QWidget) -> list:
    """The widgets whose paint says the page is wearing the new theme.

    The page's own viewport and every stage's frame: the frame is a `Surface`, which repaints on
    the theme it watches, so its paint is the theme landing rather than a demo settling.
    """
    out = [page.scroll.viewport()]
    for stage in page.stages:
        frame = stage.findChild(QtWidgets.QWidget, "demo-frame")
        if frame is not None:
            out.append(frame)
    return out


def wait_for(read, wait, ms: int) -> bool:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        wait(20)
        if read():
            return True
    return read()


def wears_dark(page: QtWidgets.QWidget) -> bool:
    """True when the page and the widgets deep inside it all read the dark theme from above."""
    if not theme_of(page).dark:
        return False
    children = page.findChildren(QtWidgets.QWidget)
    return all(theme_of(child).dark for child in children[-40:])


def switch(page, wait, prefs, to: str) -> dict:
    """Flip the theme and time it: the call itself, then the page settling."""
    marks = Paints(page)
    for widget in watched(page):
        widget.installEventFilter(marks)

    emissions: list = []

    def counted(root: QtWidgets.QWidget) -> None:
        emissions.append(root)

    theme_bus.changed.connect(counted)
    try:
        # Nothing of the last turn may be counted against this one.
        wait(120)
        marks.count = 0
        started = time.monotonic()
        prefs.set("theme", to)
        blocked = (time.monotonic() - started) * 1000.0
        deadline = started + SETTLE_MS / 1000.0
        while time.monotonic() < deadline:
            wait(20)
            if marks.count and (time.monotonic() - marks.last) * 1000.0 > QUIET_MS:
                break
        painted = (marks.last - started) * 1000.0 if marks.count else -1.0
    finally:
        theme_bus.changed.disconnect(counted)
        for widget in watched(page):
            widget.removeEventFilter(marks)

    return {
        "to": to,
        "blocked_ms": round(blocked, 1),
        "painted_ms": round(painted, 1),
        "paints": marks.count,
        "emissions": len(emissions),
    }


def drive(page, wait, find, prefs) -> dict:
    window = page.window()
    for name in WARM_PAGES:
        other = window.open_page(name)
        wait_for(lambda other=other: other.ready, wait, WARM_MS)
    hidden = window.open_page(WARM_PAGES[0])
    page = window.open_page(page.data_name)
    wait_for(lambda: page.ready, wait, WARM_MS)

    prefs.set("theme", "light")
    wait(200)
    to_dark = switch(page, wait, prefs, "dark")
    # The page left behind is read while the dark theme stands, not after the switch back.
    hidden_dark = wears_dark(hidden)
    readings = [to_dark, switch(page, wait, prefs, "light")]

    failures: list[str] = []
    worst_blocked = max(one["blocked_ms"] for one in readings)
    worst_painted = max(one["painted_ms"] for one in readings)
    if worst_blocked > BUDGET_MS:
        failures.append(f"the switch held the GUI thread for {worst_blocked:.0f}ms")
    if worst_painted < 0:
        failures.append("the page never repainted after the switch")
    elif worst_painted > BUDGET_MS:
        failures.append(f"the page took {worst_painted:.0f}ms to wear the new theme")
    if to_dark["emissions"] != 1:
        failures.append(f"the switch emitted theme_bus.changed {to_dark['emissions']} times")
    if not hidden_dark:
        failures.append("a page left hidden through the switch is still in the old theme")

    prefs.set("motion", "reduced")
    wait(60)
    if not theme_of(page).reduced_motion:
        failures.append("the theme the page reads lost reduced motion")
    prefs.set("motion", "normal")

    return {
        "verdict": (
            f"PASS the switch on {page.data_name} blocked {worst_blocked:.0f}ms and repainted in"
            f" {worst_painted:.0f}ms, inside {BUDGET_MS:.0f}ms"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "seen": {
            "page": page.data_name,
            "pages_built": len(WARM_PAGES) + 1,
            "stages": len(page.stages),
            "readings": readings,
            "worst_blocked_ms": round(worst_blocked, 1),
            "worst_painted_ms": round(worst_painted, 1),
            "budget_ms": BUDGET_MS,
        },
    }
