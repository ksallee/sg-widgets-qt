"""The context every demo in the showcase runs against.

The port of `apps/site/src/demos/_shared/client.ts` and the source half of `live.ts`. By default a
demo never talks to a site: `MockClient` answers from fixtures generated from a seed, and
`create_sg_context` wraps it the way an application is expected to, so a demo exercises the caching
path a widget's contract assumes. The latency is deliberately not zero: a widget's loading state is
part of what a reviewer is here to look at.

Live mode reads the site `.env.local` at the repo root names, through `ShotgunClient.from_env`, and
is offered only when that file holds the three keys.

`reads` counts the calls that reached the client, by method name, which is the `window.sgDemoReads`
of upstream: a drive asserts what a page cost.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

__all__ = [
    "ENV_KEYS",
    "MOCK_PROJECT_ID",
    "DemoContext",
    "clear_demo_context",
    "demo_context",
    "env_values",
    "live_available",
    "repo_root",
]

#: The project the mock fixtures are built around.
MOCK_PROJECT_ID = 70

#: What `.env.local` has to hold for live mode to be offered.
ENV_KEYS: tuple[str, ...] = ("FPT_API_SITE_URL", "FPT_API_SCRIPT_NAME", "FPT_API_API_KEY")

#: The options every mock client here is built with. The clock is pinned to the day the fixtures
#: are dated around, so a relative date filter lands on rows and answers the same on every run.
MOCK_SEED = 1
MOCK_LATENCY_MS = 150


def repo_root() -> Path:
    """The checkout this package was imported from."""
    return Path(__file__).resolve().parents[3]


def env_values(path: Path | None = None) -> dict[str, str]:
    """`.env.local` as a mapping. Missing file, empty mapping. Values are never logged."""
    target = path if path is not None else repo_root() / ".env.local"
    out: dict[str, str] = {}
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def live_available(path: Path | None = None) -> bool:
    """True when the three keys live mode needs are on hand."""
    values = env_values(path)
    return all(values.get(key) or os.environ.get(key) for key in ENV_KEYS)


# --- the counting proxy ----------------------------------------------------------------------


class _Counting:
    """A client that counts the calls that reached it, by method name."""

    def __init__(self, client: Any, reads: dict[str, int]) -> None:
        self._client = client
        self._reads = reads

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._client, name)
        if not callable(value):
            return value

        def counted(*args: Any, **kwargs: Any) -> Any:
            self._reads[name] = self._reads.get(name, 0) + 1
            return value(*args, **kwargs)

        return counted


# --- the placeholders ------------------------------------------------------------------------


class _PlaceholderClient:
    """What the demos read until `sg_widgets_core.mock` lands.

    Enough of an `SgClient` for the hello demo to answer: the entity types of a small site.
    """

    NAMES = (
        ("Asset", "Asset"),
        ("Shot", "Shot"),
        ("Sequence", "Sequence"),
        ("Task", "Task"),
        ("Version", "Version"),
        ("Note", "Note"),
        ("HumanUser", "Person"),
        ("Project", "Project"),
    )

    def __init__(self, latency_ms: int = MOCK_LATENCY_MS, **_: Any) -> None:
        self.latency_ms = latency_ms

    def entity_types(self) -> list:
        from sg_widgets_core.client import EntityTypeInfo

        self._wait()
        return [EntityTypeInfo(name=name, display_name=label) for name, label in self.NAMES]

    def statuses(self) -> list:
        self._wait()
        return []

    def _wait(self) -> None:
        import time

        if self.latency_ms:
            time.sleep(self.latency_ms / 1000.0)


class _PlaceholderContext:
    """What wraps a client until `sg_widgets_core.context` lands."""

    def __init__(self, client: Any, site_url: str = "") -> None:
        self.client = client
        self.schema = None
        self.statuses = None
        self.site_url = site_url.rstrip("/")
        self.preferences: dict[str, Any] = {}

    def invalidate(self) -> None:
        """Drop everything cached. There is nothing cached here."""


def _mock_client(reads: dict[str, int], **options: Any) -> Any:
    try:
        from sg_widgets_core.mock import MOCK_NOW, MockClient  # type: ignore[attr-defined]
    except Exception:
        return _Counting(_PlaceholderClient(**options), reads)
    built = {"seed": MOCK_SEED, "latency_ms": MOCK_LATENCY_MS, "now": MOCK_NOW}
    built.update(options)
    return _Counting(MockClient(**built), reads)


def _live_client(values: dict[str, str]) -> Any:
    from sg_widgets_core.shotgun_client import ShotgunClient  # type: ignore[attr-defined]

    env = dict(os.environ)
    env.update({key: value for key, value in values.items() if value})
    return ShotgunClient.from_env(env)


def _wrap(client: Any, site_url: str) -> Any:
    try:
        from sg_widgets_core.context import SgContextOptions, create_sg_context
    except Exception:
        return _PlaceholderContext(client, site_url)
    return create_sg_context(client, SgContextOptions(site_url=site_url or None))


# --- the context -----------------------------------------------------------------------------


class DemoContext:
    """An `SgContext`, the project a demo on it reads, and what the demos have cost."""

    def __init__(
        self,
        context: Any,
        live: bool = False,
        project_id: int = MOCK_PROJECT_ID,
        project_name: str = "",
        reads: dict[str, int] | None = None,
    ) -> None:
        self.context = context
        #: True when the rows come from a real site.
        self.live = live
        #: The project to scope to: the toolbar's pick in live mode, the mock's own otherwise.
        self.project_id = project_id
        #: What that project is called, when the pick carried a name.
        self.project_name = project_name
        #: Calls that reached the client, by method name. Live mode counts nothing.
        self.reads: dict[str, int] = reads if reads is not None else {}

    @property
    def client(self) -> Any:
        """The cached client. A demo reads rows through this."""
        return self.context.client

    @property
    def schema(self) -> Any:
        return getattr(self.context, "schema", None)

    @property
    def statuses(self) -> Any:
        return getattr(self.context, "statuses", None)

    @property
    def site_url(self) -> str:
        return getattr(self.context, "site_url", "")

    @property
    def preferences(self) -> Any:
        return getattr(self.context, "preferences", {})

    def project_for(self, mock_id: int) -> int:
        """The project a demo that names a mock project of its own should read."""
        return self.project_id if self.live else mock_id

    def invalidate(self) -> None:
        """Drop everything cached."""
        invalidate = getattr(self.context, "invalidate", None)
        if callable(invalidate):
            invalidate()

    def reset_reads(self) -> None:
        """Forget what the demos have cost so far."""
        self.reads.clear()


_SHARED: dict[tuple[bool, int], DemoContext] = {}


def demo_context(
    live: bool = False,
    project_id: int | None = None,
    env_path: Path | None = None,
    **mock_options: Any,
) -> DemoContext:
    """The one context the demos share, per source and project.

    A widget keyed on its context rebuilds its reads when it is handed a new one, so the same
    object is answered on every call for one source.
    """
    if live and not live_available(env_path):
        live = False
    key = (live, int(project_id) if project_id is not None else 0)
    if not mock_options:
        found = _SHARED.get(key)
        if found is not None:
            return found
    reads: dict[str, int] = {}
    if live:
        client = _live_client(env_values(env_path))
        site_url = env_values(env_path).get("FPT_API_SITE_URL", "") or os.environ.get(
            "FPT_API_SITE_URL", ""
        )
        built = DemoContext(
            _wrap(client, site_url),
            live=True,
            project_id=int(project_id) if project_id is not None else 0,
            reads=reads,
        )
    else:
        client = _mock_client(reads, **mock_options)
        built = DemoContext(
            _wrap(client, ""),
            live=False,
            project_id=int(project_id) if project_id is not None else MOCK_PROJECT_ID,
            reads=reads,
        )
    if not mock_options:
        _SHARED[key] = built
    return built


def clear_demo_context() -> None:
    """Forget the shared contexts. The next call builds them again."""
    _SHARED.clear()

