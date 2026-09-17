"""Paging rules.

One vocabulary for every collection that pages: `pages` walks the set with a page
number, `more` appends on a load-more row, `scroll` appends when the scroller
reaches the last loaded row. A widget draws the rows and asks these for the
decisions: whether the set is exhausted, whether the next page may be asked for
now, and what the groups are after a page lands.

A read carries no total and `links.next` is emitted forever, so the end of the set
is a short page and nothing else (006_pagination).
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .client import EntityRow
from .collection import EntitySourceState, GroupBy, RowGroup, SourceMode, group_rows

__all__ = [
    "COLLECTION_BOTTOM_VALUES",
    "COLLECTION_VIEW_VALUES",
    "PAGING_MODE_VALUES",
    "SCROLL_THRESHOLD",
    "CollectionBottom",
    "CollectionView",
    "KeyedRowGroup",
    "LoadNextOptions",
    "PagingMode",
    "can_load_next",
    "collection_bottom",
    "collection_view",
    "group_rows_keyed",
    "has_failed_page",
    "loads_on_arrow_down",
    "reached_end",
    "should_load_next",
    "source_mode_for",
]

PagingMode = Literal["pages", "more", "scroll"]
"""How a collection walks a set: a page number, a load-more row, or the scroller."""
PAGING_MODE_VALUES: tuple[PagingMode, ...] = ("pages", "more", "scroll")

#: Rows before the last at which a scroller asks for the next page.
SCROLL_THRESHOLD = 5


def source_mode_for(paging: PagingMode) -> SourceMode:
    """The source mode a paging mode needs: `pages` shows one page, the other two append."""
    return "pages" if paging == "pages" else "infinite"


def reached_end(state: EntitySourceState) -> bool:
    """True when every row the filter matches is loaded.

    A set that has never been read has not reached its end, however empty it is.
    """
    return state.status not in ("idle", "loading") and not state.has_more


def can_load_next(state: EntitySourceState, paging: PagingMode) -> bool:
    """True when the next page may be asked for now."""
    if paging == "pages" or not state.has_more:
        return False
    return state.status in ("ready", "error")


def has_failed_page(state: EntitySourceState) -> bool:
    """True when a read failed with rows already on screen: the error belongs under them, with a retry."""
    return state.status == "error" and len(state.rows) > 0


@dataclass
class LoadNextOptions:
    paging: PagingMode
    #: Index of the last row the viewport reaches. -1 when none is.
    last_visible: int = -1
    #: Rows before the last at which the next page is asked for. Default `SCROLL_THRESHOLD`.
    threshold: int | None = None


def should_load_next(state: EntitySourceState, options: LoadNextOptions) -> bool:
    """True when the scroller has reached far enough down for the next page.

    A failed page is not retried here, only on the retry the error line carries: a
    scroller that retried on its own would ask again on every pixel.
    """
    if options.paging != "scroll" or state.status != "ready" or not can_load_next(state, options.paging):
        return False
    threshold = SCROLL_THRESHOLD if options.threshold is None else options.threshold
    return options.last_visible >= len(state.rows) - 1 - threshold


def loads_on_arrow_down(state: EntitySourceState, paging: PagingMode, index: int) -> bool:
    """True when a cursor stepping to `index` runs past the loaded rows.

    It asks for the next page instead of moving, and the cursor stays where it is until
    the rows arrive.
    """
    return can_load_next(state, paging) and index >= len(state.rows)


@dataclass
class KeyedRowGroup(RowGroup):
    """A contiguous run of rows sharing a value, under the key a collapsed group is named by."""

    key: str = ""


def group_rows_keyed(rows: Sequence[EntityRow], by: GroupBy) -> list[KeyedRowGroup]:
    """Contiguous runs with a stable key.

    The key is the run's position and its value, so a page whose first rows carry the
    value the last run carries grows that run rather than opening a second one, and a
    group shut before the page arrived is still shut after it.
    """
    return [
        KeyedRowGroup(
            value=bucket.value,
            rows=bucket.rows,
            key=f"group:{at}:{json.dumps(bucket.value, sort_keys=True, default=str)}",
        )
        for at, bucket in enumerate(group_rows(rows, by))
    ]


CollectionView = Literal["error", "loading", "empty", "rows"]
"""Which of the four things a collection's body shows."""
COLLECTION_VIEW_VALUES: tuple[CollectionView, ...] = ("error", "loading", "empty", "rows")


def collection_view(state: EntitySourceState, lines: int) -> CollectionView:
    """What a collection draws in place of its rows.

    A read that failed with rows already loaded is not this block: those rows stay and
    the error goes under them, which is what `has_failed_page` answers.
    """
    if state.status == "error" and not has_failed_page(state):
        return "error"
    if state.status == "loading":
        return "loading"
    return "empty" if lines == 0 else "rows"


CollectionBottom = Literal["error", "loading", "more", "sentinel"]
"""What sits under the last loaded row, if anything."""
COLLECTION_BOTTOM_VALUES: tuple[CollectionBottom, ...] = ("error", "loading", "more", "sentinel")


def collection_bottom(state: EntitySourceState, paging: PagingMode) -> CollectionBottom | None:
    """The block under the rows.

    The failed page with its retry, the skeleton of a page on the way, the load-more
    row, or the sentinel a scroller watches. One at a time.
    """
    if has_failed_page(state):
        return "error"
    if state.status == "loadingMore":
        return "loading"
    if not state.has_more:
        return None
    if paging == "more":
        return "more"
    return "sentinel" if paging == "scroll" else None
