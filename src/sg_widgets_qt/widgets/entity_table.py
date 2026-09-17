"""A page of rows, one column per field path.

Ported from `packages/react/src/registry/sg/components/entity-table.tsx`.

Columns are schema-driven: the header is the field's display name and the cell drawing comes
from its `data_type` through `paint_field_value`. Sizing, resizing, ordering, pinning, grouping
and the selection are the view's; sorting and paging are the server's, because a sort applied to
one loaded page would order the page and not the set, and because a sort on a field that cannot
be sorted is a silent 200 no-op (026_result_order).

The drawn order and the pinned paths are the table's own: `columns` stays the list the caller
handed, and only hiding a column writes back through `columns_changed`. A header drags onto
another to reorder, and the column menu pins one to the start of the scrolling body.

`paging` says how the set is walked and the source follows it. In `pages` the footer walks with
an explicit page number and reads "n to m of N" once `_summarize` has counted it; a read carries
no total of its own (006_pagination, 020_summarize). In `more` a row at the bottom appends the
next page, in `scroll` the scroller does, and both count what is loaded in the footer. A page
that fails leaves its rows and says why at the bottom, with a retry.

An edit writes one field through the source, which follows the write with a re-read: the write's
own answer is the whole record but resolves no dotted path (024_read_after_write). A refused
write restores the value and says why in the cell.

    table = EntityTable(source=source, columns=columns, context=context, selectable=True)
    table.selection_changed.connect(store)
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, QRect, QSize, Qt, Signal

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import (
    CollectionColumn,
    EntitySource,
    SortSpec,
    SourceFilters,
    cell_value,
)
from sg_widgets_core.collection_state import (
    CollapseState,
    RowDisabledFn,
    RowIdFn,
    as_collapse_state,
    collapse_state_from,
    is_collapsed,
    same_collapse,
    toggle_collapsed,
)
from sg_widgets_core.context import SgContext, preferences_of
from sg_widgets_core.edit import editor_placement_for, is_editable_type
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.state import NO_ROWS_LABEL, StateLabels, error_text, state_line
from sg_widgets_core.status import StatusRecord

from .. import icons
from ..primitives.base import SHADOW_INK, elide
from ..primitives.button import Button
from ..primitives.roles import Roles
from ..primitives.scroll_latch import WheelLatch
from ..primitives.scrollbar import overlay_scrollbars_of
from ..primitives.skeleton import Skeleton
from ..primitives.table import CELL_PAD_X, CellDelegate, HeaderDelegate, TableSurface
from ..theme import Theme, theme_of, with_alpha
from ._sortable_rows import DRAG_THRESHOLD, DROP_LINE
from .collection_control import COLLECTION_GAP, CollectionControl, CollectionModel
from .collection_footer import DEFAULT_PAGE_SIZES, CollectionFooter
from .field_editor import FieldEditor
from .field_value import FieldValueOptions, field_value_size_hint, paint_field_value
from .state_line import StateLine

__all__ = [
    "SkeletonBlock",
    "ENTITY_TABLE_DENSITY_VALUES",
    "ENTITY_TABLE_SIZE_VALUES",
    "ENTITY_TABLE_HEAD",
    "ENTITY_TABLE_ROW_HEIGHT",
    "ENTITY_TABLE_TEXT",
    "EntityTable",
]

ENTITY_TABLE_DENSITY_VALUES: tuple[str, ...] = ("compact", "default")
ENTITY_TABLE_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")

#: Row heights per density, upstream's 33 and 41.
ENTITY_TABLE_ROW_HEIGHT: dict[str, int] = {"compact": 33, "default": 41}

#: The head a row sits under: `h-9`, `h-10`, `h-11` of the size ladder.
ENTITY_TABLE_HEAD: dict[str, int] = {"sm": 36, "md": 40, "lg": 44}

#: A row's text, on the leaf ladder (rule 6).
ENTITY_TABLE_TEXT: dict[str, int] = {"sm": 12, "md": 14, "lg": 16}

#: The select column: a fixed lane the size of a checkbox's hit box.
SELECT_WIDTH = 40

#: A column with no width of its own, and the narrowest a drag may make one.
DEFAULT_COLUMN_WIDTH = 180
MIN_COLUMN_WIDTH = 64

#: The checkbox in the select column and in the header above it.
CHECKBOX = 16

#: Said on every editable cell, because nothing else on it says an edit is possible.
EDIT_HINT = "Double-click or press Enter to edit"

#: The skeleton rows a first read stands behind, and what one costs: a cell's tallest value.
SKELETON_ROWS = 8
SKELETON_HEIGHT = 24

#: The group heading's chevron and the room the menu control takes in a head.
CHEVRON = 16
MENU_WIDTH = 24

#: What a header wears while it is carried, `opacity-50` on the dragged column upstream.
DRAG_OPACITY = 0.5

#: How far the frozen column's shadow reaches over the body it stands on, and how dark it is at
#: its own edge. `SHADOW_INK`, as every shadow is: a shadow is the light the surface blocks.
PIN_SHADOW = 8
PIN_SHADOW_ALPHA = 0.18

#: The rows the scroller leaves before it asks for the next page. Core's `SCROLL_THRESHOLD`.
BOTTOM_PAD = 8

#: Height of the scrolling body, upstream's `28rem` in pixels.
DEFAULT_MAX_HEIGHT = 448

#: What the empty and error blocks are drawn with.
EMPTY_ICON = "inbox"
ERROR_ICON = "circle-alert"


def _pad_y(density: str) -> int:
    return 4 if density == "compact" else 8


def fit_body(view: QtWidgets.QAbstractItemView, content: int, ceiling: int) -> None:
    """Give a scrolling body the room its content asks for, up to its ceiling.

    A view's own hint is one row, so a body dropped into a column would stand a row tall and
    scroll, and a body left to a stretching layout would take the whole column. The body grows
    with its content up to `max_height`, which is what the web prop says.
    """
    view.setFixedHeight(max(0, min(content, ceiling)))


def rows_height(view: QtWidgets.QAbstractItemView, lines: int, ceiling: int) -> int:
    """What `lines` rows of a view cost, stopping once the ceiling is passed."""
    total = 0
    for line in range(lines):
        total += max(1, view.sizeHintForRow(line))
        if total >= ceiling:
            break
    return total


def _px(value: int | str) -> int:
    """A height as pixels. A `rem` string is the upstream prop, at 16px to the rem."""
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        if text.endswith("rem"):
            return int(round(float(text[:-3]) * 16))
        if text.endswith("px"):
            return int(round(float(text[:-2])))
        return int(round(float(text)))
    except ValueError:
        return DEFAULT_MAX_HEIGHT


class _Header(HeaderDelegate):
    """The header row: the select column's tri-state box, the labels, the sort arrow and the menu."""

    select_toggled = Signal(bool)
    menu_requested = Signal(int, QtCore.QPoint)
    #: A section was dropped on another: the column carried, and the one it lands in front of.
    reorder_requested = Signal(int, int)

    def __init__(self, parent: QtWidgets.QWidget | None = None, density: str = "default") -> None:
        super().__init__(parent, density=density)
        self._size = "md"
        self._show_code = False
        self._menu = False
        self._select = False
        self._all = False
        self._some = False
        self._reorderable = False
        self._press: QtCore.QPoint | None = None
        self._press_column = -1
        self._press_handle = -1
        self._drag = -1
        self._drop = -1
        self._dropped = False

    def set_reorderable(self, value: bool) -> None:
        """Whether a section of this header drags onto another to reorder the columns."""
        self._reorderable = bool(value)

    def set_table_size(self, value: str) -> None:
        self._size = value if value in ENTITY_TABLE_SIZE_VALUES else "md"
        # `TEXT[size]` sets the label's step as well as the row's.
        self.set_text_size(ENTITY_TABLE_TEXT[self._size])
        self.updateGeometry()

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self.viewport().update()

    def set_column_menu(self, value: bool) -> None:
        self._menu = bool(value)
        self.viewport().update()

    def set_select_column(self, value: bool) -> None:
        self._select = bool(value)
        self.viewport().update()

    def set_check_state(self, all_: bool, some: bool) -> None:
        self._all = bool(all_)
        self._some = bool(some)
        self.viewport().update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(super().sizeHint().width(), ENTITY_TABLE_HEAD[self._size])

    def sortable(self, column: int) -> bool:
        if self._select and column == 0:
            return False
        return super().sortable(column)

    def _checkbox_rect(self, rect: QRect) -> QRect:
        box = QRect(0, 0, CHECKBOX, CHECKBOX)
        box.moveCenter(rect.center())
        return box

    def _menu_rect(self, rect: QRect) -> QRect:
        return QRect(rect.right() + 1 - MENU_WIDTH, rect.top(), MENU_WIDTH, rect.height())

    def paintSection(self, painter: QtGui.QPainter, rect: QRect, column: int) -> None:  # noqa: N802
        if column == self._drag or column == self._drop:
            painter.save()
            if column == self._drag:
                painter.setOpacity(DRAG_OPACITY)
            self._paint_section(painter, rect, column)
            painter.setOpacity(1.0)
            if column == self._drop and column != self._drag:
                # The mark stands where the carried column lands, which is in front of this one.
                painter.fillRect(
                    QRect(rect.left(), rect.top(), DROP_LINE, rect.height()),
                    theme_of(self).color("ring"),
                )
            painter.restore()
            return
        self._paint_section(painter, rect, column)

    def _paint_section(self, painter: QtGui.QPainter, rect: QRect, column: int) -> None:
        theme = theme_of(self)
        if self._select and column == 0:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.fillRect(rect, theme.color("background"))
            _paint_checkbox(
                painter, self._checkbox_rect(rect), theme, self._all, self._some and not self._all
            )
            painter.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), theme.color("border"))
            painter.restore()
            return
        body = self._menu_rect(rect) if self._menu else QRect()
        super().paintSection(painter, rect.adjusted(0, 0, -MENU_WIDTH if self._menu else 0, 0), column)
        if not self._menu:
            return
        painter.save()
        painter.fillRect(body.adjusted(0, 0, 0, -1), theme.color("background"))
        glyph = QRect(0, 0, CHEVRON, CHEVRON)
        glyph.moveCenter(body.center())
        icons.paint_icon(painter, glyph, "ellipsis-vertical", theme.color("muted_foreground"))
        painter.fillRect(QRect(body.left(), body.bottom(), body.width(), 1), theme.color("border"))
        painter.restore()

    def suffix(self, column: int) -> str:
        """The programmatic path beside the display name, in the mono family (rule 6).

        Upstream draws it inside the header's own flex row, right after the label, so it reads
        as part of the label and the column menu does not displace it.
        """
        model = self.model()
        if not self._show_code or model is None:
            return ""
        path = str(model.headerData(column, Qt.Orientation.Horizontal, Roles.CODE) or "")
        label = str(
            model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or ""
        )
        return "" if not path or path == label else path

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        column = self.logicalIndexAt(point)
        rect = QRect(
            self.sectionViewportPosition(column), 0, self.sectionSize(column), self.height()
        )
        if self._select and column == 0:
            self.select_toggled.emit(not self._all)
            return
        if self._menu and column >= 0 and self._menu_rect(rect).contains(point):
            self.menu_requested.emit(column, self.mapToGlobal(point))
            return
        # A press that landed on a divider is a resize, and a resize is never a carry.
        self._press = QtCore.QPoint(point)
        self._press_column = column
        self._press_handle = self._handle
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        if not self._reorderable or self._press is None or self._press_handle >= 0:
            return
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self._drag < 0:
            if (point - self._press).manhattanLength() < DRAG_THRESHOLD:
                return
            self._drag = self._press_column
        over = self.logicalIndexAt(point)
        if self._select and over == 0:
            over = -1
        if over != self._drop:
            self._drop = over
            self.viewport().update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        carried, target = self._drag, self._drop
        self._press = None
        self._press_column = -1
        self._drag = -1
        self._drop = -1
        if carried >= 0:
            # The drop is not a click, so the column it ends on does not also sort.
            self._dropped = True
            self.viewport().update()
        super().mouseReleaseEvent(event)
        self._dropped = False
        if carried >= 0 and target >= 0 and target != carried:
            self.reorder_requested.emit(carried, target)

    def _on_clicked(self, column: int) -> None:
        if self._dropped:
            return
        super()._on_clicked(column)


class _Cells(CellDelegate):
    """One body cell: the select box, a value through `paint_field_value`, or a group heading."""

    def __init__(self, table: EntityTable, density: str = "default") -> None:
        super().__init__(table.view, density=density)
        self._table = table

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), ENTITY_TABLE_ROW_HEIGHT[self._table.density])

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        theme = theme_of(self._table.view)
        rect = option.rect
        model = self._table.model
        line = model.line_at(index.row())
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        if line is not None and line.kind == "heading":
            self._paint_heading(painter, rect, index, theme)
            painter.restore()
            return

        row = None if line is None else line.row
        if row is None:
            painter.restore()
            return
        selected = bool(index.data(Roles.CHECKED))
        disabled = bool(index.data(Roles.DISABLED))
        hovered = self._table.hovered_row() == index.row()
        column = model.column_at(index.column())
        editable = column is not None and self._table.can_edit(column, row)

        if selected:
            painter.fillRect(rect, theme.color("accent"))
        elif hovered:
            painter.fillRect(rect, with_alpha(theme.muted, 0.5))
        else:
            painter.fillRect(rect, theme.color("background"))
        if editable and (hovered or self._table.cursor_index() == index):
            painter.fillRect(rect, with_alpha(theme.accent, 0.5))
        painter.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), theme.color("border"))
        if disabled:
            painter.setOpacity(0.5)

        if model.select_column and index.column() == 0:
            box = QRect(0, 0, CHECKBOX, CHECKBOX)
            box.moveCenter(rect.center())
            _paint_checkbox(painter, box, theme, selected, False)
            painter.restore()
            return
        if column is None:
            painter.restore()
            return

        if self._table.is_editing(model.key_of(row), column.path):
            # The editor mounted on this cell draws the value; painting it here too doubles it.
            painter.restore()
            return
        pad = _pad_y(self._table.density)
        box = rect.adjusted(CELL_PAD_X, pad, -CELL_PAD_X, -pad - 1)
        message = self._table.cell_error(model.key_of(row), column.path)
        if message:
            half = max(12, box.height() // 2)
            self._paint_error(painter, QRect(box.left(), box.bottom() + 1 - half, box.width(), half), message, theme)
            box = QRect(box.left(), box.top(), box.width(), max(0, box.height() - half))
        paint_field_value(
            painter,
            box,
            cell_value(row, column.path),
            column,
            self._table.value_options(selected=selected, enabled=not disabled),
        )
        if self._table.cursor_index() == index and self._table.body_has_focus():
            self._table.paint_cell_ring(painter, rect)
        painter.restore()

    def _paint_error(
        self, painter: QtGui.QPainter, rect: QRect, message: str, theme: Theme
    ) -> None:
        font = theme.font(12)
        painter.save()
        painter.setFont(font)
        painter.setPen(theme.color("destructive"))
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(QtGui.QFontMetrics(font), message, rect.width()),
        )
        painter.restore()

    def _paint_heading(
        self, painter: QtGui.QPainter, rect: QRect, index: QModelIndex, theme: Theme
    ) -> None:
        group = index.data(Roles.ENTITY)
        if group is None:
            return
        painter.fillRect(rect, with_alpha(theme.muted, 0.5))
        painter.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), theme.color("border"))
        open_ = bool(index.data(Roles.CHECKED))
        glyph = QRect(rect.left() + CELL_PAD_X, 0, CHEVRON, CHEVRON)
        glyph.moveTop(rect.center().y() - CHEVRON // 2)
        icons.paint_icon(
            painter,
            glyph,
            "chevron-down" if open_ else "chevron-right",
            theme.color("muted_foreground"),
        )
        left = glyph.right() + 1 + 6
        count = str(len(group.rows))
        mono = theme.font(12)
        mono.setFamily(theme.font_mono)
        count_width = QtGui.QFontMetrics(mono).horizontalAdvance(count)
        room = max(0, rect.width() - left - CELL_PAD_X - count_width - 6)
        box = QRect(left, rect.top(), room, rect.height())
        column = self._table.group_column()
        options = self._table.value_options()
        target = column if column is not None else "text"
        paint_field_value(painter, box, group.value, target, options)
        # The count follows the value in the same line, a gap away, which is what the
        # heading's own flex row does upstream. A spanned row is wide, and a count at its
        # far edge reads as a column of its own.
        used = min(field_value_size_hint(group.value, target, options).width(), room)
        painter.save()
        painter.setFont(mono)
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            QRect(left + used + 6, rect.top(), count_width, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            count,
        )
        painter.restore()


def _paint_checkbox(
    painter: QtGui.QPainter, box: QRect, theme: Theme, checked: bool, mixed: bool
) -> None:
    """The row's box, drawn by us: the primitive's look without a widget per cell."""
    radius = float(theme.radius_px("sm"))
    on = checked or mixed
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(theme.color("primary") if on else theme.color("background"))
    painter.setPen(QtGui.QPen(theme.color("primary" if on else "border"), 1.0))
    painter.drawRoundedRect(QtCore.QRectF(box).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    if on:
        icons.paint_icon(
            painter,
            box.adjusted(3, 3, -3, -3),
            "minus" if mixed else "check",
            theme.color("primary_foreground"),
        )
    painter.restore()


class _Body(TableSurface):
    """The table view: the press model of the select column, the group headings and the cursor."""

    def __init__(self, table: EntityTable, density: str = "default") -> None:
        self._table = table
        super().__init__(table, density=density)
        self._latch = WheelLatch(self, more=lambda: self._table.control.snapshot().has_more)
        self.setObjectName("entity-table-scroll")
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._table.layout_frozen()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        """A row lights across both views: the frozen column is the same row as the body's."""
        before = self.hovered_row()
        super().mouseMoveEvent(event)
        if self.hovered_row() != before:
            self._table.repaint_body()

    def leaveEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._table.repaint_body()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        """A gesture that reached the edge, or a page on its way, keeps the wheel off the page."""
        if self._latch.keeps(event):
            event.accept()
            return
        super().wheelEvent(event)
    def setHorizontalHeader(self, header: QtWidgets.QHeaderView) -> None:  # noqa: N802
        """Keep the surface's own pointer on the header that is installed.

        Installing a second header deletes the first, and the surface reaches for its own on
        every density change; without this it would reach for the one Qt has already freed.
        """
        super().setHorizontalHeader(header)
        self._header = header

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(point)
        if index.isValid() and self._table.on_cell_pressed(index):
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(point)
        if index.isValid():
            self._table.on_cell_activated(index)
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._table.on_body_key(event):
            return
        super().keyPressEvent(event)

    def viewportEvent(self, event: QtCore.QEvent) -> bool:  # noqa: N802
        """Say an editable cell can be edited: nothing else on it does.

        The cell lights under the pointer, which reads as an affordance only once a reader
        knows what it means, so the hint is the tooltip upstream puts on the same cell.
        """
        if event.type() == QtCore.QEvent.Type.ToolTip:
            point = event.pos() if hasattr(event, "pos") else QtCore.QPoint()
            index = self.indexAt(point)
            hint = self._table.edit_hint(index) if index.isValid() else ""
            if hint:
                QtWidgets.QToolTip.showText(
                    event.globalPos() if hasattr(event, "globalPos") else point, hint, self
                )
                return True
            QtWidgets.QToolTip.hideText()
        return super().viewportEvent(event)


class _Frozen(_Body):
    """The pinned columns, drawn over the body from the same model.

    A `position: sticky` cell has no equal in a `QTableView`: a view scrolls its whole viewport.
    So the pinned columns are a second view of the same model, showing those columns alone,
    standing over the body at the left edge and stepping with it row for row. Everything a cell
    knows is the model's, so the delegate, the row cursor, the selection, the editor and the
    column menu are the body's own: a press here runs the code a press there runs.
    """

    def __init__(self, table: EntityTable, density: str = "default") -> None:
        super().__init__(table, density=density)
        self.setParent(table.view)
        self.setObjectName("entity-table-frozen")
        self.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._bars = overlay_scrollbars_of(self) or ()
        for bar in self._bars:
            bar.installEventFilter(self)
            bar.hide()
        self.hide()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        QtWidgets.QTableView.resizeEvent(self, event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        """One scroller for the two views: the body owns the wheel, and this follows it."""
        QtWidgets.QApplication.sendEvent(self._table.view.viewport(), event)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        # The frozen column moves with the body, so it never carries a bar of its own.
        if event.type() == QtCore.QEvent.Type.Show and any(watched is bar for bar in self._bars):
            watched.hide()
            return True
        return super().eventFilter(watched, event)


class _PinEdge(QtWidgets.QWidget):
    """The rule down the frozen column's trailing edge, and the shadow it casts once scrolled.

    Upstream leaves a sticky cell's edge bare: the rows behind it are hidden by its own ground
    and the page reads on. A view standing over another needs to say so, so the edge carries the
    1px rule the table draws everywhere and, once the body has run under it, the short shadow
    rule 4 gives anything that floats.
    """

    def __init__(self, table: EntityTable) -> None:
        super().__init__(table.view)
        self.setObjectName("entity-table-pin-edge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._table = table

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        box = self.rect()
        if self._table.body_scrolled():
            fade = QtGui.QLinearGradient(float(box.left()), 0.0, float(box.right() + 1), 0.0)
            fade.setColorAt(0.0, with_alpha(SHADOW_INK, PIN_SHADOW_ALPHA))
            fade.setColorAt(1.0, with_alpha(SHADOW_INK, 0.0))
            painter.fillRect(box.adjusted(1, 0, 0, 0), fade)
        painter.fillRect(QRect(box.left(), box.top(), 1, box.height()), theme.color("border"))
        painter.end()


class EntityTable(QtWidgets.QWidget):
    """A page of rows, one column per field path, over the shared collection model."""

    #: The selected rows. Carries `list[EntityRef]`.
    selection_changed = Signal(object)
    #: The source's sort moved. Carries `list[SortSpec]`.
    sort_changed = Signal(object)
    #: The source's filter moved. Carries the wire group, or None.
    filters_changed = Signal(object)
    #: A column was hidden. Carries the shorter `list[CollectionColumn]`.
    columns_changed = Signal(object)
    #: The shut group headers moved. Carries a `CollapseState`.
    collapsed_changed = Signal(object)
    #: A row was opened: a double-click or Enter on a cell that does not edit.
    row_activated = Signal(object)
    #: A read, a write or a count raised. Carries the exception.
    failed = Signal(object)

    def __init__(
        self,
        source: EntitySource,
        columns: Sequence[CollectionColumn] = (),
        statuses: Mapping[str, StatusRecord] | None = None,
        context: SgContext | None = None,
        project_id: int | None = None,
        precision: int | None = None,
        symbol: str = "$",
        density: str = "default",
        size: str = "md",
        selectable: bool = False,
        selection: Sequence[EntityRef] | None = None,
        get_row_id: RowIdFn | None = None,
        is_row_disabled: RowDisabledFn | None = None,
        group_by: str | None = None,
        collapsed: Sequence[str] | CollapseState | None = None,
        sort: Sequence[SortSpec] | None = None,
        filters: SourceFilters = None,
        editable: bool = False,
        editor_for: Callable[[str], Any] | None = None,
        editor_placement: str | None = None,
        show_code: bool = False,
        column_menu: bool = False,
        paging: str = "pages",
        page_sizes: Sequence[int] = DEFAULT_PAGE_SIZES,
        max_height: int | str = DEFAULT_MAX_HEIGHT,
        virtualize_after: int = 100,
        empty_label: str = NO_ROWS_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-table")
        self._columns = list(columns)
        self._statuses = statuses
        self._context = context
        self._project_id = project_id
        self._precision = precision
        self._symbol = symbol
        self._density = density if density in ENTITY_TABLE_DENSITY_VALUES else "default"
        self._size = size if size in ENTITY_TABLE_SIZE_VALUES else "md"
        self._selectable = bool(selectable)
        self._group_by = group_by
        self._collapsed = as_collapse_state(collapsed)
        self._editable = bool(editable)
        self._editor_for = editor_for
        self._editor_placement = editor_placement
        self._show_code = bool(show_code)
        self._column_menu = bool(column_menu)
        self._virtualize_after = int(virtualize_after)
        self._empty_label = empty_label
        self._editing: tuple[str, str] | None = None
        self._draft: Any = None
        self._cell_error: tuple[str, str, str] | None = None
        self._cursor = QModelIndex()
        self._menu: Any = None
        # The display order and the pinned paths are the table's own, as upstream holds them in
        # the table rather than in the column list: `columns` stays the list the caller handed.
        self._order: list[str] = []
        self._pinned: list[str] = []
        self._widths: dict[str, int] = {}
        self._sizing = False
        #: The body's room the last time rows stood in it, which a re-read keeps.
        self._held_body = 0

        self.control = CollectionControl(
            source,
            paging=paging,
            sort=sort,
            filters=filters,
            selection=selection,
            get_row_id=get_row_id,
            is_row_disabled=is_row_disabled,
            loading_label=loading_label,
            empty_label=empty_label,
            error_label=error_label,
            parent=self,
        )
        self.model.set_columns(self._columns)
        self.model.set_select_column(self._selectable)
        self.model.set_collapsed(self._collapsed)
        self.model.set_group_by(self._group_by)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(COLLECTION_GAP)

        self._toolbar = QtWidgets.QWidget(self)
        self._toolbar.setObjectName("entity-table-toolbar")
        bar = QtWidgets.QHBoxLayout(self._toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(COLLECTION_GAP)
        self._toolbar_start = QtWidgets.QWidget(self._toolbar)
        self._toolbar_start.setObjectName("entity-table-toolbar-start")
        start = QtWidgets.QHBoxLayout(self._toolbar_start)
        start.setContentsMargins(0, 0, 0, 0)
        start.setSpacing(COLLECTION_GAP)
        # `items-center`: each block is as tall as what it holds and sits on the bar's centre
        # line, so a filter bar that wrapped to two rows does not stretch the sort control beside it.
        bar.addWidget(self._toolbar_start, 0, Qt.AlignmentFlag.AlignVCenter)
        bar.addStretch(1)
        self._toolbar_end = QtWidgets.QWidget(self._toolbar)
        self._toolbar_end.setObjectName("entity-table-toolbar-end")
        end = QtWidgets.QHBoxLayout(self._toolbar_end)
        end.setContentsMargins(0, 0, 0, 0)
        end.setSpacing(COLLECTION_GAP)
        bar.addWidget(self._toolbar_end, 0, Qt.AlignmentFlag.AlignVCenter)
        self._toolbar.hide()
        column.addWidget(self._toolbar)

        self._box = QtWidgets.QWidget(self)
        self._box.setObjectName("entity-table-box")
        body = QtWidgets.QVBoxLayout(self._box)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.view = _Body(self, density=self._density)
        self._header = _Header(self.view, density=self._density)
        self.view.setHorizontalHeader(self._header)
        self._header.setSectionsClickable(True)
        self._header.setStretchLastSection(True)
        self._header.sort_requested.connect(self._on_sort_requested)
        self._header.select_toggled.connect(self.control.toggle_all)
        self._header.menu_requested.connect(self._open_column_menu)
        self._header.reorder_requested.connect(self._on_reorder)
        self._header.set_reorderable(True)
        self._cells = _Cells(self, density=self._density)
        self.view.setItemDelegate(self._cells)
        self.view.setModel(self.model)
        self._max_height = _px(max_height)
        self.view.setMaximumHeight(self._max_height)
        body.addWidget(self.view)

        self.frozen = _Frozen(self, density=self._density)
        self._frozen_header = _Header(self.frozen, density=self._density)
        self.frozen.setHorizontalHeader(self._frozen_header)
        self._frozen_header.setStretchLastSection(False)
        self._frozen_header.sort_requested.connect(self._on_sort_requested)
        self._frozen_header.menu_requested.connect(
            lambda column, point: self._open_column_menu(column, point, self._frozen_header)
        )
        self._frozen_header.reorder_requested.connect(self._on_reorder)
        self._frozen_header.set_reorderable(True)
        self.frozen.setItemDelegate(self._cells)
        self.frozen.setModel(self.model)
        self._pin_edge = _PinEdge(self)
        self._pin_edge.hide()

        self._state = StateLine(pad="table", slot_name="entity-table-state", parent=self._box)
        self._state.hide()
        body.addWidget(self._state)
        self._skeleton = _TableSkeleton(self._box)
        self._skeleton.hide()
        body.addWidget(self._skeleton)
        self._bottom = _BottomBlock(self._box)
        self._bottom.retry_requested.connect(self.control.retry)
        self._bottom.more_requested.connect(self.control.load_more)
        self._bottom.hide()
        body.addWidget(self._bottom)
        column.addWidget(self._box)

        self.footer = CollectionFooter(
            self.control.binding, page_sizes=page_sizes, slot_name="entity-table", parent=self
        )
        column.addWidget(self.footer)

        self.control.changed.connect(self._sync)
        self.control.selection_changed.connect(self._on_selection)
        self.control.sort_changed.connect(self._on_sort_moved)
        self.control.filters_changed.connect(self.filters_changed.emit)
        self.control.failed.connect(self.failed.emit)
        self.model.modelReset.connect(self._apply_spans)
        bar_ = self.view.verticalScrollBar()
        if bar_ is not None:
            bar_.valueChanged.connect(self._on_scrolled)
            bar_.valueChanged.connect(self._follow_body)
        across = self.view.horizontalScrollBar()
        if across is not None:
            across.valueChanged.connect(self.layout_frozen)
        frozen_bar = self.frozen.verticalScrollBar()
        if frozen_bar is not None:
            frozen_bar.valueChanged.connect(self._follow_frozen)
        self._header.sectionResized.connect(self._on_section_resized)
        self._apply_display()
        self._apply_sort_indicator()
        self._sync()

    # --- the model ------------------------------------------------------------------------

    @property
    def model(self) -> CollectionModel:
        """The snapshot the three layouts share."""
        return self.control.model

    @property
    def source(self) -> EntitySource:
        return self.control.source

    # --- props ----------------------------------------------------------------------------

    @property
    def columns(self) -> list[CollectionColumn]:
        """Columns in display order, from `resolve_columns`."""
        return list(self._columns)

    def set_columns(self, value: Sequence[CollectionColumn]) -> None:
        self._columns = list(value)
        self._apply_display()
        self._apply_sort_indicator()
        self._sync()

    @property
    def pinned_columns(self) -> list[str]:
        """The paths stuck to the start of the scrolling body, in the order they were pinned."""
        return [path for path in self._pinned if any(c.path == path for c in self._columns)]

    @property
    def column_order(self) -> list[str]:
        """The paths in the order the table draws them: the pinned ones first, then the rest."""
        return [column.path for column in self._display_columns()]

    def pin_column(self, path: str, pinned: bool = True) -> None:
        """Stick a column to the start of the scrolling body, or give it back to its place."""
        held = [one for one in self._pinned if one != path]
        if pinned:
            held.append(path)
        if held == self._pinned:
            return
        self.close_editor()
        self._pinned = held
        self._apply_display()
        self._sync()

    def move_column(self, path: str, before: str | None) -> None:
        """Put one column in front of another, or at the end where `before` is None."""
        order = self.column_order
        if path not in order or path == before:
            return
        order.remove(path)
        order.insert(order.index(before) if before in order else len(order), path)
        if order == self._order:
            return
        self.close_editor()
        self._order = order
        self._apply_display()
        self._sync()

    def _display_columns(self) -> list[CollectionColumn]:
        """The columns as they are drawn: pinned to the start first, the rest as ordered."""
        by_path = {column.path: column for column in self._columns}
        order = [path for path in self._order if path in by_path]
        order += [column.path for column in self._columns if column.path not in order]
        pinned = [path for path in order if path in self._pinned]
        return [by_path[path] for path in pinned + [p for p in order if p not in pinned]]

    @property
    def statuses(self) -> Mapping[str, StatusRecord] | None:
        """`Status` rows by code, for status cells (probe 010)."""
        return self._statuses

    def set_statuses(self, value: Mapping[str, StatusRecord] | None) -> None:
        self._statuses = value
        self.view.viewport().update()

    @property
    def context(self) -> SgContext | None:
        """The widget context. Cells render with its preferences and a cell editor reads through it."""
        return self._context

    def set_context(self, value: SgContext | None) -> None:
        self._context = value
        self.view.viewport().update()

    @property
    def project_id(self) -> int | None:
        """The project the columns were resolved with. Scopes a status, list or entity cell editor."""
        return self._project_id

    def set_project_id(self, value: int | None) -> None:
        self._project_id = value

    @property
    def precision(self) -> int | None:
        """Decimals a float cell keeps."""
        return self._precision

    def set_precision(self, value: int | None) -> None:
        self._precision = value
        self.view.viewport().update()

    @property
    def symbol(self) -> str:
        """Shown before the value in a currency cell."""
        return self._symbol

    def set_symbol(self, value: str) -> None:
        self._symbol = value
        self.view.viewport().update()

    @property
    def density(self) -> str:
        """`compact` halves the vertical cell padding."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value if value in ENTITY_TABLE_DENSITY_VALUES else "default"
        self._cells.set_density(self._density)
        for view, header in ((self.view, self._header), (self.frozen, self._frozen_header)):
            view.set_density(self._density)
            header.set_density(self._density)
            view.verticalHeader().setDefaultSectionSize(ENTITY_TABLE_ROW_HEIGHT[self._density])
        self.layout_frozen()
        self.repaint_body()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the row text and the head it sits under."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in ENTITY_TABLE_SIZE_VALUES else "md"
        self._header.set_table_size(self._size)
        self._frozen_header.set_table_size(self._size)
        self.layout_frozen()
        self.repaint_body()

    @property
    def selectable(self) -> bool:
        """Draws a checkbox column and reports the selection."""
        return self._selectable

    def set_selectable(self, value: bool) -> None:
        self._selectable = bool(value)
        self.model.set_select_column(self._selectable)
        self._apply_columns()

    @property
    def selection(self) -> list[EntityRef]:
        """The selected rows."""
        return self.control.selection

    def set_selection(self, value: Sequence[EntityRef]) -> None:
        self.control.set_selection(value)
        self._sync()

    def set_get_row_id(self, fn: RowIdFn | None) -> None:
        self.control.set_get_row_id(fn)

    def set_is_row_disabled(self, fn: RowDisabledFn | None) -> None:
        self.control.set_is_row_disabled(fn)

    @property
    def group_by(self) -> str | None:
        """Collapse rows under headers of a shared value at this path."""
        return self._group_by

    def set_group_by(self, value: str | None) -> None:
        self._group_by = value
        self.model.set_group_by(value)
        self._lead_sort()
        self._sync()

    @property
    def collapsed(self) -> CollapseState:
        """Which group headers are shut."""
        return self._collapsed

    def set_collapsed(self, value: Sequence[str] | CollapseState | None) -> None:
        state = as_collapse_state(value)
        if same_collapse(state, self._collapsed):
            return
        self._collapsed = state
        self.model.set_collapsed(state)
        self._sync()

    @property
    def sort(self) -> list[SortSpec]:
        """The source's sort."""
        return self.control.sort

    def set_sort(self, value: Sequence[SortSpec] | None) -> None:
        self.control.set_sort(value)

    @property
    def filters(self) -> SourceFilters:
        """The source's filter."""
        return self.control.filters

    def set_filters(self, value: SourceFilters) -> None:
        self.control.set_filters(value)

    @property
    def editable(self) -> bool:
        """Opens an editor on a double-click or Enter in an editable cell."""
        return self._editable

    def set_editable(self, value: bool) -> None:
        self._editable = bool(value)
        self.view.viewport().update()

    @property
    def editor_for(self) -> Callable[[str], Any] | None:
        """The editor a cell opens, by data type. A type it does not answer for opens FieldEditor."""
        return self._editor_for

    def set_editor_for(self, value: Callable[[str], Any] | None) -> None:
        self._editor_for = value

    @property
    def editor_placement(self) -> str | None:
        """Where every cell editor opens. A column's own wins over it; the data type decides last."""
        return self._editor_placement

    def set_editor_placement(self, value: str | None) -> None:
        self._editor_placement = value

    @property
    def show_code(self) -> bool:
        """Show the programmatic field path beside the header's display name."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._header.set_show_code(self._show_code)
        self._frozen_header.set_show_code(self._show_code)

    @property
    def column_menu(self) -> bool:
        """A menu on every header: sort, hide and pin left."""
        return self._column_menu

    def set_column_menu(self, value: bool) -> None:
        self._column_menu = bool(value)
        self._header.set_column_menu(self._column_menu)
        self._frozen_header.set_column_menu(self._column_menu)

    @property
    def paging(self) -> str:
        """`pages`, `more` or `scroll`."""
        return self.control.paging

    def set_paging(self, value: str) -> None:
        self.control.set_paging(value)
        self._sync()

    @property
    def page_sizes(self) -> list[int]:
        return self.footer.page_sizes

    def set_page_sizes(self, value: Sequence[int]) -> None:
        self.footer.set_page_sizes(value)

    @property
    def max_height(self) -> int:
        """Height of the scrolling body, in pixels."""
        return self._max_height

    def set_max_height(self, value: int | str) -> None:
        self._max_height = _px(value)
        self._fit()

    @property
    def virtualize_after(self) -> int:
        """Kept for parity. A `QTableView` draws only the rows on screen at any length."""
        return self._virtualize_after

    def set_virtualize_after(self, value: int) -> None:
        self._virtualize_after = int(value)

    @property
    def empty_label(self) -> str:
        """Shown when the read returned nothing."""
        return self._empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = value
        labels = self.control.labels
        self.control.set_labels(
            StateLabels(
                empty_label=value,
                loading_label=labels.loading_label,
                error_label=labels.error_label,
            )
        )
        self._sync()

    def set_loading_label(self, value: str | None) -> None:
        labels = self.control.labels
        self.control.set_labels(
            StateLabels(
                empty_label=labels.empty_label, loading_label=value, error_label=labels.error_label
            )
        )

    def set_error_label(self, value: str | None) -> None:
        labels = self.control.labels
        self.control.set_labels(
            StateLabels(
                empty_label=labels.empty_label,
                loading_label=labels.loading_label,
                error_label=value,
            )
        )
        self._sync()

    # --- the toolbar ----------------------------------------------------------------------

    def set_toolbar_start(self, *widgets: QtWidgets.QWidget) -> None:
        """The left region of the toolbar above the table."""
        self._fill(self._toolbar_start, widgets)

    def set_toolbar_end(self, *widgets: QtWidgets.QWidget) -> None:
        """The right region of the toolbar above the table."""
        self._fill(self._toolbar_end, widgets)

    def _fill(self, holder: QtWidgets.QWidget, widgets: Sequence[QtWidgets.QWidget]) -> None:
        layout = holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            made = item.widget()
            if made is not None:
                made.setParent(None)
        for widget in widgets:
            widget.setParent(holder)
            layout.addWidget(widget)
        self._toolbar.setVisible(
            self._toolbar_start.layout().count() > 0 or self._toolbar_end.layout().count() > 0
        )

    # --- what a cell draws with -----------------------------------------------------------

    def value_options(self, selected: bool = False, enabled: bool = True) -> FieldValueOptions:
        """What `paint_field_value` draws a cell with: the theme, the statuses and the preferences."""
        text = preferences_of(self._context)
        if self._precision is not None:
            text.precision = self._precision
        return FieldValueOptions(
            theme=theme_of(self.view),
            statuses=self._statuses,
            site_url=self._context.site_url if self._context is not None else "",
            density=self._density,
            text=text,
            selected=selected,
            enabled=enabled,
            on_ready=self.view.viewport().update,
        )

    def group_column(self) -> CollectionColumn | None:
        """The column the group path was read from, so a heading draws by its data type."""
        if self._group_by is None:
            return None
        return next((column for column in self._columns if column.path == self._group_by), None)

    def cell_error(self, key: str, path: str) -> str:
        """What a refused write said on this cell, or an empty string."""
        held = self._cell_error
        return held[2] if held is not None and held[0] == key and held[1] == path else ""

    def cursor_index(self) -> QModelIndex:
        """The cell the keyboard cursor is on."""
        return self._cursor

    def paint_cell_ring(self, painter: QtGui.QPainter, rect: QRect) -> None:
        """The 2px ring rule 5 paints around the cell the keyboard is on."""
        theme = theme_of(self.view)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(theme.color("ring"), 2.0))
        painter.drawRect(QtCore.QRectF(rect).adjusted(1, 1, -1, -1))
        painter.restore()

    # --- sorting --------------------------------------------------------------------------

    def _sort_of(self, path: str) -> SortSpec | None:
        return next((key for key in self.control.sort if key.path == path), None)

    def toggle_sort(self, path: str) -> None:
        """Ascending, then descending, then unsorted, which is the server's id ascending."""
        current = self._sort_of(path)
        if current is None:
            self._apply_sort([SortSpec(path=path, descending=False)])
        elif not current.descending:
            self._apply_sort([SortSpec(path=path, descending=True)])
        else:
            self._apply_sort([])

    def _apply_sort(self, keys: Sequence[SortSpec]) -> None:
        """The group path stays the first sort key: a split group is not a group."""
        wanted = list(keys)
        if self._group_by and (not wanted or wanted[0].path != self._group_by):
            wanted = [SortSpec(path=self._group_by, descending=False), *wanted]
        self.control.apply_sort(wanted)

    def _lead_sort(self) -> None:
        """A group is only whole when the server put its rows together, so the path leads the sort."""
        if not self._group_by:
            return
        keys = self.control.sort
        if keys and keys[0].path == self._group_by:
            return
        self.control.apply_sort(
            [
                SortSpec(path=self._group_by, descending=False),
                *[key for key in keys if key.path != self._group_by],
            ]
        )

    def _on_sort_requested(self, column: int, _order: object) -> None:
        found = self.model.column_at(column)
        if found is None or not found.sortable:
            return
        self.toggle_sort(found.path)

    def _on_sort_moved(self, keys: object) -> None:
        self._apply_sort_indicator()
        self.sort_changed.emit(keys)

    def _apply_sort_indicator(self) -> None:
        keys = self.control.sort
        first = next((key for key in keys if self.model.column_index_of(key.path) >= 0), None)
        for header in (self._header, self._frozen_header):
            if first is None:
                header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
                continue
            header.setSortIndicator(
                self.model.column_index_of(first.path),
                Qt.SortOrder.DescendingOrder if first.descending else Qt.SortOrder.AscendingOrder,
            )

    # --- the column menu ------------------------------------------------------------------

    def _open_column_menu(
        self, column: int, _point: QtCore.QPoint, header: _Header | None = None
    ) -> None:
        from ..primitives.dropdown_menu import DropdownMenu

        found = self.model.column_at(column)
        if found is None:
            return
        menu = DropdownMenu(header or self._header, side="bottom", align="start")
        menu.add_item(
            "Sort ascending",
            icon="arrow-up",
            disabled=not found.sortable,
            on_activate=lambda: self._apply_sort([SortSpec(path=found.path, descending=False)]),
        )
        menu.add_item(
            "Sort descending",
            icon="arrow-down",
            disabled=not found.sortable,
            on_activate=lambda: self._apply_sort([SortSpec(path=found.path, descending=True)]),
        )
        menu.add_item(
            "Clear sort",
            icon="arrow-up-down",
            disabled=self._sort_of(found.path) is None,
            on_activate=lambda: self._apply_sort([]),
        )
        menu.add_separator()
        menu.add_item("Hide column", icon="eye-off", on_activate=lambda: self.hide_column(found.path))
        pinned = found.path in self.pinned_columns
        menu.add_item(
            "Unpin" if pinned else "Pin left",
            icon="pin-off" if pinned else "arrow-left-to-line",
            on_activate=lambda: self.pin_column(found.path, not pinned),
        )
        self._menu = menu
        menu.open()

    def hide_column(self, path: str) -> None:
        """Drop one column and write the shorter list back through `columns_changed`."""
        kept = [column for column in self._columns if column.path != path]
        if len(kept) == len(self._columns):
            return
        self.set_columns(kept)
        self.columns_changed.emit(kept)

    # --- the column order -----------------------------------------------------------------

    def _on_reorder(self, carried: int, target: int) -> None:
        """A section dropped on another lands in front of it, as upstream's drop does."""
        moved = self.model.column_at(carried)
        onto = self.model.column_at(target)
        if moved is None or onto is None:
            return
        self.move_column(moved.path, onto.path)

    # --- the body -------------------------------------------------------------------------

    def _apply_columns(self) -> None:
        offset = self.model.select_offset
        drawn = self.model.columns
        self._sizing = True
        for header in (self._header, self._frozen_header):
            header.set_select_column(self._selectable)
            header.set_table_size(self._size)
            header.set_show_code(self._show_code)
            header.set_column_menu(self._column_menu)
            header.setMinimumSectionSize(MIN_COLUMN_WIDTH)
            if self._selectable:
                header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
                header.resizeSection(0, SELECT_WIDTH)
            for at, column in enumerate(drawn):
                header.resizeSection(at + offset, self._width_of(column))
        self._sizing = False
        pinned = self.pinned_columns
        for at, column in enumerate(drawn):
            self.frozen.setColumnHidden(at + offset, column.path not in pinned)
        if self._selectable:
            self.frozen.setColumnHidden(0, True)
        for view in (self.view, self.frozen):
            view.verticalHeader().setDefaultSectionSize(ENTITY_TABLE_ROW_HEIGHT[self._density])
        self.layout_frozen()

    def _width_of(self, column: CollectionColumn) -> int:
        """What a column stands at: what a drag left it at, else its own width, else the default."""
        return self._widths.get(column.path, column.width or DEFAULT_COLUMN_WIDTH)

    def _on_section_resized(self, at: int, _old: int, size: int) -> None:
        if self._sizing:
            return
        column = self.model.column_at(at)
        if column is not None:
            self._widths[column.path] = int(size)
        self.layout_frozen()

    def _apply_display(self) -> None:
        """Write the drawn order into the model, then put the header and the frozen view on it."""
        self.model.set_columns(self._display_columns())
        self._apply_columns()
        self._apply_spans()

    # --- the frozen column ----------------------------------------------------------------

    def body_scrolled(self) -> bool:
        """True while the body has run under the frozen column."""
        bar = self.view.horizontalScrollBar()
        return bar is not None and bar.value() > 0

    def repaint_body(self) -> None:
        """A row lights, a cursor moves or a value lands in both views at once."""
        self.view.viewport().update()
        if hasattr(self, "frozen"):
            self.frozen.viewport().update()

    def hovered_row(self) -> int:
        """The row under the pointer in either view, or -1."""
        if not hasattr(self, "frozen"):
            return self.view.hovered_row()
        return max(self.view.hovered_row(), self.frozen.hovered_row())

    def body_has_focus(self) -> bool:
        """True while the keyboard is in the body or in the frozen column."""
        return self.view.hasFocus() or (hasattr(self, "frozen") and self.frozen.hasFocus())

    def view_for(self, column: int) -> _Body:
        """The view that draws this column: the frozen one where it is pinned."""
        found = self.model.column_at(column)
        if found is not None and found.path in self.pinned_columns:
            return self.frozen
        return self.view

    def layout_frozen(self) -> None:
        """Stand the frozen view where a sticky cell would stand, and size it to its columns."""
        if not hasattr(self, "frozen"):
            return
        pinned = self.pinned_columns
        if not pinned:
            self.frozen.hide()
            self._pin_edge.hide()
            return
        offset = self.model.select_offset
        at = [i + offset for i, c in enumerate(self.model.columns) if c.path in pinned]
        width = sum(self._header.sectionSize(i) for i in at)
        # A sticky cell sits at its own place until the scroller would take it past the edge,
        # so the frozen view follows the first pinned section until that section reaches zero.
        left = max(0, self._header.sectionViewportPosition(at[0])) if at else 0
        left += self.view.viewport().x()
        self.frozen.setGeometry(left, 0, width, self.view.height())
        self._pin_edge.setGeometry(left + width, 0, PIN_SHADOW + 1, self.view.height())
        self.frozen.show()
        self.frozen.raise_()
        self._pin_edge.show()
        self._pin_edge.raise_()
        self._pin_edge.update()

    def _follow_body(self, value: int) -> None:
        bar = self.frozen.verticalScrollBar()
        if bar is not None and bar.value() != value:
            bar.setValue(value)

    def _follow_frozen(self, value: int) -> None:
        bar = self.view.verticalScrollBar()
        if bar is not None and bar.value() != value:
            bar.setValue(value)

    def _apply_spans(self) -> None:
        """A group heading is one cell across the table, so it is spanned after every reset."""
        width = max(1, self.model.columnCount())
        self.view.clearSpans()
        self.frozen.clearSpans()
        offset = self.model.select_offset
        pinned = self.pinned_columns
        # The frozen view shows the pinned columns alone, so a heading spans from the first of
        # them: a span that opens on a hidden column has no width to stand in.
        first = next(
            (i + offset for i, c in enumerate(self.model.columns) if c.path in pinned), -1
        )
        for at, line in enumerate(self.model.lines):
            if line.kind != "heading":
                continue
            self.view.setSpan(at, 0, 1, width)
            if first >= 0:
                self.frozen.setSpan(at, first, 1, width - first)

    def can_edit(self, column: CollectionColumn, row: EntityRow) -> bool:
        """True when this cell may open an editor. A projection is never writable."""
        if not self._editable or not column.editable or self.control.row_disabled(row):
            return False
        if self._editor_for is not None and self._editor_for(column.data_type) is not None:
            return True
        return is_editable_type(column.data_type)

    def edit_hint(self, index: QModelIndex) -> str:
        """`EDIT_HINT` on a cell that opens an editor, and nothing anywhere else."""
        line = self.model.line_at(index.row())
        if line is None or line.kind != "row" or line.row is None:
            return ""
        column = self.model.column_at(index.column())
        if column is None or not self.can_edit(column, line.row):
            return ""
        return EDIT_HINT

    def placement_for(self, column: CollectionColumn) -> str:
        """The column's own placement, then the table's, then the data type's."""
        if column.editor_placement is not None:
            return column.editor_placement
        if self._editor_placement is not None:
            return self._editor_placement
        return editor_placement_for(column.data_type)

    # --- interaction ----------------------------------------------------------------------

    def on_cell_pressed(self, index: QModelIndex) -> bool:
        """True when the press was the table's own: a heading, or the select column."""
        line = self.model.line_at(index.row())
        if line is None:
            return False
        if line.kind == "heading" and line.group is not None:
            self._toggle_group(line.group.key)
            return True
        if line.row is None:
            return False
        self._cursor = index
        if self.model.select_column and index.column() == 0:
            self.control.toggle(line.row)
            self.repaint_body()
            return True
        self.repaint_body()
        return False

    def on_cell_activated(self, index: QModelIndex) -> None:
        """A double-click: the editor where the cell edits, the row otherwise."""
        line = self.model.line_at(index.row())
        if line is None or line.row is None:
            return
        column = self.model.column_at(index.column())
        if column is not None and self.can_edit(column, line.row):
            self.open_editor(index)
            return
        self.row_activated.emit(line.row)

    def on_body_key(self, event: QtGui.QKeyEvent) -> bool:
        """The arrows walk one column of the body; Enter opens an editor or the row."""
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            return self._move_cursor(1 if key == Qt.Key.Key_Down else -1)
        if key == Qt.Key.Key_Space and self.model.select_column:
            line = self.model.line_at(self._cursor.row())
            if line is not None and line.row is not None:
                self.control.toggle(line.row)
                self.repaint_body()
                return True
            return False
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self._cursor.isValid():
                return False
            self.on_cell_activated(self._cursor)
            return True
        return False

    def _move_cursor(self, step: int) -> bool:
        rows = self.model.rows
        if not rows:
            return False
        column = self._cursor.column() if self._cursor.isValid() else self.model.select_offset
        at = self.model.row_index_of_line(self._cursor.row()) if self._cursor.isValid() else -1
        if at < 0:
            at = self.control.active
            if at < 0:
                return False
            self._focus_row(at, column)
            return True
        if step > 0 and self.control.ask_for_page(at + 1):
            return True
        self._focus_row(self.control.step_cursor(step, at), column)
        return True

    def _focus_row(self, index: int, column: int) -> None:
        line = self.model.line_of_row_index(index)
        if line < 0:
            return
        self.control.set_cursor(index)
        self._cursor = self.model.index(line, max(column, self.model.select_offset))
        self.view_for(self._cursor.column()).scrollTo(
            self._cursor, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible
        )
        self.repaint_body()

    def _toggle_group(self, key: str) -> None:
        state = toggle_collapsed(self._collapsed, key)
        drawn = [group.key for group in self.model.groups]
        shut = [entry for entry in drawn if is_collapsed(state, entry)]
        self._collapsed = collapse_state_from(state, shut, drawn)
        self.model.set_collapsed(self._collapsed)
        self.collapsed_changed.emit(self._collapsed)
        self._sync()

    def _on_scrolled(self, _value: int) -> None:
        bar = self.view.verticalScrollBar()
        if bar is None:
            return
        last = self.view.indexAt(self.view.viewport().rect().bottomLeft())
        line = last.row() if last.isValid() else self.model.rowCount() - 1
        self.control.on_last_visible(self.model.last_row_of_line(line))

    # --- the editor -----------------------------------------------------------------------

    def open_editor(self, index: QModelIndex) -> None:
        """Open the type's own editor in this cell, in place or in a popover."""
        line = self.model.line_at(index.row())
        column = self.model.column_at(index.column())
        if line is None or line.row is None or column is None:
            return
        row = line.row
        if not self.can_edit(column, row):
            return
        self.close_editor()
        self._cell_error = None
        value = cell_value(row, column.path)
        self._draft = value
        key = self.model.key_of(row)
        self._editing = (key, column.path)
        # A pinned cell is drawn by the frozen view, so its editor mounts there: one path, one
        # commit, wherever the cell stands.
        host = self.view_for(index.column())
        placement = self.placement_for(column)
        text = preferences_of(self._context)
        editor = FieldEditor(
            value=value,
            data_type=column.data_type,
            field=column.field,
            mode="edit",
            editable=True,
            editor_placement=placement,
            statuses=dict(self._statuses) if self._statuses else None,
            context=self._context,
            project_id=self._project_id,
            precision=self._precision,
            symbol=self._symbol,
            hours_per_day=text.hours_per_day,
            locale=text.locale,
            time_zone=text.time_zone,
            frame_rate=text.frame_rate,
            size="sm",
            parent=host,
        )
        editor.setObjectName("entity-table-editor")
        editor.value_changed.connect(self._on_draft)
        editor.mode_changed.connect(lambda mode: self._on_editor_mode(mode, key, column))
        editor.installEventFilter(self)
        host.setIndexWidget(index, editor)
        self.repaint_body()
        editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_draft(self, value: object) -> None:
        self._draft = value

    def _on_editor_mode(self, mode: str, key: str, column: CollectionColumn) -> None:
        """An editor that closed itself takes the cell with it, and commits what it holds.

        Escape and Cancel restore the value the session opened on before they report the
        close, so the commit they end on writes nothing; Save and Enter report the value
        that was typed. An editor left mounted after it went back to display would draw a
        dead half over the cell and refuse to open again.
        """
        if mode != "display" or not self.is_editing(key, column.path):
            return
        self.commit(key, column, self._draft)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if event.type() == QtCore.QEvent.Type.KeyPress and self._editing is not None:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                held = self._editing
                column = next((c for c in self._columns if c.path == held[1]), None)
                if column is not None:
                    self.commit(held[0], column, self._draft)
                return True
            if key == Qt.Key.Key_Escape:
                self.close_editor()
                return True
        return super().eventFilter(watched, event)

    def is_editing(self, key: str, path: str) -> bool:
        """True while an editor is mounted on that cell."""
        return self._editing == (key, path)

    def close_editor(self) -> None:
        """Take the editor off the cell without writing."""
        held = self._editing
        self._editing = None
        if held is None:
            return
        index = self._index_of(held[0], held[1])
        if index.isValid():
            host = self.view_for(index.column())
            editor = host.indexWidget(index)
            host.setIndexWidget(index, None)
            if editor is not None:
                editor.deleteLater()
            host.setFocus(Qt.FocusReason.OtherFocusReason)
        self.repaint_body()

    def commit(self, key: str, column: CollectionColumn, value: Any) -> None:
        """Write one field through the source, which re-reads the row (024_read_after_write)."""
        at = self.model.index_of_key(key)
        row = self.model.row_at(at)
        self.close_editor()
        if row is None:
            return
        if value == cell_value(row, column.path):
            return
        self._cell_error = None

        def done(answer: object) -> None:
            if isinstance(answer, BaseException):
                # The write is refused, so the cell goes back to what the row still holds and
                # says why beside it.
                self._cell_error = (key, column.path, error_text(answer))
            self._sync()

        self.control.binding.update_row(
            EntityRef(type=row.type, id=row.id), {column.path: value}, done
        )

    def _index_of(self, key: str, path: str) -> QModelIndex:
        at = self.model.index_of_key(key)
        line = self.model.line_of_row_index(at)
        column = self.model.column_index_of(path)
        if line < 0 or column < 0:
            return QModelIndex()
        return self.model.index(line, column)

    # --- drawing --------------------------------------------------------------------------

    def _on_selection(self, rows: object) -> None:
        """Keep the header's box on the selection, then report it.

        `_sync` runs on a snapshot, and taking a row moves no snapshot: without this the
        header's tri state is whatever the last read left, so the box never draws itself
        full and the press that should clear the selection takes it again.
        """
        self._header.set_check_state(
            self.control.all_selected.all, self.control.all_selected.some
        )
        self.repaint_body()
        self.selection_changed.emit(rows)

    def _sync(self) -> None:
        state = self.control.snapshot()
        # The mark follows the sort the source holds, however it got there: a header click, the
        # column menu, or a `sort` prop a toolbar's SortPicker writes.
        self._apply_sort_indicator()
        view = self.control.view(len(self.model.lines))
        # The header stands through a read, so the view keeps its place and the blank rows
        # take the body's room under it.
        self.view.setVisible(view in ("rows", "loading"))
        self.layout_frozen()
        self._skeleton.setVisible(view == "loading")
        self._state.setVisible(view in ("empty", "error"))
        if view == "empty":
            self._state.set_icon(EMPTY_ICON)
            self._state.apply_state("empty", self.control.labels)
        elif view == "error":
            self._state.set_icon(ERROR_ICON)
            self._state.apply_state(
                "error", self.control.labels, None if state.error is None else str(state.error)
            )
        self._bottom.apply(
            self.control.bottom(),
            state_line("error", self.control.labels, None if state.error is None else str(state.error)),
            self.control.loading_text,
        )
        self._header.set_check_state(
            self.control.all_selected.all, self.control.all_selected.some
        )
        self.footer.set_pager(self.control.pager)
        self.footer.set_loading(state.status == "loading")
        waiting = self.control.take_pending_cursor()
        if waiting >= 0:
            self._focus_row(waiting, self._cursor.column())
        self._apply_spans()
        self._fit()
        self.repaint_body()

    def _fit(self) -> None:
        head = ENTITY_TABLE_HEAD[self._size]
        step = ENTITY_TABLE_ROW_HEIGHT[self._density]
        lines = len(self.model.lines)
        if lines:
            self._held_body = min(head + lines * step, self._max_height)
        if self._skeleton.isVisible():
            # A re-read keeps the box the rows stood in, so nothing under the table moves while
            # it reads. A cold load has no box to keep and draws upstream's eight rows.
            room = self._held_body - head if self._held_body else SKELETON_ROWS * step
            rows = max(1, -(-room // step))
            self._skeleton.set_shape(rows, max(1, self.model.columnCount()), step, room)
            self._skeleton.set_lanes(self._lanes())
            fit_body(self.view, head, self._max_height)
        else:
            fit_body(self.view, head + lines * step, self._max_height)
        self.layout_frozen()

    def _lanes(self) -> list[tuple[int, int]]:
        """Where each column stands in the body, which is where a blank row's bars stand."""
        header = self._header
        return [
            (header.sectionViewportPosition(at), header.sectionSize(at))
            for at in range(self.model.columnCount())
        ]


class SkeletonBlock(QtWidgets.QWidget):
    """A block of skeletons that only shimmers while it is on show.

    Motion explains a change (`docs/design-rules.md` rule 4), and a block standing behind rows
    that have already landed explains nothing: the shimmer stops with the block rather than
    running on a widget nobody is looking at.
    """

    def blocks(self) -> list[Skeleton]:
        """Every skeleton in this block."""
        return self.findChildren(Skeleton)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        for block in self.blocks():
            block.set_animated(True)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:  # noqa: N802
        super().hideEvent(event)
        for block in self.blocks():
            block.set_animated(False)


class _TableSkeleton(SkeletonBlock):
    """A table of blank rows: one bar per cell, at the row height and the column widths.

    A skeleton stands in for what it replaces (rule 4), so the read leaves the header where it
    is and puts one `h-6 w-full` bar in every cell, which is what upstream draws. The bars are
    laid out against the header's own sections rather than by a layout, so a column that was
    dragged wider keeps its width through a re-read.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-table-loading")
        self.setAccessibleName("Loading…")
        self._bars: list[list[Skeleton]] = []
        self._row_height = ENTITY_TABLE_ROW_HEIGHT["default"]
        self._lanes: list[tuple[int, int]] = []

    @property
    def rows(self) -> int:
        """How many blank rows stand here."""
        return len(self._bars)

    def set_shape(self, rows: int, columns: int, row_height: int, height: int | None = None) -> None:
        """Hold `rows` blank rows of `columns` bars each, at that row height.

        `height` is the room the block stands in, which a view's own ceiling may cut short of a
        whole row: the last blank row is then clipped as the view clips its last row.
        """
        self._row_height = max(1, int(row_height))
        while len(self._bars) > rows:
            for bar in self._bars.pop():
                bar.setParent(None)
                bar.deleteLater()
        while len(self._bars) < rows:
            self._bars.append([])
        for line in self._bars:
            while len(line) > columns:
                bar = line.pop()
                bar.setParent(None)
                bar.deleteLater()
            while len(line) < columns:
                bar = Skeleton(height=SKELETON_HEIGHT, parent=self)
                bar.set_animated(self.isVisible())
                bar.show()
                line.append(bar)
        self.setFixedHeight(rows * self._row_height if height is None else max(0, int(height)))
        self._place()

    def set_lanes(self, lanes: Sequence[tuple[int, int]]) -> None:
        """Where the columns stand, as the header has them: an (x, width) per column."""
        self._lanes = [(int(x), int(width)) for x, width in lanes]
        self._place()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place()

    def _place(self) -> None:
        top = 0
        inset = (self._row_height - SKELETON_HEIGHT) // 2
        for line in self._bars:
            for at, bar in enumerate(line):
                x, width = self._lanes[at] if at < len(self._lanes) else (0, self.width())
                bar.setGeometry(
                    x + CELL_PAD_X, top + inset, max(1, width - 2 * CELL_PAD_X), SKELETON_HEIGHT
                )
            top += self._row_height

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        """The rule under every row, so the blank rows read as rows and not as one block."""
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), theme.color("background"))
        for line in range(len(self._bars)):
            bottom = (line + 1) * self._row_height - 1
            painter.fillRect(QRect(0, bottom, self.width(), 1), theme.color("border"))
        painter.end()


class _BottomBlock(SkeletonBlock):
    """What sits under the last row: a failed page, a page on the way, a load-more row, a sentinel."""

    retry_requested = Signal()
    more_requested = Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-table-bottom")
        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, BOTTOM_PAD, 0, BOTTOM_PAD)
        line.setSpacing(COLLECTION_GAP)
        self._error = StateLine(
            state="error", pad="none", slot_name="entity-table-page-error", parent=self
        )
        self._error.set_icon(ERROR_ICON)
        self._error.hide()
        line.addWidget(self._error, 1)
        self._retry = Button("Retry", variant="outline", size="sm", parent=self)
        self._retry.clicked.connect(self.retry_requested.emit)
        self._retry.hide()
        line.addWidget(self._retry)
        self._loading = Skeleton(height=16, parent=self)
        self._loading.setObjectName("entity-table-loading-more")
        self._loading.set_animated(False)
        self._loading.hide()
        line.addWidget(self._loading, 1)
        self._more = Button("Load more", variant="outline", size="sm", parent=self)
        self._more.clicked.connect(self.more_requested.emit)
        self._more.hide()
        line.addWidget(self._more)
        self._sentinel = QtWidgets.QWidget(self)
        self._sentinel.setObjectName("entity-table-sentinel")
        self._sentinel.setFixedHeight(4)
        self._sentinel.hide()
        line.addWidget(self._sentinel, 1)

    def apply(self, bottom: str | None, error: str, loading: str) -> None:
        self._error.setVisible(bottom == "error")
        self._retry.setVisible(bottom == "error")
        self._loading.setVisible(bottom == "loading")
        self._loading.set_animated(bottom == "loading")
        self._more.setVisible(bottom == "more")
        self._sentinel.setVisible(bottom == "sentinel")
        if bottom == "error":
            self._error.set_label(error)
        self._loading.setAccessibleName(loading)
        self.setVisible(bottom is not None)
