"""The binding between a collection and its source: the queue, and the answers it drops.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from sg_widgets_core.collection import EntitySourceOptions, create_entity_source
from sg_widgets_core.filter import condition
from sg_widgets_qt.widgets.collection_source import CollectionSource, SerialRunner

from .collections import mock_context, source_for

#: A status a few of the mock's Versions carry, so a filter on it matches fewer than the set.
NARROW = condition("sg_status_list", "is", "na")


class HeldClient:
    """The mock with `search` held at a gate, so a read can be caught in flight."""

    def __init__(self, client: Any, gate: threading.Event, arrived: threading.Event) -> None:
        self._client = client
        self._gate = gate
        self._arrived = arrived

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def search(self, *args: Any, **kwargs: Any) -> Any:
        self._arrived.set()
        self._gate.wait(5.0)
        return self._client.search(*args, **kwargs)


def test_the_runner_runs_one_call_at_a_time_in_the_order_it_was_asked(qtbot):
    runner = SerialRunner()
    order: list[int] = []
    live = 0
    most = 0
    lock = threading.Lock()

    def work(n: int) -> int:
        nonlocal live, most
        with lock:
            live += 1
            most = max(most, live)
        time.sleep(0.005)
        with lock:
            live -= 1
        return n

    for n in range(6):
        runner.submit(work, n, on_result=order.append)
    assert runner.running is True
    runner.wait(5000)
    assert order == [0, 1, 2, 3, 4, 5]
    assert most == 1, "two calls mutated the source at once"
    assert runner.running is False


def test_a_call_that_raises_leaves_the_queue_moving(qtbot):
    runner = SerialRunner()
    seen: list[Any] = []
    runner.submit(lambda: 1 / 0, on_error=seen.append)
    runner.submit(lambda: "after", on_result=seen.append)
    runner.wait(5000)
    assert isinstance(seen[0], ZeroDivisionError)
    assert seen[1] == "after"


def test_a_page_whose_ticket_moved_is_dropped(qtbot):
    context = mock_context()
    gate, arrived = threading.Event(), threading.Event()
    source = create_entity_source(
        EntitySourceOptions(
            client=HeldClient(context.client, gate, arrived),
            entity_type="Version",
            fields=["code"],
            page_size=5,
            mode="pages",
        )
    )
    binding = CollectionSource(source, paging="pages")
    assert arrived.wait(5.0), "the first page never reached the client"
    # The reader moved on while the page was still being read, so every answer in flight is
    # stale from here: `EntitySource.begin` is what says so.
    source.begin()
    gate.set()
    binding.wait(5000)
    assert binding.snapshot().rows == []
    assert binding.snapshot().status == "loading"
    binding.close()


def test_a_count_whose_filter_moved_is_dropped(qtbot):
    context = mock_context()
    binding = CollectionSource(source_for(context, mode="pages"), paging="pages")
    binding.wait(5000)
    whole = binding.snapshot().total
    assert whole

    narrowed = CollectionSource(source_for(context, mode="pages"), paging="pages", filters=NARROW)
    narrowed.wait(5000)
    narrow_total = narrowed.snapshot().total
    assert narrow_total and narrow_total < whole
    narrowed.close()

    # The filter moves first; the count is taken on this thread, under the filter it replaced,
    # and lands last. Writing it would put the old set's total against the new filter.
    binding.apply_filters(NARROW)
    binding.count()
    binding.wait(5000)
    assert binding.snapshot().total == narrow_total
    binding.close()


def test_a_snapshot_the_source_published_reaches_the_gui_thread(qtbot):
    context = mock_context()
    binding = CollectionSource(source_for(context, mode="pages"), paging="pages")
    changes: list[int] = []
    binding.changed.connect(lambda: changes.append(1))
    binding.wait(5000)
    assert binding.snapshot().rows
    assert changes, "the source moved and the view was never told"
    binding.close()
