"""Ordered lists that reorder by pointer and by keyboard.

The model answers what a move does to an order and what a screen reader should be told
about it. The hit testing answers where a dragged item lands, how far the rows it passes
shift, and how fast the container scrolls under the pointer.

The upstream controller and its measurement helpers bind one list element: they turn
pointer events into a drag, move rows with a transform and observe reduced motion. They
are not ported. The Qt layer runs the gesture on its item view and feeds the geometry
here as `SortableRect` and `SortablePoint`, in the view's own coordinates.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "SortableAnnouncements",
    "SortableDirection",
    "SORTABLE_DIRECTION_VALUES",
    "SortableModel",
    "SortableModelOptions",
    "SortableOrientation",
    "SORTABLE_ORIENTATION_VALUES",
    "SortablePoint",
    "SortableRect",
    "SortableScrollOptions",
    "create_sortable",
    "sortable_announcements",
    "sortable_drop_index",
    "sortable_scroll_step",
    "sortable_stride",
]

SortableDirection = Literal["up", "down"]
SORTABLE_DIRECTION_VALUES: tuple[SortableDirection, ...] = ("up", "down")

SortableOrientation = Literal["vertical", "horizontal"]
SORTABLE_ORIENTATION_VALUES: tuple[SortableOrientation, ...] = ("vertical", "horizontal")


@dataclass(frozen=True)
class SortableRect:
    """The edges of an item, as the view measures them."""

    top: float
    bottom: float
    left: float
    right: float


@dataclass(frozen=True)
class SortablePoint:
    """A point in the same coordinates as the rects it is tested against."""

    x: float
    y: float


# ---------------------------------------------------------------------------
# announcements
# ---------------------------------------------------------------------------


class SortableAnnouncements:
    """The live-region copy, one line per gesture step. Indexes are counted from zero."""

    @staticmethod
    def pickup(label: str, index: int, count: int) -> str:
        return f"Picked up {label}, position {index + 1} of {count}"

    @staticmethod
    def move(label: str, index: int, count: int) -> str:
        return f"Moved {label} to position {index + 1} of {count}"

    @staticmethod
    def drop(label: str) -> str:
        return f"Dropped {label}"

    @staticmethod
    def cancel() -> str:
        return "Cancelled"


sortable_announcements = SortableAnnouncements()


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


@dataclass
class SortableModelOptions:
    """How a model names what it holds."""

    #: The name announced for an id. The id itself by default.
    label: Callable[[str], str] | None = None


class SortableModel:
    """A frozen view of one order: every move answers with a new list."""

    def __init__(self, ids: Sequence[str], options: SortableModelOptions | None = None) -> None:
        self._ids = list(ids)
        self._label = options.label if options is not None else None

    @property
    def ids(self) -> list[str]:
        return self._ids

    def index_of(self, id_: str) -> int:
        """Where an id sits, or -1 when the order does not hold it."""
        try:
            return self._ids.index(id_)
        except ValueError:
            return -1

    def label_of(self, id_: str) -> str:
        """The name announced for an id."""
        named = self._label(id_) if self._label is not None else None
        return named if named is not None else id_

    def move_to(self, from_index: int, to: int) -> list[str]:
        """The order with the entry at `from_index` moved to `to`.

        An index off either end leaves it alone.
        """
        next_ = list(self._ids)
        if from_index < 0 or from_index >= len(next_) or to < 0 or to >= len(next_) or from_index == to:
            return next_
        moved = next_.pop(from_index)
        next_.insert(to, moved)
        return next_

    def keyboard_move(self, id_: str, direction: SortableDirection) -> list[str]:
        """The order with `id_` moved one place towards the start or the end."""
        from_index = self.index_of(id_)
        if from_index == -1:
            return list(self._ids)
        return self.move_to(from_index, from_index + (-1 if direction == "up" else 1))

    def picked_up(self, id_: str) -> str:
        return sortable_announcements.pickup(self.label_of(id_), self.index_of(id_), len(self._ids))

    def moved_to(self, id_: str, index: int) -> str:
        return sortable_announcements.move(self.label_of(id_), index, len(self._ids))

    def dropped(self, id_: str) -> str:
        return sortable_announcements.drop(self.label_of(id_))

    def cancelled(self) -> str:
        return sortable_announcements.cancel()


def create_sortable(ids: Sequence[str], options: SortableModelOptions | None = None) -> SortableModel:
    """A frozen view of one order: every move answers with a new list."""
    return SortableModel(ids, options)


# ---------------------------------------------------------------------------
# hit testing
# ---------------------------------------------------------------------------


def _midpoint_of(rect: SortableRect, orientation: SortableOrientation) -> float:
    if orientation == "vertical":
        return (rect.top + rect.bottom) / 2
    return (rect.left + rect.right) / 2


def _along(point: SortablePoint, orientation: SortableOrientation) -> float:
    return point.y if orientation == "vertical" else point.x


def sortable_drop_index(
    rects: Sequence[SortableRect],
    from_index: int,
    point: SortablePoint,
    orientation: SortableOrientation = "vertical",
) -> int:
    """The index an item dragged from `from_index` lands on.

    `rects` are the items in list order, measured before the drag; `point` is the dragged
    item's own midpoint, moved by the pointer. A neighbour's place is claimed once its
    midpoint is crossed, so the far edge of a tall row does not take a place the item is
    only overlapping.
    """
    if from_index < 0 or from_index >= len(rects):
        return from_index
    at = _along(point, orientation)
    for i in range(len(rects) - 1, from_index, -1):
        if at > _midpoint_of(rects[i], orientation):
            return i
    for i in range(0, from_index):
        if at < _midpoint_of(rects[i], orientation):
            return i
    return from_index


def sortable_stride(
    rects: Sequence[SortableRect],
    from_index: int,
    orientation: SortableOrientation = "vertical",
) -> float:
    """How far one item sits from the next, so the rows a drag passes shift by a whole row."""

    def size(rect: SortableRect) -> float:
        return rect.bottom - rect.top if orientation == "vertical" else rect.right - rect.left

    def start(rect: SortableRect) -> float:
        return rect.top if orientation == "vertical" else rect.left

    current = rects[from_index] if 0 <= from_index < len(rects) else None
    if current is None:
        return 0
    next_ = rects[from_index + 1] if 0 <= from_index + 1 < len(rects) else None
    if next_ is not None:
        return start(next_) - start(current)
    previous = rects[from_index - 1] if 0 <= from_index - 1 < len(rects) else None
    if previous is not None:
        return start(current) - start(previous)
    return size(current)


@dataclass
class SortableScrollOptions:
    """How a container scrolls itself under a drag near its edge."""

    #: How near an edge the pointer has to be before the container scrolls.
    threshold: float = 48
    #: Pixels per frame at the edge itself.
    speed: float = 12
    orientation: SortableOrientation = "vertical"


def sortable_scroll_step(
    bounds: SortableRect,
    point: SortablePoint,
    options: SortableScrollOptions | None = None,
) -> float:
    """Pixels to scroll the container this frame, negative towards the start.

    Zero until the pointer is inside `threshold` of an edge, then proportional to how far
    past it, up to `speed` at the edge and beyond.
    """
    options = options if options is not None else SortableScrollOptions()
    threshold, speed, orientation = options.threshold, options.speed, options.orientation
    at = _along(point, orientation)
    start = bounds.top if orientation == "vertical" else bounds.left
    end = bounds.bottom if orientation == "vertical" else bounds.right
    if threshold <= 0 or end - start <= threshold * 2:
        return 0
    if at < start + threshold:
        return -min(1, (start + threshold - at) / threshold) * speed
    if at > end - threshold:
        return min(1, (at - (end - threshold)) / threshold) * speed
    return 0
