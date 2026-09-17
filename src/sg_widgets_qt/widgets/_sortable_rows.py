"""Pointer and keyboard reordering for a column of row widgets.

The Qt half of `packages/react/src/registry/sg/components/sortable.tsx`. The order itself lives
in `sg_widgets_core.sortable`: the model answers what a move does and what a screen reader is
told, and `sortable_drop_index` answers where a dragged row lands. This object owns neither the
rows nor the order: it watches the grips, reports where a drop would land, and emits the move.

    rows = SortableRows(body)
    rows.set_rows(ids, widgets)
    rows.attach_grip(grip, index)
    rows.moved.connect(commit)
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
)

__all__ = ["DRAG_THRESHOLD", "DROP_LINE", "SortableRows", "paint_drop_line"]

#: How far the pointer travels before a press on a grip becomes a drag.
DRAG_THRESHOLD = 4

#: The insertion mark drawn between two rows while one is carried.
DROP_LINE = 2


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
        self._press_at: QtCore.QPoint | None = None
        self._press_index = -1
        self._dragging = False
        self._drop = -1
        self._enabled = True

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
        return self._dragging

    @property
    def carried(self) -> int:
        """The index of the row being dragged, or -1."""
        return self._press_index if self._dragging else -1

    @property
    def drop_index(self) -> int:
        """Where a drop would land, or -1 while nothing is carried."""
        return self._drop

    def set_enabled(self, value: bool) -> None:
        """A disabled column neither drags nor moves."""
        self._enabled = bool(value)
        if not self._enabled:
            self._end(commit=False)

    def set_rows(self, ids: Sequence[str], widgets: Sequence[QtWidgets.QWidget]) -> None:
        """Take the order and the widget each id is drawn in. Clears every grip."""
        self._ids = [str(one) for one in ids]
        self._widgets = list(widgets)
        self._grips = {}
        self._end(commit=False)

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

    @staticmethod
    def _global_of(event: QtCore.QEvent) -> QtCore.QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()  # type: ignore[attr-defined]
        return event.globalPos()  # type: ignore[attr-defined]

    def _on_press(self, event: QtCore.QEvent, index: int) -> bool:
        if getattr(event, "button", lambda: None)() != Qt.MouseButton.LeftButton:
            return False
        self._press_at = self._container.mapFromGlobal(self._global_of(event))
        self._press_index = index
        return False

    def _on_move(self, event: QtCore.QEvent) -> bool:
        if self._press_at is None:
            return False
        point = self._container.mapFromGlobal(self._global_of(event))
        if not self._dragging:
            if abs(point.y() - self._press_at.y()) < DRAG_THRESHOLD:
                return False
            self._dragging = True
            self.announced.emit(self.model().picked_up(self._id_at(self._press_index)))
        self._set_drop(self._landing(point))
        return True

    def _on_release(self) -> bool:
        if not self._dragging:
            self._press_at = None
            self._press_index = -1
            return False
        self._end(commit=True)
        return True

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

    def _landing(self, point: QtCore.QPoint) -> int:
        rects = self._rects()
        if not 0 <= self._press_index < len(rects):
            return -1
        return sortable_drop_index(
            rects, self._press_index, SortablePoint(x=float(point.x()), y=float(point.y()))
        )

    def _id_at(self, index: int) -> str:
        return self._ids[index] if 0 <= index < len(self._ids) else ""

    def _set_drop(self, index: int) -> None:
        if index == self._drop:
            return
        self._drop = index
        self.drop_changed.emit(index)
        self._container.update()

    def _end(self, commit: bool) -> None:
        landing = self._drop
        carried = self._press_index
        was = self._dragging
        self._dragging = False
        self._press_at = None
        self._press_index = -1
        self._set_drop(-1)
        if not was:
            return
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
