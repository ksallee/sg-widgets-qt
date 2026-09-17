"""Entity picker model.

Everything an entity picker does that is not drawing: the filter a query becomes, the
runs a match highlights, the row shape a picker renders, and a controller owning paging,
hydration, cancellation and the error surface. Every picker widget drives this one
controller, so two widgets cannot drift.

Search is one `search` per type. `text_search` is not used: it has no `fields`
parameter, so every row comes back as name, links and status only, and a picker needs a
thumbnail and a sub-label (endpoints/post_entity_text_search).

With nothing typed, or less than `min_query_length`, the same search runs without the
name condition, sorted `-updated_at`, so an open picker lists the rows most recently
worked on rather than nothing. The caller's pre-filter, project scope and exclusions
still apply.

Every read here is synchronous. `sg_widgets_qt.workers` leaves the pause a typist needs,
runs `fetch_page` on a thread and calls `deliver` back on the GUI thread with the ticket
`begin` handed out; an answer whose ticket no longer holds is dropped, so a slow earlier
query can never overwrite a later one. `set_query` and `load_more` do the three steps in
one call, for a caller that is already off the GUI thread.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dc_field
from typing import Any, Callable, Generic, Literal, TypeVar, Union

from .client import EntityRow, SearchOptions, SgClient
from .filter import (
    EntityRef,
    FilterGroup,
    FilterNode,
    WireGroup,
    condition,
    from_wire,
    group,
    is_empty_filter,
    to_api3_hash,
)
from .row import FieldSpec, path_of
from .schema import DISPLAY_NAME_FIELDS, FieldSchema, display_name_of
from .schema_service import SchemaService, create_schema_service
from .search import MatchRun, match_runs, request_gate, search_words

__all__ = [
    "BROWSE_SORT",
    "DEFAULT_DEBOUNCE_MS",
    "DEFAULT_MIN_QUERY_LENGTH",
    "DEFAULT_PAGE_SIZE",
    "ELLIPSIS_CHIPS",
    "PICKER_SUMMARIES",
    "PROJECT_PICKER_FIELDS",
    "USER_PICKER_FIELDS",
    "ChipFit",
    "ChipRow",
    "EntitySearch",
    "EntitySearchOptions",
    "EntitySearchState",
    "HighlightRun",
    "PageResult",
    "PickerRow",
    "PickerSummary",
    "ProjectPickerOptions",
    "SearchField",
    "SearchFieldSpec",
    "SelectionSummary",
    "UserPickerOptions",
    "as_filter_group",
    "clearable_for_field",
    "create_entity_search",
    "entity_key",
    "fit_chips",
    "flatten_row",
    "highlight_runs",
    "is_bare_ref",
    "merge_filters",
    "name_search_filter",
    "placeholder_name",
    "project_picker_filters",
    "prune_filter_to_fields",
    "query_tokens",
    "summarise_selection",
    "to_ref",
    "user_picker_filters",
    "user_picker_search_fields",
    "user_picker_sub_label",
    "user_picker_types",
    "user_search_fields",
    "with_selected_pinned",
]


# -------------------------------------------------------------------------- #
# rows                                                                        #
# -------------------------------------------------------------------------- #


@dataclass
class PickerRow:
    """One searched row, flattened for display."""

    type: str
    id: int
    #: The label, from `label_field` or the display-name chain, never empty.
    name: str = ""
    #: Attributes and relationships in one map. A dotted path is a literal key with dots
    #: in it, not a nested object (003_query), and a relationship is `{type, id, name}`
    #: rather than an envelope.
    values: dict[str, Any] = dc_field(default_factory=dict)


#: Anything a picker keys and names: a reference, a searched row, or a raw row.
RefLike = Union[EntityRef, PickerRow, EntityRow]


def entity_key(ref: RefLike) -> str:
    """The key a picker holds a row under, everywhere.

    A numeric id alone collides: a Shot and an Asset on one site share ids freely, and a
    picker may search both.
    """
    return f"{ref.type}:{ref.id}"


def placeholder_name(ref: RefLike) -> str:
    """`Type 123`, the label a row falls back to when nothing names it."""
    return f"{ref.type} {ref.id}"


def is_bare_ref(ref: EntityRef | PickerRow) -> bool:
    """True when a reference carries no usable name and needs a read to become a row."""
    return not ref.name or len(ref.name) == 0 or ref.name == placeholder_name(ref)


def to_ref(row: PickerRow) -> EntityRef:
    return EntityRef(type=row.type, id=row.id, name=row.name)


def flatten_row(row: EntityRow, label_field: str | None = None) -> PickerRow:
    """Flatten a searched row. `label_field` wins over the display-name chain when set."""
    values = dict(row.values)
    explicit = values.get(label_field) if label_field is not None else None
    if isinstance(explicit, str) and len(explicit) > 0:
        name = explicit
    else:
        name = display_name_of(row.values, placeholder_name(row))
    return PickerRow(type=row.type, id=row.id, name=name, values=values)


# -------------------------------------------------------------------------- #
# the query filter                                                            #
# -------------------------------------------------------------------------- #

query_tokens = search_words
"""The words of a query. The name the pickers were written against; `search_words` is the function."""


@dataclass
class SearchField:
    """One field a query is matched against, and how."""

    path: str
    #: Default `contains`. `starts_with` keeps a shared tail, such as an email domain, out of the match.
    operator: Literal["contains", "starts_with", "ends_with", "is"] | None = None


SearchFieldSpec = Union[str, SearchField]
"""A field name, or a field name with the operator it is matched with."""


def _as_search_field(spec: SearchFieldSpec) -> SearchField:
    return SearchField(path=spec) if isinstance(spec, str) else spec


def name_search_filter(query: str, fields: Sequence[SearchFieldSpec]) -> FilterGroup:
    """The filter a typed query becomes.

    Every word must match, each anywhere in the field, and a word may sit in any one of
    `fields`. So "pub an" finds "Published Anna" and a login search finds a person by
    either half of a name.

    An empty query, or no fields, gives an empty group, which matches every row:
    `"conditions": []` is 200 and unscoped (030_complex_filters). `contains` and
    `starts_with` both work on text fields and through dotted paths, so a field may be
    `entity.Shot.code` (017_filter_operators).
    """
    tokens = search_words(query)
    usable = [field for field in (_as_search_field(spec) for spec in fields) if len(field.path) > 0]
    if len(tokens) == 0 or len(usable) == 0:
        return group("and")
    per_field = [
        group("and", [condition(field.path, field.operator or "contains", token) for token in tokens])
        for field in usable
    ]
    return per_field[0] if len(per_field) == 1 else group("or", list(per_field))


def user_search_fields(query: str) -> list[SearchFieldSpec]:
    """The extra fields a person search matches, for the query as typed.

    The email is always searched, because it is what a person is known by on a site, but
    only on its local part until the query holds an `@`: every address shares one domain,
    so `contains` on "le" matches `example.studio` and with it the whole site. A login
    never holds whitespace, so it is dropped once the query does. The display-name chain
    is searched either way.
    """
    trimmed = query.strip()
    if len(trimmed) == 0:
        return []
    fields: list[SearchFieldSpec] = [
        SearchField(path="email", operator="contains" if "@" in trimmed else "starts_with"),
    ]
    if not any(char.isspace() for char in trimmed):
        fields.append("login")
    return fields


def as_filter_group(filter: FilterGroup | WireGroup | None) -> FilterGroup | None:
    """Accept either the editor tree or the wire shape wherever a caller supplies a filter."""
    if not filter:
        return None
    if isinstance(filter, FilterGroup):
        return filter
    return from_wire(filter)


def prune_filter_to_fields(node: FilterNode, field_names: set[str]) -> FilterNode | None:
    """Drop every condition whose root field the type does not have, and every group left empty by that.

    A picker across several types shares one pre-filter, and a filter naming a field the
    type lacks is a 400 rather than a silent no-op (017_filter_operators), so the
    condition is dropped on the types it cannot apply to. Dropping widens a result set;
    it never narrows one wrongly.
    """
    if node.kind == "condition":
        root = node.path.split(".")[0] if node.path else ""
        return node if root in field_names else None
    conditions = [c for c in (prune_filter_to_fields(one, field_names) for one in node.conditions) if c is not None]
    return None if len(conditions) == 0 else group(node.logical_operator, conditions)


def merge_filters(*parts: FilterNode | None) -> FilterGroup:
    """One `and` of the parts that are not empty. Blank parts are dropped, not sent."""
    return group("and", [part for part in parts if part is not None and not is_empty_filter(part)])


# -------------------------------------------------------------------------- #
# people and projects                                                         #
# -------------------------------------------------------------------------- #


@dataclass
class UserPickerOptions:
    """What a caller narrows a person search with."""

    #: Search script accounts alongside people.
    include_api_users: bool = False
    #: Offer people whose status is `dis`.
    include_inactive: bool = False


USER_PICKER_FIELDS = ["login", "email", "sg_status_list"]
"""Login and email are searched and shown, so they have to be read (entity_types/HumanUser)."""


def user_picker_types(include_api_users: bool) -> list[str]:
    """People and script accounts, in that order."""
    return ["HumanUser", "ApiUser"] if include_api_users else ["HumanUser"]


def user_picker_filters(include_inactive: bool, extra: FilterGroup | WireGroup | None) -> FilterGroup:
    """The active condition, unless inactive people are wanted.

    `sg_status_list` on HumanUser is two codes, `act` and `dis`, and `act` is the default
    (entity_types/HumanUser). ApiUser has no status field, so a picker drops the
    condition on that type rather than sending a filter that would 400.
    """
    return merge_filters(
        as_filter_group(extra),
        None if include_inactive else condition("sg_status_list", "is", "act"),
    )


def user_picker_sub_label(row: PickerRow) -> str:
    """`API user` for a script account, the email for a person, nothing without one."""
    if row.type == "ApiUser":
        return "API user"
    email = row.values.get("email")
    return email if isinstance(email, str) else ""


def user_picker_search_fields(
    extra: Sequence[SearchFieldSpec] | Callable[[str], Sequence[SearchFieldSpec]],
) -> Callable[[str], list[SearchFieldSpec]]:
    """The caller's own search fields, on top of the ones a person is searched by."""

    def fields_for(query: str) -> list[SearchFieldSpec]:
        own = extra(query) if callable(extra) else extra
        return [*user_search_fields(query), *own]

    return fields_for


@dataclass
class ProjectPickerOptions:
    """What a caller narrows a project search with."""

    #: Offer projects whose `archived` checkbox is set.
    include_archived: bool = False


PROJECT_PICKER_FIELDS = ["sg_status", "archived"]
"""Project's status field is `sg_status`, a plain list, not `sg_status_list`."""


def project_picker_filters(include_archived: bool, extra: FilterGroup | WireGroup | None) -> FilterGroup:
    """Archived projects are hidden unless asked for.

    `sg_status` is not a liveness filter and is null on most projects; `archived`,
    `is_template` and `is_demo` are the discriminators (018_project_listing).
    """
    return merge_filters(
        as_filter_group(extra),
        None if include_archived else condition("archived", "is", False),
    )


def clearable_for_field(clearable: bool | None, field: FieldSchema | None) -> bool:
    """Clause 8 of the picker contract: the clear control follows `clearable`.

    A mandatory field never offers one. A field whose schema the widget has not read is
    not mandatory as far as it knows, so the caller's answer stands.
    """
    if field is not None and field.mandatory is True:
        return False
    return True if clearable is None else clearable


# -------------------------------------------------------------------------- #
# highlighting                                                                #
# -------------------------------------------------------------------------- #

HighlightRun = MatchRun
"""A stretch of a label, matched or not. The shape `match_runs` answers."""

highlight_runs = match_runs
"""Split a label into matched and unmatched runs for the current query, the one splitting
`match_runs` does. Kept as the name the pickers were written against."""


# -------------------------------------------------------------------------- #
# option list composition                                                     #
# -------------------------------------------------------------------------- #


def with_selected_pinned(
    rows: Sequence[PickerRow],
    selected: Sequence[EntityRef],
    known: Mapping[str, PickerRow],
) -> list[PickerRow]:
    """Search results first, then any selected row not among them.

    Keyboard picking lands on fresh matches, and a selected row never leaves the list, so
    it stays deselectable with an empty query.
    """
    seen = {entity_key(row) for row in rows}
    out = list(rows)
    for ref in selected:
        key = entity_key(ref)
        if key in seen:
            continue
        seen.add(key)
        found = known.get(key)
        out.append(found if found is not None else PickerRow(
            type=ref.type, id=ref.id, name=ref.name or placeholder_name(ref), values={},
        ))
    return out


# -------------------------------------------------------------------------- #
# the closed control's summary                                                #
# -------------------------------------------------------------------------- #

PickerSummary = Literal["chips", "ellipsis", "count"]
"""What a multi picker's control shows for the selection."""

PICKER_SUMMARIES: tuple[PickerSummary, ...] = ("chips", "ellipsis", "count")

#: Chips `ellipsis` draws before the rest becomes `+n`, when nothing has measured the row.
ELLIPSIS_CHIPS = 3


@dataclass
class ChipFit:
    """How many chips a row shows, and how many it hides behind `+n`."""

    visible: int
    hidden: int


@dataclass
class ChipRow:
    """A measured chip row: each chip's width, the room it has, and the room held back."""

    #: Chip widths in order, each carrying the gap that follows it.
    widths: Sequence[float] = dc_field(default_factory=list)
    #: The room the chips may occupy.
    available: float = 0
    #: Room held back for the `+n` pill, spent only when something is hidden.
    reserve: float = 0


def fit_chips(widths: Sequence[float], available: float, reserve: float) -> ChipFit:
    """How many whole chips fit `available`, taken greedily from the first.

    A chip is never cut: one that does not fit whole is hidden, and so is every chip
    after it. `reserve` is the room the `+n` pill needs, so it is subtracted only once
    the row overflows and the pill is drawn. Each width carries its own trailing gap, so
    `k` chips cost the sum of the first `k` widths whatever follows them.
    """
    total = sum(widths)
    if total <= available:
        return ChipFit(visible=len(widths), hidden=0)
    budget = max(0, available - reserve)
    used = 0.0
    visible = 0
    for width in widths:
        if used + width > budget:
            break
        used += width
        visible += 1
    return ChipFit(visible=visible, hidden=len(widths) - visible)


T = TypeVar("T")


@dataclass
class SelectionSummary(Generic[T]):
    #: The items drawn as chips, in order. Empty under `count`.
    shown: list[T] = dc_field(default_factory=list)
    #: Items past `shown`. Drawn as `+n` beside the chips.
    overflow: int = 0
    #: Every label, comma-joined, for the control's tooltip.
    title: str = ""
    #: `3 selected`, which is the whole control under `count`.
    count_label: str = ""
    #: True while the chips must stay on one line rather than wrap.
    one_line: bool = False


def summarise_selection(
    items: Sequence[T],
    label_of: Callable[[T], str],
    summary: PickerSummary | None = None,
    max: int | None = None,
    fit: ChipRow | None = None,
) -> SelectionSummary[T]:
    """What a multi picker draws for its selection.

    `chips` draws every chip and wraps. `ellipsis`, the default, keeps one line: as many
    whole chips as the measured row fits, then `+n`, with the whole list in the title.
    `count` draws neither and reads `3 selected`. `max` bounds the chips in either chip
    mode; `0` means every chip. An `ellipsis` row nothing has measured yet falls back to
    three chips.
    """
    mode: PickerSummary = summary if summary is not None else "ellipsis"
    asked = max if max is not None else 0
    fitted = (
        fit_chips(fit.widths, fit.available, fit.reserve).visible
        if mode == "ellipsis" and fit is not None
        else None
    )
    if asked > 0:
        limit_base = asked
    elif mode == "ellipsis" and fitted is None:
        limit_base = ELLIPSIS_CHIPS
    else:
        limit_base = 0
    if fitted is None:
        limit = limit_base
    elif limit_base > 0:
        limit = min(fitted, limit_base)
    else:
        limit = fitted
    if mode == "count":
        shown: list[T] = []
    elif fitted is None and limit == 0:
        shown = list(items)
    else:
        shown = list(items[:limit])
    return SelectionSummary(
        shown=shown,
        overflow=len(items) - len(shown),
        title=", ".join(label_of(item) for item in items),
        count_label=f"{len(items)} selected",
        one_line=mode == "ellipsis",
    )


# -------------------------------------------------------------------------- #
# the controller                                                              #
# -------------------------------------------------------------------------- #


@dataclass
class EntitySearchOptions:
    #: A cached client. Every read goes through it, so repeated queries cost one request.
    client: SgClient
    entity_types: list[str] = dc_field(default_factory=list)
    #: Shared schema service. One is built over the client when absent.
    schema: SchemaService | None = None
    #: Field holding the row label. Defaults to the display-name chain.
    label_field: str | None = None
    #: Extra fields the query is matched against, on top of the display-name chain. A
    #: callable is called with the query, so a field is searched only when the query
    #: suits it, and a field may name the operator it is matched with.
    search_fields: Sequence[SearchFieldSpec] | Callable[[str], Sequence[SearchFieldSpec]] | None = None
    #: Field shown right-aligned, rendered by its data type. Nothing is shown without it.
    secondary_field: FieldSpec | None = None
    #: Field shown under the label. Defaults to the entity type when several are searched.
    sub_label_field: FieldSpec | None = None
    #: Field holding the thumbnail URL. `False` hides thumbnails.
    thumbnail: str | bool | None = None
    #: Extra fields to request, so a caller's own sub-label or secondary can be read.
    fields: list[str] | None = None
    #: Caller pre-filter, merged into every request with `and`.
    filters: FilterGroup | WireGroup | None = None
    #: Sugar for a project condition. Skipped on a type that has no project link.
    project_id: int | None = None
    #: Rows to keep out of the results. Pushed into the server filter, per type.
    exclude: list[EntityRef] | None = None
    min_query_length: int | None = None
    page_size: int | None = None
    on_error: Callable[[Exception], None] | None = None


@dataclass
class EntitySearchState:
    #: The query the current rows answer. Highlighting reads this, not the input.
    query: str = ""
    loading: bool = False
    error: Exception | None = None
    rows: list[PickerRow] = dc_field(default_factory=list)
    #: True when another page exists. From a full page, never from `links.next` (006_pagination).
    has_more: bool = False
    #: True when the query is shorter than the minimum, so the rows answer no query.
    too_short: bool = True


@dataclass
class PageResult:
    """One page of one query, before it is written to the state."""

    rows: list[PickerRow] = dc_field(default_factory=list)
    has_more: bool = False


@dataclass
class _TypePlan:
    """What a type can be searched and scoped on."""

    #: `project`, `projects`, or None when the type is not project-scoped.
    project_path: str | None
    #: Every field the type has, so a pre-filter can be pruned to it.
    field_names: set[str]


DEFAULT_MIN_QUERY_LENGTH = 0
DEFAULT_PAGE_SIZE = 20
#: The pause a picker leaves before it asks. The Qt layer owns the timer, not this model.
DEFAULT_DEBOUNCE_MS = 250
#: Most recently worked on first, for the list an open picker shows before anything is typed (026_result_order).
BROWSE_SORT = "-updated_at"


def _as_error(cause: Any) -> Exception:
    return cause if isinstance(cause, Exception) else Exception(str(cause))


class EntitySearch:
    """The query a picker runs, the rows it holds, and the references it has hydrated."""

    def __init__(self, options: EntitySearchOptions) -> None:
        self._opts = options
        self._client: SgClient = options.client
        self._schema: SchemaService = (
            options.schema if options.schema is not None else create_schema_service(options.client)
        )
        self._known: dict[str, PickerRow] = {}
        self._listeners: list[Callable[[EntitySearchState], None]] = []
        #: Keys already asked for, so a failed or empty hydration is not retried forever.
        self._hydrated: set[str] = set()
        #: The fields and the project path of a type. Resolved once, from the cached schema.
        self._plans: dict[str, _TypePlan] = {}
        #: True once a search has run, so changed props reload only a picker already showing rows.
        self._started = False

        self._state = EntitySearchState()
        self._gate = request_gate()
        self._page = 1
        self._disposed = False

    # state ------------------------------------------------------------------ #

    @property
    def state(self) -> EntitySearchState:
        return self._state

    @property
    def known(self) -> Mapping[str, PickerRow]:
        """Rows seen or hydrated so far, by `Type:id`."""
        return self._known

    def subscribe(self, listener: Callable[[EntitySearchState], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _emit(self, **changes: Any) -> None:
        # A new state object on every change, so identity is the signal a view redraws on.
        self._state = replace(self._state, **changes)
        for listener in list(self._listeners):
            listener(self._state)

    def _fail(self, error: Exception) -> None:
        self._emit(loading=False, error=error)
        if self._opts.on_error is not None:
            self._opts.on_error(error)

    def _min_length(self) -> int:
        value = self._opts.min_query_length
        return value if value is not None else DEFAULT_MIN_QUERY_LENGTH

    def _is_browse(self, query: str) -> bool:
        """True when the query carries no name condition, so the request is the plain first page."""
        typed = len(query.strip())
        return typed == 0 or typed < self._min_length()

    # fields ----------------------------------------------------------------- #

    def _plan_for(self, entity_type: str) -> _TypePlan:
        """What a type can be searched and scoped on.

        Unknown field names are dropped: a bogus name in `fields` is a silent 200
        (003_query) but the same name in a filter is a 400 (017_filter_operators), so a
        filter may only name real fields.
        """
        cached = self._plans.get(entity_type)
        if cached is not None:
            return cached
        fields = self._schema.fields(entity_type)
        # Project is site-wide and has no project field; a person's membership is the
        # `projects` multi_entity on the row (entity_types/HumanUser, 018_project_listing).
        if "project" in fields:
            project_path: str | None = "project"
        elif "projects" in fields:
            project_path = "projects"
        else:
            project_path = None
        plan = _TypePlan(project_path=project_path, field_names=set(fields.keys()))
        self._plans[entity_type] = plan
        return plan

    def _search_fields_for(self, query: str) -> list[SearchField]:
        """The fields this query is matched against, before the type is known.

        The first mention of a path wins.
        """
        raw = self._opts.search_fields
        extra: Sequence[SearchFieldSpec] = raw(query) if callable(raw) else (raw or [])
        specs = [
            *DISPLAY_NAME_FIELDS,
            *([self._opts.label_field] if self._opts.label_field else []),
            *extra,
        ]
        by_path: dict[str, SearchField] = {}
        for spec in (_as_search_field(one) for one in specs):
            if spec.path not in by_path:
                by_path[spec.path] = spec
        return list(by_path.values())

    def _requested_fields(self) -> list[str]:
        """The union a row needs to render, deduplicated. Unknown names are dropped at 200."""
        wanted = ["id", "type", *DISPLAY_NAME_FIELDS]
        if self._opts.label_field:
            wanted.append(self._opts.label_field)
        secondary = path_of(self._opts.secondary_field)
        if secondary:
            wanted.append(secondary)
        sub_label = path_of(self._opts.sub_label_field)
        if sub_label:
            wanted.append(sub_label)
        if self._opts.thumbnail is not False:
            wanted.append(self._opts.thumbnail if self._opts.thumbnail else "image")
        wanted.extend(self._opts.fields or [])
        return list(dict.fromkeys(wanted))

    def _excluded_ids(self, entity_type: str) -> list[int]:
        return [ref.id for ref in (self._opts.exclude or []) if ref.type == entity_type]

    def _filters_for(self, entity_type: str, query: str) -> WireGroup | None:
        plan = self._plan_for(entity_type)
        fields = [field for field in self._search_fields_for(query) if field.path in plan.field_names]
        parts: list[FilterNode | None] = [name_search_filter(query, fields)]
        caller = as_filter_group(self._opts.filters)
        pruned = prune_filter_to_fields(caller, plan.field_names) if caller is not None else None
        if pruned is not None:
            parts.append(pruned)
        if self._opts.project_id is not None and plan.project_path:
            parts.append(condition(
                plan.project_path, "is", EntityRef(type="Project", id=self._opts.project_id),
            ))
        excluded = self._excluded_ids(entity_type)
        if len(excluded) > 0:
            parts.append(condition("id", "not_in", excluded))
        return to_api3_hash(merge_filters(*parts))

    # searching --------------------------------------------------------------- #

    def begin(self) -> int:
        """Take the ticket the next answer has to hold, and mark the picker busy.

        Every earlier ticket is stale from here on, so a read the Qt layer left running
        on a thread is dropped rather than written over the query that replaced it.
        """
        ticket = self._gate.next()
        self._started = True
        self._emit(loading=True, error=None)
        return ticket

    def fetch_page(self, query: str, number: int) -> PageResult:
        """Read one page of one query. This is the call the Qt layer runs on a thread."""
        size = self._opts.page_size if self._opts.page_size is not None else DEFAULT_PAGE_SIZE
        fields = self._requested_fields()
        # Nothing typed leaves the rows in id order, which is the oldest work on the site,
        # so the browse list is sorted instead (026_result_order).
        sort = BROWSE_SORT if self._is_browse(query) else None
        rows: list[PickerRow] = []
        has_more = False
        # Types are concatenated in the order the caller gave them, so a multi-type list
        # is stable between queries rather than reordered by the server.
        for entity_type in self._opts.entity_types:
            filters = self._filters_for(entity_type, query)
            result = self._client.search(entity_type, SearchOptions(
                filters=filters, fields=fields, sort=sort, page={"size": size, "number": number},
            ))
            has_more = has_more or result.has_more
            for row in result.data:
                rows.append(flatten_row(row, self._opts.label_field))
        return PageResult(rows=rows, has_more=has_more)

    def deliver(self, ticket: int, query: str, number: int, result: PageResult) -> None:
        """Write a page to the state, if its ticket is still the one that may write."""
        if self._disposed or not self._gate.holds(ticket):
            return
        self._page = number
        self.remember(result.rows)
        self._emit(
            # A browse list answers no query, so nothing in it is highlighted.
            query="" if self._is_browse(query) else query,
            loading=False,
            error=None,
            rows=list(result.rows) if number == 1 else [*self._state.rows, *result.rows],
            has_more=result.has_more,
            too_short=len(query.strip()) < self._min_length(),
        )

    def fail(self, ticket: int, error: Exception) -> None:
        """Surface the failure of a read, if its ticket is still the one that may write."""
        if self._disposed or not self._gate.holds(ticket):
            return
        self._fail(_as_error(error))

    def _run(self, query: str, number: int) -> None:
        ticket = self.begin()
        try:
            result = self.fetch_page(query, number)
        except Exception as cause:
            self.fail(ticket, _as_error(cause))
            return
        self.deliver(ticket, query, number, result)

    def set_query(self, query: str) -> None:
        """Set the typed query and read its first page.

        Under the minimum the name condition is dropped, but the search still runs: the
        list an open picker shows is the first page, not nothing.
        """
        self._emit(query="" if self._is_browse(query) else query)
        self._run(query, 1)

    def load_more(self) -> None:
        """Append the next page of the current query."""
        if not self._state.has_more or self._state.loading:
            return
        self._run(self._state.query, self._page + 1)

    def remember(self, rows: Sequence[PickerRow]) -> None:
        """Remember a row so a selection can be shown before it is searched again."""
        for row in rows:
            self._known[entity_key(row)] = row

    # hydration --------------------------------------------------------------- #

    def hydrate(self, refs: Sequence[EntityRef]) -> None:
        """Read the rows behind bare references, one batched request per type."""
        by_type: dict[str, list[int]] = {}
        for ref in refs:
            key = entity_key(ref)
            if key in self._hydrated:
                continue
            row = self._known.get(key)
            if row is not None and not is_bare_ref(row):
                continue
            if not is_bare_ref(ref):
                # A caller-supplied name is already a row: register it without a request,
                # and never let it overwrite one that was read.
                if key not in self._known:
                    self._known[key] = PickerRow(type=ref.type, id=ref.id, name=ref.name or "", values={})
                self._hydrated.add(key)
                continue
            self._hydrated.add(key)
            by_type.setdefault(ref.type, []).append(ref.id)
        if len(by_type) == 0:
            return

        fields = self._requested_fields()
        for entity_type, ids in by_type.items():
            try:
                result = self._client.search(entity_type, SearchOptions(
                    filters=to_api3_hash(group("and", [condition("id", "in", ids)])),
                    fields=fields,
                    page={"size": len(ids)},
                ))
            except Exception as cause:
                if self._disposed:
                    return
                self._name_missing(entity_type, ids)
                self._fail(_as_error(cause))
                continue
            if self._disposed:
                return
            for row in result.data:
                hydrated = flatten_row(row, self._opts.label_field)
                self._known[entity_key(hydrated)] = hydrated
            # Resolve-then-merge: a hydrated row is never replaced by a bare one.
            self._name_missing(entity_type, ids)
            self._emit()

    def _name_missing(self, entity_type: str, ids: Sequence[int]) -> None:
        for id in ids:
            key = f"{entity_type}:{id}"
            if key not in self._known:
                self._known[key] = PickerRow(
                    type=entity_type, id=id, name=f"{entity_type} {id}", values={},
                )

    # props ------------------------------------------------------------------- #

    def update(self, **changes: Any) -> None:
        """Apply changed props. Resets the results when the request would change."""
        before = self._request_shape()
        schema = changes.pop("schema", None)
        client = changes.pop("client", None)
        for name, value in changes.items():
            setattr(self._opts, name, value)
        if schema is not None and schema is not self._schema:
            self._opts.schema = schema
            self._schema = schema
        elif client is not None and client is not self._client:
            self._opts.client = client
            self._client = client
            self._schema = create_schema_service(client)
            self._plans.clear()
        if self._request_shape() == before:
            return
        self._plans.clear()
        self._hydrated.clear()
        # A picker that has never searched stays idle: the first request is the one its
        # list asks for when it opens.
        if self._started:
            self._run(self._state.query, 1)

    def dispose(self) -> None:
        self._disposed = True
        self._gate.cancel()
        self._listeners.clear()

    def _request_shape(self) -> str:
        """Everything that changes what a request asks for, as one comparable string."""
        raw = self._opts.search_fields
        return repr([
            list(self._opts.entity_types),
            self._opts.label_field,
            "per query" if callable(raw) else _shape_of_fields(raw),
            self._requested_fields(),
            as_filter_group(self._opts.filters),
            self._opts.project_id,
            [entity_key(ref) for ref in (self._opts.exclude or [])],
            self._opts.page_size if self._opts.page_size is not None else DEFAULT_PAGE_SIZE,
            self._opts.min_query_length if self._opts.min_query_length is not None else DEFAULT_MIN_QUERY_LENGTH,
        ])


def _shape_of_fields(fields: Sequence[SearchFieldSpec] | None) -> Any:
    if fields is None:
        return None
    return [spec if isinstance(spec, str) else (spec.path, spec.operator) for spec in fields]


def create_entity_search(options: EntitySearchOptions) -> EntitySearch:
    return EntitySearch(options)

