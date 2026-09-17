"""Entity source.

The headless half of every collection widget: one object that holds a page of
rows, the filter and the sort behind them, and the calls that move them. It has
no Qt in it. A widget subscribes to it and neither reimplements paging, ordering
nor the read-after-write rule.

Paging stops on an empty page, never on a missing `links.next`, which the API
emits forever (006_pagination). A read carries no total, so `pages` mode walks
the set with an explicit page number and asks `_summarize` for the count that
turns a range into "n to m of N" (020_summarize). Ordering is the server's: with
no sort rows come back id ascending and id ascending is the implicit tiebreak,
and a sort on a field that cannot be sorted is a silent 200 no-op, so a widget
verifies a sort path against the schema before offering it (026_result_order).

Every call here is synchronous. `sg_widgets_qt.workers` runs the read on a thread
and calls back on the GUI thread; `InFlight` is what tells a late answer from the
one that still stands.
"""
from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Literal, Union

from .client import EntityRow, SearchOptions, SgClient, SummarizeOptions, SummaryField
from .edit import EditorPlacement
from .field_types import is_numeric_type
from .filter import EntityRef, FilterNode, WireGroup, to_api3_hash
from .filter_ux import is_sortable
from .schema import FieldSchema, display_name_of
from .schema_service import SchemaService

__all__ = [
    "SOURCE_MODE_VALUES",
    "SOURCE_STATUS_VALUES",
    "CollectionColumn",
    "ColumnSpec",
    "EntitySource",
    "EntitySourceOptions",
    "EntitySourceState",
    "GroupBy",
    "GroupKeyFn",
    "InFlight",
    "PagingModel",
    "RowGroup",
    "SortSpec",
    "SourceFilters",
    "SourceMode",
    "SourceStatus",
    "cell_value",
    "create_entity_source",
    "describe_paging",
    "group_key_text",
    "group_rows",
    "resolve_columns",
    "row_key",
    "serialize_sort",
    "to_column",
    "to_wire_group",
]


@dataclass
class SortSpec:
    """One sort key. Serialised as `path` or `-path` (026_result_order)."""

    path: str
    descending: bool = False


#: A filter as the caller holds it: the editor's tree, the wire group, or nothing.
SourceFilters = Union[FilterNode, WireGroup, None]

SourceStatus = Literal["idle", "loading", "loadingMore", "ready", "error"]
SOURCE_STATUS_VALUES: tuple[SourceStatus, ...] = ("idle", "loading", "loadingMore", "ready", "error")

SourceMode = Literal["pages", "infinite"]
"""`pages` shows one page at a time; `infinite` appends page after page."""
SOURCE_MODE_VALUES: tuple[SourceMode, ...] = ("pages", "infinite")


@dataclass
class EntitySourceOptions:
    client: SgClient
    entity_type: str
    #: Paths to read, plain or dotted. `id` is always read.
    fields: list[str] = dc_field(default_factory=list)
    filters: SourceFilters = None
    sort: list[SortSpec] | None = None
    #: Rows per request. Default 50.
    page_size: int = 50
    #: Default `infinite`.
    mode: SourceMode = "infinite"
    #: The page `pages` mode opens on. Default 1.
    page: int = 1


@dataclass
class EntitySourceState:
    """Everything a view renders. A new object on every change, so identity is the signal."""

    rows: list[EntityRow] = dc_field(default_factory=list)
    status: SourceStatus = "idle"
    error: Exception | None = None
    #: True when another page exists.
    has_more: bool = False
    #: The total the last `count()` answered. None until one is asked for, and None when
    #: the site did not answer it.
    total: int | None = None
    filters: WireGroup | None = None
    sort: list[SortSpec] = dc_field(default_factory=list)
    mode: SourceMode = "infinite"
    #: 1-based page number of the rows on screen. 1 in infinite mode.
    page: int = 1
    page_size: int = 50


@dataclass
class InFlight:
    """A read that has started: the ticket it holds and the filter it was taken under.

    The Qt layer (`src/sg_widgets_qt/workers.py`) runs the read on a thread and calls
    back, so the answer lands after the state may have moved. A row read is dropped
    once its ticket is no longer the source's, and a count is dropped once the filter
    it counted has been replaced.
    """

    ticket: int
    filters: WireGroup | None = None


def row_key(row: EntityRow | EntityRef) -> str:
    """`Type:id`, the key a list keys rows on."""
    return f"{row.type}:{row.id}"


def cell_value(row: EntityRow, path: str) -> Any:
    """The value at a path on a row.

    A dotted path comes back flat under its literal key, as a plain field does
    (003_query, endpoints/post_entity_type_search).
    """
    if path == "id":
        return row.id
    if path == "type":
        return row.type
    return row.values.get(path)


def serialize_sort(sort: Sequence[SortSpec]) -> str | None:
    """Sort keys as the API's `sort` value: comma separated, `-` per key (026_result_order)."""
    keys = [f"-{k.path}" if k.descending else k.path for k in sort if k.path]
    return ",".join(keys) if keys else None


def to_wire_group(filters: SourceFilters) -> WireGroup | None:
    """A filter in the one shape a read carries, whichever spelling the caller holds."""
    if not filters:
        return None
    if isinstance(filters, dict):
        return filters
    return to_api3_hash(filters)


def _as_error(value: Any) -> Exception:
    return value if isinstance(value, Exception) else Exception(str(value))


class EntitySource:
    """A page of rows of one type, the filter and the sort behind them, and the calls that move them."""

    def __init__(self, options: EntitySourceOptions) -> None:
        self._client = options.client
        self._entity_type = options.entity_type
        # `id` is what a row is keyed and re-read on, so it is never left out of a projection.
        self._fields: list[str] = list(dict.fromkeys(["id", *options.fields]))
        self._state = EntitySourceState(
            filters=to_wire_group(options.filters),
            sort=list(options.sort or []),
            mode=options.mode,
            page=max(1, options.page),
            page_size=options.page_size,
        )
        self._listeners: list[Callable[[], None]] = []
        # Every read carries the generation it started in; a later filter or sort discards it.
        self._generation = 0
        self._in_flight = False
        # One count per filter, whatever it answered: a site that answers no total answers
        # none however often it is asked (020_summarize).
        self._counted = False

    # ------------------------------------------------------------------ #

    @property
    def entity_type(self) -> str:
        return self._entity_type

    @property
    def fields(self) -> list[str]:
        return self._fields

    @property
    def rows(self) -> list[EntityRow]:
        return self._state.rows

    @property
    def status(self) -> SourceStatus:
        return self._state.status

    @property
    def error(self) -> Exception | None:
        return self._state.error

    @property
    def has_more(self) -> bool:
        return self._state.has_more

    @property
    def filters(self) -> WireGroup | None:
        return self._state.filters

    @property
    def sort(self) -> list[SortSpec]:
        return self._state.sort

    @property
    def mode(self) -> SourceMode:
        return self._state.mode

    @property
    def page(self) -> int:
        return self._state.page

    @property
    def page_size(self) -> int:
        return self._state.page_size

    @property
    def total(self) -> int | None:
        return self._state.total

    # ------------------------------------------------------------------ #

    def begin(self) -> InFlight:
        """Take the ticket the next read holds, with the filter it is taken under.

        Every read already in flight is stale from here on. `load` and the rest take
        their own; a caller running the read elsewhere takes one here and asks `holds`
        before writing the answer.
        """
        self._generation += 1
        return InFlight(ticket=self._generation, filters=self._state.filters)

    def begin_count(self) -> InFlight:
        """The record a count carries. Only the filter decides whether its answer still stands."""
        return InFlight(ticket=self._generation, filters=self._state.filters)

    def holds(self, pending: InFlight) -> bool:
        """True while an answer taken under `pending` may still be written."""
        return pending.ticket == self._generation

    def snapshot(self) -> EntitySourceState:
        """The current state object, stable between changes."""
        return self._state

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` on every change. The return value stops it."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    # ------------------------------------------------------------------ #

    def _set(self, **next_: Any) -> None:
        self._state = dataclasses.replace(self._state, **next_)
        for listener in list(self._listeners):
            listener()

    def _request_page(self, number: int) -> SearchOptions:
        # An empty `sort` is 400 `sort must be filled`, so the key is left None rather
        # than sent blank (026_result_order).
        return SearchOptions(
            filters=self._state.filters,
            fields=list(self._fields),
            sort=serialize_sort(self._state.sort),
            page={"size": self._state.page_size, "number": number},
        )

    def _read(self, pages: int, status: SourceStatus, keep: list[EntityRow], first: int) -> None:
        pending = self.begin()
        self._set(status=status, error=None)
        try:
            rows = list(keep)
            more = False
            for n in range(pages):
                result = self._client.search(self._entity_type, self._request_page(first + n))
                if not self.holds(pending):
                    return
                rows.extend(result.data)
                more = result.has_more
                # A short page is the end of the set: `links.next` is emitted forever (006_pagination).
                if not more:
                    break
            self._set(rows=rows, has_more=more, status="ready")
        except Exception as error:
            if not self.holds(pending):
                return
            self._set(status="error", error=_as_error(error))

    def _run(self, task: Callable[[], None]) -> None:
        self._in_flight = True
        try:
            task()
        finally:
            self._in_flight = False

    def _reread(self) -> None:
        """Read the page the state now names, and count the set once per filter in `pages` mode.

        A range reads "n to m of N" only after something counted, because no total is in
        a read (006_pagination).
        """
        first = self._state.page if self._state.mode == "pages" else 1
        pages_mode = self._state.mode == "pages"
        counted = self._counted
        self._run(lambda: self._read(1, "loading", [], first))
        if not pages_mode or counted:
            return
        try:
            self.count()
        except Exception:
            pass

    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """Read the first page, discarding anything already loaded, and count the set in `pages` mode."""
        # A new read invalidates the total: the filter it was taken under may have moved.
        self._counted = False
        self._set(total=None, page=1)
        self._reread()

    def load_more(self) -> None:
        """Append the next page.

        A no-op in `pages` mode, while another read is in flight, or when there is no
        more. Calling it again is what retries a page that failed.
        """
        # A failed page leaves its rows and its error in place, and asking again is the retry.
        if self._state.mode == "pages" or self._in_flight or not self._state.has_more:
            return
        first = len(self._state.rows) // self._state.page_size + 1
        self._run(lambda: self._read(1, "loadingMore", self._state.rows, first))

    def refresh(self) -> None:
        """Read every page already shown again, keeping the row count."""
        self._counted = False
        if self._state.mode == "pages":
            self._set(total=None)
            self._reread()
            return
        pages = max(1, -(-len(self._state.rows) // self._state.page_size))
        self._set(total=None)
        self._run(lambda: self._read(pages, "loading", [], 1))

    def set_filters(self, filters: SourceFilters) -> None:
        self._set(filters=to_wire_group(filters))
        self.load()

    def set_sort(self, sort: list[SortSpec]) -> None:
        # An order moves the rows, not the set, so the total counted under this filter stands.
        self._set(sort=list(sort), page=1)
        self._reread()

    def set_page(self, page: int) -> None:
        """Show one page of the set. `pages` mode only."""
        if self._state.mode != "pages":
            return
        self._set(page=max(1, int(page)))
        self._reread()

    def set_mode(self, mode: SourceMode) -> None:
        """Walk the set a page at a time, or append page after page. Opens at the first page."""
        if self._state.mode == mode:
            return
        self._set(mode=mode, page=1)
        self._reread()

    def set_page_size(self, size: int) -> None:
        """Change the rows per page and open at the first one."""
        self._set(page_size=max(1, int(size)), page=1)
        self._reread()

    def count(self, pending: InFlight | None = None) -> int | None:
        """Total rows the filter matches, through `_summarize` (020_summarize).

        None when the site did not answer the key. `pending` is what `begin_count`
        answered, for a count the Qt layer ran on a thread: its answer is written only
        while the filter it counted is still the source's.
        """
        started = pending if pending is not None else self.begin_count()
        # A field that cannot be summarized answers 200 with its key absent, so the key is
        # tested rather than assumed (020_summarize).
        summary = self._client.summarize(
            self._entity_type,
            SummarizeOptions(
                filters=started.filters,
                summary_fields=[SummaryField(field="id", type="count")],
            ),
        )
        total = summary.summaries.get("id")
        value = total if isinstance(total, (int, float)) else None
        # Only the filter decides the total, so a count outlives the read it started beside
        # and is dropped only when the filter it counted has moved.
        if self._state.filters is started.filters:
            self._counted = True
            self._set(total=value)
        return value

    def update_row(self, ref: EntityRef, patch: dict[str, Any]) -> EntityRow:
        """Write the named fields of one row and put the re-read row back in place."""
        self._client.update(ref.type, ref.id, patch)
        # The write answers the whole record but never resolves a dotted path, so the row
        # is read again with the source's own projection (024_read_after_write). The re-read
        # ignores the source's filter: a change that moves the row out of it still has to
        # come back so the view can show what was written.
        reread = self._client.search(
            ref.type,
            SearchOptions(
                filters={"logical_operator": "and", "conditions": [["id", "is", ref.id]]},
                fields=list(self._fields),
                page={"size": 1, "number": 1},
            ),
        )
        fresh = reread.data[0] if reread.data else None
        if fresh is None:
            raise ValueError(f"{ref.type} {ref.id} could not be read back after the write.")
        key = row_key(ref)
        self._set(rows=[fresh if row_key(row) == key else row for row in self._state.rows])
        return fresh

    def reread_rows(self, ids: Sequence[int]) -> None:
        """Read these rows again with the source's own projection and swap them in place.

        A row the site no longer answers (retired, or moved out of reach) leaves the
        list. The filter is not applied, as on `update_row`: a row that moved out of the
        filter still comes back so the view can show what changed. Ids not on screen are
        ignored. Neither status nor order changes, so nothing dims and nothing jumps.
        """
        on_screen = {row.id for row in self._state.rows}
        wanted = [id_ for id_ in dict.fromkeys(ids) if id_ in on_screen]
        if len(wanted) == 0:
            return
        # One read for the whole list: `page[size]` reached no cap at 5000 rows
        # (endpoints/get_entity_type). It carries no filter and no sort, so a row that moved
        # out of either still comes back, as on `update_row`.
        result = self._client.search(
            self._entity_type,
            SearchOptions(
                filters={"logical_operator": "and", "conditions": [["id", "in", wanted]]},
                fields=list(self._fields),
                page={"size": len(wanted), "number": 1},
            ),
        )
        fresh = {row.id: row for row in result.data}
        asked = set(wanted)
        # A row the site did not answer for is gone; every other row keeps its place, and
        # nothing here touches the status, the paging or the total.
        rows: list[EntityRow] = []
        for row in self._state.rows:
            if row.id not in asked:
                rows.append(row)
                continue
            next_ = fresh.get(row.id)
            if next_ is not None:
                rows.append(next_)
        self._set(rows=rows)


def create_entity_source(options: EntitySourceOptions) -> EntitySource:
    return EntitySource(options)


# -------------------------------------------------------------------------- #
# paging                                                                      #
# -------------------------------------------------------------------------- #


@dataclass
class PagingModel:
    """The numbers a collection's footer draws, in either mode."""

    mode: SourceMode
    page: int
    page_size: int
    #: 1-based index of the first row on screen. 0 when there are none.
    from_: int
    #: 1-based index of the last row on screen. 0 when there are none.
    to: int
    total: int | None
    #: Pages the total implies. None when nothing counted the set.
    page_count: int | None
    has_previous: bool
    has_next: bool
    #: `1 to 25 of 320`, and `1 to 25` when nothing counted the set.
    range_label: str
    #: `25 loaded`, and `25 of 320 loaded` once the set is counted.
    loaded_label: str


def describe_paging(state: EntitySourceState) -> PagingModel:
    """The footer's numbers for one state.

    A read answers no total of its own, so a range reads "of N" only once `_summarize`
    has counted the set, and a next page exists either because that count says so or
    because the page that came back was full (006_pagination, 020_summarize).
    """
    loaded = len(state.rows)
    if loaded == 0:
        from_ = 0
    elif state.mode == "pages":
        from_ = (state.page - 1) * state.page_size + 1
    else:
        from_ = 1
    to = 0 if loaded == 0 else from_ + loaded - 1
    page_count = None if state.total is None else max(1, math.ceil(state.total / state.page_size))
    return PagingModel(
        mode=state.mode,
        page=state.page,
        page_size=state.page_size,
        from_=from_,
        to=to,
        total=state.total,
        page_count=page_count,
        has_previous=state.mode == "pages" and state.page > 1,
        has_next=state.has_more if page_count is None else state.page < page_count,
        range_label=f"{from_} to {to}" if state.total is None else f"{from_} to {to} of {state.total}",
        loaded_label=f"{loaded} loaded" if state.total is None else f"{loaded} of {state.total} loaded",
    )


# -------------------------------------------------------------------------- #
# columns                                                                     #
# -------------------------------------------------------------------------- #


@dataclass
class ColumnSpec:
    """A column as a caller writes it: a path, and anything the schema should not decide."""

    #: Plain or dotted path, e.g. `entity.Shot.code`.
    path: str
    header: str | None = None
    data_type: str | None = None
    #: Starting width in pixels.
    width: int | None = None
    editable: bool | None = None
    align: Literal["left", "right"] | None = None
    field: FieldSchema | None = None
    #: Override the sortability the data type implies.
    sortable: bool | None = None
    #: Override where this column's editor opens.
    editor_placement: EditorPlacement | None = None


@dataclass
class CollectionColumn:
    """A column with every question answered, which is what a collection widget takes."""

    path: str
    header: str
    data_type: str
    #: True when a cell may open an editor. A projection is never writable.
    editable: bool = False
    align: Literal["left", "right"] = "left"
    #: False for a type the server sorts as a silent no-op or a 400 (026_result_order).
    sortable: bool = False
    #: The schema of the field the path lands on, for a status label out of `display_values`.
    field: FieldSchema | None = None
    width: int | None = None
    #: Where this column's editor opens. None leaves it to the data type.
    editor_placement: EditorPlacement | None = None


def resolve_columns(
    schema: SchemaService,
    entity_type: str,
    columns: Sequence[str | ColumnSpec],
) -> list[CollectionColumn]:
    """Fill in headers, data types and editability from the schema.

    The header of a dotted path is the display name of the field it lands on. A
    projection is never writable: a write names one field of one row
    (put_entity_type_id), so only a plain path can open an editor.
    """
    out: list[CollectionColumn] = []
    for entry in columns:
        spec = ColumnSpec(path=entry) if isinstance(entry, str) else entry
        segments = schema.resolve_path(entity_type, spec.path)
        last = segments[-1] if segments else None
        field = spec.field if spec.field is not None else (last.field if last else None)
        data_type = spec.data_type if spec.data_type is not None else (last.data_type if last else "text")
        out.append(CollectionColumn(
            path=spec.path,
            header=spec.header if spec.header is not None else (last.display_name if last else spec.path),
            data_type=data_type,
            editable=(
                spec.editable
                if spec.editable is not None
                else len(segments) == 1 and bool(field.editable if field else False)
            ),
            align=spec.align if spec.align is not None else ("right" if is_numeric_type(data_type) else "left"),
            sortable=spec.sortable if spec.sortable is not None else is_sortable(data_type),
            field=field,
            width=spec.width,
            editor_placement=spec.editor_placement,
        ))
    return out


def to_column(spec: str | CollectionColumn) -> CollectionColumn:
    """A column from a bare path, for a row-anatomy prop that takes either.

    Nothing but the path is known, so the value renders as text and the column is
    neither sortable nor editable. A caller that wants the field's own type passes the
    resolved column from `resolve_columns` instead.
    """
    if not isinstance(spec, str):
        return spec
    return CollectionColumn(
        path=spec,
        header=spec,
        data_type="text",
        editable=False,
        align="left",
        sortable=False,
        field=None,
    )


@dataclass
class RowGroup:
    """A contiguous run of rows sharing a value at a path.

    Grouping a paged read is only honest over an order the server produced, so a caller
    sorts on the same path and this walks the runs. A group whose rows continue on the
    next page grows when that page arrives.
    """

    #: The raw value the run shares.
    value: Any
    rows: list[EntityRow] = dc_field(default_factory=list)


#: The value a row groups under, derived rather than read from a column. For a group a
#: column cannot name: a multi-entity field no site sorts on, or a value that comes from
#: one field on one type and another on another. The order the runs are walked in is the
#: caller's, so a caller passing this sorts the source itself.
GroupKeyFn = Callable[[EntityRow], Any]

#: What the rows are grouped on: a path they are sorted by, or a key derived from each row.
GroupBy = Union[str, GroupKeyFn]


def group_rows(rows: Sequence[EntityRow], by: GroupBy) -> list[RowGroup]:
    groups: list[RowGroup] = []
    key: str | None = None
    for row in rows:
        value = by(row) if callable(by) else cell_value(row, by)
        next_ = json.dumps(value, sort_keys=True, default=str)
        last = groups[-1] if groups else None
        if last is not None and next_ == key:
            last.rows.append(row)
        else:
            groups.append(RowGroup(value=value, rows=[row]))
        key = next_
    return groups


def group_key_text(value: Any) -> str:
    """The text a group key reads as when there is no column to render it by.

    A row reads as its display name, anything else as its own text, and a key that is
    nothing at all as the empty string.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return display_name_of(value, "")
    return str(value)
