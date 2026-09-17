"""Client adapter.

Widgets talk to a `SgClient` and nothing else. The implementations live beside it:
`shotgun_api3` against a site, the mock against generated fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Literal, Protocol, TypedDict

from .filter import EntityRef, TextSearchFilter, WireCondition, WireGroup
from .schema import FieldSchema
from .status import StatusRecord

__all__ = [
    "EVENT_LOG_FIELDS",
    "SUMMARY_TYPES",
    "EntityRow",
    "EntityTypeInfo",
    "EventLogEntry",
    "EventLogOptions",
    "EventLogResult",
    "FollowingOptions",
    "HierarchyNode",
    "HierarchyPath",
    "HierarchyRef",
    "Page",
    "RawHierarchyNode",
    "SearchOptions",
    "SearchResult",
    "SgApiError",
    "SgClient",
    "SummarizeOptions",
    "SummarizeResult",
    "SummaryField",
    "SummaryGroup",
    "SummaryGrouping",
    "SummaryType",
    "TextSearchRow",
    "ThreadAuthor",
    "ThreadRow",
    "UploadFile",
    "UploadResult",
    "event_log_filters",
    "hierarchy_entity",
    "normalize_event_log_entry",
    "normalize_hierarchy_node",
    "plural_path",
]


class Page(TypedDict, total=False):
    """One page of a read: `size` rows starting at page `number`, which is one-based."""

    size: int
    number: int


@dataclass
class SearchOptions:
    filters: WireGroup | None = None
    fields: list[str] | None = None
    sort: str | None = None
    page: Page | None = None


@dataclass
class EntityRow:
    """One row of a search, its attributes, links and dotted fields in one flat map."""

    type: str
    id: int
    values: dict[str, Any] = dc_field(default_factory=dict)


@dataclass
class SearchResult:
    data: list[EntityRow] = dc_field(default_factory=list)
    #: True when another page exists. Computed from data length, not `links.next`,
    #: which is emitted on empty pages too (probe 006).
    has_more: bool = False


@dataclass
class TextSearchRow:
    """Row of `_text_search`, which is flattened and not the search shape.

    There is no `fields` parameter: every row is name, links and status whatever the
    type, so a caller that needs a thumbnail or a project re-reads with `search`
    (post_entity_text_search).
    """

    type: str
    id: int
    name: str
    #: The linked row's type and name, `('', '')` when it links to nothing. Two bare strings, not a reference.
    links: tuple[str, str] = ("", "")
    #: Status code, never a label.
    status: str | None = None


@dataclass
class HierarchyRef:
    """What a navigation node stands for.

    `entity` carries a `{type, id}`, `entity_type` a bare schema name; other kinds are
    passed through as the site sends them.
    """

    kind: str
    value: EntityRef | str | None = None


@dataclass
class HierarchyNode:
    """One level of the navigation tree the web interface draws (post_hierarchy_expand)."""

    label: str
    ref: HierarchyRef
    #: The path to pass back to `hierarchy_expand` to open this node.
    path: str
    parent_path: str | None = None
    #: False when expanding this node would return nothing.
    has_children: bool = False
    #: One level only: a child's own children come from its own call.
    children: list[HierarchyNode] = dc_field(default_factory=list)


@dataclass
class HierarchyPath:
    """Where one row sits in the navigation tree, as a hierarchy search answers it."""

    #: The row's own display name.
    label: str
    #: The same breadcrumb rendered for a person. The project is not in it.
    path_label: str
    #: One path per level, root first; the last entry is the row itself.
    incremental_path: list[str]
    ref: EntityRef
    project_id: int | None = None


def hierarchy_entity(ref: HierarchyRef | None) -> EntityRef | None:
    """The row a node stands for, or None when it stands for a type or nothing."""
    if ref is None or ref.kind != "entity" or not isinstance(ref.value, EntityRef):
        return None
    return ref.value


SummaryType = Literal[
    "record_count", "count", "sum", "maximum", "minimum", "average", "earliest", "latest",
    "percentage", "status_percentage", "status_percentage_as_float", "status_list", "checked", "unchecked",
]
"""The aggregates a summarize offers. The endpoint prints the whole set in the 400 it
answers a bogus one (020_summarize)."""

SUMMARY_TYPES: tuple[SummaryType, ...] = (
    "record_count", "count", "sum", "maximum", "minimum", "average", "earliest", "latest",
    "percentage", "status_percentage", "status_percentage_as_float", "status_list", "checked", "unchecked",
)


@dataclass
class SummaryField:
    field: str
    type: SummaryType


@dataclass
class SummaryGrouping:
    field: str
    #: Default `exact`, one group per distinct value.
    type: str | None = None
    direction: Literal["asc", "desc"] | None = None


@dataclass
class SummarizeOptions:
    filters: WireGroup | None = None
    #: Default `[SummaryField('id', 'count')]`. One type per field per call: the last entry wins (020_summarize).
    summary_fields: list[SummaryField] | None = None
    grouping: list[SummaryGrouping] | None = None


@dataclass
class SummaryGroup:
    #: The server's render of the value, for display. Not unique.
    group_name: str
    #: What the grouping was computed on. Key on this (020_summarize).
    group_value: Any = None
    summaries: dict[str, float] = dc_field(default_factory=dict)


@dataclass
class SummarizeResult:
    #: Keyed by field name. A field that cannot be summarized answers 200 with the key absent.
    summaries: dict[str, float] = dc_field(default_factory=dict)
    groups: list[SummaryGroup] = dc_field(default_factory=list)


@dataclass
class EntityTypeInfo:
    name: str
    display_name: str


@dataclass
class ThreadAuthor(EntityRef):
    """Who wrote a thread row.

    A Reply's hash carries a fourth key, `image`, a presigned avatar re-signed on every
    read; the `created_by` hash on a Note and an Attachment has none
    (get_entity_notes_id_thread_contents).
    """

    image: str | None = None


@dataclass
class ThreadRow:
    """One row of a note thread, flat and not the search shape."""

    #: `Note`, `Attachment` or `Reply`.
    type: str
    id: int
    created_at: str | None = None
    #: The body. An Attachment row has none.
    content: str | None = None
    author: ThreadAuthor | None = None
    #: The row as it arrived, including whatever `entity_fields` widened it by.
    fields: dict[str, Any] = dc_field(default_factory=dict)


@dataclass
class EventLogOptions:
    """Which rows the event log answers.

    `meta` holds what changed and takes neither a filter nor a sort, so the cut is made
    on these and `meta` is read off the row (025_event_log).
    """

    project_id: int | None = None
    #: The row the events are about. It is null on an event whose target has been
    #: deleted, so a deleted row's history is reachable by `event_type` and dates alone.
    entity: EntityRef | None = None
    #: One event type or several, e.g. `Shotgun_Shot_Change`.
    event_type: str | list[str] | None = None
    #: The field that changed. Site-wide on its own, so pair it with `entity` or `event_type`.
    attribute_name: str | None = None
    #: Keep events after this `date_time`, as `created_at greater_than`.
    since: str | None = None
    #: Keep events before this `date_time`, as `created_at less_than`.
    until: str | None = None
    page: Page | None = None


def event_log_filters(options: EventLogOptions | None = None) -> WireGroup:
    """The cut the event log takes, as the `and` group a search wants.

    Nothing here touches `meta`: it takes no filter (025_event_log).
    """
    if options is None:
        options = EventLogOptions()
    conditions: list[WireCondition] = []
    if options.project_id is not None:
        conditions.append(["project", "is", {"type": "Project", "id": options.project_id}])
    if options.entity:
        conditions.append(["entity", "is", {"type": options.entity.type, "id": options.entity.id}])
    if options.event_type is not None:
        conditions.append(
            ["event_type", "in", options.event_type]
            if isinstance(options.event_type, list)
            else ["event_type", "is", options.event_type]
        )
    if options.attribute_name is not None:
        conditions.append(["attribute_name", "is", options.attribute_name])
    if options.since is not None:
        conditions.append(["created_at", "greater_than", options.since])
    if options.until is not None:
        conditions.append(["created_at", "less_than", options.until])
    return {"logical_operator": "and", "conditions": list(conditions)}


EVENT_LOG_FIELDS: tuple[str, ...] = (
    "event_type", "attribute_name", "description", "created_at", "meta", "entity", "project", "user",
)
"""What an event is read with. `audit_trail` is never returned even when it is
named, so it is not asked for (025_event_log)."""


@dataclass
class EventLogEntry:
    """One event, `meta` decoded, with the two values an attribute change carries lifted out."""

    id: int
    event_type: str | None = None
    attribute_name: str | None = None
    #: The rendered English sentence the server writes.
    description: str | None = None
    created_at: str | None = None
    #: None once the row the event is about is deleted; `meta` still names it.
    entity: EntityRef | None = None
    project: EntityRef | None = None
    user: EntityRef | None = None
    #: The whole decoded `meta`. Its keys follow `meta.type`.
    meta: dict[str, Any] | None = None
    #: `meta.old_value`, present on an `attribute_change` and nowhere else.
    old_value: Any = None
    #: `meta.new_value`, present on an `attribute_change` and nowhere else.
    new_value: Any = None


@dataclass
class EventLogResult:
    data: list[EventLogEntry] = dc_field(default_factory=list)
    #: True when another page exists. Read from the row count, as on `search` (probe 006).
    has_more: bool = False


@dataclass
class UploadFile:
    """Bytes to put on a row, and where they land."""

    #: The name the bytes are stored under. Its extension decides the upload type.
    filename: str
    #: The bytes themselves.
    data: bytes
    #: The field in the path, which picks the kind: `image` is a Thumbnail, another
    #: field an Attachment on that field, and no field at all a generic Attachment on
    #: `attachment_links` (recipes/001).
    field: str | None = None


@dataclass
class UploadResult:
    """What the handshake answered. The Attachment it made is visible only on the parent row."""

    #: `Thumbnail` on `image`, `Attachment` on any other form. Nothing in the request names it.
    upload_type: str
    #: The whole `upload_info` the ticket carried and the third call sent back.
    upload_info: dict[str, Any] = dc_field(default_factory=dict)
    #: The storage's `ETag`, when it exposes one; the `PUT` status is the receipt (put_links_upload).
    etag: str | None = None


@dataclass
class FollowingOptions:
    """The two cuts `following` takes. Both are made server-side."""

    #: One type to keep. The schema name and the snake_case plural both work.
    entity: str | None = None
    project_id: int | None = None


class SgClient(Protocol):
    """What a widget reads a site through."""

    def entity_types(self) -> list[EntityTypeInfo]:
        """Enabled entity types on the site with their display names."""

    def fields(self, entity_type: str, project_id: int | None = None) -> dict[str, FieldSchema]:
        """All fields of a type. Pass `project_id` to get `hidden_values` on status and list fields."""

    def field_with_project(self, entity_type: str, field: str, project_id: int) -> FieldSchema:
        """One field at project scope, 1.2KB against 48KB for the whole type (probe 002).

        Only `hidden_values` differs from the site-scope read (probe 009).
        """

    def search(self, entity_type: str, options: SearchOptions) -> SearchResult:
        """Rows of one type, filtered, sorted and paged."""

    def text_search(
        self,
        text: str,
        entity_types: dict[str, TextSearchFilter],
        page: Page | None = None,
    ) -> list[TextSearchRow]:
        """Free-text search across several types at once.

        Every word must match, each as a case-insensitive substring of the row's name or
        of the linked row's name (probe 053). Page size is 1 to 25 and 25 is also the
        default; there is no `links`, so page until the answer is empty.
        """

    def statuses(self) -> list[StatusRecord]:
        """Status entities with colour and icon."""

    def update(self, entity_type: str, id: int, patch: dict[str, Any]) -> EntityRow:
        """Change the named fields of one row and answer the whole record.

        A key left out of `patch` is unchanged, not cleared, and an empty patch is a
        no-op (put_entity_type_id). The answer never resolves a dotted path, so a
        caller that shows one re-reads the row (024_read_after_write).
        """

    def hierarchy_expand(self, path: str) -> HierarchyNode:
        """One level of the site's navigation tree.

        `path` is `/Project/<id>` at the root and a child's own `path` below it
        (post_hierarchy_expand).
        """

    def hierarchy_search(self, root_path: str, entity: EntityRef) -> list[HierarchyPath]:
        """Where a row sits in the navigation tree, under `root_path` (`/Project/<id>`).

        The search criteria takes the literal key `entity` and nothing else: any other
        key answers `search_criteria size must be 1`, which counts the keys it
        recognises rather than the ones sent (post_hierarchy_search).
        """

    def summarize(self, entity_type: str, options: SummarizeOptions | None = None) -> SummarizeResult:
        """Aggregate rows without paging them.

        One `grouping` returns a field's distinct values and their counts (020_summarize).
        """

    def create(self, entity_type: str, body: dict[str, Any]) -> EntityRow:
        """Create one row and answer it.

        `project` is the create contract on a project-scoped type and the schema's
        `mandatory` flags are not it: the identity field is flagged mandatory, is
        optional, and is generated by the server when it is left out (012_create_version).
        An entity link is a `{type, id}` hash; a bare id 400s. Nothing is unique on any
        type measured, so two creates of the same body make two rows: key on `id`.
        """

    def upload(self, entity_type: str, id: int, file: UploadFile) -> UploadResult:
        """Put a file on a row.

        The 201 the handshake answers proves the handshake and not that bytes exist
        (039_upload_silent_failures). A media field is not readable straight after: it
        returns a placeholder under `/images/status/transient/` until the transcode
        lands (recipes/001).
        """

    def thread_contents(self, note_id: int, entity_fields: dict[str, list[str]] | None = None) -> list[ThreadRow]:
        """A Note, its Attachments and its Replies as one list in time order.

        It replaces a search on each of the three types and orders them together.
        `entity_fields` widens a row type, one entry per type; it is accepted and
        changes nothing for Reply, whose extra fields need a search on replies
        (get_entity_notes_id_thread_contents).
        """

    def event_log(self, options: EventLogOptions | None = None) -> EventLogResult:
        """What changed, newest first.

        This is the change log, not the activity stream: a status change written over
        the API was on no stream 430s later (067_notes_in_the_stream). Rows are sorted
        `-id`; `id` and `created_at` are the two orders the type answers, and ids at the
        head are sparse and fill in later, so a cursor on `max(id)` drops events: re-scan
        behind the head or drive the feed from `created_at` and deduplicate on `id`
        (025_event_log).
        """

    def following(self, user_id: int, options: FollowingOptions | None = None) -> list[EntityRef]:
        """Everything one person follows, in one unpaged body.

        Each row is a type and an id: neither the record's name nor the date the
        follow started is returned, so a display list costs a search on the ids.
        The user must be a HumanUser; a script cannot ask what it follows
        (get_entity_human_users_id_following).
        """


class RawHierarchyNode(TypedDict, total=False):
    """The node shape a hierarchy expand answers, before normalising."""

    label: str
    ref: dict[str, Any]
    path: str
    parent_path: str | None
    has_children: bool
    children: list[Any]


def normalize_hierarchy_node(raw: RawHierarchyNode, path: str) -> HierarchyNode:
    """Normalise one node and the level below it.

    The sample response gives a child a `label`, a `ref` and `has_children` but not
    always a `path`, so a child without one is addressed by appending its ref to the
    parent's path (post_hierarchy_expand).
    """
    raw_ref = raw.get("ref") or {}
    ref = HierarchyRef(kind=str(raw_ref.get("kind") or "empty"), value=_ref_value(raw_ref.get("value")))
    own = raw["path"] if raw.get("path") is not None else path
    children = [
        normalize_hierarchy_node(child, _child_path(own, child)) for child in (raw.get("children") or [])
    ]
    return HierarchyNode(
        label=str(raw["label"]) if raw.get("label") is not None else "",
        ref=ref,
        path=own,
        parent_path=raw.get("parent_path"),
        has_children=bool(raw.get("has_children")),
        children=_unique_by_path(children),
    )


def _ref_value(value: Any) -> EntityRef | str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return EntityRef(type=value.get("type"), id=value.get("id"), name=name if isinstance(name, str) else None)
    if isinstance(value, str):
        return value
    return None


def _unique_by_path(nodes: list[HierarchyNode]) -> list[HierarchyNode]:
    """Children keyed by path, first occurrence kept.

    An expand repeats the "no <field>" bucket (`.../Sequence/__none__`) once after every
    group on a grouped level, and the repeats are the same node (post_hierarchy_expand,
    064_hierarchy_expand_buckets).
    """
    seen: set[str] = set()
    out: list[HierarchyNode] = []
    for node in nodes:
        if node.path in seen:
            continue
        seen.add(node.path)
        out.append(node)
    return out


def _child_path(parent_path: str, child: RawHierarchyNode) -> str:
    if isinstance(child.get("path"), str):
        return child["path"]
    ref = child.get("ref") or {}
    value = ref.get("value")
    if ref.get("kind") == "entity_type" and isinstance(value, str):
        return f"{parent_path}/{value}"
    if ref.get("kind") == "entity" and isinstance(value, dict):
        return f"{parent_path}/id/{value.get('id')}"
    return parent_path


class SgApiError(Exception):
    """What the API refused, with the status and the body it answered."""

    def __init__(self, status: int, body: Any, message: str | None = None) -> None:
        super().__init__(message if message is not None else f"Flow PT API error {status}")
        self.status = status
        self.body = body


def _entity_ref_of(value: Any) -> EntityRef | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return EntityRef(type=value.get("type"), id=value.get("id"), name=name if isinstance(name, str) else None)


def normalize_event_log_entry(row: EntityRow) -> EventLogEntry:
    """One row of `EventLogEntry`, with `meta` decoded as the API returns it."""
    v = row.values
    meta = v.get("meta")
    return EventLogEntry(
        id=row.id,
        event_type=v.get("event_type"),
        attribute_name=v.get("attribute_name"),
        description=v.get("description"),
        created_at=v.get("created_at"),
        entity=_entity_ref_of(v.get("entity")),
        project=_entity_ref_of(v.get("project")),
        user=_entity_ref_of(v.get("user")),
        meta=meta,
        old_value=(meta or {}).get("old_value"),
        new_value=(meta or {}).get("new_value"),
    )


def plural_path(entity_type: str) -> str:
    """The path segment a type is addressed by: HumanUser is `human_users`, Status is `statuses`."""
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", entity_type).lower()
    if snake.endswith("s"):
        return f"{snake}es"
    if snake.endswith("y") and not re.search(r"[aeiou]y$", snake):
        return f"{snake[:-1]}ies"
    return f"{snake}s"
