"""What the collection tests share: a context on the mock, a source, and a way to wait on one.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import time
from typing import Any

from qtpy import QtCore, QtWidgets

from sg_widgets_core.collection import (
    EntitySource,
    EntitySourceOptions,
    create_entity_source,
    resolve_columns,
)
from sg_widgets_core.context import SgContext, SgContextOptions, create_sg_context
from sg_widgets_core.mock import MockClient

__all__ = [
    "SITE",
    "TASK_FIELDS",
    "VERSION_FIELDS",
    "FailingClient",
    "columns_for",
    "drain",
    "mock_context",
    "settle",
    "source_for",
]

#: How long `drain` sleeps on the pool between turns of the event loop.
DRAIN_STEP_MS = 20

#: A site to address rows on, so a status sprite and a linked row have somewhere to point.
SITE = "https://demo.example.com"

#: What a Version row is read under on these pages, and what a Task row is.
VERSION_FIELDS = ("code", "sg_status_list", "user", "created_at")
TASK_FIELDS = ("content", "sg_status_list", "step.Step.code", "due_date")


def mock_context(**options: Any) -> SgContext:
    """A context on the mock, with no latency, so a read settles inside a test."""
    built = {"seed": 1, "latency_ms": 0}
    built.update(options)
    return create_sg_context(MockClient(**built), SgContextOptions(site_url=SITE))


def source_for(
    context: SgContext,
    entity_type: str = "Version",
    fields: tuple[str, ...] = VERSION_FIELDS,
    **options: Any,
) -> EntitySource:
    """One source over the mock, with the page size a test asks for."""
    built: dict[str, Any] = {"mode": "pages", "page_size": 10}
    built.update(options)
    return create_entity_source(
        EntitySourceOptions(
            client=context.client, entity_type=entity_type, fields=list(fields), **built
        )
    )


def columns_for(
    context: SgContext, entity_type: str = "Version", paths: tuple[str, ...] = VERSION_FIELDS
) -> list:
    """The resolved columns for a type, straight off the schema service."""
    return resolve_columns(context.schema, entity_type, list(paths))


def drain(runner: Any, timeout_ms: int = 5000) -> bool:
    """Turn the loop until a `SerialRunner` has answered every call it holds.

    A test drives the queue from the thread that draws, which a widget never does: it would
    block the reader it is drawing for.
    """
    end = time.monotonic() + timeout_ms / 1000.0
    while runner.running and time.monotonic() < end:
        runner.pool.wait(DRAIN_STEP_MS)
        QtWidgets.QApplication.processEvents()
    QtWidgets.QApplication.processEvents()
    return not runner.running


def settle(widget: QtWidgets.QWidget, *bindings: Any, rounds: int = 4) -> None:
    """Wait for every read in flight and deliver what it published.

    A collection's reads run on a pool of one thread and answer on a queued signal, so a test
    waits for the pool and then turns the event loop. Several rounds, because one read can
    start another: a `pages` load counts the set behind it.
    """
    for _ in range(rounds):
        for binding in bindings:
            drain(binding.runner)
        for _ in range(4):
            QtWidgets.QApplication.processEvents()
            time.sleep(0.001)
    QtWidgets.QApplication.processEvents()


class FailingClient:
    """The mock with one method armed to raise, so a failed read is on the page."""

    def __init__(self, client: Any, fail_search: bool = False, fail_update: bool = False) -> None:
        self._client = client
        #: True while the next `search` raises.
        self.fail_search = bool(fail_search)
        #: True while the next `update` raises, which is a write the site refused.
        self.fail_update = bool(fail_update)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def search(self, *args: Any, **kwargs: Any) -> Any:
        if self.fail_search:
            raise RuntimeError("Flow PT API error 503")
        return self._client.search(*args, **kwargs)

    def update(self, *args: Any, **kwargs: Any) -> Any:
        if self.fail_update:
            raise RuntimeError("Flow PT API error 403")
        return self._client.update(*args, **kwargs)


def press(widget: QtWidgets.QWidget, key: Any, modifiers: Any = None) -> None:
    """Send one key press to a widget, on either binding."""
    flags = modifiers if modifiers is not None else QtCore.Qt.KeyboardModifier.NoModifier
    event = QtCore.QEvent(QtCore.QEvent.Type.KeyPress)
    widget.keyPressEvent(_key_event(key, flags))
    del event


def _key_event(key: Any, modifiers: Any) -> Any:
    from qtpy.QtGui import QKeyEvent

    return QKeyEvent(QtCore.QEvent.Type.KeyPress, int(key), modifiers)
