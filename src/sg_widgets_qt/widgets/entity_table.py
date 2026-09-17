"""A page of rows, one column per field path.

Ported from `packages/react/src/registry/sg/components/entity-table.tsx`.

Columns are schema-driven: the header is the field's display name and the cell drawing comes
from its `data_type` through `paint_field_value`. Sizing, resizing, grouping and the selection
are the view's; sorting and paging are the server's, because a sort applied to one loaded page
would order the page and not the set, and because a sort on a field that cannot be sorted is a
silent 200 no-op (026_result_order).

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
from ..primitives.base import elide
from ..primitives.button import Button
from ..primitives.roles import Roles
from ..primitives.skeleton import Skeleton
from ..primitives.table import CELL_PAD_X, CellDelegate, HeaderDelegate, TableSurface
from ..theme import Theme, theme_of, with_alpha
from .collection_control import COLLECTION_GAP, CollectionControl, CollectionModel
from .collection_footer import DEFAULT_PAGE_SIZES, CollectionFooter
from .field_editor import FieldEditor
from .field_value import FieldValueOptions, paint_field_value
from .state_line import StateLine

__all__ = [
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

#: The rows the scroller leaves before it asks for the next page. Core's `SCROLL_THRESHOLD`.
BOTTOM_PAD = 8

#: Height of the scrolling body, upstream's `28rem` in pixels.
DEFAULT_MAX_HEIGHT = 448

#: What the empty and error blocks are drawn with.
EMPTY_ICON = "inbox"
ERROR_ICON = "circle-alert"


def _pad_y(density: str) -> int:
    return 4 if density == "compact" else 8


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

    def __init__(self, parent: QtWidgets.QWidget | None = None, density: str = "default") -> None:
        super().__init__(parent, density=density)
        self._size = "md"
        self._show_code = False
        self._menu = False
        self._select = False
        self._all = False
        self._some = False

    def set_table_size(self, value: str) -> None:
        self._size = value if value in ENTITY_TABLE_SIZE_VALUES else "md"
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
            self._paint_code(painter, rect, column, theme)
            return
        painter.save()
        painter.fillRect(body.adjusted(0, 0, 0, -1), theme.color("background"))
        glyph = QRect(0, 0, CHEVRON, CHEVRON)
        glyph.moveCenter(body.center())
        icons.paint_icon(painter, glyph, "ellipsis-vertical", theme.color("muted_foreground"))
        painter.fillRect(QRect(body.left(), body.bottom(), body.width(), 1), theme.color("border"))
        painter.restore()

    def _paint_code(self, painter: QtGui.QPainter, rect: QRect, column: int, theme: Theme) -> None:
        """The programmatic path beside the display name, in the mono family (rule 6)."""
        model = self.model()
        if not self._show_code or model is None:
            return
        path = str(model.headerData(column, Qt.Orientation.Horizontal, Roles.CODE) or "")
        label = str(
            model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or ""
        )
        if not path or path == label:
            return
        font = theme.font(12)
        font.setFamily(theme.font_mono)
        metrics = QtGui.QFontMetrics(font)
        painter.save()
        painter.setFont(font)
        painter.setPen(theme.color("muted_foreground"))
        box = QRect(rect.left() + CELL_PAD_X, rect.top(), max(0, rect.width() - 2 * CELL_PAD_X), rect.height())
        painter.drawText(
            box,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            elide(metrics, path, box.width()),
        )
        painter.restore()

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
        super().mousePressEvent(event)


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
        hovered = self._table.view.hovered_row() == index.row()
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
        if self._table.cursor_index() == index and self._table.view.hasFocus():
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
        count_width = QtGui.QFontMetrics(mono).horizontalAdvance(count) + 8
        box = QRect(left, rect.top(), max(0, rect.width() - left - CELL_PAD_X - count_width), rect.height())
        column = self._table.group_column()
        paint_field_value(
            painter,
            box,
            group.value,
            column if column is not None else "text",
            self._table.value_options(),
        )
        painter.save()
        painter.setFont(mono)
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            QRect(box.right() + 1, rect.top(), count_width, rect.height()),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
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
        self.setObjectName("entity-table-scroll")
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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
        bar.addWidget(self._toolbar_start)
        bar.addStretch(1)
        self._toolbar_end = QtWidgets.QWidget(self._toolbar)
        self._toolbar_end.setObjectName("entity-table-toolbar-end")
        end = QtWidgets.QHBoxLayout(self._toolbar_end)
        end.setContentsMargins(0, 0, 0, 0)
        end.setSpacing(COLLECTION_GAP)
        bar.addWidget(self._toolbar_end)
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
        self._cells = _Cells(self, density=self._density)
        self.view.setItemDelegate(self._cells)
        self.view.setModel(self.model)
        self.view.setMaximumHeight(_px(max_height))
        body.addWidget(self.view)

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
        self.control.selection_changed.connect(self.selection_changed.emit)
        self.control.sort_changed.connect(self._on_sort_moved)
        self.control.filters_changed.connect(self.filters_changed.emit)
        self.control.failed.connect(self.failed.emit)
        self.model.modelReset.connect(self._apply_spans)
        bar_ = self.view.verticalScrollBar()
        if bar_ is not None:
            bar_.valueChanged.connect(self._on_scrolled)
        self._apply_columns()
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
        self.model.set_columns(self._columns)
        self._apply_columns()
        self._apply_sort_indicator()
        self._sync()

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
        self.view.set_density(self._density)
        self._header.set_density(self._density)
        self._cells.set_density(self._density)
        self.view.verticalHeader().setDefaultSectionSize(ENTITY_TABLE_ROW_HEIGHT[self._density])
        self.view.viewport().update()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the row text and the head it sits under."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in ENTITY_TABLE_SIZE_VALUES else "md"
        self._header.set_table_size(self._size)
        self.view.viewport().update()

    @property
    def selectable(self) -> bool:
        """Draws a checkbox column and reports the selection."""
        return self._selectable

    def set_selectable(self, value: bool) -> None:
        self._selectable = bool(value)
        self.model.set_select_column(self._selectable)
        self._header.set_select_column(self._selectable)
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

    @property
    def column_menu(self) -> bool:
        """A menu on every header: sort and hide."""
        return self._column_menu

    def set_column_menu(self, value: bool) -> None:
        self._column_menu = bool(value)
        self._header.set_column_menu(self._column_menu)

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
        return self.view.maximumHeight()

    def set_max_height(self, value: int | str) -> None:
        self.view.setMaximumHeight(_px(value))

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
        self.control.set_sort(wanted)

    def _lead_sort(self) -> None:
        """A group is only whole when the server put its rows together, so the path leads the sort."""
        if not self._group_by:
            return
        keys = self.control.sort
        if keys and keys[0].path == self._group_by:
            return
        self.control.set_sort(
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
        if first is None:
            self._header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            return
        self._header.setSortIndicator(
            self.model.column_index_of(first.path),
            Qt.SortOrder.DescendingOrder if first.descending else Qt.SortOrder.AscendingOrder,
        )

    # --- the column menu ------------------------------------------------------------------

    def _open_column_menu(self, column: int, _point: QtCore.QPoint) -> None:
        from ..primitives.dropdown_menu import DropdownMenu

        found = self.model.column_at(column)
        if found is None:
            return
        menu = DropdownMenu(self._header, side="bottom", align="start")
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
        self._menu = menu
        menu.open()

    def hide_column(self, path: str) -> None:
        """Drop one column and write the shorter list back through `columns_changed`."""
        kept = [column for column in self._columns if column.path != path]
        if len(kept) == len(self._columns):
            return
        self.set_columns(kept)
        self.columns_changed.emit(kept)

    # --- the body -------------------------------------------------------------------------

    def _apply_columns(self) -> None:
        header = self._header
        header.set_select_column(self._selectable)
        header.set_table_size(self._size)
        header.set_show_code(self._show_code)
        header.set_column_menu(self._column_menu)
        header.setMinimumSectionSize(MIN_COLUMN_WIDTH)
        offset = self.model.select_offset
        if self._selectable:
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
            header.resizeSection(0, SELECT_WIDTH)
        for at, column in enumerate(self._columns):
            header.resizeSection(at + offset, column.width or DEFAULT_COLUMN_WIDTH)
        self.view.verticalHeader().setDefaultSectionSize(ENTITY_TABLE_ROW_HEIGHT[self._density])

    def _apply_spans(self) -> None:
        """A group heading is one cell across the table, so it is spanned after every reset."""
        self.view.clearSpans()
        width = max(1, self.model.columnCount())
        for at, line in enumerate(self.model.lines):
            if line.kind == "heading":
                self.view.setSpan(at, 0, 1, width)

    def can_edit(self, column: CollectionColumn, row: EntityRow) -> bool:
        """True when this cell may open an editor. A projection is never writable."""
        if not self._editable or not column.editable or self.control.row_disabled(row):
            return False
        if self._editor_for is not None and self._editor_for(column.data_type) is not None:
            return True
        return is_editable_type(column.data_type)

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
            self.view.viewport().update()
            return True
        self.view.viewport().update()
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
                self.view.viewport().update()
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
        self.view.scrollTo(self._cursor, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)
        self.view.viewport().update()

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
            parent=self.view,
        )
        editor.setObjectName("entity-table-editor")
        editor.value_changed.connect(self._on_draft)
        editor.mode_changed.connect(lambda mode: self._on_editor_mode(mode, key, column))
        editor.installEventFilter(self)
        self.view.setIndexWidget(index, editor)
        editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_draft(self, value: object) -> None:
        self._draft = value

    def _on_editor_mode(self, mode: str, key: str, column: CollectionColumn) -> None:
        """A popover editor drives its own close and reports it; the cell commits what it holds."""
        if mode != "display" or self.placement_for(column) != "popover":
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

    def close_editor(self) -> None:
        """Take the editor off the cell without writing."""
        held = self._editing
        self._editing = None
        if held is None:
            return
        index = self._index_of(held[0], held[1])
        if index.isValid():
            editor = self.view.indexWidget(index)
            self.view.setIndexWidget(index, None)
            if editor is not None:
                editor.deleteLater()
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)

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

    def _sync(self) -> None:
        state = self.control.snapshot()
        view = self.control.view(len(self.model.lines))
        self.view.setVisible(view == "rows")
        self._skeleton.setVisible(view == "loading")
        self._skeleton.set_columns(max(1, self.model.columnCount()))
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
        self.view.viewport().update()


class _TableSkeleton(QtWidgets.QWidget):
    """Eight rows of the shape they stand in for: the same inset, the same height, no gap."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-table-loading")
        self.setAccessibleName("Loading…")
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(CELL_PAD_X)
        self._grid.setVerticalSpacing(0)
        self._count = 0
        self.set_columns(1)

    def set_columns(self, count: int) -> None:
        if count == self._count:
            return
        self._count = count
        while self._grid.count():
            item = self._grid.takeAt(0)
            made = item.widget()
            if made is not None:
                made.setParent(None)
                made.deleteLater()
        for line in range(SKELETON_ROWS):
            for column in range(count):
                self._grid.addWidget(Skeleton(height=SKELETON_HEIGHT, parent=self), line, column)


class _BottomBlock(QtWidgets.QWidget):
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
        self._more.setVisible(bottom == "more")
        self._sentinel.setVisible(bottom == "sentinel")
        if bottom == "error":
            self._error.set_label(error)
        self._loading.setAccessibleName(loading)
        self.setVisible(bottom is not None)
