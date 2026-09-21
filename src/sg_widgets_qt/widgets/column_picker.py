"""The columns of a grid, as a field picker over the ordered list it fills.

Ported from `packages/react/src/registry/sg/components/column-picker.tsx` and its Svelte twin.
Picking a field appends its path and clears the picker; each row carries a grip, the friendly
path and a remove control, and moves by drag or from the keyboard. `layout='dual'` swaps that
for the two lists side by side, the type's fields checked on the left and the chosen paths on
the right.

The order lives in `sg_widgets_core.sortable`: the model answers what a move does and what a
screen reader is told, and the hit testing answers where a dragged row lands and how fast the
list scrolls under the pointer. The levels are `field_picker.FieldLevels`, so both layouts walk
the same path through linked types.

    picker = ColumnPicker(context=context, entity_type="Version", value=["code"])
    picker.value_changed.connect(save)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QT5, QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, Qt, Signal

from sg_widgets_core.pickers import (
    DEFAULT_MAX_DEPTH,
    ExtraField,
    move_field_path,
    toggle_field_path,
)
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.sortable import (
    SortableModel,
    SortableModelOptions,
    SortablePoint,
    SortableRect,
    SortableScrollOptions,
    sortable_drop_index,
    sortable_scroll_step,
    sortable_stride,
)
from sg_widgets_core.state import NO_MATCH_LABEL, NOTHING_CHOSEN_LABEL, StateLabels, state_line

from .. import icons
from ..primitives.base import CONTROL_HEIGHT, THUMB_SIZE, ThemedWidget, painter_for
from ..primitives.command import Command
from ..primitives.list_view import LIST_PAD, ListSurface
from ..primitives.roles import Roles
from ..primitives.row_delegate import GAP, LEAD_GLYPH, ROW_PAD_X, RowDelegate
from ..primitives.skeleton import Skeleton
from ..theme import theme_of
from ..workers import Ticket, default_pool
from ._sortable_rows import (
    DRAG_THRESHOLD as SORT_DRAG_THRESHOLD,  # noqa: F401
)
from ._sortable_rows import (
    LIFT_OPACITY,
    LIFT_SCALE,
    LIFT_SHADOW,
    LIFT_SHADOW_ALPHA,
    SortableMotion,
    slide_targets,
)
from .field_picker import (
    CRUMB_SEPARATOR,
    Breadcrumb,
    FieldLevels,
    FieldOptionModel,
    FieldPicker,
    descend_hit,
    extra_fields_of,
    schema_of,
)
from .picker_control import PICKER_SIZE_VALUES
from .state_line import StateLine

__all__ = [
    "COLUMN_LAYOUT_VALUES",
    "DRAG_THRESHOLD",
    "DUAL_BREAKPOINT",
    "REMOVE_ZONE",
    "ChosenColumns",
    "ColumnPicker",
    "ColumnRowModel",
]

#: `layout`: the field picker over the ordered list, or the two lists side by side.
COLUMN_LAYOUT_VALUES: tuple[str, ...] = ("list", "dual")

#: How far the pointer travels before a press on a grip becomes a drag.
DRAG_THRESHOLD = 4

#: `@lg`, the 32rem the two panes stand side by side from, measured on the widget itself.
DUAL_BREAKPOINT = 512

#: The trailing strip of a chosen row where a press removes it.
REMOVE_ZONE = 28

#: `max-h-72`: how tall the chosen list grows before it scrolls.
CHOSEN_MAX_HEIGHT = 288

#: A section of the dual layout: the border, its radius step and its inset.
PANE_PAD = 12
PANE_GAP = 12
HEADING_TEXT = 14

#: The metadata step the count line under the list is on.
COUNT_TEXT = 12

#: The mark a chosen row is dragged by.
GRIP_GLYPH = "grip-vertical"

#: The line the chosen list shows when nothing is chosen.
EMPTY_GLYPH = "columns-3"


def _remove_painter(size: str = "md") -> Callable[..., None]:
    """The cross a chosen row carries at its trailing edge, on the row's own glyph ladder."""

    def paint(painter: QtGui.QPainter, rect: QtCore.QRect, option: Any) -> None:
        widget = getattr(option, "widget", None)
        theme = theme_of(widget) if widget is not None else None
        ink = theme.color("muted_foreground") if theme is not None else QtGui.QColor(128, 128, 128)
        side = LEAD_GLYPH.get(size, LEAD_GLYPH["md"])
        box = QtCore.QRect(rect.right() + 1 - side, rect.center().y() - side // 2, side, side)
        painter.setOpacity(0.7)
        icons.paint_icon(painter, box, "x", ink)

    return paint


class ColumnRowModel(QtCore.QAbstractListModel):
    """The chosen paths in the order they are drawn, each with the grip and the cross.

    A path whose friendly label has not resolved yet reads as the path itself, so a list is
    never blank while the schema of every type it travels is read.
    """

    def __init__(self, parent: QtCore.QObject | None = None, size: str = "md") -> None:
        super().__init__(parent)
        self._paths: list[str] = []
        self._labels: dict[str, list[str]] = {}
        self._readonly = False
        self._size = size if size in PICKER_SIZE_VALUES else "md"

    def set_size(self, value: str) -> None:
        """The step the cross is drawn on, so it rides the ladder the row does."""
        self._size = value if value in PICKER_SIZE_VALUES else "md"
        self._redraw()

    @property
    def paths(self) -> list[str]:
        """The chosen paths, in order."""
        return list(self._paths)

    def set_paths(self, paths: Sequence[str]) -> None:
        self.beginResetModel()
        self._paths = [str(path) for path in paths]
        self.endResetModel()

    def set_labels(self, labels: dict[str, list[str]]) -> None:
        """The display name of every segment of every path, keyed by the path."""
        self._labels = dict(labels)
        self._redraw()

    def set_readonly(self, value: bool) -> None:
        """A read-only list drops the grip and the cross."""
        self._readonly = bool(value)
        self._redraw()

    def parts_of(self, path: str) -> list[str] | None:
        """The resolved segments of a path, or None while the read is in flight."""
        return self._labels.get(path)

    def label_of(self, path: str) -> str:
        """The friendly path, or the raw one until it resolves."""
        parts = self._labels.get(path)
        return CRUMB_SEPARATOR.join(parts) if parts else path

    def _redraw(self) -> None:
        if self._paths:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._paths) - 1, 0))

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._paths)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._paths):
            return None
        path = self._paths[index.row()]
        parts = self._labels.get(path)
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return self.label_of(path)
        if role == Roles.RUNS:
            if not parts:
                return [(path, False, False)]
            runs: list[tuple[str, bool, bool]] = []
            for crumb in parts[:-1]:
                runs.append((crumb, False, True))
                runs.append((CRUMB_SEPARATOR, False, True))
            runs.append((parts[-1], False, False))
            return runs
        if role == Roles.GLYPH:
            return "" if self._readonly else GRIP_GLYPH
        if role == Roles.PAINTER:
            return None if self._readonly else _remove_painter(self._size)
        if role == Roles.ENTITY:
            return path
        if role == Qt.ItemDataRole.ToolTipRole:
            return path
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class _ShiftedRows(RowDelegate):
    """The chosen rows, drawn where the gesture has put them rather than where the list lays them.

    Rule 4 animates a translate and nothing else, so a row a drag passes is drawn at an offset
    while the order itself stands still; the model changes once, on the drop. The row under the
    pointer is held back here and drawn over the rest by the list, which is the `z-index` the
    upstream row carries while it is dragged (`column-picker.tsx:604`).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._motion: SortableMotion | None = None
        #: The option the list last measured the lifted row with, for the layer over the rest.
        self.lifted_option: QtWidgets.QStyleOptionViewItem | None = None
        self.lifted_index: QModelIndex | None = None

    def set_motion(self, motion: SortableMotion | None) -> None:
        self._motion = motion

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        motion = self._motion
        if motion is None:
            super().paint(painter, option, index)
            return
        if index.row() == motion.lifted:
            held = QtWidgets.QStyleOptionViewItem(option)
            self.lifted_option = held
            self.lifted_index = index
            return
        offset = motion.offset_of(index.row())
        if abs(offset) < 0.5:
            super().paint(painter, option, index)
            return
        shifted = QtWidgets.QStyleOptionViewItem(option)
        shifted.rect = option.rect.translated(0, int(round(offset)))
        super().paint(painter, shifted, index)


class ChosenColumns(ListSurface):
    """The ordered list of chosen columns: a grip, the friendly path and a remove control.

    A row is dragged by its grip once the pointer has travelled four pixels, and the rows it
    passes give way at their midpoint. From the keyboard, Space picks the row under the cursor
    up, the arrows move it and Space drops it; Escape puts it back. Alt with an arrow moves the
    row without picking it up, and Delete removes it.
    """

    #: The order changed. Carries the paths in their new order.
    reordered = Signal(list)
    #: The cross of the row at this index was pressed.
    remove_requested = Signal(int)
    #: One line for the live region, from core's `sortable_announcements`.
    announced = Signal(str)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        size: str = "md",
        label_of: Callable[[str], str] | None = None,
    ) -> None:
        delegate = _ShiftedRows(None, size=size, thumbnail=True, indicator="none")
        # The grip stands on its own: upstream draws a ghost icon button, not the picture
        # plate a row with a thumbnail would fall back to.
        delegate.set_bare_glyph(True)
        super().__init__(parent, max_height=CHOSEN_MAX_HEIGHT, size=size, delegate=delegate)
        delegate.setParent(self)
        self._rows = ColumnRowModel(self, size=size)
        self.setModel(self._rows)
        self._label_of = label_of
        self._editable = True
        self._carrying: str | None = None
        self._before: list[str] = []
        self._press_at: QtCore.QPoint | None = None
        self._press_row = -1
        self._dragging = False
        self._rects: list[SortableRect] = []
        self._scroll = QtCore.QTimer(self)
        self._scroll.setInterval(16)
        self._scroll.timeout.connect(self._auto_scroll)
        self._pointer = QtCore.QPoint()
        #: Where each row is drawn while a drag or a keyboard move runs.
        self._motion = SortableMotion(self, parent=self)
        self._motion.changed.connect(self.viewport().update)
        delegate.set_motion(self._motion)
        #: Where the drag started from and where it hangs, which the drop commits.
        self._from_row = -1
        self._to_row = -1
        self.setObjectName("column-picker-list")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- what it holds --------------------------------------------------------------------

    @property
    def rows_model(self) -> ColumnRowModel:
        """The chosen paths the list draws."""
        return self._rows

    @property
    def paths(self) -> list[str]:
        """The chosen paths, in the order they are drawn."""
        return self._rows.paths

    def set_paths(self, paths: Sequence[str]) -> None:
        self._rows.set_paths(paths)
        self.updateGeometry()

    @property
    def carrying(self) -> str | None:
        """The path the keyboard or the pointer is carrying, or None."""
        return self._carrying

    @property
    def motion(self) -> SortableMotion:
        """Where the rows are drawn while a gesture runs: the lifted row and the slides."""
        return self._motion

    def offset_of(self, row: int) -> float:
        """How far the row at `row` is drawn from the slot the list lays it in."""
        return self._motion.offset_of(row)

    def set_editable(self, value: bool) -> None:
        """A read-only or disabled list neither reorders nor removes."""
        self._editable = bool(value)

    def set_readonly(self, value: bool) -> None:
        """A read-only row is the label alone: no grip, none of its inset, and no cross.

        A merely disabled list keeps both, drawn inert, which is what upstream's `disabled`
        buttons do (column-picker.tsx:609-645).
        """
        self._rows.set_readonly(bool(value))
        self.row_delegate().set_thumbnail(not value)
        self.viewport().update()

    def sortable(self) -> SortableModel:
        """A frozen view of the order, with the labels a live region announces."""
        return SortableModel(
            self._rows.paths, SortableModelOptions(label=self._label_of or self._rows.label_of)
        )

    def _announce(self, line: str) -> None:
        self.setAccessibleDescription(line)
        self.announced.emit(line)

    def _apply(self, order: Sequence[str], quiet: bool = False) -> None:
        """Take a new order. `quiet` moves the rows without telling the caller.

        A keyboard move emits per step, as upstream's `onKeyDown` does. A pointer drag moves
        the rows as the pointer crosses each midpoint but emits once, on release, which is
        what upstream's `endDrag` does (`packages/core/src/sortable.ts:492-508`), so a caller
        writing the order away sees one change per gesture and none at all from a cancel.
        """
        if list(order) == self._rows.paths:
            return
        # Where the rows stand before the change, so the one that moved slides onto its new
        # slot and its neighbours slide into the gap: `playSortableFlip`, both measures taken
        # around the one change. A drop has its own measure and takes it before this runs.
        was = {} if self._dragging else self._row_tops()
        self._rows.set_paths(order)
        if was:
            self._slide_from(was)
        if not quiet:
            self.reordered.emit(list(order))

    # --- the keyboard ----------------------------------------------------------------------

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802, C901
        key = event.key()
        if self._dragging:
            if key == Qt.Key.Key_Escape:
                self._end_drag(cancel=True)
                event.accept()
                return
            super().keyPressEvent(event)
            return
        row = self.highlighted()
        paths = self._rows.paths
        model = self.sortable()
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        if not self._editable:
            super().keyPressEvent(event)
            return
        if self._carrying is not None:
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                order = model.keyboard_move(self._carrying, "up" if key == Qt.Key.Key_Up else "down")
                self._apply(order)
                index = order.index(self._carrying)
                self.set_highlight(index)
                self._announce(self.sortable().moved_to(self._carrying, index))
                event.accept()
                return
            if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._announce(model.dropped(self._carrying))
                self._carrying = None
                event.accept()
                return
            if key == Qt.Key.Key_Escape:
                self._apply(self._before)
                self._announce(model.cancelled())
                self._carrying = None
                event.accept()
                return
        if not 0 <= row < len(paths):
            super().keyPressEvent(event)
            return
        if alt and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = -1 if key == Qt.Key.Key_Up else 1
            self._apply(move_field_path(paths, row, row + step))
            self.set_highlight(max(0, min(len(paths) - 1, row + step)))
            self._announce(self.sortable().moved_to(paths[row], max(0, min(len(paths) - 1, row + step))))
            event.accept()
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_requested.emit(row)
            event.accept()
            return
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._carrying = paths[row]
            self._before = list(paths)
            self._announce(model.picked_up(self._carrying))
            event.accept()
            return
        super().keyPressEvent(event)

    # --- the pointer -----------------------------------------------------------------------

    def _grip_width(self) -> int:
        """The leading slot the grip sits in, which is where a drag starts."""
        return ROW_PAD_X + THUMB_SIZE[self.row_delegate().size] + GAP

    def _point_of(self, event: QtGui.QMouseEvent) -> QtCore.QPoint:
        return event.pos() if hasattr(event, "pos") else event.position().toPoint()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = self._point_of(event)
        index = self.indexAt(point)
        if self._editable and event.button() == Qt.MouseButton.LeftButton and index.isValid():
            rect = self.visualRect(index)
            if point.x() >= rect.right() + 1 - REMOVE_ZONE:
                self.remove_requested.emit(index.row())
                event.accept()
                return
            if point.x() - rect.left() <= self._grip_width():
                self._press_at = QtCore.QPoint(point)
                self._press_row = index.row()
                self.set_highlight(index.row())
                # Upstream listens for Escape on the window; the list takes the keyboard here
                # so the key reaches `keyPressEvent` while the pointer holds a row.
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = self._point_of(event)
        self._pointer = QtCore.QPoint(point)
        if self._press_at is not None and not self._dragging:
            if abs(point.y() - self._press_at.y()) >= DRAG_THRESHOLD:
                self._begin_drag()
        if self._dragging:
            self._drag_to(point)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._end_drag(cancel=False)
            event.accept()
            return
        self._press_at = None
        self._press_row = -1
        super().mouseReleaseEvent(event)

    def _begin_drag(self) -> None:
        paths = self._rows.paths
        if not 0 <= self._press_row < len(paths):
            return
        self._dragging = True
        self._carrying = paths[self._press_row]
        self._before = list(paths)
        self._from_row = self._press_row
        self._to_row = self._press_row
        # The row leaves the column and follows the pointer; the order stands still until the
        # drop, and the rows it passes are drawn one row out of its way.
        self._motion.lift(self._press_row)
        self._rects = [
            SortableRect(
                top=float(self.visualRect(self.model().index(i, 0)).top()),
                bottom=float(self.visualRect(self.model().index(i, 0)).bottom()),
                left=float(self.visualRect(self.model().index(i, 0)).left()),
                right=float(self.visualRect(self.model().index(i, 0)).right()),
            )
            for i in range(len(paths))
        ]
        self._announce(self.sortable().picked_up(self._carrying))
        self._scroll.start()

    def _drag_to(self, point: QtCore.QPoint) -> None:
        if self._carrying is None or not 0 <= self._from_row < len(self._rects):
            return
        landing = sortable_drop_index(
            self._rects, self._from_row, SortablePoint(x=float(point.x()), y=float(point.y()))
        )
        # The lifted row follows the pointer, and the rows it passes give way by one row over
        # 200ms. The order itself moves once, on release, which is what upstream's `endDrag`
        # does (`packages/core/src/sortable.ts:492-508`), so a caller writing the order away
        # sees one change per gesture and none at all from a cancel.
        carried = self._rects[self._from_row]
        self._motion.carry_to(float(point.y()) - (carried.top + carried.bottom) / 2.0)
        if landing != self._to_row:
            self._to_row = landing
            self._motion.slide(
                slide_targets(len(self._rects), self._from_row, landing, self._stride())
            )

    def _auto_scroll(self) -> None:
        if not self._dragging:
            return
        bar = self.verticalScrollBar()
        bounds = SortableRect(
            top=0.0,
            bottom=float(self.viewport().height()),
            left=0.0,
            right=float(self.viewport().width()),
        )
        step = sortable_scroll_step(
            bounds,
            SortablePoint(x=float(self._pointer.x()), y=float(self._pointer.y())),
            SortableScrollOptions(),
        )
        if step:
            bar.setValue(bar.value() + int(step))

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        """The rows, then the one the pointer carries, over them.

        A list paints its rows top to bottom, so a lifted row drawn in its turn would be
        painted over by the row under it. The delegate holds it back and it is drawn here
        instead: the `z-index`, the shadow and the press scale upstream's dragged row wears
        (`column-picker.tsx:604`, rule 4).
        """
        super().paintEvent(event)
        delegate = self.row_delegate()
        option = getattr(delegate, "lifted_option", None)
        index = getattr(delegate, "lifted_index", None)
        if option is None or index is None or self._motion.lifted < 0:
            return
        theme = theme_of(self)
        box = option.rect.translated(0, int(round(self._motion.carry)))
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        radius = float(theme.radius_px("md"))
        # The shadow under the lifted row: `shadow-md`, drawn as a few rings rather than a
        # blur, which is what the popover surface does.
        for step in range(LIFT_SHADOW, 0, -1):
            wash = QtGui.QColor(0, 0, 0)
            wash.setAlphaF(LIFT_SHADOW_ALPHA / LIFT_SHADOW)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(wash)
            painter.drawRoundedRect(
                QtCore.QRectF(box).adjusted(-step, -step / 2.0, step, step), radius, radius
            )
        painter.setBrush(theme.color("background"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QtCore.QRectF(box), radius, radius)
        painter.setOpacity(LIFT_OPACITY)
        # `active:scale`: the row shrinks a touch under the pointer while it is carried.
        centre = QtCore.QPointF(box.center())
        painter.translate(centre)
        painter.scale(LIFT_SCALE, LIFT_SCALE)
        painter.translate(-centre)
        lifted = QtWidgets.QStyleOptionViewItem(option)
        lifted.rect = box
        RowDelegate.paint(delegate, painter, lifted, index)
        painter.end()

    def _stride(self) -> float:
        """How far one row is from the next, which is how far a row the drag passes gives way."""
        return sortable_stride(self._rects, max(0, self._from_row))

    def _row_tops(self) -> dict:
        """Where each path is drawn now, its offset counted: the measure a slide runs from."""
        return {
            path: self.visualRect(self.model().index(row, 0)).top() + self._motion.offset_of(row)
            for row, path in enumerate(self._rows.paths)
        }

    def _slide_from(self, was: dict) -> None:
        """Let every row slide from where it was drawn onto the slot it now has."""
        offsets = {
            row: was[path] - self.visualRect(self.model().index(row, 0)).top()
            for row, path in enumerate(self._rows.paths)
            if path in was
        }
        self._motion.flip(offsets)

    def _end_drag(self, cancel: bool) -> None:
        carried = self._carrying
        was = self._row_tops()
        if not cancel and 0 <= self._from_row and self._to_row != self._from_row:
            # The one change of the gesture, and the rows settle onto it from where the drag
            # left them.
            self._apply(move_field_path(self._before, self._from_row, self._to_row), quiet=True)
        order = self._rows.paths
        moved = not cancel and order != self._before
        self._motion.lift(-1)
        self._slide_from(was)
        if carried is not None:
            model = self.sortable()
            if cancel:
                self._announce(model.cancelled())
            elif moved:
                self._announce(model.moved_to(carried, order.index(carried)))
            else:
                self._announce(model.dropped(carried))
        if moved:
            self.reordered.emit(list(order))
        self._scroll.stop()
        self._dragging = False
        self._carrying = None
        self._press_at = None
        self._press_row = -1
        self._from_row = -1
        self._to_row = -1
        self._rects = []




class _Pane(ThemedWidget):
    """One bordered section of the dual layout: a heading over its list."""

    def __init__(
        self,
        title: str = "",
        slot: str = "column-picker-available",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._invalid = False
        self.setObjectName(slot)
        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(PANE_PAD, PANE_PAD, PANE_PAD, PANE_PAD)
        self._column.setSpacing(PANE_GAP)
        self._heading = _Heading(title, self)
        self._column.addWidget(self._heading)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        widget.setParent(self)
        self._column.addWidget(widget)

    def set_title(self, value: str) -> None:
        self._heading.set_text(value)

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        radius = float(theme.radius_px("md"))
        box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(theme.color("destructive" if self._invalid else "border"))
        painter.drawRoundedRect(box, radius, radius)
        painter.end()


class _Heading(ThemedWidget):
    """The name over a pane: the body step, one weight up."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setObjectName("column-picker-heading")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(HEADING_TEXT, QtGui.QFont.Weight.Medium)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, QtGui.QFontMetrics(self._font()).height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setFont(self._font())
        painter.setPen(self.theme.color("foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.elide(painter, self._text, self.width()),
        )
        painter.end()


class _Panes(QtWidgets.QWidget):
    """The two panes of the dual layout, side by side from `DUAL_BREAKPOINT` and stacked under.

    The breakpoint is measured on this widget, not on the window, so a column picker in a
    narrow panel stacks on a wide page.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("column-picker-panes")
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(PANE_GAP)
        self._grid.setVerticalSpacing(PANE_GAP)
        self._panes: list[QtWidgets.QWidget] = []
        self._side_by_side = False

    def set_panes(self, panes: Sequence[QtWidgets.QWidget]) -> None:
        for pane in self._panes:
            self._grid.removeWidget(pane)
        self._panes = list(panes)
        self._lay()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._lay()

    def _lay(self) -> None:
        wide = self.width() >= DUAL_BREAKPOINT and len(self._panes) > 1
        if wide == self._side_by_side and all(
            self._grid.indexOf(pane) >= 0 for pane in self._panes
        ):
            return
        self._side_by_side = wide
        for pane in self._panes:
            self._grid.removeWidget(pane)
        for index, pane in enumerate(self._panes):
            pane.setParent(self)
            if wide:
                self._grid.addWidget(pane, 0, index)
            else:
                self._grid.addWidget(pane, index, 0)
            pane.show()


class _CountLine(ThemedWidget):
    """How many columns are chosen, under the list."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = ""
        self.setObjectName("column-picker-count")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, QtGui.QFontMetrics(self.theme.font(COUNT_TEXT)).height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setFont(self.theme.font(COUNT_TEXT))
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()


class ColumnPicker(QtWidgets.QWidget):
    """The columns of a grid, as a field picker over the ordered list it fills.

    The value is the chosen dotted paths in the order the columns will be drawn in. Picking a
    field appends its path, a path already chosen is off the field list, and a row moves by
    drag or from the keyboard.
    """

    #: The chosen paths, in order. A column was added, removed or moved.
    value_changed = Signal(list)

    def __init__(
        self,
        context: Any = None,
        entity_type: str = "",
        value: Sequence[str] = (),
        layout: str = "list",
        show_count: bool = False,
        deep_links: bool = True,
        max_depth: int = DEFAULT_MAX_DEPTH,
        data_types: str | Sequence[str] | None = None,
        valid_types: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        hide_paths: Sequence[str] | None = None,
        filterable_only: bool = False,
        extra_fields: Sequence[Any] | None = None,
        filter: Callable[[FieldSchema, str], bool] | None = None,  # noqa: A002
        placeholder: str = "Add a column",
        search_placeholder: str = "Search fields…",
        empty_label: str = NOTHING_CHOSEN_LABEL,
        no_match_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        available_label: str = "Available",
        chosen_label: str = "Columns",
        readonly: bool = False,
        disabled: bool = False,
        invalid: bool = False,
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("column-picker")
        self._value = [str(path) for path in value]
        self._layout_kind = layout if layout in COLUMN_LAYOUT_VALUES else "list"
        self._show_count = bool(show_count)
        self._readonly = bool(readonly)
        self._disabled = bool(disabled)
        self._invalid = bool(invalid)
        self._size = size if size in PICKER_SIZE_VALUES else "md"
        self._exclude = [str(path) for path in exclude] if exclude is not None else None
        self._extra_fields = extra_fields_of(extra_fields)
        self._available_label = available_label
        self._chosen_label = chosen_label
        self._labels: dict[str, list[str]] = {}
        self._label_ticket = Ticket()
        # A picker taken down under a read in flight — a page left, a demo the toolbar
        # rebuilds — leaves the friendly paths on their way to a list that has gone, and
        # writing them to a deleted model raises into the event loop. The ticket is a plain
        # object and outlives the widget, so taking it as it goes drops whatever is still out.
        ticket = self._label_ticket
        self.destroyed.connect(lambda *_ignored: ticket.cancel())
        self._state_labels = StateLabels(
            empty_label=no_match_label, loading_label=loading_label, error_label=error_label
        )

        self._picker = FieldPicker(
            context=context,
            entity_type=entity_type,
            deep_links=deep_links,
            max_depth=max_depth,
            data_types=data_types,
            valid_types=valid_types,
            exclude=self._offered(),
            hide_paths=hide_paths,
            filterable_only=filterable_only,
            extra_fields=extra_fields,
            filter=filter,
            search_placeholder=search_placeholder,
            placeholder=placeholder,
            disabled=disabled,
            invalid=invalid,
            size=self._size,
            clearable=False,
            empty_label="No field left to add",
            loading_label=loading_label,
            error_label=error_label,
            parent=self,
        )
        self._picker.value_changed.connect(self._append)

        self._chosen = ChosenColumns(self, size=self._size, label_of=self._label_of)
        self._chosen.reordered.connect(self._on_reordered)
        self._chosen.remove_requested.connect(self._remove_at)
        self._chosen.set_readonly(self._readonly)
        self._chosen.set_editable(self._editable())
        # `disabled` handed in is the same state `set_disabled` puts the widget in, so the
        # inert step of rule 5 is worn from the first paint rather than only after a setter.
        self.setEnabled(not self._disabled)

        self._empty = StateLine(
            state="empty",
            label=empty_label,
            icon=EMPTY_GLYPH,
            slot_name="column-picker-empty",
            size=self._size,
            parent=self,
        )
        self._count = _CountLine(self)

        # The dual layout's own list: the same levels, drawn in place instead of in a popup.
        self._levels = FieldLevels(
            self,
            context=context,
            entity_type=entity_type,
            deep_links=deep_links,
            max_depth=max_depth,
            data_types=data_types,
            valid_types=valid_types,
            exclude=self._exclude,
            hide_paths=hide_paths,
            filterable_only=filterable_only,
            extra_fields=extra_fields,
            filter=filter,
        )
        self._levels.changed.connect(self._refresh_available)
        # The dual list names the field's code beside its display name whenever the two
        # differ, which upstream's own row does unconditionally (column-picker.tsx:545-549).
        self._available_model = FieldOptionModel(self, checkable=True, show_code=True)
        self._crumbs = Breadcrumb("column-picker", self)
        self._crumbs.back_requested.connect(self._go_back)
        self._crumbs.reset_requested.connect(self._go_root)
        self._command = Command(
            self,
            placeholder=search_placeholder,
            should_filter=False,
            size=self._size,
            labels=self._state_labels,
        )
        available_row = self._command.list_surface().row_delegate()
        available_row.set_size(self._size)
        available_row.set_thumbnail(True)
        # A data type has a glyph, not a picture, so it is drawn bare rather than on a plate.
        available_row.set_bare_glyph(True)
        available_row.set_indicator("checkbox")
        self._command.set_model(self._available_model)
        self._command.query_changed.connect(lambda _query: self._refresh_available())
        self._command.activated.connect(self._on_available)
        self._command.input().installEventFilter(self)
        self._command.list_surface().viewport().installEventFilter(self)
        self._available_error = StateLine(
            state="error",
            icon="triangle-alert",
            slot_name="column-picker-error",
            size=self._size,
            parent=self,
        )
        self._available_skeletons = _Skeletons(self)

        self._panes = _Panes(self)
        self._available_pane = _Pane(available_label, "column-picker-available", self._panes)
        self._available_pane.add_widget(self._crumbs)
        self._available_pane.add_widget(self._available_error)
        self._available_pane.add_widget(self._available_skeletons)
        self._available_pane.add_widget(self._command)
        self._chosen_pane = _Pane(chosen_label, "column-picker-chosen", self._panes)

        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(PANE_GAP)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self._build()
        self._resolve_labels()
        self._refresh()
        if self._layout_kind == "dual":
            self._levels.read()

    # --- the parts ------------------------------------------------------------------------

    @property
    def field_picker(self) -> FieldPicker:
        """The picker a column is added through, in the list layout."""
        return self._picker

    @property
    def chosen_list(self) -> ChosenColumns:
        """The ordered list of chosen columns."""
        return self._chosen

    @property
    def available(self) -> Command:
        """The search row over the checked field list, in the dual layout."""
        return self._command

    @property
    def levels(self) -> FieldLevels:
        """Where the dual layout's own list stands."""
        return self._levels

    @property
    def breadcrumb(self) -> Breadcrumb:
        """The bar over the dual layout's search row."""
        return self._crumbs

    @property
    def announcement(self) -> str:
        """The last line the live region carried."""
        return self._chosen.accessibleDescription()

    # --- props ----------------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. The schema is read through it, once per page."""
        return self._levels.context

    def set_context(self, value: Any) -> None:
        self._levels.context = value
        self._picker.set_context(value)
        self._levels.reset()
        self._forget_labels()
        self._resolve_labels()

    @property
    def entity_type(self) -> str:
        """The type every path starts on."""
        return self._levels.entity_type

    def set_entity_type(self, value: str) -> None:
        self._levels.entity_type = str(value)
        self._picker.set_entity_type(value)
        self._levels.reset()
        self._forget_labels()
        self._resolve_labels()

    @property
    def value(self) -> list[str]:
        """The chosen dotted paths, in the order they are shown."""
        return list(self._value)

    def set_value(self, value: Sequence[str]) -> None:
        """Replace the chosen columns. Emits nothing: a caller setting the value knows it."""
        self._value = [str(path) for path in value]
        self._picker.set_exclude(self._offered())
        self._resolve_labels()
        self._refresh()

    @property
    def layout_kind(self) -> str:
        """`list` is the field picker over the ordered list; `dual` is the two lists."""
        return self._layout_kind

    def set_layout(self, value: str) -> None:
        self._layout_kind = value if value in COLUMN_LAYOUT_VALUES else "list"
        self._build()
        if self._layout_kind == "dual":
            self._levels.read()
        self._refresh()

    @property
    def show_count(self) -> bool:
        """Show how many columns are chosen under the list."""
        return self._show_count

    def set_show_count(self, value: bool) -> None:
        self._show_count = bool(value)
        self._refresh()

    @property
    def deep_links(self) -> bool:
        """Allow descending through entity fields."""
        return self._levels.deep_links

    def set_deep_links(self, value: bool) -> None:
        self._levels.deep_links = bool(value)
        self._picker.set_deep_links(value)
        self._refresh_available()

    @property
    def max_depth(self) -> int:
        """How many hops a path may take."""
        return self._levels.max_depth

    def set_max_depth(self, value: int) -> None:
        self._levels.max_depth = int(value)
        self._picker.set_max_depth(value)
        self._refresh_available()

    @property
    def data_types(self) -> str | list[str] | None:
        """Data types a field must have to be selected. Traversal ignores this."""
        return self._levels.data_types

    def set_data_types(self, value: str | Sequence[str] | None) -> None:
        self._levels.data_types = value
        self._picker.set_data_types(value)
        self._refresh_available()

    @property
    def valid_types(self) -> list[str] | None:
        """A field is selectable only if it links one of these."""
        return self._levels.valid_types

    def set_valid_types(self, value: Sequence[str] | None) -> None:
        self._levels.valid_types = list(value) if value is not None else None
        self._picker.set_valid_types(value)
        self._refresh_available()

    @property
    def exclude(self) -> list[str] | None:
        """Full dotted paths to drop."""
        return list(self._exclude) if self._exclude is not None else None

    def set_exclude(self, value: Sequence[str] | None) -> None:
        self._exclude = [str(path) for path in value] if value is not None else None
        self._levels.exclude = self.exclude
        self._picker.set_exclude(self._offered())
        self._refresh_available()

    @property
    def hide_paths(self) -> list[str] | None:
        """Dotted prefixes to drop, along with everything beneath them."""
        return self._levels.hide_paths

    def set_hide_paths(self, value: Sequence[str] | None) -> None:
        self._levels.hide_paths = list(value) if value is not None else None
        self._picker.set_hide_paths(value)
        self._refresh_available()

    @property
    def filterable_only(self) -> bool:
        """Drop the data types the API refuses in a filter."""
        return self._levels.filterable_only

    def set_filterable_only(self, value: bool) -> None:
        self._levels.filterable_only = bool(value)
        self._picker.set_filterable_only(value)
        self._refresh_available()

    @property
    def extra_fields(self) -> list[ExtraField]:
        """Synthetic entries offered at the root only."""
        return list(self._extra_fields)

    def set_extra_fields(self, value: Sequence[Any] | None) -> None:
        self._extra_fields = extra_fields_of(value)
        self._levels.extra_fields = self._extra_fields
        self._picker.set_extra_fields(value)
        self._resolve_labels()
        self._refresh_available()

    @property
    def filter(self) -> Callable[[FieldSchema, str], bool] | None:
        """The caller's own visibility test over the schema and the candidate's full path."""
        return self._levels.filter

    def set_filter(self, value: Callable[[FieldSchema, str], bool] | None) -> None:
        self._levels.filter = value
        self._picker.set_filter(value)
        self._refresh_available()

    @property
    def placeholder(self) -> str:
        return self._picker.placeholder

    def set_placeholder(self, value: str) -> None:
        self._picker.set_placeholder(value)

    @property
    def search_placeholder(self) -> str:
        return self._picker.search_placeholder

    def set_search_placeholder(self, value: str) -> None:
        self._picker.set_search_placeholder(value)
        self._command.input().setPlaceholderText(value)

    @property
    def empty_label(self) -> str:
        """Shown when nothing is chosen."""
        return self._empty.label

    def set_empty_label(self, value: str) -> None:
        self._empty.set_label(value)

    @property
    def no_match_label(self) -> str:
        """Shown when the search over the fields on offer matches nothing."""
        return self._state_labels.empty_label or NO_MATCH_LABEL

    def set_no_match_label(self, value: str) -> None:
        self._state_labels.empty_label = value
        self._refresh_available()

    @property
    def loading_label(self) -> str | None:
        return self._state_labels.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._state_labels.loading_label = value
        self._picker.set_loading_label(value)
        self._refresh_available()

    @property
    def error_label(self) -> str | None:
        return self._state_labels.error_label

    def set_error_label(self, value: str | None) -> None:
        self._state_labels.error_label = value
        self._picker.set_error_label(value)
        self._refresh_available()

    @property
    def available_label(self) -> str:
        return self._available_label

    def set_available_label(self, value: str) -> None:
        self._available_label = value
        self._available_pane.set_title(value)

    @property
    def chosen_label(self) -> str:
        return self._chosen_label

    def set_chosen_label(self, value: str) -> None:
        self._chosen_label = value
        self._chosen_pane.set_title(value)

    @property
    def readonly(self) -> bool:
        return self._readonly

    def set_readonly(self, value: bool) -> None:
        self._readonly = bool(value)
        self._build()
        self._refresh()

    @property
    def disabled(self) -> bool:
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self.setEnabled(not self._disabled)
        self._picker.set_disabled(self._disabled)
        self._chosen.set_readonly(self._readonly)
        self._chosen.set_editable(self._editable())
        self._refresh()

    @property
    def invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        self._picker.set_invalid(self._invalid)
        self._available_pane.set_invalid(self._invalid)
        self._chosen_pane.set_invalid(self._invalid)

    @property
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in PICKER_SIZE_VALUES else "md"
        self._picker.set_size(self._size)
        self._chosen.row_delegate().set_size(self._size)
        self._chosen.rows_model.set_size(self._size)
        self._chosen.viewport().update()

    # --- the layout -----------------------------------------------------------------------

    def _editable(self) -> bool:
        return not self._readonly and not self._disabled

    def _offered(self) -> list[str]:
        """A chosen path is off the field picker's list, so a column is never added twice."""
        return [*(self._exclude or []), *self._value]

    def _build(self) -> None:
        """Put the parts where the layout wants them."""
        for widget in (
            self._picker,
            self._chosen,
            self._empty,
            self._count,
            self._panes,
            self._crumbs,
            self._command,
            self._available_error,
            self._available_skeletons,
        ):
            self._column.removeWidget(widget)
        self._available_pane.setParent(self._panes)
        self._chosen_pane.setParent(self._panes)
        if self._layout_kind == "dual":
            self._panes.set_panes(
                [self._available_pane, self._chosen_pane]
                if self._editable()
                else [self._chosen_pane]
            )
            self._available_pane.setVisible(self._editable())
            for widget in (self._chosen, self._empty, self._count):
                widget.setParent(self._chosen_pane)
            self._chosen_pane.add_widget(self._chosen)
            self._chosen_pane.add_widget(self._empty)
            self._chosen_pane.add_widget(self._count)
            self._picker.hide()
            self._column.addWidget(self._panes)
            self._panes.show()
        else:
            self._panes.hide()
            for widget in (self._chosen, self._empty, self._count):
                widget.setParent(self)
            self._picker.setVisible(self._editable())
            if self._editable():
                self._column.addWidget(self._picker)
            self._column.addWidget(self._chosen)
            self._column.addWidget(self._empty)
            self._column.addWidget(self._count)
        self._chosen.set_readonly(self._readonly)
        self._chosen.set_editable(self._editable())
        self._order_tabs()

    def _order_tabs(self) -> None:
        """Walk the two panes the way they are read, not the order they were built in.

        The chosen list is built before the pane beside it, so the chain construction leaves
        runs backwards: the chosen columns first, then the controls that fill them. The list
        layout needs none of this, its picker being built before its list.

        Qt 5 is left alone. A pane there lands in a focus chain of its own as it is stacked and
        unstacked, the Tab key never reaches its controls, and an order set here is undone by
        the next layout pass and takes the chosen list out of the chain with it.
        """
        if self._layout_kind != "dual" or QT5:
            return
        run = [
            self._crumbs.back_button,
            self._crumbs.reset_button,
            self._command.input(),
            self._chosen,
        ]
        # A link through a widget that takes no focus is refused and drops the rest of the run
        # with it, so only the controls the Tab key stops on are named here.
        for before, after in zip(run, run[1:]):
            QtWidgets.QWidget.setTabOrder(before, after)

    # --- the chosen columns ------------------------------------------------------------------

    def _label_of(self, path: str) -> str:
        parts = self._labels.get(path)
        return CRUMB_SEPARATOR.join(parts) if parts else path

    def _resolve_labels(self) -> None:
        """One friendly label per chosen path, through the schema of every type it travels."""
        schema = schema_of(self._levels.context)
        paths = list(self._value)
        computed = {one.name: (one.display_name or one.name) for one in self._extra_fields}
        wanted = []
        for path in paths:
            if path in computed:
                self._labels[path] = [computed[path]]
            elif path not in self._labels:
                wanted.append(path)
        if schema is None or not self._levels.entity_type or not wanted:
            self._chosen.rows_model.set_labels(self._labels)
            return
        root = self._levels.entity_type
        number = self._label_ticket.next()

        def read() -> dict[str, list[str]]:
            out: dict[str, list[str]] = {}
            for path in wanted:
                try:
                    out[path] = [segment.display_name for segment in schema.resolve_path(root, path)]
                except Exception:
                    # A path the schema no longer holds still has to be readable.
                    out[path] = [path]
            return out

        default_pool().submit(
            read,
            on_result=lambda found, r=root: self._labels_landed(r, found),
            on_error=lambda _error: None,
            ticket=(self._label_ticket, number),
        )

    def _go_back(self) -> None:
        """The dual bar's Back, which clears the query the way the Left key does."""
        self._command.set_query("")
        self._levels.back()

    def _go_root(self) -> None:
        """The dual bar's Reset, which clears the query too."""
        self._command.set_query("")
        self._levels.reset()

    def _forget_labels(self) -> None:
        """Drop the resolved labels when the root moves.

        A label belongs to the type the path starts on, so the same dotted path reads
        differently under another root. Upstream keys its cache by `type::path` and
        re-resolves on a change of type; the cache here is emptied instead.
        """
        self._labels = {}
        self._chosen.rows_model.set_labels(self._labels)

    def _labels_landed(self, root: str, found: dict) -> None:
        if root != self._levels.entity_type:
            return
        self._labels.update(found)
        self._chosen.rows_model.set_labels(self._labels)
        self._refresh()

    def _emit(self, value: Sequence[str]) -> None:
        self._value = [str(path) for path in value]
        self._picker.set_exclude(self._offered())
        self._resolve_labels()
        self._refresh()
        self.value_changed.emit(list(self._value))

    def _append(self, path: str) -> None:
        # The picker clears as soon as the path is appended, so the next pick starts empty.
        self._picker.set_value("")
        if not self._editable() or path == "" or path in self._value:
            return
        self._emit([*self._value, path])

    def _remove_at(self, index: int) -> None:
        if not self._editable() or not 0 <= index < len(self._value):
            return
        self._emit([path for i, path in enumerate(self._value) if i != index])

    def _on_reordered(self, order: list) -> None:
        if not self._editable():
            return
        self._emit([str(path) for path in order])

    def _refresh(self) -> None:
        self._chosen.set_paths(self._value)
        self._chosen.rows_model.set_labels(self._labels)
        self._chosen.setVisible(len(self._value) > 0)
        self._empty.setVisible(len(self._value) == 0)
        self._count.setVisible(self._show_count)
        self._count.set_text(f"{len(self._value)} column{'' if len(self._value) == 1 else 's'}")
        self._available_model.set_chosen(self._value)

    # --- the dual layout's own list ------------------------------------------------------------

    def _refresh_available(self) -> None:
        query = self._command.query
        self._available_model.set_query(query)
        self._available_model.set_chosen(self._value)
        self._available_model.set_rows(self._levels.rows(query), self._levels.targets(query))
        self._crumbs.set_path(
            self._levels.entity_type,
            self._levels.crumbs(),
            self._levels.choosing.display_name if self._levels.choosing is not None else "",
        )
        self._crumbs.setVisible(self._levels.deep and self._layout_kind == "dual")
        failed = self._levels.failure is not None
        loading = self._levels.loading and self._levels.choosing is None
        if failed:
            self._available_error.set_label(
                state_line("error", self._state_labels, self._levels.failure)
            )
        self._available_error.setVisible(failed)
        self._available_skeletons.setVisible(loading and not failed)
        self._command.setVisible(not failed and not loading)
        self._command.list_surface().setAccessibleDescription(
            self._command.status_line(loading=loading, error=self._levels.failure)
        )

    def _on_available(self, row: int) -> None:
        choosing = self._levels.choosing
        if choosing is not None:
            target = self._available_model.target_at(row)
            if target is not None:
                self._command.set_query("")
                self._levels.descend(choosing, target)
            return
        option = self._available_model.option_at(row)
        if option is None:
            return
        if option.selectable:
            if self._editable():
                self._emit(toggle_field_path(self._value, option.path))
            return
        self._command.set_query("")
        self._levels.descend_into(option)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QtCore.QEvent.Type.KeyPress and self._on_available_key(event):
            return True
        if kind == QtCore.QEvent.Type.MouseButtonRelease:
            if obj is self._command.list_surface().viewport() and self._on_available_press(event):
                return True
        return super().eventFilter(obj, event)

    def _on_available_key(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        row = self._command.list_surface().highlighted()
        choosing = self._levels.choosing
        if key == Qt.Key.Key_Right:
            if choosing is not None:
                target = self._available_model.target_at(row)
                if target is not None:
                    self._command.set_query("")
                    self._levels.descend(choosing, target)
                return True
            option = self._available_model.option_at(row)
            if option is not None and option.traversable:
                self._command.set_query("")
                self._levels.descend_into(option)
                return True
            return False
        if key == Qt.Key.Key_Left and self._levels.deep:
            self._command.set_query("")
            self._levels.back()
            return True
        return False

    def _on_available_press(self, event: QtGui.QMouseEvent) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        surface = self._command.list_surface()
        point = event.pos() if hasattr(event, "pos") else event.position().toPoint()
        index = surface.indexAt(point)
        if not index.isValid():
            return False
        if self._levels.choosing is not None:
            return False
        option = self._available_model.option_at(index.row())
        if option is None or not option.traversable:
            return False
        if descend_hit(surface, index, point):
            self._command.set_query("")
            self._levels.descend_into(option)
            return True
        return False


class _Skeletons(QtWidgets.QWidget):
    """The rows the dual layout's list stands behind while the schema read is in flight."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(LIST_PAD, LIST_PAD, LIST_PAD, LIST_PAD)
        column.setSpacing(0)
        for _ in range(3):
            row = QtWidgets.QWidget(self)
            inner = QtWidgets.QHBoxLayout(row)
            inner.setContentsMargins(ROW_PAD_X, 6, ROW_PAD_X, 6)
            inner.setSpacing(0)
            inner.addWidget(Skeleton(height=CONTROL_HEIGHT["sm"] - 8, parent=row))
            column.addWidget(row)
