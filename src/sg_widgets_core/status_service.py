"""Status service.

The site's Status table, read once and indexed by code. A Status carries the
colour and the icon; the codes a given field offers come from the field schema
instead (probe 009), so this answers "what does `apr` look like", never "may I
use `apr` here".

Statuses are site-wide and keyed by code, not per entity type (probe 010).
"""
from __future__ import annotations

import threading
from collections.abc import Mapping

from .client import SgClient
from .query import QueryCache
from .status import StatusRecord

__all__ = ["StatusService", "create_status_service"]


def _is_query_cache(client: SgClient | QueryCache) -> bool:
    return callable(getattr(client, "invalidate", None))


class StatusService:
    """Every Status on the site, read once and kept by code."""

    def __init__(self, client: SgClient | QueryCache) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._table: dict[str, StatusRecord] | None = None

    def _load(self) -> dict[str, StatusRecord]:
        # The lock is held across the read, so two threads asking at once cost one call.
        with self._lock:
            if self._table is not None:
                return self._table
            # A failure is not remembered, so the next call retries.
            records = self._client.statuses()
            index: dict[str, StatusRecord] = {}
            for record in records:
                if record.code not in index:
                    index[record.code] = record
            self._table = index
            return index

    def all(self) -> list[StatusRecord]:
        """Every Status on the site. Fetched once."""
        return list(self._load().values())

    def by_code(self) -> Mapping[str, StatusRecord]:
        """The table indexed by code. The first row wins when a code repeats."""
        return self._load()

    def record(self, code: str) -> StatusRecord | None:
        """One status, or None for a code with no Status behind it, such as a plain `list` value."""
        return self._load().get(code)

    def invalidate(self) -> None:
        with self._lock:
            self._table = None
        # A shared cache holds the same read, so drop it there too or the next load replays it.
        if _is_query_cache(self._client):
            self._client.invalidate("statuses")


def create_status_service(client: SgClient | QueryCache) -> StatusService:
    """The Status table over a client, or over a cache several services share."""
    return StatusService(client)
