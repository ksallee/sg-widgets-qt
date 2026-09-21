"""The context every demo in the showcase runs against.

The port of `apps/site/src/demos/_shared/client.ts` and the source half of `live.ts`. By default a
demo never talks to a site: `MockClient` answers from fixtures generated from a seed, and
`create_sg_context` wraps it the way an application is expected to, so a demo exercises the caching
path a widget's contract assumes. The latency is deliberately not zero: a widget's loading state is
part of what a reviewer is here to look at.

Live mode reads the site `.env.local` names, through `ShotgunClient.from_env`, and is offered
only when that file holds the three keys. `showcase.paths` says which file that is.

`reads` counts the calls that reached the client, by method name, which is the `window.sgDemoReads`
of upstream: a drive asserts what a page cost.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sg_widgets_core.context import SgContext, SgContextOptions, create_sg_context
from sg_widgets_core.mock import MOCK_NOW, MockClient

from .paths import env_file

__all__ = [
    "ENV_KEYS",
    "MOCK_PROJECT_ID",
    "DemoContext",
    "clear_demo_context",
    "demo_context",
    "env_values",
    "live_available",
]

#: The project the mock fixtures are built around.
MOCK_PROJECT_ID = 70

#: What `.env.local` has to hold for live mode to be offered.
ENV_KEYS: tuple[str, ...] = ("FPT_API_SITE_URL", "FPT_API_SCRIPT_NAME", "FPT_API_API_KEY")

#: The options every mock client here is built with. The clock is pinned to the day the fixtures
#: are dated around, so a relative date filter lands on rows and answers the same on every run.
MOCK_SEED = 1
MOCK_LATENCY_MS = 150


def env_values(path: Path | None = None) -> dict[str, str]:
    """`.env.local` as a mapping. Missing file, empty mapping. Values are never logged."""
    target = path if path is not None else env_file()
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


def _mock_client(reads: dict[str, int], **options: Any) -> Any:
    """The mock, counted. The clock is pinned to the day the fixtures are dated around."""
    built: dict[str, Any] = {"seed": MOCK_SEED, "latency_ms": MOCK_LATENCY_MS, "now": MOCK_NOW}
    built.update(options)
    return _Counting(MockClient(**built), reads)


def _live_client(values: dict[str, str]) -> Any:
    from sg_widgets_core.shotgun_client import ShotgunClient

    env = dict(os.environ)
    env.update({key: value for key, value in values.items() if value})
    return ShotgunClient.from_env(env)


def _wrap(client: Any, site_url: str) -> SgContext:
    return create_sg_context(client, SgContextOptions(site_url=site_url or None))


# --- the context -----------------------------------------------------------------------------


class DemoContext:
    """An `SgContext`, the project a demo on it reads, and what the demos have cost."""

    def __init__(
        self,
        context: SgContext,
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
        """The schema service every widget on this context shares."""
        return self.context.schema

    @property
    def statuses(self) -> Any:
        """The status table, read once for the site."""
        return self.context.statuses

    @property
    def site_url(self) -> str:
        """The web app the rows came from, without its trailing slash."""
        return self.context.site_url

    @property
    def preferences(self) -> Any:
        """What the site decides about display."""
        return self.context.preferences

    def project_for(self, mock_id: int) -> int:
        """The project a demo that names a mock project of its own should read."""
        return self.project_id if self.live else mock_id

    def invalidate(self) -> None:
        """Drop everything cached. Call it after a write."""
        self.context.invalidate()

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

