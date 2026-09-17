"""Query cache.

A `SgClient` decorator that remembers answers, folds concurrent identical calls
into one request, and forgets on demand. It is deliberately tiny and framework
free: the Qt layer wraps it in a worker, it does not reimplement it.

Reads on this API are expensive in ways worth caching. `/schema/<Type>/fields`
is 48KB and ~330ms a type and must never be looped (probe 002), and a picker
that re-asks for the same page on every keystroke pays ~270ms a call (probe
053). A read is invalidated by `invalidate()` or by a write through this cache:
`create`, `update` and `upload` are never cached, and each drops every cached
row read of the type it touched, and every cached thread, before it returns.
"""
from __future__ import annotations

import dataclasses
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .client import (
    EntityRow,
    EntityTypeInfo,
    EventLogOptions,
    EventLogResult,
    FollowingOptions,
    HierarchyNode,
    HierarchyPath,
    Page,
    SearchOptions,
    SearchResult,
    SgClient,
    SummarizeOptions,
    SummarizeResult,
    TextSearchRow,
    ThreadRow,
    UploadFile,
    UploadResult,
)
from .filter import EntityRef, TextSearchFilter
from .schema import FieldSchema
from .status import StatusRecord

__all__ = ["QueryCache", "QueryCacheOptions", "create_query_cache"]


@dataclass
class QueryCacheOptions:
    """How long an answer stays fresh, and where the clock comes from."""

    #: How long a resolved value stays fresh, in milliseconds. Default 30000.
    #: `math.inf` keeps values until `invalidate()`; `0` disables caching and leaves
    #: only the in-flight deduping.
    ttl_ms: float = 30_000.0
    #: Monotonic seconds. Injected so a test can move time without sleeping.
    now: Callable[[], float] = time.monotonic


def _stable(value: Any) -> str:
    """Stable JSON: object keys sorted, so `{fields, filters}` and `{filters, fields}` are one key."""
    if value is None:
        return "null"
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _stable(dataclasses.asdict(value))
    if isinstance(value, (str, bool, int, float)):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_stable(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(f"{json.dumps(str(k))}:{_stable(value[k])}" for k in sorted(value, key=str)) + "}"
    return json.dumps(str(value))


def _key_of(method: str, args: list[Any]) -> str:
    return f"{method}:{_stable(args)}"


@dataclass
class _Entry:
    value: Any
    expires_at: float


class _Flight:
    """One read in progress. Its lock is held until the read answers."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.lock.acquire()
        self.value: Any = None
        self.error: BaseException | None = None


class QueryCache:
    """An `SgClient` that answers from memory where it can."""

    def __init__(self, client: SgClient, options: QueryCacheOptions | None = None) -> None:
        settings = options if options is not None else QueryCacheOptions()
        self._client = client
        self._ttl_ms = settings.ttl_ms
        self._now = settings.now
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}
        self._in_flight: dict[str, _Flight] = {}

    def _run(self, method: str, args: list[Any], call: Callable[[], Any]) -> Any:
        key = _key_of(method, args)
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None:
                if hit.expires_at > self._now():
                    return hit.value
                del self._entries[key]
            pending = self._in_flight.get(key)
            # Two concurrent identical calls share one request.
            if pending is None:
                flight = _Flight()
                self._in_flight[key] = flight
            else:
                flight = pending
        if pending is not None:
            with flight.lock:
                pass
            if flight.error is not None:
                raise flight.error
            return flight.value
        try:
            value = call()
        except BaseException as error:
            # Errors are never cached, so the next call retries rather than replaying the failure.
            with self._lock:
                if self._in_flight.get(key) is flight:
                    del self._in_flight[key]
            flight.error = error
            flight.lock.release()
            raise
        with self._lock:
            # A value invalidated while its request was in flight must not come back.
            if self._in_flight.get(key) is flight:
                del self._in_flight[key]
                if self._ttl_ms > 0:
                    self._entries[key] = _Entry(value=value, expires_at=self._now() + self._ttl_ms / 1000.0)
        flight.value = value
        flight.lock.release()
        return value

    def _drop(self, prefix: str, flights: bool = True) -> None:
        with self._lock:
            for key in [k for k in self._entries if k.startswith(prefix)]:
                del self._entries[key]
            if not flights:
                return
            for key in [k for k in self._in_flight if k.startswith(prefix)]:
                del self._in_flight[key]

    def _invalidate_searches(self, entity_type: str) -> None:
        self._drop(f'search:[{json.dumps(entity_type)}')
        self._drop("text_search", flights=False)
        self._drop(f'summarize:[{json.dumps(entity_type)}', flights=False)

    def _invalidate_threads(self) -> None:
        """Every cached thread goes.

        A write may land in a thread: a Reply names its Note in `entity`, an Attachment
        in `attachment_links`, and a Note's own row is the thread's first line
        (get_entity_notes_id_thread_contents).
        """
        self._drop("thread_contents")

    def entity_types(self) -> list[EntityTypeInfo]:
        return self._run("entity_types", [], lambda: self._client.entity_types())

    def fields(self, entity_type: str, project_id: int | None = None) -> dict[str, FieldSchema]:
        # `project_id` changes only `hidden_values` (probe 009), but it is still a different answer.
        return self._run("fields", [entity_type, project_id], lambda: self._client.fields(entity_type, project_id))

    def field_with_project(self, entity_type: str, field: str, project_id: int) -> FieldSchema:
        return self._run(
            "field_with_project",
            [entity_type, field, project_id],
            lambda: self._client.field_with_project(entity_type, field, project_id),
        )

    def search(self, entity_type: str, options: SearchOptions) -> SearchResult:
        return self._run("search", [entity_type, options], lambda: self._client.search(entity_type, options))

    def text_search(
        self,
        text: str,
        entity_types: dict[str, TextSearchFilter],
        page: Page | None = None,
    ) -> list[TextSearchRow]:
        return self._run(
            "text_search",
            [text, entity_types, page],
            lambda: self._client.text_search(text, entity_types, page),
        )

    def statuses(self) -> list[StatusRecord]:
        return self._run("statuses", [], lambda: self._client.statuses())

    def summarize(self, entity_type: str, options: SummarizeOptions | None = None) -> SummarizeResult:
        return self._run("summarize", [entity_type, options], lambda: self._client.summarize(entity_type, options))

    def hierarchy_search(self, root_path: str, entity: EntityRef) -> list[HierarchyPath]:
        # A search result's path is asked for once per row shown, so deduping it matters
        # more here than caching it: several rows of one query hit the same branch.
        return self._run(
            "hierarchy_search",
            [root_path, entity.type, entity.id],
            lambda: self._client.hierarchy_search(root_path, entity),
        )

    def hierarchy_expand(self, path: str) -> HierarchyNode:
        # One level per call, so a tree that walks a project is one cached entry per node
        # (post_hierarchy_expand).
        return self._run("hierarchy_expand", [path], lambda: self._client.hierarchy_expand(path))

    def thread_contents(self, note_id: int, entity_fields: dict[str, list[str]] | None = None) -> list[ThreadRow]:
        return self._run(
            "thread_contents",
            [note_id, entity_fields],
            lambda: self._client.thread_contents(note_id, entity_fields),
        )

    def event_log(self, options: EventLogOptions | None = None) -> EventLogResult:
        # Never cached: a change feed answered from a cache reports that nothing changed.
        return self._client.event_log(options)

    def following(self, user_id: int, options: FollowingOptions | None = None) -> list[EntityRef]:
        return self._run("following", [user_id, options], lambda: self._client.following(user_id, options))

    def create(self, entity_type: str, body: dict[str, Any]) -> EntityRow:
        row = self._client.create(entity_type, body)
        self._invalidate_searches(entity_type)
        self._invalidate_threads()
        return row

    def upload(self, entity_type: str, id: int, file: UploadFile) -> UploadResult:
        result = self._client.upload(entity_type, id, file)
        # The row gained a field value or an Attachment, and the Attachment is a new row.
        self._invalidate_searches(entity_type)
        self._invalidate_searches("Attachment")
        self._invalidate_threads()
        return result

    def update(self, entity_type: str, id: int, patch: dict[str, Any]) -> EntityRow:
        row = self._client.update(entity_type, id, patch)
        # Every cached page of the type is now stale, including one whose filter or sort
        # the change moved the row out of.
        self._invalidate_searches(entity_type)
        self._invalidate_threads()
        return row

    def invalidate(self, prefix: str | None = None) -> None:
        """Forget cached values.

        With no argument, all of them. With a prefix, every key that starts with it; a
        key is `<method>:<json args>`, so `'fields'` drops every schema read and
        `'fields:["Shot"'` drops only Shot's.
        """
        if prefix is None:
            with self._lock:
                self._entries.clear()
                self._in_flight.clear()
            return
        self._drop(prefix)


def create_query_cache(client: SgClient, options: QueryCacheOptions | None = None) -> QueryCache:
    """A cache in front of a client. Widgets read through this, never through the client."""
    return QueryCache(client, options)
