"""The binding between a collection and the source behind it.

Ported from `packages/react/src/registry/sg/components/collection-source.ts`. The table,
the grid and the grouped list each hold a source, follow its snapshot, load it when it is
idle, keep its mode on the `paging` prop and mirror its sort and its filter out through
`sort_changed` and `filters_changed`. That is one model, so it lives here and each widget
keeps only what it draws.

Core's source is synchronous, so every call it makes runs on a pool of one thread and the
snapshot it publishes crosses back to the GUI thread on a queued signal: a widget only ever
reads `snapshot()` on the thread it draws on. One thread, because two reads writing the same
source would interleave; the source's own ticket (`begin`, `holds`) is what drops the answer a
later read replaced, and `begin_count` is what drops a count whose filter has moved.

    binding = CollectionSource(source, paging="pages")
    binding.changed.connect(redraw)
"""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Sequence
from typing import Any

from qtpy import QtCore
from qtpy.QtCore import QObject, Qt, Signal

from sg_widgets_core.collection import (
    EntitySource,
    EntitySourceState,
    SortSpec,
    SourceFilters,
)
from sg_widgets_core.collection_state import same_filters, same_sort
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.paging import PAGING_MODE_VALUES, source_mode_for

from ..workers import Job, JobPool, default_pool

__all__ = [
    "COLLECTION_PAGING_VALUES",
    "Alive",
    "Beacon",
    "CollectionSource",
    "SerialRunner",
]

#: How long a `wait` sleeps on the pool between turns of the event loop.
WAIT_STEP_MS = 20

#: How a collection walks a set. Core's `PagingMode`.
COLLECTION_PAGING_VALUES: tuple[str, ...] = PAGING_MODE_VALUES


class Alive:
    """A flag a store's listener reads before it touches the binding that made it.

    A core store keeps the listener it was handed, and a widget can be deleted while a read is
    still running on a worker. The flag is a plain object, not the QObject, so it outlives the
    deletion that turns it off, and `stop` takes the argument `destroyed` carries so a binding
    can wire the two together.
    """

    # `__weakref__` because PyQt5 holds a receiver by weak reference, and a binding wires its
    # own `destroyed` to `stop`. The beacon is what keeps the flag alive past the binding.
    __slots__ = ("__weakref__", "on")

    def __init__(self) -> None:
        self.on = True

    def stop(self, *_args: object) -> None:
        self.on = False


class Beacon(QObject):
    """The object a store's listener emits on, held by the listener and not by the binding.

    A binding is a child of the widget it serves, so Qt frees it while a read is still running
    on a worker; the store, which knows nothing of Qt, still holds the listener that read was
    about to call. Emitting on the binding there is emitting on a freed C++ object: PyQt5 keeps
    no guard on a bound signal it handed out and the process dies on the pool thread.

    So nothing a worker touches belongs to the binding. The beacon is parentless and the store's
    own listener keeps it alive, the binding only connects to it, and Qt drops that connection
    and every event already posted under it when the binding goes.

    `alive` is turned off by `close` and by the binding's `destroyed`, so a listener that has
    outlived its binding stops the store from working for no one.
    """

    #: The store moved. Queued to the thread the binding draws on.
    published = Signal()

    def __init__(self, alive: Alive) -> None:
        super().__init__()
        self._alive = alive

    @property
    def alive(self) -> Alive:
        """The flag this beacon publishes under."""
        return self._alive

    def publish(self) -> None:
        """The listener a store is handed. Emits while the binding is there and drops after."""
        if not self._alive.on:
            return
        try:
            self.published.emit()
        except RuntimeError:
            self._alive.stop()


def quietly(emit: Any, alive: Alive | None = None) -> Any:
    """A callback that drops its answer once the object it would reach has gone.

    `alive` is the binding's flag: a bound signal of a freed wrapper is not something PyQt5
    raises on, so the flag is what says the answer has nowhere to land, and the `RuntimeError`
    behind it is only what PySide6 adds.
    """

    def deliver(value: object) -> None:
        if alive is not None and not alive.on:
            return
        try:
            emit(value)
        except RuntimeError:
            return

    return deliver


class SerialRunner:
    """One call at a time on the shared pool, in the order they were asked for.

    A store is mutated by the call that reads it, so two reads running at once would interleave
    and the state would be neither. A pool of one thread would do it, but a pool owned by a
    widget is deleted with that widget, and a job is only held by its pool: the shared pool and
    a queue give the same order without tying a thread's life to a widget's.
    """

    def __init__(self, pool: JobPool | None = None, on_error: Any = None) -> None:
        self._pool = pool if pool is not None else default_pool()
        self._on_error = on_error
        self._queue: deque = deque()
        self._live: Job | None = None
        # Raised before the pool is asked, not once `submit` answers: the job may have run and
        # been forgotten by then, and a flag set afterwards would say a call is in flight for
        # ever and hold every call behind it.
        self._in_flight = False

    @property
    def pool(self) -> JobPool:
        """The pool the calls run on."""
        return self._pool

    @property
    def running(self) -> bool:
        """True while a call is in flight or waiting its turn."""
        return self._in_flight or bool(self._queue)

    def submit(self, fn: Any, *args: Any, on_result: Any = None, on_error: Any = None) -> None:
        """Run `fn(*args)` once every call asked for before it has answered."""
        self._queue.append((fn, args, on_result, on_error))
        self._pump()

    def cancel_all(self) -> None:
        """Drop what is waiting and mark what is running, whose answer is then unwanted."""
        self._queue.clear()
        if self._live is not None:
            self._live.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        """Block until the queue is empty, delivering each answer. For a test and for teardown."""
        end = time.monotonic() + timeout_ms / 1000.0
        while self.running and time.monotonic() < end:
            self._pool.wait(WAIT_STEP_MS)
            QtCore.QCoreApplication.processEvents()
        QtCore.QCoreApplication.processEvents()
        return not self.running

    def _pump(self) -> None:
        if self._in_flight or not self._queue:
            return
        fn, args, on_result, on_error = self._queue.popleft()
        # `on_finished` rather than `job.finished.connect(self._done)` after the call: the pool
        # starts the job inside `submit`, and a call the mock answers in a microsecond finishes
        # before that connection exists. The queue behind it then never moves again, which on
        # PyQt5 is what a page size, a pager arrow and a write all wait on for ever.
        self._in_flight = True
        self._live = None
        job = self._pool.submit(
            fn,
            *args,
            on_result=on_result,
            on_error=on_error or self._on_error,
            on_finished=self._done,
        )
        # `_done` may already have run and started the next call, whose job this is not.
        if self._in_flight:
            self._live = job

    def _done(self) -> None:
        self._in_flight = False
        self._live = None
        self._pump()


class CollectionSource(QObject):
    """One `EntitySource`, read off the GUI thread, with its sort and its filter two-way."""

    #: The source published a new snapshot.
    changed = Signal()
    #: The source's sort moved. Carries `list[SortSpec]`.
    sort_changed = Signal(object)
    #: The source's filter moved. Carries the wire group, or None.
    filters_changed = Signal(object)
    #: A write, a count or a re-read raised. Carries the exception.
    failed = Signal(object)

    def __init__(
        self,
        source: EntitySource,
        paging: str = "pages",
        sort: Sequence[SortSpec] | None = None,
        filters: SourceFilters = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._paging = paging if paging in COLLECTION_PAGING_VALUES else "pages"
        self._alive = Alive()
        # Qt frees this binding with the widget it serves, and a read on the pool answers after.
        # The flag is what every callback the pool still holds reads before it emits.
        self.destroyed.connect(self._alive.stop)
        # One call at a time, so the source is never mutated by two reads at once.
        self._runner = SerialRunner(on_error=quietly(self.failed.emit, self._alive))
        self._sort: list[SortSpec] | None = None if sort is None else list(sort)
        self._filters: SourceFilters = filters
        self._sort_seen = list(source.sort)
        self._filters_seen = source.filters

        self._beacon = Beacon(self._alive)
        self._beacon.published.connect(self._on_published, Qt.ConnectionType.QueuedConnection)
        self._unsubscribe = source.subscribe(self._beacon.publish)
        self._apply_mode()
        if self._sort is not None and not same_sort(self._sort, source.sort):
            self.set_sort(self._sort)
        if self._filters is not None and not same_filters(self._filters, source.filters):
            self.set_filters(self._filters)
        if source.status == "idle":
            self.load()

    # --- props ----------------------------------------------------------------------------

    @property
    def source(self) -> EntitySource:
        """The rows, the filter, the sort and the page behind them."""
        return self._source

    @property
    def paging(self) -> str:
        """`pages`, `more` or `scroll`. The source's mode follows it."""
        return self._paging

    def set_paging(self, value: str) -> None:
        value = value if value in COLLECTION_PAGING_VALUES else "pages"
        if value == self._paging:
            return
        self._paging = value
        self._apply_mode()

    @property
    def sort(self) -> list[SortSpec]:
        """The sort the source holds."""
        return list(self._source.sort)

    def set_sort(self, value: Sequence[SortSpec] | None) -> None:
        """Take a sort from the `sort` prop. A sort the source already holds is a no-op.

        The prop is recorded, so the snapshot that comes back says what the caller already
        knows and nothing is reported: a change travels once, and the two never write to each
        other. A sort the widget itself makes goes through `apply_sort` instead.
        """
        if value is None:
            return
        keys = list(value)
        self._sort = keys
        if same_sort(keys, self._source.sort):
            return
        self._run(self._source.set_sort, keys)

    def apply_sort(self, value: Sequence[SortSpec]) -> None:
        """Sort from the widget's own control: a header click, or a sort picker.

        The prop is not recorded, so the snapshot that comes back is reported through
        `sort_changed` and a `sort` prop follows it.
        """
        keys = list(value)
        if same_sort(keys, self._source.sort):
            return
        self._run(self._source.set_sort, keys)

    @property
    def filters(self) -> SourceFilters:
        """The filter the source holds, as the wire group."""
        return self._source.filters

    def set_filters(self, value: SourceFilters) -> None:
        """Take a filter from the `filters` prop. One the source already holds is a no-op."""
        self._filters = value
        if same_filters(value, self._source.filters):
            return
        self._run(self._source.set_filters, value)

    def apply_filters(self, value: SourceFilters) -> None:
        """Filter from the widget's own control, so the change is reported back out."""
        if same_filters(value, self._source.filters):
            return
        self._run(self._source.set_filters, value)

    # --- what a view reads ----------------------------------------------------------------

    def snapshot(self) -> EntitySourceState:
        """The last state the source published."""
        return self._source.snapshot()

    @property
    def status(self) -> str:
        return self._source.status

    @property
    def busy(self) -> bool:
        """True while a call to the source is in flight."""
        return self._runner.running

    @property
    def runner(self) -> SerialRunner:
        """The queue the source is read through.

        A widget reading beside it, a schema lookup for a column or a status field, submits
        here rather than straight to the pool, so the reads stay in the order they were asked
        for and a teardown drops them together.
        """
        return self._runner

    # --- the calls ------------------------------------------------------------------------

    def load(self) -> None:
        """Read the first page, discarding anything already loaded."""
        self._run(self._source.load)

    def load_more(self) -> None:
        """Append the next page. A no-op in `pages` mode or with nothing more."""
        if self._paging == "pages" or self.busy or not self._source.has_more:
            return
        self._run(self._source.load_more)

    def refresh(self) -> None:
        """Read every page already shown again."""
        self._run(self._source.refresh)

    def retry(self) -> None:
        """Read the page that failed again: the one a pager is on, or the one appended."""
        if self._paging == "pages":
            self._run(self._source.set_page, self._source.page)
        else:
            self._run(self._source.load_more)

    def set_page(self, page: int) -> None:
        """Show one page of the set. `pages` mode only."""
        self._run(self._source.set_page, int(page))

    def set_page_size(self, size: int) -> None:
        self._run(self._source.set_page_size, int(size))

    def count(self) -> None:
        """Count the set through `_summarize`, so a range can read "n to m of N" (020_summarize).

        The ticket is taken here, on the GUI thread, so an answer whose filter has moved is
        dropped rather than written over the filter that replaced it.
        """
        pending = self._source.begin_count()
        self._run(self._source.count, pending)

    def update_row(self, ref: EntityRef, patch: dict[str, Any], on_done: Any = None) -> None:
        """Write one field of one row and put the re-read row back in place.

        The write answers the whole record but resolves no dotted path, so the source reads
        the row again with its own projection (024_read_after_write). `on_done` is called on
        the GUI thread with the fresh row, or with the exception a refused write raised.
        """

        def done(row: object) -> None:
            if not self._alive.on:
                return
            if on_done is not None:
                on_done(row)

        def failed(error: BaseException) -> None:
            if not self._alive.on:
                return
            self.failed.emit(error)
            if on_done is not None:
                on_done(error)

        self._runner.submit(
            self._source.update_row, ref, patch, on_result=done, on_error=failed
        )

    def reread_rows(self, ids: Sequence[int]) -> None:
        """Read these rows again with the source's own projection and swap them in place."""
        self._run(self._source.reread_rows, list(ids))

    def wait(self, timeout_ms: int = 5000) -> bool:
        """Block until every call is answered, then deliver what they published.

        For a test and for teardown. Never on a GUI thread that has a reader waiting.
        """
        return self._runner.wait(timeout_ms)

    # --- internals ------------------------------------------------------------------------

    def _apply_mode(self) -> None:
        mode = source_mode_for(self._paging)
        if self._source.mode != mode:
            self._run(self._source.set_mode, mode)

    def _run(self, fn: Any, *args: Any) -> None:
        self._runner.submit(fn, *args)

    def _on_published(self) -> None:
        """The source moved. Mirror the sort and the filter out, then tell the view."""
        state = self._source.snapshot()
        if not same_sort(state.sort, self._sort_seen):
            self._sort_seen = list(state.sort)
            if self._sort is None or not same_sort(state.sort, self._sort):
                self._sort = list(state.sort)
                self.sort_changed.emit(list(state.sort))
        if not same_filters(state.filters, self._filters_seen):
            self._filters_seen = state.filters
            if self._filters is None or not same_filters(state.filters, self._filters):
                self._filters = state.filters
                self.filters_changed.emit(state.filters)
        self.changed.emit()

    def close(self) -> None:
        """Stop following the source and drop what is in flight."""
        self._alive.stop()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._runner.cancel_all()
