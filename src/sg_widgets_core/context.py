"""Widget context.

One object an app builds once and hands to every widget: a cached client, the
schema service, the status table and the site preferences the render layer needs.
Widgets never construct a client or a cache of their own, so two widgets on a page
asking for the same type's fields cost one request.
"""
from __future__ import annotations

import weakref
from dataclasses import dataclass, field

from .client import SgClient
from .presentation import normalize_site_url
from .query import QueryCache, QueryCacheOptions, create_query_cache
from .render import FieldTextOptions
from .schema_service import SchemaService, create_schema_service
from .status_service import StatusService, create_status_service

__all__ = [
    "SITE_TTL_MS",
    "SgContext",
    "SgContextOptions",
    "SitePreferences",
    "context_from_client",
    "create_sg_context",
    "preferences_of",
]

#: One hour. Schema and the Status table are site configuration; they do not move under a session.
SITE_TTL_MS = 3_600_000.0


@dataclass
class SitePreferences:
    """What the site decides about display.

    None of it is on a field: the unit behind a duration is `hours_per_day` from
    `GET /preferences` (field_types/duration), and nothing at all names the frame rate
    behind a timecode (field_types/timecode), so the app supplies that one.
    """

    #: The site's `hours_per_day`; a duration then renders in days.
    hours_per_day: float | None = None
    locale: str | None = None
    #: IANA zone a `date_time` is shown in. Defaults to the render layer's.
    time_zone: str | None = None
    #: Frames a second, for a timecode. Given, a timecode gains its frame digits.
    frame_rate: float | None = None


@dataclass
class SgContextOptions(SitePreferences):
    """The site preferences, plus how long a row read stays fresh and where it came from."""

    #: How long a row read stays fresh. Schema and statuses keep their own hour-long cache. Default 30000.
    ttl_ms: float | None = None
    #: The web app this data comes from, so widgets can link a row to its page.
    site_url: str | None = None


@dataclass
class SgContext:
    #: The cached client. Widgets read rows through this, not through the one passed in.
    client: QueryCache
    schema: SchemaService
    statuses: StatusService
    #: The web app this data comes from, without its trailing slash. Empty when the app named none.
    site_url: str = ""
    #: What the site decides about display. Empty when the app named nothing.
    preferences: SitePreferences = field(default_factory=SitePreferences)

    def invalidate(self) -> None:
        """Drop everything cached. Call it after a write."""
        self.client.invalidate()
        self.schema.invalidate()
        self.statuses.invalidate()


def create_sg_context(client: SgClient, options: SgContextOptions | None = None) -> SgContext:
    """The one object a widget reads a site through."""
    settings = options if options is not None else SgContextOptions()
    rows = create_query_cache(
        client,
        QueryCacheOptions() if settings.ttl_ms is None else QueryCacheOptions(ttl_ms=settings.ttl_ms),
    )
    # Schema and the Status table share a cache of their own, longer than the row reads:
    # `/schema/<Type>/fields` is 48KB and ~330ms (probe 002), and the Status table is one
    # read for the whole site (probe 010).
    site = create_query_cache(client, QueryCacheOptions(ttl_ms=SITE_TTL_MS))
    return SgContext(
        client=rows,
        schema=create_schema_service(site),
        statuses=create_status_service(site),
        site_url=normalize_site_url(settings.site_url),
        preferences=_preferences_from(settings),
    )


def _preferences_from(source: SitePreferences) -> SitePreferences:
    return SitePreferences(
        hours_per_day=source.hours_per_day,
        locale=source.locale,
        time_zone=source.time_zone,
        frame_rate=source.frame_rate,
    )


_by_client: weakref.WeakKeyDictionary[SgClient, SgContext] = weakref.WeakKeyDictionary()


def context_from_client(client: SgClient, options: SgContextOptions | None = None) -> SgContext:
    """The context for a bare client, built once.

    A widget given a client and no context calls this, and every widget on the page
    handed that client shares its caches. The options are read on the first call for a
    client; a later call returns what that one built.
    """
    built = _by_client.get(client)
    if built is not None:
        return built
    context = create_sg_context(client, options)
    _by_client[client] = context
    return context


def preferences_of(context: SgContext | None = None) -> FieldTextOptions:
    """The site preferences a formatter takes, ready to hand to `field_text`."""
    preferences = context.preferences if context is not None else SitePreferences()
    return FieldTextOptions(
        hours_per_day=preferences.hours_per_day,
        locale=preferences.locale,
        time_zone=preferences.time_zone,
        frame_rate=preferences.frame_rate,
    )
