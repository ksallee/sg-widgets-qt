"""Rows as EntityCard tiles.

Ported from `packages/react/src/registry/sg/components/entity-grid.tsx`.

The tile is the card's own `tile` face, so a grid cell and a card show the same row the same
way: the thumbnail, the status over it, the name, and one metadata line from the row-anatomy
props. A Version with media carries the play overlay, and a row with no picture, one still
transcoding and one ready all render, the value of an `image` field being the only state marker
there is (field_types/image).

The grid owns the layout and the cursor: one tab stop moves into the tiles, the arrows walk
them, and Space selects where Enter opens.

`paging` says how the set is walked and the source follows it. In `scroll` reaching the end of
the body asks for the next page, in `more` a row under the tiles does, and paging stops on a
short page, never on a missing `links.next`, which the API emits forever (006_pagination). In
`pages` the footer walks the set with an explicit page number and reads "n to m of N" once
`_summarize` has counted it (020_summarize).

    grid = EntityGrid(source=source, context=context, secondary_field=artist)
    grid.selected.connect(open_it)
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, QSize, Qt, Signal

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import (
    CollectionColumn,
    EntitySource,
    SortSpec,
    SourceFilters,
    cell_value,
    resolve_columns,
    to_column,
)
from sg_widgets_core.collection_state import RowDisabledFn, RowIdFn
from sg_widgets_core.context import SgContext, preferences_of
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.render import field_text, image_state, is_empty_value
from sg_widgets_core.row import FieldSpec, path_of
from sg_widgets_core.schema import display_name_of, status_field_for
from sg_widgets_core.state import NO_ROWS_LABEL, StateLabels
from sg_widgets_core.status import StatusRecord

from ..primitives.roles import Roles
from ..primitives.scrollbar import install_overlay_scrollbars
from ..primitives.skeleton import Skeleton
from ..theme import theme_of
from ..workers import Ticket
from .collection_control import COLLECTION_GAP, CollectionControl, CollectionModel
from .collection_footer import DEFAULT_PAGE_SIZES, CollectionFooter
from .entity_card import (
    CARD_TILE_WIDTH,
    CardTile,
    CardTileOptions,
    card_tile_checkbox_rect,
    card_tile_size,
    paint_card_tile,
)
from .entity_table import EMPTY_ICON, ERROR_ICON, _BottomBlock, _px, fit_body
from .state_line import StateLine

__all__ = [
    "ENTITY_GRID_DENSITY_VALUES",
    "ENTITY_GRID_GAP",
    "ENTITY_GRID_SIZE_VALUES",
    "EntityGrid",
]

ENTITY_GRID_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")
ENTITY_GRID_DENSITY_VALUES: tuple[str, ...] = ("compact", "default")

#: The gap between tiles; compact halves it, as it halves a row's padding elsewhere.
ENTITY_GRID_GAP: dict[str, int] = {"compact": 6, "default": 12}

#: The inset the grid's own box takes around its tiles.
GRID_PAD = 12

#: Tiles a first read stands behind.
SKELETON_TILES = 8

#: Height of the scrolling body, upstream's `32rem` in pixels.
DEFAULT_MAX_HEIGHT = 512

#: The field names a row's status is read from, the two the API uses.
STATUS_FIELDS: tuple[str, ...] = ("sg_status_list", "sg_status")


class _TileDelegate(QtWidgets.QStyledItemDelegate):
    """One grid cell: the shared tile face, and the ring the cursor wears."""

    def __init__(self, grid: EntityGrid) -> None:
        super().__init__(grid.view)
        self._grid = grid

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return card_tile_size(self._grid.size)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        row = index.data(Roles.ENTITY)
        if not isinstance(row, EntityRow):
            return
        disabled = bool(index.data(Roles.DISABLED))
        tile = self._grid.tile_of(row)
        paint_card_tile(
            painter,
            option.rect,
            tile,
            CardTileOptions(
                theme=theme_of(self._grid.view),
                size=self._grid.size,
                statuses=self._grid.statuses,
                site_url=self._grid.site_url,
                selectable=self._grid.selectable,
                selected=bool(index.data(Roles.CHECKED)),
                enabled=not disabled,
                on_ready=self._grid.view.viewport().update,
            ),
        )
        # The ring is the keyboard cursor's, so it is drawn only while the view holds focus.
        if self._grid.view.hasFocus() and self._grid.view.currentIndex() == index:
            theme = theme_of(self._grid.view)
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(theme.color("ring"), 2.0))
            painter.drawRoundedRect(
                QtCore.QRectF(option.rect).adjusted(1, 1, -1, -1),
                theme.radius_px("lg"),
                theme.radius_px("lg"),
            )
            painter.restore()


class _GridView(QtWidgets.QListView):
    """The flow of fixed-width tiles: our scrollbars, our delegate, the grid's own keys."""

    def __init__(self, grid: EntityGrid) -> None:
        self._grid = grid
        super().__init__(grid)
        self.setObjectName("entity-grid-list")
        self.setFrameShape(QtWidgets.QListView.Shape.NoFrame)
        self.setViewMode(QtWidgets.QListView.ViewMode.IconMode)
        self.setFlow(QtWidgets.QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setMovement(QtWidgets.QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        install_overlay_scrollbars(self)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(point)
        if index.isValid():
            self.setCurrentIndex(index)
            self._grid.on_tile_pressed(index, point)
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(point)
        if index.isValid():
            self._grid.activate(index.row())
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._grid.on_key(event):
            return
        super().keyPressEvent(event)

    def columns_across(self) -> int:
        """Tiles a line holds, at the width the view has."""
        step = self.gridSize().width()
        if step <= 0:
            return 1
        return max(1, self.viewport().width() // step)


class EntityGrid(QtWidgets.QWidget):
    """Rows as tiles, in a flow of fixed widths, with the cursor and the paging of a collection."""

    #: A tile was opened. Carries the `EntityRow`.
    selected = Signal(object)
    #: The selected rows. Carries `list[EntityRef]`.
    selection_changed = Signal(object)
    #: The source's sort moved. Carries `list[SortSpec]`.
    sort_changed = Signal(object)
    #: The source's filter moved. Carries the wire group, or None.
    filters_changed = Signal(object)
    #: A read or a count raised. Carries the exception.
    failed = Signal(object)

    def __init__(
        self,
        source: EntitySource,
        context: SgContext | None = None,
        thumbnail: str | bool = "image",
        label_field: str | None = None,
        sub_label_field: FieldSpec | None = None,
        sub_label: Callable[[EntityRow], str] | None = None,
        secondary_field: FieldSpec | None = None,
        secondary: Callable[[EntityRow], str] | None = None,
        show_code: bool = False,
        statuses: Mapping[str, StatusRecord] | None = None,
        size: str = "md",
        density: str = "default",
        selectable: bool = False,
        selection: Sequence[EntityRef] | None = None,
        get_row_id: RowIdFn | None = None,
        is_row_disabled: RowDisabledFn | None = None,
        sort: Sequence[SortSpec] | None = None,
        filters: SourceFilters = None,
        page_sizes: Sequence[int] = DEFAULT_PAGE_SIZES,
        paging: str = "scroll",
        max_height: int | str = DEFAULT_MAX_HEIGHT,
        virtualize_after: int = 100,
        empty_label: str = NO_ROWS_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        site_url: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-grid")
        self._context = context
        self._thumbnail = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._statuses = statuses
        self._size = size if size in ENTITY_GRID_SIZE_VALUES else "md"
        self._density = density if density in ENTITY_GRID_DENSITY_VALUES else "default"
        self._selectable = bool(selectable)
        self._virtualize_after = int(virtualize_after)
        self._site_url = site_url
        self._status_field: Any = None
        self._resolved: dict[str, CollectionColumn] = {}
        self._ticket = Ticket()

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

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(COLLECTION_GAP)

        self._header = QtWidgets.QWidget(self)
        self._header.setObjectName("entity-grid-header")
        head = QtWidgets.QHBoxLayout(self._header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(COLLECTION_GAP)
        self._header.hide()
        column.addWidget(self._header)

        self._box = QtWidgets.QWidget(self)
        self._box.setObjectName("entity-grid-scroll")
        body = QtWidgets.QVBoxLayout(self._box)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.view = _GridView(self)
        self._delegate = _TileDelegate(self)
        self.view.setItemDelegate(self._delegate)
        self.view.setModel(self.model)
        self._max_height = _px(max_height)
        self.view.setMaximumHeight(self._max_height)
        body.addWidget(self.view)
        self._state = StateLine(pad="table", slot_name="entity-grid-state", parent=self._box)
        self._state.hide()
        body.addWidget(self._state)
        self._skeleton = _GridSkeleton(self._box)
        self._skeleton.hide()
        body.addWidget(self._skeleton)
        self._bottom = _BottomBlock(self._box)
        self._bottom.setObjectName("entity-grid-bottom")
        self._bottom.retry_requested.connect(self.control.retry)
        self._bottom.more_requested.connect(self.control.load_more)
        self._bottom.hide()
        body.addWidget(self._bottom)
        column.addWidget(self._box)

        self.footer = CollectionFooter(
            self.control.binding, page_sizes=page_sizes, slot_name="entity-grid", parent=self
        )
        column.addWidget(self.footer)

        self._footer_region = QtWidgets.QWidget(self)
        self._footer_region.setObjectName("entity-grid-footer-region")
        region = QtWidgets.QHBoxLayout(self._footer_region)
        region.setContentsMargins(0, 0, 0, 0)
        region.setSpacing(COLLECTION_GAP)
        self._footer_region.hide()
        column.addWidget(self._footer_region)

        self.control.changed.connect(self._sync)
        self.control.selection_changed.connect(self.selection_changed.emit)
        self.control.sort_changed.connect(self.sort_changed.emit)
        self.control.filters_changed.connect(self.filters_changed.emit)
        self.control.failed.connect(self.failed.emit)
        bar = self.view.verticalScrollBar()
        if bar is not None:
            bar.valueChanged.connect(self._on_scrolled)
        self._apply_grid()
        self._read_status_field()
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
    def context(self) -> SgContext | None:
        """The widget context. Every tile reads its schema and its links through it."""
        return self._context

    def set_context(self, value: SgContext | None) -> None:
        self._context = value
        self._read_status_field()
        self.view.viewport().update()

    @property
    def thumbnail(self) -> str | bool:
        """Field holding the thumbnail URL. False leaves every tile on the placeholder."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self.view.viewport().update()

    @property
    def label_field(self) -> str | None:
        """Field shown as the tile's name. Defaults to the type's own display name."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self.view.viewport().update()

    @property
    def sub_label_field(self) -> FieldSpec | None:
        """The left of the tile's metadata line."""
        return self._sub_label_field

    def set_sub_label_field(self, value: FieldSpec | None) -> None:
        self._sub_label_field = value
        self.view.viewport().update()

    @property
    def sub_label(self) -> Callable[[EntityRow], str] | None:
        """The caller's own sub-label. Wins over `sub_label_field`."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[EntityRow], str] | None) -> None:
        self._sub_label = value
        self.view.viewport().update()

    @property
    def secondary_field(self) -> FieldSpec | None:
        """The right of the tile's metadata line."""
        return self._secondary_field

    def set_secondary_field(self, value: FieldSpec | None) -> None:
        self._secondary_field = value
        self.view.viewport().update()

    @property
    def secondary(self) -> Callable[[EntityRow], str] | None:
        """The caller's own text on the right of the metadata line."""
        return self._secondary

    def set_secondary(self, value: Callable[[EntityRow], str] | None) -> None:
        self._secondary = value
        self.view.viewport().update()

    @property
    def show_code(self) -> bool:
        """Show the row's `code` beside the name when the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self.view.viewport().update()

    @property
    def statuses(self) -> Mapping[str, StatusRecord] | None:
        """`Status` rows by code, for the badge (probe 010)."""
        return self._statuses

    def set_statuses(self, value: Mapping[str, StatusRecord] | None) -> None:
        self._statuses = value
        self.view.viewport().update()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the tile width, 160, 224 or 288 pixels."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in ENTITY_GRID_SIZE_VALUES else "md"
        self._apply_grid()

    @property
    def density(self) -> str:
        """`compact` halves the gap between tiles."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value if value in ENTITY_GRID_DENSITY_VALUES else "default"
        self._apply_grid()

    @property
    def selectable(self) -> bool:
        """Draws a checkbox on each tile."""
        return self._selectable

    def set_selectable(self, value: bool) -> None:
        self._selectable = bool(value)
        self.view.viewport().update()

    @property
    def selection(self) -> list[EntityRef]:
        return self.control.selection

    def set_selection(self, value: Sequence[EntityRef]) -> None:
        self.control.set_selection(value)
        self.view.viewport().update()

    def set_get_row_id(self, fn: RowIdFn | None) -> None:
        self.control.set_get_row_id(fn)

    def set_is_row_disabled(self, fn: RowDisabledFn | None) -> None:
        self.control.set_is_row_disabled(fn)

    @property
    def sort(self) -> list[SortSpec]:
        return self.control.sort

    def set_sort(self, value: Sequence[SortSpec] | None) -> None:
        self.control.set_sort(value)

    @property
    def filters(self) -> SourceFilters:
        return self.control.filters

    def set_filters(self, value: SourceFilters) -> None:
        self.control.set_filters(value)

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
        """Kept for parity. A `QListView` draws only the tiles on screen at any length."""
        return self._virtualize_after

    def set_virtualize_after(self, value: int) -> None:
        self._virtualize_after = int(value)

    @property
    def empty_label(self) -> str:
        return self.control.labels.empty_label or NO_ROWS_LABEL

    def set_empty_label(self, value: str) -> None:
        labels = self.control.labels
        self.control.set_labels(
            StateLabels(
                empty_label=value,
                loading_label=labels.loading_label,
                error_label=labels.error_label,
            )
        )
        self._sync()

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

    @property
    def site_url(self) -> str:
        """The site a status sprite is served from. Defaults to the context's."""
        return self._site_url or (self._context.site_url if self._context is not None else "")

    def set_site_url(self, value: str) -> None:
        self._site_url = value
        self.view.viewport().update()

    # --- the regions ----------------------------------------------------------------------

    def set_header(self, *widgets: QtWidgets.QWidget) -> None:
        """The region above the grid, where a sort picker or a filter bar goes."""
        self._fill(self._header, widgets)

    def set_footer(self, *widgets: QtWidgets.QWidget) -> None:
        """The region below the footer."""
        self._fill(self._footer_region, widgets)

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
        holder.setVisible(layout.count() > 0)

    # --- the tile -------------------------------------------------------------------------

    def tile_of(self, row: EntityRow) -> CardTile:
        """One row as the tile face reads it."""
        name = (
            str(cell_value(row, self._label_field) or "")
            if self._label_field
            else display_name_of(row.values, f"{row.type} #{row.id}")
        )
        code = ""
        if self._show_code:
            raw = cell_value(row, "code")
            code = raw if isinstance(raw, str) and raw and raw != name else ""
        picture = None
        if self._thumbnail is not False:
            raw = cell_value(row, str(self._thumbnail))
            picture = raw if isinstance(raw, str) and raw else None
        status = ""
        for field in STATUS_FIELDS:
            value = row.values.get(field)
            if isinstance(value, str) and value:
                status = value
                break
        return CardTile(
            name=name,
            code=code,
            sub_label=self._side(row, self._sub_label, self._sub_label_field),
            secondary=self._side(row, self._secondary, self._secondary_field),
            thumbnail=picture,
            entity_type=row.type,
            status_code=status,
            status_field=self._status_field,
            playable=row.type == "Version" and image_state(picture) == "ready",
        )

    def _side(
        self,
        row: EntityRow,
        custom: Callable[[EntityRow], str] | None,
        spec: FieldSpec | None,
    ) -> str:
        """One side of the metadata line: the caller's own, then the column's own text."""
        if custom is not None:
            return custom(row)
        path = path_of(spec)
        if not path:
            return ""
        value = cell_value(row, path)
        if is_empty_value(value):
            return ""
        column = self._resolved.get(path) if isinstance(spec, str) else to_column(spec)
        if column is None:
            column = to_column(path)
        return field_text(value, column.data_type, preferences_of(self._context))

    def _read_status_field(self) -> None:
        """The type's status field and the metadata line's columns, resolved once off the GUI thread.

        A bare path renders by its own data type, as it does on a card, so a date reads as a date
        and a linked row as its name (probe 009).
        """
        context = self._context
        if context is None:
            return
        entity_type = self.control.source.entity_type
        paths = [
            path
            for path in (path_of(self._sub_label_field), path_of(self._secondary_field))
            if path and isinstance(path, str)
        ]
        n = self._ticket.next()

        def read() -> Any:
            found = status_field_for(entity_type, context.schema.fields(entity_type))
            status = None if isinstance(found, str) or found.data_type != "status_list" else found
            columns = resolve_columns(context.schema, entity_type, paths) if paths else []
            return status, columns

        self.control.binding.pool.submit(
            read, on_result=self._schema_read, ticket=(self._ticket, n)
        )

    def _schema_read(self, answer: Any) -> None:
        status, columns = answer
        self._status_field = status
        self._resolved = {column.path: column for column in columns}
        self.view.viewport().update()

    # --- interaction ----------------------------------------------------------------------

    def on_tile_pressed(self, index: QModelIndex, point: QtCore.QPoint) -> None:
        """A press on the checkbox takes the tile; anywhere else moves the cursor."""
        row = index.data(Roles.ENTITY)
        if not isinstance(row, EntityRow):
            return
        self.control.set_cursor(index.row())
        rect = self.view.visualRect(index)
        if self._selectable and card_tile_checkbox_rect(rect).contains(point):
            self.control.toggle(row)
            self.view.viewport().update()

    def activate(self, index: int) -> None:
        row = self.model.row_at(index)
        if row is not None and not self.control.disabled_at(index):
            self.selected.emit(row)

    def on_key(self, event: QtGui.QKeyEvent) -> bool:
        """The arrows walk the tiles; Space selects, Enter opens, and the end asks for a page."""
        rows = len(self.model.rows)
        if rows == 0:
            return False
        at = self.view.currentIndex().row()
        if at < 0:
            at = max(0, self.control.active)
        step = self.view.columns_across()
        key = event.key()
        if key == Qt.Key.Key_Right:
            if self.control.ask_for_page(at + 1):
                return True
            self._focus(self.control.step_cursor(1, at))
        elif key == Qt.Key.Key_Left:
            self._focus(self.control.step_cursor(-1, at))
        elif key == Qt.Key.Key_Down:
            if self.control.ask_for_page(at + step):
                return True
            self._focus(self.control.step_cursor(step, at))
        elif key == Qt.Key.Key_Up:
            self._focus(self.control.step_cursor(-step, at))
        elif key == Qt.Key.Key_Home:
            self._focus(self.control.first_cursor(0, 1))
        elif key == Qt.Key.Key_End:
            self._focus(self.control.first_cursor(rows - 1, -1))
        elif key == Qt.Key.Key_Space:
            row = self.model.row_at(at)
            if self._selectable and row is not None:
                self.control.toggle(row)
                self.view.viewport().update()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate(at)
        else:
            return False
        return True

    def _focus(self, index: int) -> None:
        if index < 0:
            return
        self.control.set_cursor(index)
        self.view.setCurrentIndex(self.model.index(index, 0))
        self.view.scrollTo(
            self.model.index(index, 0), QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible
        )

    def _on_scrolled(self, _value: int) -> None:
        last = self.view.indexAt(self.view.viewport().rect().bottomRight())
        if not last.isValid():
            last = self.view.indexAt(self.view.viewport().rect().bottomLeft())
        line = last.row() if last.isValid() else len(self.model.rows) - 1
        self.control.on_last_visible(line)

    # --- drawing --------------------------------------------------------------------------

    def _apply_grid(self) -> None:
        gap = ENTITY_GRID_GAP[self._density]
        tile = card_tile_size(self._size)
        self.view.setGridSize(QSize(tile.width() + gap, tile.height() + gap))
        self.view.setViewportMargins(GRID_PAD, GRID_PAD, GRID_PAD, GRID_PAD)
        self._fit()
        self.view.viewport().update()

    def _sync(self) -> None:
        state = self.control.snapshot()
        view = self.control.view(len(self.model.rows))
        self.view.setVisible(view == "rows")
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
        from sg_widgets_core.state import state_line

        self._bottom.apply(
            self.control.bottom(),
            state_line("error", self.control.labels, None if state.error is None else str(state.error)),
            self.control.loading_text,
        )
        self.footer.set_pager(self.control.pager)
        self.footer.set_loading(state.status == "loading")
        waiting = self.control.take_pending_cursor()
        if waiting >= 0:
            self._focus(waiting)
        self._fit()
        self.view.viewport().update()

    def _fit(self) -> None:
        across = max(1, self.view.columns_across())
        lines = -(-len(self.model.rows) // across)
        step = self.view.gridSize().height()
        fit_body(self.view, lines * step + 2 * GRID_PAD, self._max_height)


class _GridSkeleton(QtWidgets.QWidget):
    """Tiles a first read stands behind: the same surface, the same inset, the same height."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-grid-loading")
        self.setAccessibleName("Loading…")
        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(GRID_PAD, GRID_PAD, GRID_PAD, GRID_PAD)
        line.setSpacing(ENTITY_GRID_GAP["default"])
        tile = card_tile_size("md")
        for _ in range(4):
            block = Skeleton(width=tile.width(), height=tile.height(), parent=self)
            line.addWidget(block)
        line.addStretch(1)


#: The tile width per step, so a caller can size its own column around one.
GRID_TILE_WIDTH = CARD_TILE_WIDTH
