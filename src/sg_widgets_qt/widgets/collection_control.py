"""The state and behaviour every collection shares.

Ported from `packages/react/src/registry/sg/components/collection-control.ts`. The table,
the grid and the grouped list draw three different things over one model: a source read
through `collection_source`, a snapshot as a `QAbstractItemModel` the three layouts share,
a selection with its tri-state, a keyboard cursor that skips disabled rows and asks for the
next page at the end, and the scroll and load-more triggers of the `paging` prop.

React derives its lines in the component and hands the base a descriptor. Qt has models, so
the lines live in `CollectionModel`: it holds the rows the source published, the resolved
columns, and the group headings a `group_by` puts between them, and answers the roles both
`RowDelegate` and the table's cell delegate read. A layout then keeps only what it draws.

    control = CollectionControl(source, paging="scroll")
    control.model.set_columns(columns)
    control.changed.connect(redraw)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, Signal

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import (
    CollectionColumn,
    EntitySource,
    EntitySourceState,
    GroupBy,
    PagingModel,
    SortSpec,
    SourceFilters,
    cell_value,
    describe_paging,
    row_key,
)
from sg_widgets_core.collection_state import (
    CollapseState,
    RowDisabledFn,
    RowIdFn,
    SelectionState,
    as_collapse_state,
    expand_all,
    first_enabled_index,
    is_collapsed,
    next_enabled_index,
    row_id_of,
    row_is_disabled,
    same_refs,
    selectable_refs,
    selection_state,
    toggle_ref,
)
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.paging import (
    KeyedRowGroup,
    LoadNextOptions,
    collection_bottom,
    collection_view,
    group_rows_keyed,
    has_failed_page,
    loads_on_arrow_down,
    should_load_next,
)
from sg_widgets_core.state import StateLabels, state_line

from ..primitives.roles import Roles
from .collection_source import COLLECTION_PAGING_VALUES, CollectionSource

__all__ = [
    "COLLECTION_GAP",
    "COLLECTION_PAGING_VALUES",
    "CollectionControl",
    "CollectionLine",
    "CollectionModel",
    "collapse_from",
    "group_of",
]

#: The gap between a collection's regions: its toolbar, its body and its footer (rule 2).
COLLECTION_GAP = 8

#: The column a heading line spans from. A heading carries its own value under `Roles.ENTITY`.
_ROOT = QModelIndex()


class CollectionLine:
    """One line of a layout: a row, or the heading of a group."""

    __slots__ = ("group", "index", "kind", "row")

    def __init__(
        self,
        kind: str,
        row: EntityRow | None = None,
        index: int = -1,
        group: KeyedRowGroup | None = None,
    ) -> None:
        #: `row` or `heading`.
        self.kind = kind
        self.row = row
        #: The row's index among the loaded rows. -1 on a heading.
        self.index = index
        self.group = group


class CollectionModel(QAbstractTableModel):
    """The snapshot the three layouts share: the rows, the columns and the group headings.

    A row is one line; a `group_by` puts a heading line before each contiguous run and the
    rows of a shut group leave the list. The columns are core's resolved ones, so a cell knows
    its data type, its alignment and the schema behind it without asking again.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[EntityRow] = []
        self._columns: list[CollectionColumn] = []
        self._lines: list[CollectionLine] = []
        self._groups: list[KeyedRowGroup] = []
        self._group_by: GroupBy | None = None
        self._collapsed: CollapseState = expand_all()
        self._selected: set[str] = set()
        self._row_id: RowIdFn | None = None
        self._row_disabled: RowDisabledFn | None = None
        self._select_column = False

    # --- what it holds --------------------------------------------------------------------

    @property
    def rows(self) -> list[EntityRow]:
        """The rows the source published, ungrouped."""
        return list(self._rows)

    @property
    def columns(self) -> list[CollectionColumn]:
        """The resolved columns, in display order."""
        return list(self._columns)

    @property
    def groups(self) -> list[KeyedRowGroup]:
        """The contiguous runs a `group_by` found, each under the key it collapses by."""
        return list(self._groups)

    @property
    def lines(self) -> list[CollectionLine]:
        """The lines on show: rows, and the headings between them."""
        return list(self._lines)

    def set_rows(self, rows: Sequence[EntityRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self._rebuild()
        self.endResetModel()

    def set_columns(self, columns: Sequence[CollectionColumn]) -> None:
        self.beginResetModel()
        self._columns = list(columns)
        self.endResetModel()

    def set_group_by(self, by: GroupBy | None) -> None:
        self.beginResetModel()
        self._group_by = by
        self._rebuild()
        self.endResetModel()

    @property
    def group_by(self) -> GroupBy | None:
        return self._group_by

    def set_collapsed(self, state: CollapseState) -> None:
        self.beginResetModel()
        self._collapsed = state
        self._rebuild()
        self.endResetModel()

    @property
    def collapsed(self) -> CollapseState:
        return self._collapsed

    @property
    def select_column(self) -> bool:
        """True while a leading column holds the row's checkbox. The table's alone."""
        return self._select_column

    def set_select_column(self, on: bool) -> None:
        self.beginResetModel()
        self._select_column = bool(on)
        self.endResetModel()

    @property
    def select_offset(self) -> int:
        """Columns before the first field column: 1 with a select column, 0 without."""
        return 1 if self._select_column else 0

    def set_selected_keys(self, keys: Sequence[str]) -> None:
        """The selection, as row keys, so a cell answers whether it is chosen in constant time."""
        self._selected = set(keys)
        self._touch()

    def set_row_id(self, fn: RowIdFn | None) -> None:
        self._row_id = fn
        self._touch()

    def set_row_disabled(self, fn: RowDisabledFn | None) -> None:
        self._row_disabled = fn
        self._touch()

    # --- lookups --------------------------------------------------------------------------

    def line_at(self, line: int) -> CollectionLine | None:
        return self._lines[line] if 0 <= line < len(self._lines) else None

    def row_at(self, index: int) -> EntityRow | None:
        """A loaded row by its index among the rows, not among the lines."""
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def column_at(self, column: int) -> CollectionColumn | None:
        """The field column at a view column. None on the select column."""
        at = column - self.select_offset
        return self._columns[at] if 0 <= at < len(self._columns) else None

    def column_index_of(self, path: str) -> int:
        """The view column a path is drawn in. -1 when it is not on show."""
        for at, column in enumerate(self._columns):
            if column.path == path:
                return at + self.select_offset
        return -1

    def key_of(self, row: EntityRow) -> str:
        """The row's id: the caller's, or `Type:id`."""
        return row_id_of(row, self._row_id)

    def row_index_of_line(self, line: int) -> int:
        """The index among the rows of the line, or -1 for a heading."""
        found = self.line_at(line)
        return found.index if found is not None else -1

    def line_of_row_index(self, index: int) -> int:
        """The line a loaded row sits on. -1 when its group is shut."""
        for at, line in enumerate(self._lines):
            if line.index == index and line.kind == "row":
                return at
        return -1

    def last_row_of_line(self, line: int) -> int:
        """The last loaded row the viewport reaches, given the last line it drew.

        Lines below the window count headings as well, so a heading only ever makes the
        scroller ask later.
        """
        if line < 0 or not self._lines:
            return -1
        return len(self._rows) - 1 - (len(self._lines) - 1 - min(line, len(self._lines) - 1))

    def index_of_key(self, key: str) -> int:
        for at, row in enumerate(self._rows):
            if self.key_of(row) == key:
                return at
        return -1

    def is_disabled(self, row: EntityRow) -> bool:
        return row_is_disabled(row, self._row_disabled)

    # --- the model ------------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._lines)

    def columnCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else max(1, len(self._columns) + self.select_offset)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation != Qt.Orientation.Horizontal:
            return None
        column = self.column_at(section)
        if column is None:
            return "" if role == Qt.ItemDataRole.DisplayRole else None
        if role == Qt.ItemDataRole.DisplayRole:
            return column.header
        if role == Roles.SORTABLE:
            return column.sortable
        if role == Roles.CODE:
            return column.path
        if role == Roles.ENTITY:
            return column
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        line = self.line_at(index.row())
        if line is None:
            return None
        if line.kind == "heading":
            return self._heading_data(line, role)
        row = line.row
        if row is None:
            return None
        if role == Roles.KIND:
            return "row"
        if role == Roles.ENTITY:
            return row
        if role == Roles.DISABLED:
            return self.is_disabled(row)
        if role == Roles.CHECKED:
            return row_key(row) in self._selected
        if role == Roles.LABEL:
            column = self.column_at(index.column())
            return "" if column is None else str(cell_value(row, column.path) or "")
        if role == Qt.ItemDataRole.DisplayRole:
            column = self.column_at(index.column())
            return None if column is None else cell_value(row, column.path)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            column = self.column_at(index.column())
            if column is not None and column.align == "right":
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def _heading_data(self, line: CollectionLine, role: int) -> Any:
        group = line.group
        if group is None:
            return None
        if role == Roles.KIND:
            return "heading"
        if role == Roles.ENTITY:
            return group
        if role == Roles.CHECKED:
            return not is_collapsed(self._collapsed, group.key)
        if role == Roles.SECONDARY:
            return str(len(group.rows))
        if role == Roles.CODE:
            return group.key
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        line = self.line_at(index.row())
        if line is None or line.kind == "heading":
            return Qt.ItemFlag.ItemIsEnabled
        if line.row is not None and self.is_disabled(line.row):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # --- internals ------------------------------------------------------------------------

    def _rebuild(self) -> None:
        if self._group_by is None:
            self._groups = []
            self._lines = [
                CollectionLine("row", row, at) for at, row in enumerate(self._rows)
            ]
            return
        self._groups = group_rows_keyed(self._rows, self._group_by)
        lines: list[CollectionLine] = []
        at = 0
        for group in self._groups:
            lines.append(CollectionLine("heading", None, -1, group))
            shut = is_collapsed(self._collapsed, group.key)
            for row in group.rows:
                if not shut:
                    lines.append(CollectionLine("row", row, at, group))
                at += 1
        self._lines = lines

    def _touch(self) -> None:
        if not self._lines:
            return
        top = self.index(0, 0)
        bottom = self.index(len(self._lines) - 1, max(0, self.columnCount() - 1))
        self.dataChanged.emit(top, bottom)


class CollectionControl(QObject):
    """The source, the shared model, the selection, the cursor and the paging triggers.

    A widget owns one and draws its own layout over `model`. Nothing here draws.
    """

    #: The snapshot moved: rows, status, error, paging or total.
    changed = Signal()
    #: The selected rows. Carries `list[EntityRef]`.
    selection_changed = Signal(object)
    #: The source's sort moved. Carries `list[SortSpec]`.
    sort_changed = Signal(object)
    #: The source's filter moved. Carries the wire group, or None.
    filters_changed = Signal(object)
    #: A read, a write or a count raised. Carries the exception.
    failed = Signal(object)

    def __init__(
        self,
        source: EntitySource,
        paging: str = "pages",
        sort: Sequence[SortSpec] | None = None,
        filters: SourceFilters = None,
        selection: Sequence[EntityRef] | None = None,
        get_row_id: RowIdFn | None = None,
        is_row_disabled: RowDisabledFn | None = None,
        loading_label: str | None = None,
        empty_label: str | None = None,
        error_label: str | None = None,
        model: CollectionModel | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_row_id = get_row_id
        self._is_row_disabled = is_row_disabled
        self._labels = StateLabels(
            empty_label=empty_label, loading_label=loading_label, error_label=error_label
        )
        self._selection: list[EntityRef] = list(selection or [])
        self._cursor = 0
        #: The row a cursor waits on while the page it asked for is read. -1 when none.
        self._pending = -1

        #: The snapshot the layout draws. A layout that needs more roles brings its own subclass.
        self.model = model if model is not None else CollectionModel(self)
        self.model.setParent(self)
        self.model.set_row_id(get_row_id)
        self.model.set_row_disabled(is_row_disabled)
        self.model.set_selected_keys([row_key(ref) for ref in self._selection])

        self.binding = CollectionSource(source, paging=paging, sort=sort, filters=filters, parent=self)
        self.binding.changed.connect(self._on_changed)
        self.binding.sort_changed.connect(self.sort_changed.emit)
        self.binding.filters_changed.connect(self.filters_changed.emit)
        self.binding.failed.connect(self.failed.emit)
        self._sync_rows()

    # --- the source -----------------------------------------------------------------------

    @property
    def source(self) -> EntitySource:
        return self.binding.source

    @property
    def paging(self) -> str:
        """`pages`, `more` or `scroll`."""
        return self.binding.paging

    def set_paging(self, value: str) -> None:
        self.binding.set_paging(value)

    @property
    def sort(self) -> list[SortSpec]:
        return self.binding.sort

    def set_sort(self, value: Sequence[SortSpec] | None) -> None:
        """Take a sort from the `sort` prop. Nothing is reported back out."""
        self.binding.set_sort(value)

    def apply_sort(self, value: Sequence[SortSpec]) -> None:
        """Sort from the widget's own control, so `sort_changed` reports it."""
        self.binding.apply_sort(value)

    @property
    def filters(self) -> SourceFilters:
        return self.binding.filters

    def set_filters(self, value: SourceFilters) -> None:
        """Take a filter from the `filters` prop. Nothing is reported back out."""
        self.binding.set_filters(value)

    def apply_filters(self, value: SourceFilters) -> None:
        """Filter from the widget's own control, so `filters_changed` reports it."""
        self.binding.apply_filters(value)

    def snapshot(self) -> EntitySourceState:
        return self.binding.snapshot()

    @property
    def rows(self) -> list[EntityRow]:
        return self.model.rows

    @property
    def pager(self) -> PagingModel:
        """The numbers the footer draws, from core's `describe_paging`."""
        return describe_paging(self.snapshot())

    @property
    def page_error(self) -> bool:
        """True when a read failed with rows already on screen."""
        return has_failed_page(self.snapshot())

    @property
    def loading_text(self) -> str:
        """The accessible name the skeletons carry."""
        return state_line("loading", self._labels)

    @property
    def labels(self) -> StateLabels:
        """The empty, loading and error lines this collection was given."""
        return self._labels

    def set_labels(self, labels: StateLabels) -> None:
        self._labels = labels

    def view(self, lines: int) -> str:
        """Which of `error`, `loading`, `empty` and `rows` the body shows."""
        return collection_view(self.snapshot(), lines)

    def bottom(self) -> str | None:
        """What sits under the last row: `error`, `loading`, `more`, `sentinel` or nothing."""
        return collection_bottom(self.snapshot(), self.paging)

    def retry(self) -> None:
        self.binding.retry()

    def load_more(self) -> None:
        self.binding.load_more()

    def count(self) -> None:
        self.binding.count()

    # --- rows -----------------------------------------------------------------------------

    def row_id(self, row: EntityRow) -> str:
        return row_id_of(row, self._get_row_id)

    def set_get_row_id(self, fn: RowIdFn | None) -> None:
        self._get_row_id = fn
        self.model.set_row_id(fn)

    def row_disabled(self, row: EntityRow) -> bool:
        return row_is_disabled(row, self._is_row_disabled)

    def set_is_row_disabled(self, fn: RowDisabledFn | None) -> None:
        self._is_row_disabled = fn
        self.model.set_row_disabled(fn)

    def disabled_at(self, index: int) -> bool:
        row = self.model.row_at(index)
        return row is None or self.row_disabled(row)

    # --- the selection --------------------------------------------------------------------

    @property
    def selection(self) -> list[EntityRef]:
        """The selected rows."""
        return list(self._selection)

    def set_selection(self, value: Sequence[EntityRef]) -> None:
        """Take a selection without reporting it, which is what a two-way prop does."""
        rows = list(value)
        if same_refs(rows, self._selection):
            return
        self._selection = rows
        self.model.set_selected_keys([row_key(ref) for ref in rows])

    def _write_selection(self, rows: Sequence[EntityRef]) -> None:
        if same_refs(rows, self._selection):
            return
        self._selection = list(rows)
        self.model.set_selected_keys([row_key(ref) for ref in self._selection])
        self.selection_changed.emit(list(self._selection))

    def is_selected(self, row: EntityRow) -> bool:
        key = row_key(row)
        return any(row_key(ref) == key for ref in self._selection)

    def toggle(self, row: EntityRow) -> None:
        """Add or drop one row. A disabled row refuses."""
        if self.row_disabled(row):
            return
        self._write_selection(toggle_ref(self._selection, EntityRef(type=row.type, id=row.id)))

    @property
    def all_selected(self) -> SelectionState:
        """The tri-state a header checkbox reads over the rows that are loaded."""
        return selection_state(self.model.rows, self._selection, self._is_row_disabled)

    def toggle_all(self, on: bool) -> None:
        """Take or drop every loaded row that is not disabled."""
        self._write_selection(
            selectable_refs(self.model.rows, self._is_row_disabled) if on else []
        )

    # --- the cursor -----------------------------------------------------------------------

    @property
    def cursor(self) -> int:
        """Where the keyboard cursor is, among the loaded rows."""
        return self._cursor

    @property
    def active(self) -> int:
        """The row that owns the one tab stop. -1 when there is none."""
        count = len(self.model.rows)
        if count == 0:
            return -1
        return first_enabled_index(count, min(self._cursor, count - 1), 1, self.disabled_at)

    def set_cursor(self, index: int) -> None:
        self._cursor = max(0, index)

    def step_cursor(self, step: int, from_: int | None = None) -> int:
        """Where the cursor lands moving `step`, skipping disabled rows."""
        start = self._cursor if from_ is None else from_
        return next_enabled_index(len(self.model.rows), start, step, self.disabled_at)

    def first_cursor(self, from_: int, step: int) -> int:
        return first_enabled_index(len(self.model.rows), from_, step, self.disabled_at)

    def ask_for_page(self, index: int) -> bool:
        """Ask for the next page where the cursor ran past the loaded rows.

        True when the step was an ask rather than a move: the cursor then stays where it is
        until the rows arrive, and `pending_cursor` says where it goes next.
        """
        if not loads_on_arrow_down(self.snapshot(), self.paging, index):
            return False
        self._pending = index
        self.binding.load_more()
        return True

    @property
    def pending_cursor(self) -> int:
        """The row a cursor is waiting on, until the page it asked for lands. -1 when none."""
        return self._pending

    def take_pending_cursor(self) -> int:
        """The waiting row, once it is loaded. -1 while it is not."""
        wanted = self._pending
        if wanted < 0:
            return -1
        state = self.snapshot()
        if state.status == "error":
            self._pending = -1
            return -1
        if len(state.rows) <= wanted:
            return -1
        self._pending = -1
        return wanted

    # --- the scroll trigger ---------------------------------------------------------------

    def on_last_visible(self, index: int) -> None:
        """The scroller reached this row. Asks for the next page when it is near enough."""
        if index < 0:
            return
        if should_load_next(self.snapshot(), LoadNextOptions(paging=self.paging, last_visible=index)):
            self.binding.load_more()

    # --- internals ------------------------------------------------------------------------

    def _sync_rows(self) -> None:
        rows = self.snapshot().rows
        if rows != self.model.rows:
            self.model.set_rows(rows)

    def _on_changed(self) -> None:
        self._sync_rows()
        self.changed.emit()

    def close(self) -> None:
        """Stop following the source."""
        self.binding.close()


def collapse_from(value: Sequence[str] | CollapseState | None) -> CollapseState:
    """A caller's collapse prop as a state. A bare key list is the open mode with those shut."""
    return as_collapse_state(value)


def group_of(rows: Sequence[EntityRow], by: GroupBy) -> list[KeyedRowGroup]:
    """The contiguous runs of `rows`, each under the key a collapsed group is named by."""
    return group_rows_keyed(rows, by)


#: Kept so a layout can name the callable types without reaching into core.
RowIdCallable = Callable[[EntityRow], str]
RowDisabledCallable = Callable[[EntityRow], bool]
