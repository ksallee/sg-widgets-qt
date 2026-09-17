"""The chrome a popup list wears: what its live region says, and how far its edges
have more content past them.

Both registries draw the same row and read the same numbers, so the wording and the
arithmetic are settled here rather than twice in the UI packages.

The upstream `markOverflow` and `watchOverflow` hold no decision beyond `overflow_edges`
and are not ported. The Qt layer reads the scroll metrics off its view and repaints the
fade on each edge when the view scrolls, resizes or takes new rows.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .state import StateLabels, state_line

__all__ = [
    "ListStatusState",
    "OverflowEdges",
    "SEARCHING_LABEL",
    "count_line",
    "list_status",
    "overflow_edges",
]

#: A read is on its way and the list is standing by.
SEARCHING_LABEL = "Searching…"


def count_line(count: int) -> str:
    """What the live row says about a list that answered."""
    return "1 result" if count == 1 else f"{count} results"


@dataclass
class ListStatusState:
    """What the live row is told about the list under it."""

    #: A read is in flight.
    loading: bool
    #: Rows on show.
    count: int
    #: What the failed read said, or None.
    error: str | None = None
    #: Nothing is announced until something has been asked for.
    asked: bool | None = None


def list_status(state: ListStatusState, labels: StateLabels | None = None) -> str:
    """The one line a list's live region carries.

    A failure wins, then a read in flight, then what the read answered. Nothing is
    announced before anything has been asked for, so an idle list stays silent.
    """
    labels = labels if labels is not None else StateLabels()
    if state.error is not None and state.error != "":
        return state_line("error", labels, state.error)
    if state.loading:
        return SEARCHING_LABEL
    if state.asked is False:
        return ""
    if state.count == 0:
        return state_line("empty", labels)
    return count_line(state.count)


@dataclass(frozen=True)
class OverflowEdges:
    """How far a scroller has more content past each of its edges, in pixels."""

    start: int
    end: int


def _round(value: float) -> int:
    """A half rounds towards the larger number, as the upstream arithmetic does."""
    return int(math.floor(value + 0.5))


def overflow_edges(scroll_top: float, scroll_height: float, client_height: float) -> OverflowEdges:
    """The room above and below what a scroller shows."""
    start = max(0, _round(scroll_top))
    end = max(0, _round(scroll_height - client_height - scroll_top))
    return OverflowEdges(start=start, end=end)
