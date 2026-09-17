"""The search model both search widgets share.

`POST /entity/_text_search` matches a row when *every* whitespace-separated word of
the query appears in it, so "pub ad" finds "Published Ada"
(053_text_search_matching). The same rule drives what a result row bolds.

The endpoint answers a thin row, name, the linked row's type and name, and a status
code, and has no `fields` parameter, so anything a result row shows beyond that is a
second read (post_entity_text_search). `hydrate` is that read, one `search` per type
over the page just returned.

Timing lives in the Qt layer. `RequestGate` is the ticket alone and `PressGate` reads
an injectable clock; `sg_widgets_qt.workers` supplies the timers and the debounce.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Literal, Protocol

from .client import SgClient, TextSearchRow
from .filter import EntityRef, WireCondition
from .schema import display_name_of

__all__ = [
    "HIERARCHY_LEAF_LIMIT",
    "PRESS_WINDOW_MS",
    "QUERY_PLANS",
    "SEARCH_DEBOUNCE_MS",
    "SEARCH_PAGE_SIZE",
    "SEARCH_VIEWS",
    "FieldLookup",
    "MatchRun",
    "PressGate",
    "QueryPlan",
    "RequestGate",
    "SearchHit",
    "SearchLink",
    "SearchView",
    "SearchViewState",
    "breadcrumb",
    "has_more_page",
    "hydrate",
    "match_runs",
    "matches_every_word",
    "path_refs",
    "prepend_recent",
    "press_gate",
    "project_of_path",
    "query_plan",
    "request_gate",
    "scope_to_project",
    "search_type_map",
    "search_view",
    "search_words",
    "to_search_hit",
]

_WHITESPACE = re.compile(r"\s+")


def search_words(text: str) -> list[str]:
    """The words the API matches on: whitespace-separated, empties dropped."""
    return [word for word in _WHITESPACE.split(text.strip()) if word]


@dataclass
class MatchRun:
    """One stretch of a label, either inside a matched word or outside every one."""

    text: str
    match: bool


def match_runs(label: str, query: str) -> list[MatchRun]:
    """Split a label into alternating plain and matched runs, one run per stretch.

    Matching is case-insensitive and every word is highlighted wherever it occurs,
    because that is what the server matched on. Overlapping words merge into one run,
    so a run never nests and the runs always rebuild the label exactly.

    The result is text, never markup: a widget draws each run and never sets markup
    from a row.
    """
    if len(label) == 0:
        return []
    words = search_words(query)
    if len(words) == 0:
        return [MatchRun(text=label, match=False)]

    haystack = label.lower()
    ranges: list[list[int]] = []
    for word in words:
        needle = word.lower()
        at = haystack.find(needle)
        while at != -1:
            ranges.append([at, at + len(needle)])
            at = haystack.find(needle, at + 1)
    if len(ranges) == 0:
        return [MatchRun(text=label, match=False)]

    ranges.sort(key=lambda r: (r[0], r[1]))
    merged: list[list[int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    runs: list[MatchRun] = []
    cursor = 0
    for start, end in merged:
        if start > cursor:
            runs.append(MatchRun(text=label[cursor:start], match=False))
        runs.append(MatchRun(text=label[start:end], match=True))
        cursor = end
    if cursor < len(label):
        runs.append(MatchRun(text=label[cursor:], match=False))
    return runs


def matches_every_word(text: str, query: str) -> bool:
    """True when every word of the query appears in the text, the server's own rule."""
    haystack = text.lower()
    return all(word.lower() in haystack for word in search_words(query))


# -------------------------------------------------------------------------- #
# result rows                                                                 #
# -------------------------------------------------------------------------- #


@dataclass
class SearchLink:
    """The row `_text_search` also matched the words against. Two bare strings, not a reference."""

    type: str
    name: str


@dataclass
class SearchHit:
    """One search result, with what a row needs to draw itself."""

    #: The row, `name` filled from the search answer.
    ref: EntityRef
    #: Status code, never a label.
    status: str | None = None
    #: The row `_text_search` also matched the words against, when the row links to one.
    link: SearchLink | None = None
    #: `image`, when the type has one. Presigned and short-lived (field_types/image).
    image: str | None = None
    #: The row's project, `name` being its `cached_display_name`. None on a site-wide type.
    project: EntityRef | None = None
    #: Values of the second read, so a row anatomy reads any field a caller asked for.
    values: dict[str, Any] = dc_field(default_factory=dict)


def to_search_hit(row: TextSearchRow) -> SearchHit:
    """A hit with only what `_text_search` itself answers."""
    link_type, link_name = row.links
    return SearchHit(
        ref=EntityRef(type=row.type, id=row.id, name=row.name),
        status=row.status,
        link=SearchLink(type=link_type, name=link_name) if link_type and link_name else None,
        image=None,
        project=None,
        values={},
    )


#: The identity fields a type may be named by. Unknown ones are dropped at 200 (probe 003).
_DISPLAY_FIELDS: tuple[str, ...] = ("cached_display_name", "code", "name", "content")


def hydrate(
    client: SgClient,
    rows: list[TextSearchRow],
    fields: Sequence[str] | None = None,
    label_field: str | None = None,
) -> list[SearchHit]:
    """Fill in what `_text_search` does not answer: one `search` per type over the ids just returned.

    An unknown field name is dropped at 200, so asking every type for `image`,
    `project` and whatever a row anatomy names is safe even where the type carries
    none of it (probe 003).
    """
    from .client import SearchOptions

    hits = [to_search_hit(row) for row in rows]
    if len(hits) == 0:
        return hits
    by_type: dict[str, list[int]] = {}
    for hit in hits:
        by_type.setdefault(hit.ref.type, []).append(hit.ref.id)
    wanted: list[str] = []
    for name in ("id", "image", "project", *_DISPLAY_FIELDS, *(fields or ())):
        if name not in wanted:
            wanted.append(name)

    rows_by_id: dict[str, Any] = {}
    for entity_type, ids in by_type.items():
        filters = {"logical_operator": "and", "conditions": [["id", "in", list(ids)]]}
        result = client.search(
            entity_type,
            SearchOptions(fields=list(wanted), filters=filters, page={"size": len(ids)}),
        )
        for row in result.data:
            rows_by_id[f"{entity_type}:{row.id}"] = row

    for hit in hits:
        row = rows_by_id.get(f"{hit.ref.type}:{hit.ref.id}")
        if row is None:
            continue
        values = dict(row.values)
        hit.values = values
        image = values.get("image")
        hit.image = image if isinstance(image, str) else None
        hit.project = _entity_ref_of(values.get("project"))
        labelled = values.get(label_field) if label_field is not None else None
        name = labelled if isinstance(labelled, str) and len(labelled) > 0 else display_name_of(values)
        if name:
            hit.ref = EntityRef(type=hit.ref.type, id=hit.ref.id, name=name)
    return hits


def _entity_ref_of(value: Any) -> EntityRef | None:
    if isinstance(value, EntityRef):
        return value
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return EntityRef(type=value.get("type"), id=value.get("id"), name=name if isinstance(name, str) else None)


# -------------------------------------------------------------------------- #
# scoping                                                                     #
# -------------------------------------------------------------------------- #


class FieldLookup(Protocol):
    """Enough of a schema service to answer whether a type carries a field."""

    def field(self, entity_type: str, name: str) -> Any | None:
        ...


def scope_to_project(
    schema: FieldLookup,
    entity_types: dict[str, list[WireCondition] | None],
    project_id: int,
) -> dict[str, list[WireCondition]]:
    """Add a project condition to every searched type that has a `project` field.

    A type without one 400s on the path rather than returning nothing: Project has no
    `project` field at all (entity_types/Project) and neither does Step
    (entity_types/Step), so the schema decides which types can be scoped.
    """
    scoped: dict[str, list[WireCondition]] = {}
    for entity_type, filter in entity_types.items():
        conditions = list(filter or [])
        if schema.field(entity_type, "project"):
            conditions.append(["project", "is", {"type": "Project", "id": project_id}])
        scoped[entity_type] = conditions
    return scoped


#: The pause a search widget leaves before it asks. Long enough that a typist does not
#: fire a request a letter, short enough to feel live.
SEARCH_DEBOUNCE_MS = 250

#: The page `_text_search` answers at its cap, which is also its default (probe 053).
SEARCH_PAGE_SIZE = 25

#: The rows a hierarchy search asks for. Each hit costs one path lookup on top of the
#: search itself, so it asks for fewer than the endpoint allows.
HIERARCHY_LEAF_LIMIT = 10


def has_more_page(count: int, size: int) -> bool:
    """True when a further page may be there.

    A read carries no total and `links.next` is emitted forever, so a full page is the
    only sign of another one (006_pagination).
    """
    return size > 0 and count >= size


_PROJECT_PATH = re.compile(r"^/Project/(\d+)")


def project_of_path(path: str) -> int | None:
    """The project a tree root path names, or None on the site root."""
    match = _PROJECT_PATH.match(path)
    return int(match.group(1)) if match else None


QueryPlan = Literal["clear", "now", "debounce"]
"""What a search does with the query it now holds: empty the list, ask at once, or ask
once the pause has elapsed."""

QUERY_PLANS: tuple[QueryPlan, ...] = ("clear", "now", "debounce")


def query_plan(query: str, reads_empty: bool) -> QueryPlan:
    """The plan for a query.

    A widget that browses rather than matching reads on an empty query too, which is
    what `reads_empty` says; nothing is debounced there, because no one is typing.
    """
    if len(query.strip()) > 0:
        return "debounce"
    return "now" if reads_empty else "clear"


SearchView = Literal["error", "loading", "empty", "rows"]
"""Which of the four things a search list shows in place of its rows."""

SEARCH_VIEWS: tuple[SearchView, ...] = ("error", "loading", "empty", "rows")


@dataclass
class SearchViewState:
    #: What the failed read said, or None.
    error: str | None = None
    loading: bool = False
    #: Rows on show.
    count: int = 0
    #: An empty list is the empty line only once something has been asked for.
    asked: bool = False


def search_view(state: SearchViewState) -> SearchView:
    """What a search list draws.

    The skeletons stand for a first page only: a page on the way under rows already on
    screen leaves those rows where they are.
    """
    if state.error is not None and state.error != "":
        return "error"
    if state.loading and state.count == 0:
        return "loading"
    if state.count == 0 and state.asked:
        return "empty"
    return "rows"


class RequestGate:
    """The ticket an answer has to still hold to be written.

    A search cancels by taking the next ticket: whatever is in flight then holds a
    stale one and is dropped rather than landing over the query that replaced it.
    """

    def __init__(self) -> None:
        self._current = 0

    def next(self) -> int:
        """Take the next ticket. Every earlier one is stale from here on."""
        self._current += 1
        return self._current

    def cancel(self) -> None:
        """Drop whatever is in flight without starting anything."""
        self._current += 1

    def holds(self, ticket: int) -> bool:
        """True while `ticket` is the one that may write."""
        return ticket == self._current


def request_gate() -> RequestGate:
    return RequestGate()


#: How long a press stays answerable for what it set off. A press that replaces the rows
#: under it does so while the event it started is still unfolding, and each toolkit
#: flushes that on its own schedule, so the mark outlives the press by a little and no
#: longer.
PRESS_WINDOW_MS = 400


def _monotonic_ms() -> float:
    return time.monotonic() * 1000.0


class PressGate:
    """The press a replacement is the consequence of.

    A press inside a list that replaces the rows under it leaves the caret on a row
    that is gone. `mark` is the press; `takes` answers true once, to whatever the press
    led to inside the window.

    `clock` reads milliseconds and is injected, so the model carries no timer.
    """

    def __init__(self, window_ms: int = PRESS_WINDOW_MS, clock: Callable[[], float] | None = None) -> None:
        self._window_ms = window_ms
        self._clock = clock if clock is not None else _monotonic_ms
        self._at = float("-inf")

    def mark(self) -> None:
        """A press landed inside the list."""
        self._at = self._clock()

    def takes(self) -> bool:
        """True when a press is still answerable, and spends it."""
        fresh = self._clock() - self._at < self._window_ms
        self._at = float("-inf")
        return fresh


def press_gate(window_ms: int = PRESS_WINDOW_MS, clock: Callable[[], float] | None = None) -> PressGate:
    return PressGate(window_ms, clock)


def search_type_map(
    types: list[str] | dict[str, list[WireCondition] | None],
) -> dict[str, list[WireCondition] | None]:
    """The types to search, as the map `_text_search` takes: bare names carry no filter."""
    if isinstance(types, list):
        return {entity_type: None for entity_type in types}
    return types


def prepend_recent(
    recents: Sequence[Any],
    picked: Any,
    limit: int,
    key_of: Callable[[Any], str],
) -> list[Any]:
    """A list of what was picked before, newest first.

    The new entry leads, the one it repeats is dropped, and the list is cut to `limit`.
    """
    key = key_of(picked)
    out = [picked, *(item for item in recents if key_of(item) != key)]
    return out[:limit]


# -------------------------------------------------------------------------- #
# hierarchy paths                                                             #
# -------------------------------------------------------------------------- #

_TYPE_SEGMENT = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_DIGITS = re.compile(r"^\d+$")


def path_refs(path: str | Iterable[str]) -> list[EntityRef]:
    """The rows a tree path runs through, root first.

    A path is read left to right. A capitalised segment names the type the level below
    is drawn from; `<Type>/<id>` and `<field>/<Type>/<id>` are a row of that type, and a
    bare `id/<n>` is a row of the type the last folder named. The path runs through
    field names such as `sg_sequence`, because the tree follows the site's own
    navigation configuration rather than a fixed hierarchy (post_hierarchy_search).
    """
    if isinstance(path, str):
        deepest = path
    else:
        paths = list(path)
        deepest = paths[-1] if paths else ""
    segments = [s for s in deepest.split("/") if s]
    refs: list[EntityRef] = []
    folder: str | None = None
    i = 0
    while i < len(segments):
        segment = segments[i]
        next_segment = segments[i + 1] if i + 1 < len(segments) else None
        if segment == "id" and next_segment is not None and folder:
            refs.append(EntityRef(type=folder, id=int(next_segment)))
            i += 2
            continue
        if not _TYPE_SEGMENT.match(segment):
            i += 1
            continue
        if next_segment is not None and _DIGITS.match(next_segment):
            # A grouping such as `sg_sequence/Sequence/23` is a row on the way, and it
            # does not change the type the leaves below it are drawn from.
            refs.append(EntityRef(type=segment, id=int(next_segment)))
            i += 2
            continue
        folder = segment
        i += 1
    return refs


def breadcrumb(path: Any) -> list[str]:
    """The breadcrumb a hierarchy row shows: the path rendered for a person, then the row."""
    above = [part for part in path.path_label.split(" > ") if part] if path.path_label else []
    return [*above, path.label]
