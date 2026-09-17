"""The wheel stays on a scrolling view the way a browser chains scroll.

A browser hands the wheel to the page only when a new gesture starts on a view already at its
edge; the gesture that reached the edge stays on the view. Qt's scroll areas ignore a wheel event
the moment the bar cannot move, so the page under a collection scrolls in the same gesture that
loaded its next page. `WheelLatch` restores the browser's rule, and keeps the wheel on the view
while more rows are on their way.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from qtpy import QtCore, QtWidgets

__all__ = ["GESTURE_PAUSE_MS", "WheelLatch"]

#: A wheel event later than this after the previous one starts a new gesture.
GESTURE_PAUSE_MS = 400


class WheelLatch:
    """Decides whether a view at its edge keeps a wheel event or lets the page take it."""

    def __init__(
        self,
        view: QtWidgets.QAbstractScrollArea,
        more: Callable[[], bool] | None = None,
        pause_ms: int = GESTURE_PAUSE_MS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._view = view
        self._more = more
        self._pause = pause_ms / 1000.0
        self._clock = clock
        self._last = -1.0

    def keeps(self, event: QtCore.QEvent) -> bool:
        """True when the view must consume this wheel event although its bar cannot move.

        Call it before the view's own wheel handling: when it answers True, accept the event and
        do nothing, so the page under the view stays put.

        A gesture is the view's only once the view scrolled during it: a view that never moved,
        one with no range at all or one already at its edge when the gesture began, hands every
        event to the page, so a page scrolls past a list that shows all of its rows.
        """
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else 0
        pixel = event.pixelDelta().y() if hasattr(event, "pixelDelta") else 0
        moving = delta or pixel
        now = self._clock()
        if not moving:
            return False
        bar = self._view.verticalScrollBar()
        at_edge = bar.value() >= bar.maximum() if moving < 0 else bar.value() <= bar.minimum()
        if not at_edge:
            # The view scrolls this event, so the gesture is its own from here.
            self._last = now
            return False
        if moving < 0 and self._more is not None and self._more():
            return True
        owned = self._last >= 0 and (now - self._last) < self._pause
        if owned:
            self._last = now
        return owned

    def reset(self) -> None:
        """Forget the gesture, so the next wheel at the edge reaches the page."""
        self._last = -1.0
