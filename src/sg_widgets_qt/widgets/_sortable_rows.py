"""Pointer and keyboard reordering for a column of rows, and the motion it moves with.

The Qt half of `packages/react/src/registry/sg/components/sortable.tsx`. The order itself lives
in `sg_widgets_core.sortable`: the model answers what a move does and what a screen reader is
told, and `sortable_drop_index` answers where a dragged row lands. This object owns neither the
rows nor the order: it watches the grips, reports where a drop would land, and emits the move.

    rows = SortableRows(body)
    rows.set_rows(ids, widgets)
    rows.attach_grip(grip, index)
    rows.moved.connect(commit)

`SortableMotion` is the other half: the offsets the rows are drawn at while a gesture runs. It
is the port of `playSortableFlip` and the transform half of `createSortableController`
(`packages/core/src/sortable.ts`): the row under the pointer follows it as a lifted layer, and a
row the drag passes slides one row out of the way over 200ms on an out-cubic curve, transform
only — rule 4 of `docs/design-rules.md` animates a translate, never a sibling's position in the
layout. Under `theme.reduced_motion` the rows take their offsets at once and nothing moves.

A column of widgets (the sort picker's, the filter editor's) hands the offsets to `move`; a list
that draws its rows with a delegate (the column picker's) reads them in `paint`. Both are the
same gesture, so they share one object.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.sortable import (
    SortableModel,
    SortableModelOptions,
    SortablePoint,
    SortableRect,
    sortable_drop_index,
    sortable_stride,
)

from ..primitives.base import event_global_point


def _alive(widget: QtWidgets.QWidget) -> bool:
    """False once Qt has deleted the widget under the Python wrapper this object still holds."""
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True

__all__ = [
    "DRAG_THRESHOLD",
    "DROP_LINE",
    "LIFT_OPACITY",
    "LIFT_SCALE",
    "SLIDE_MS",
    "SortableDrag",
    "SortableMotion",
    "SortableRows",
    "paint_drop_line",
]

#: How far the pointer travels before a press on a grip becomes a drag.
DRAG_THRESHOLD = 4

#: The insertion mark drawn between two rows while one is carried.
DROP_LINE = 2

#: How long a row takes to slide out of the way, and to settle into its slot on the drop.
#: `DURATION["item"]` of the primitives: a row entering or leaving, rule 4.
SLIDE_MS = 200

#: What a lifted row wears while it is carried: `data-[dragging]:opacity-90 shadow-md` of
#: `column-picker.tsx`, and the press scale of rule 4.
LIFT_OPACITY = 0.9
LIFT_SCALE = 0.98

#: How far the shadow under a lifted row reaches, and how dark it is at the row's own edge.
LIFT_SHADOW = 8
LIFT_SHADOW_ALPHA = 0.18


class SortableMotion(QtCore.QObject):
    """Where each row of a sortable column is drawn while a gesture runs.

    Offsets are held per index, in pixels along the column. `changed` fires on every frame, so
    a widget column re-places its rows and a list repaints; nothing is laid out again, which is
    what rule 4 asks for. `lifted` names the row the pointer carries, which is drawn over the
    rest with a shadow and the press scale.
    """

    #: The offsets moved. A column redraws from them.
    changed = Signal()
    #: The last slide or settle finished, so a drive can wait for the motion to end.
    finished = Signal()

    def __init__(
        self,
        widget: QtWidgets.QWidget,
        duration_ms: int = SLIDE_MS,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent if parent is not None else widget)
        self._widget = widget
        self._duration = int(duration_ms)
        self._from: dict[int, float] = {}
        self._to: dict[int, float] = {}
        self._now: dict[int, float] = {}
        self._lifted = -1
        self._carry = 0.0
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QtCore.QEasingCurve(QtCore.QEasingCurve.Type.OutCubic))
        self._animation.valueChanged.connect(self._on_frame)
        self._animation.finished.connect(self._on_done)

    # --- what it holds --------------------------------------------------------------------

    @property
    def running(self) -> bool:
        """True while a slide or a settle is still playing."""
        return self._animation.state() == QtCore.QAbstractAnimation.State.Running

    @property
    def lifted(self) -> int:
        """The row the pointer is carrying, or -1."""
        return self._lifted

    @property
    def carry(self) -> float:
        """How far the lifted row stands from its slot, which is the pointer's own travel."""
        return self._carry

    @property
    def moving(self) -> bool:
        """True while any row is drawn away from its slot."""
        return self._lifted >= 0 or any(abs(value) >= 0.5 for value in self._now.values())

    def offset_of(self, index: int) -> float:
        """How far the row at `index` is drawn from where the layout puts it."""
        if index == self._lifted:
            return self._carry
        return self._now.get(index, 0.0)

    def offsets(self) -> dict:
        """Every offset that is not zero, by index."""
        out = {index: value for index, value in self._now.items() if abs(value) >= 0.5}
        if self._lifted >= 0:
            out[self._lifted] = self._carry
        return out

    # --- the gesture ----------------------------------------------------------------------

    def _reduced(self) -> bool:
        from ..theme import theme_of

        try:
            return bool(theme_of(self._widget).reduced_motion)
        except RuntimeError:
            return True

    def lift(self, index: int) -> None:
        """Take the row at `index` off the column: it follows the pointer from here on."""
        self._lifted = int(index)
        self._carry = 0.0
        self.changed.emit()

    def carry_to(self, offset: float) -> None:
        """The lifted row follows the pointer at once: a carried row never lags behind it."""
        if self._lifted < 0 or abs(offset - self._carry) < 0.5:
            return
        self._carry = float(offset)
        self.changed.emit()

    def slide(self, targets: dict) -> None:
        """Send every row to its offset, over `SLIDE_MS`. Offsets left out go back to zero."""
        wanted = {int(index): float(value) for index, value in targets.items()}
        if wanted == {index: value for index, value in self._to.items() if abs(value) >= 0.5}:
            return
        self._animation.stop()
        self._from = dict(self._now)
        self._to = wanted
        if self._reduced() or not self._widget.isVisible():
            self._now = dict(wanted)
            self.changed.emit()
            self.finished.emit()
            return
        self._animation.setDuration(self._duration)
        self._animation.start()

    def flip(self, offsets: dict) -> None:
        """Put the rows back where they were and let them slide to where they are now.

        The port of `playSortableFlip`: the caller measures before the order changes and again
        after the column has been laid out again, and hands over the difference. Nothing is
        laid out here; the rows are only drawn off their slots and animated onto them.
        """
        wanted = {int(index): float(value) for index, value in offsets.items() if abs(value) >= 1}
        self._animation.stop()
        self._now = dict(wanted)
        self._from = dict(wanted)
        self._to = {}
        if not wanted:
            self.changed.emit()
            self.finished.emit()
            return
        if self._reduced() or not self._widget.isVisible():
            self._now = {}
            self.changed.emit()
            self.finished.emit()
            return
        self._animation.setDuration(self._duration)
        self._animation.start()

    def settle(self) -> None:
        """The drop: the lifted row takes its slot and every other row its own, over `SLIDE_MS`.

        The lifted row is put down where it stands, so the settle runs from the place the
        pointer left it rather than jumping to the slot and sliding back.
        """
        if self._lifted >= 0:
            self._now[self._lifted] = self._carry
            self._lifted = -1
            self._carry = 0.0
        self.slide({})

    def stop(self) -> None:
        """Drop everything at once: nothing is carried and no row stands off its slot."""
        self._animation.stop()
        self._from = {}
        self._to = {}
        self._now = {}
        self._lifted = -1
        self._carry = 0.0
        self.changed.emit()

    def _on_frame(self, value: object) -> None:
        share = float(value) if isinstance(value, (int, float)) else 0.0
        keys = set(self._from) | set(self._to)
        self._now = {}
        for index in keys:
            start = self._from.get(index, 0.0)
            end = self._to.get(index, 0.0)
            self._now[index] = start + (end - start) * share
        self.changed.emit()

    def _on_done(self) -> None:
        self._now = dict(self._to)
        self.changed.emit()
        self.finished.emit()


def slide_targets(count: int, carried: int, landing: int, stride: float) -> dict:
    """Where every row stands while a row dragged from `carried` hangs over `landing`.

    The port of the loop in `createSortableController`'s `project`: a row between the two
    gives way by one row, and every other row stays where the layout put it.
    """
    out: dict = {}
    if carried < 0 or landing < 0:
        return out
    for index in range(count):
        if index == carried:
            continue
        if carried < index <= landing:
            out[index] = -stride
        elif landing <= index < carried:
            out[index] = stride
    return out


class SortableDrag(QtCore.QObject):
    """The pointer half of a sortable column: the threshold, the carry and where a drop lands.

    The owner measures its rows, because one column draws them as widgets and another paints
    them in a view, and the owner decides what a drop commits. Everything between the press and
    that decision is here: the four pixels a press travels before it is a drag, the row the
    pointer carries, the rows it passes giving way by one row, and the landing core answers.
    """

    #: The pointer picked the row at this index up.
    picked_up = Signal(int)
    #: Where a drop would land moved, or -1 once nothing is carried.
    drop_changed = Signal(int)

    def __init__(
        self,
        motion: SortableMotion,
        rects: Callable[[], Sequence[SortableRect]],
        centred: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent if parent is not None else motion)
        self._motion = motion
        self._rects_of = rects
        #: True where the lifted row centres on the pointer rather than keeping the grab offset.
        self._centred = bool(centred)
        self._press_at: QtCore.QPoint | None = None
        self._press_index = -1
        self._dragging = False
        self._drop = -1
        #: The rows as they were measured at pickup. The drag draws them elsewhere, so the
        #: landing is read off the measure rather than off where they stand now.
        self._rects: list[SortableRect] = []

    # --- what it holds --------------------------------------------------------------------

    @property
    def dragging(self) -> bool:
        """True while a row is under the pointer."""
        return self._dragging

    @property
    def carried(self) -> int:
        """The index of the row being dragged, or -1."""
        return self._press_index if self._dragging else -1

    @property
    def drop_index(self) -> int:
        """Where a drop would land, or -1 while nothing is carried."""
        return self._drop

    @property
    def rects(self) -> list[SortableRect]:
        """The rows as they were measured at pickup."""
        return list(self._rects)

    # --- the gesture ----------------------------------------------------------------------

    def press(self, point: QtCore.QPoint, index: int) -> None:
        """A press on the row at `index`, in the coordinates the rows are measured in."""
        self._press_at = QtCore.QPoint(point)
        self._press_index = int(index)

    def move_to(self, point: QtCore.QPoint) -> bool:
        """Carry the row to the pointer. True once the press has become a drag."""
        if self._press_at is None:
            return False
        if not self._dragging:
            if abs(point.y() - self._press_at.y()) < DRAG_THRESHOLD:
                return False
            rects = list(self._rects_of())
            if not 0 <= self._press_index < len(rects):
                return False
            self._rects = rects
            self._dragging = True
            self.picked_up.emit(self._press_index)
            # The row leaves the column and follows the pointer; the order stands still until
            # the drop, and the rows it passes are drawn one row out of its way.
            self._motion.lift(self._press_index)
        self._motion.carry_to(self._carry_for(point))
        self._set_drop(self._landing(point))
        return True

    def end(self) -> tuple:
        """Let the row go: the index it left and the index it landed on, or `(-1, -1)`."""
        carried = self._press_index if self._dragging else -1
        landing = self._drop if self._dragging else -1
        self._dragging = False
        self._press_at = None
        self._press_index = -1
        self._set_drop(-1)
        self._rects = []
        return carried, landing

    def _carry_for(self, point: QtCore.QPoint) -> float:
        if not self._centred:
            at = self._press_at
            return float(point.y() - at.y()) if at is not None else 0.0
        box = self._rects[self._press_index]
        return float(point.y()) - (box.top + box.bottom) / 2.0

    def _landing(self, point: QtCore.QPoint) -> int:
        if not 0 <= self._press_index < len(self._rects):
            return -1
        return sortable_drop_index(
            self._rects,
            self._press_index,
            SortablePoint(x=float(point.x()), y=float(point.y())),
        )

    def _stride(self) -> float:
        """How far one row is from the next, which is how far a row the drag passes gives way."""
        if not 0 <= self._press_index < len(self._rects):
            return 0.0
        return sortable_stride(self._rects, self._press_index)

    def _set_drop(self, index: int) -> None:
        if index == self._drop:
            return
        self._drop = index
        if self._dragging:
            self._motion.slide(
                slide_targets(len(self._rects), self._press_index, index, self._stride())
            )
        self.drop_changed.emit(index)


class SortableRows(QtCore.QObject):
    """The drag and the arrow keys of one column of rows.

    `set_rows` takes the ids in the order they are drawn and the widget each one is drawn in;
    `attach_grip` puts a grip under the pointer. A drop emits `moved` once, with the index the
    row started at and the one it landed on, so the owner commits a single change.
    """

    #: A row moved: the index it left and the index it landed on.
    moved = Signal(int, int)
    #: One line for the live region, from core's announcements.
    announced = Signal(str)
    #: The gap a drop would land in changed, or -1 once nothing is carried.
    drop_changed = Signal(int)

    def __init__(
        self,
        container: QtWidgets.QWidget,
        label_of: Callable[[str], str] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent if parent is not None else container)
        self._container = container
        self._label_of = label_of
        self._ids: list[str] = []
        self._widgets: list[QtWidgets.QWidget] = []
        self._grips: dict[QtWidgets.QWidget, int] = {}
        self._enabled = True
        #: Where each row is drawn while a gesture runs, and the row the pointer carries.
        self._motion = SortableMotion(container, parent=self)
        self._motion.changed.connect(self._place)
        #: The press, the threshold, the carry and the landing, shared with the column picker.
        self._drag = SortableDrag(self._motion, self._rects, parent=self)
        self._drag.picked_up.connect(self._on_picked_up)
        self._drag.drop_changed.connect(self._on_drop_changed)
        #: Where the layout put each row when the gesture began, which the offsets are from.
        self._bases: list[int] = []
        #: Where each id stood before the last `set_rows`, for the slide onto its new slot.
        self._was: dict[str, int] = {}

    # --- what it holds --------------------------------------------------------------------

    @property
    def ids(self) -> list[str]:
        """The ids in the order they are drawn."""
        return list(self._ids)

    @property
    def widgets(self) -> list[QtWidgets.QWidget]:
        """The widget each id is drawn in, in the order they are drawn."""
        return list(self._widgets)

    @property
    def dragging(self) -> bool:
        """True while a row is under the pointer."""
        return self._drag.dragging

    @property
    def carried(self) -> int:
        """The index of the row being dragged, or -1."""
        return self._drag.carried

    @property
    def drop_index(self) -> int:
        """Where a drop would land, or -1 while nothing is carried."""
        return self._drag.drop_index

    @property
    def motion(self) -> SortableMotion:
        """Where the rows are drawn while the gesture runs."""
        return self._motion

    def offset_of(self, index: int) -> float:
        """How far the row at `index` is drawn from where the layout puts it."""
        return self._motion.offset_of(index)

    def set_enabled(self, value: bool) -> None:
        """A disabled column neither drags nor moves."""
        self._enabled = bool(value)
        if not self._enabled:
            self._end(commit=False)

    def set_rows(self, ids: Sequence[str], widgets: Sequence[QtWidgets.QWidget]) -> None:
        """Take the order and the widget each id is drawn in. Clears every grip.

        A grip a redraw kept stands under a new model, so the filter this one put on it goes
        before the next one is attached: a kept grip is never watched twice.
        """
        for grip in list(self._grips):
            try:
                grip.removeEventFilter(self)
            except RuntimeError:
                pass
        # Where every row stood before this change, so the one that moved slides onto its new
        # slot rather than appearing there: `playSortableFlip`, measured on both sides.
        self._was = {
            one: widget.pos().y()
            for one, widget in zip(self._ids, self._widgets)
            if _alive(widget)
        }
        self._ids = [str(one) for one in ids]
        self._widgets = list(widgets)
        self._grips = {}
        self._end(commit=False)
        if self._was:
            QtCore.QTimer.singleShot(0, self._flip_from_last)

    def _place(self) -> None:
        """Draw every row at its slot plus its offset. Nothing is laid out again, rule 4."""
        if not self._bases or len(self._bases) != len(self._widgets):
            self._container.update()
            return
        lifted = self._motion.lifted
        for index, widget in enumerate(self._widgets):
            if not _alive(widget):
                continue
            offset = int(round(self._motion.offset_of(index)))
            widget.move(widget.x(), self._bases[index] + offset)
        if 0 <= lifted < len(self._widgets) and _alive(self._widgets[lifted]):
            self._widgets[lifted].raise_()
        self._container.update()

    def _flip_from_last(self) -> None:
        """Slide every row that moved from where it stood onto where the layout now puts it."""
        was, self._was = self._was, {}
        if not was or self._drag.dragging:
            return
        offsets: dict = {}
        for index, (one, widget) in enumerate(zip(self._ids, self._widgets)):
            if not _alive(widget) or one not in was:
                continue
            offsets[index] = float(was[one] - widget.pos().y())
        self._bases = [widget.pos().y() for widget in self._widgets if _alive(widget)]
        if len(self._bases) != len(self._widgets):
            self._bases = []
            return
        self._motion.flip(offsets)

    def model(self) -> SortableModel:
        """A frozen view of the order, with the labels a live region announces."""
        return SortableModel(self._ids, SortableModelOptions(label=self._label_of))

    # --- the pointer ----------------------------------------------------------------------

    def attach_grip(self, grip: QtWidgets.QWidget, index: int) -> None:
        """Make a widget the handle of the row at `index`."""
        self._grips[grip] = int(index)
        grip.installEventFilter(self)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        index = self._grips.get(watched)  # type: ignore[arg-type]
        if index is None or not self._enabled:
            return False
        kind = event.type()
        if kind == QtCore.QEvent.Type.MouseButtonPress:
            return self._on_press(event, index)
        if kind == QtCore.QEvent.Type.MouseMove:
            return self._on_move(event)
        if kind == QtCore.QEvent.Type.MouseButtonRelease:
            return self._on_release()
        if kind == QtCore.QEvent.Type.KeyPress:
            return self._on_key(event, index)
        return False

    def _on_press(self, event: QtCore.QEvent, index: int) -> bool:
        if getattr(event, "button", lambda: None)() != Qt.MouseButton.LeftButton:
            return False
        self._drag.press(self._container.mapFromGlobal(event_global_point(event)), index)
        return False

    def _on_move(self, event: QtCore.QEvent) -> bool:
        return self._drag.move_to(self._container.mapFromGlobal(event_global_point(event)))

    def _on_release(self) -> bool:
        if not self._drag.dragging:
            self._drag.end()
            return False
        self._end(commit=True)
        return True

    def _on_picked_up(self, index: int) -> None:
        """The slots the offsets are measured from, and the line the live region reads."""
        self._bases = [widget.pos().y() for widget in self._widgets if _alive(widget)]
        self.announced.emit(self.model().picked_up(self._id_at(index)))

    def _on_drop_changed(self, index: int) -> None:
        self.drop_changed.emit(index)
        self._container.update()

    def _rects(self) -> list[SortableRect]:
        out: list[SortableRect] = []
        for widget in self._widgets:
            box = widget.geometry()
            out.append(
                SortableRect(
                    top=float(box.top()),
                    bottom=float(box.bottom()),
                    left=float(box.left()),
                    right=float(box.right()),
                )
            )
        return out

    def _id_at(self, index: int) -> str:
        return self._ids[index] if 0 <= index < len(self._ids) else ""

    def _end(self, commit: bool) -> None:
        was = self._drag.dragging
        carried, landing = self._drag.end()
        if not was:
            return
        # The row is put down where the pointer left it and settles into its slot; a commit
        # lays the column out again, and `set_rows` slides the rows from there.
        self._motion.settle()
        if commit and landing >= 0 and landing != carried:
            self.announced.emit(self.model().moved_to(self._id_at(carried), landing))
            self.moved.emit(carried, landing)
        else:
            self.announced.emit(self.model().cancelled())

    # --- the keyboard ---------------------------------------------------------------------

    def _on_key(self, event: QtCore.QEvent, index: int) -> bool:
        key = getattr(event, "key", lambda: 0)()
        mods = getattr(event, "modifiers", lambda: Qt.KeyboardModifier.NoModifier)()
        if not bool(mods & Qt.KeyboardModifier.AltModifier):
            return False
        if key not in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            return False
        return self.move_by(index, -1 if key == Qt.Key.Key_Up else 1)

    def move_by(self, index: int, delta: int) -> bool:
        """Move the row at `index` by one place, which is what Alt with an arrow does."""
        landing = index + delta
        if not self._enabled or not 0 <= landing < len(self._ids) or not 0 <= index < len(self._ids):
            return False
        self.announced.emit(self.model().moved_to(self._id_at(index), landing))
        self.moved.emit(index, landing)
        return True


def paint_drop_line(
    widget: QtWidgets.QWidget, rows: SortableRows, color: QtGui.QColor, gap: int = 0
) -> None:
    """Draw the mark where a carried row would land, between the two rows it falls between."""
    landing = rows.drop_index
    widgets = rows.widgets
    if landing < 0 or not widgets:
        return
    if landing >= len(widgets):
        y = widgets[-1].geometry().bottom() + 1 + gap // 2
    else:
        box = widgets[landing].geometry()
        y = box.top() - gap // 2 if landing > rows.carried else box.bottom() + 1 + gap // 2
    painter = QtGui.QPainter(widget)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(
        QtCore.QRectF(0, y - DROP_LINE / 2.0, widget.width(), DROP_LINE), 1.0, 1.0
    )
    painter.end()
