"""The threading layer every widget reads through.

A read runs on a `QThreadPool` and its answer crosses back to the thread that asked for it
through a signal, so a callback never touches Qt from a worker thread. A `Ticket` per query
drops an answer the next query replaced, which is the upstream `requestGate` (`core/search.ts`),
and a `Debounce` is the pause a search leaves before it asks, upstream's `SEARCH_DEBOUNCE_MS`.

`QueryRunner` bundles the three for the widgets that type into a read.

A job cannot be interrupted: `Job.cancel` marks it, and a late answer is dropped rather than
delivered. The callable itself runs to its end.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from qtpy.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

__all__ = [
    "DEFAULT_DEBOUNCE_MS",
    "DEFAULT_MAX_THREADS",
    "Debounce",
    "Job",
    "JobPool",
    "QueryRunner",
    "Ticket",
    "default_pool",
    "run_later",
]

#: The pause a search leaves before it asks, upstream's `SEARCH_DEBOUNCE_MS`.
DEFAULT_DEBOUNCE_MS = 250

#: Threads a pool runs at once. A read is network bound and a site rate limits, so the pool stays
#: small and never competes with the host application's own pool.
DEFAULT_MAX_THREADS = 4

TicketRef = tuple["Ticket", int]

ResultCallback = Callable[[Any], None]
ErrorCallback = Callable[[BaseException], None]


class Ticket:
    """The ticket an answer has to still hold to be delivered.

    A query cancels by taking the next ticket: whatever is in flight then holds a stale one and
    is dropped rather than landing over the query that replaced it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current = 0

    def next(self) -> int:
        """Take the next ticket. Every earlier one is stale from here on."""
        with self._lock:
            self._current += 1
            return self._current

    def is_current(self, n: int) -> bool:
        """True while `n` is the ticket that may deliver."""
        with self._lock:
            return n == self._current

    def cancel(self) -> None:
        """Drop whatever is in flight without starting anything."""
        self.next()

    @property
    def current(self) -> int:
        """The ticket that holds now."""
        with self._lock:
            return self._current


class _JobState:
    """What the runner may read after the job is deleted: whether it is gone."""

    def __init__(self) -> None:
        self.gone = False

    def mark_gone(self, *_args: object) -> None:
        self.gone = True


class Job(QObject):
    """One submitted callable, and the signals its answer crosses threads on.

    The job lives on the thread that submitted it, so `done` and `failed`, emitted from the pool
    thread, are delivered there and the callbacks run on that thread.
    """

    #: The value the callable returned.
    done = Signal(object)
    #: The exception it raised.
    failed = Signal(object)
    #: Emitted on the owning thread once the job has answered, failed or been dropped.
    finished = Signal()

    def __init__(
        self,
        fn: Callable[..., Any],
        args: tuple,
        on_result: ResultCallback | None = None,
        on_error: ErrorCallback | None = None,
        ticket: TicketRef | None = None,
        pool: JobPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._on_result = on_result
        self._on_error = on_error
        self._ticket = ticket
        self._pool = pool
        self._cancelled = False
        # Shared with the runner and outlives this QObject: a window closing while the callable
        # runs deletes the job, and the pool thread must then drop the answer, not emit on it.
        self._state = _JobState()
        self.destroyed.connect(self._state.mark_gone)
        # Bound slots of this object, so the delivery is queued to the owning thread.
        self.done.connect(self._deliver_result)
        self.failed.connect(self._deliver_error)
        self.finished.connect(self._retire)

    def cancel(self) -> None:
        """Mark the job so a late answer is dropped. The callable itself runs to its end."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        """True once `cancel` has been called."""
        return self._cancelled

    @property
    def live(self) -> bool:
        """True while the job may still deliver: not cancelled, and holding a current ticket."""
        if self._cancelled:
            return False
        if self._ticket is None:
            return True
        ticket, n = self._ticket
        return ticket.is_current(n)

    def _run(self) -> None:
        """The work, on a pool thread. Every exit emits `finished` while the job still exists."""
        state = self._state
        try:
            if state.gone or not self.live:
                return
            try:
                value = self._fn(*self._args)
            except Exception as error:
                self._emit(state, self.failed, error)
            else:
                self._emit(state, self.done, value)
        finally:
            self._emit(state, self.finished)

    @staticmethod
    def _emit(state: _JobState, signal: Any, *args: object) -> None:
        """Emit unless the job was deleted under the runner; a deleted wrapper raises, and is dropped."""
        if state.gone:
            return
        try:
            signal.emit(*args)
        except RuntimeError:
            state.gone = True

    @Slot(object)
    def _deliver_result(self, value: object) -> None:
        if self.live and self._on_result is not None:
            self._on_result(value)

    @Slot(object)
    def _deliver_error(self, error: object) -> None:
        if self.live and self._on_error is not None:
            self._on_error(error)

    @Slot()
    def _retire(self) -> None:
        # After the queued `done` or `failed` event, so dropping the last reference to the job
        # never discards an answer still on its way.
        self._fn = None
        self._args = ()
        self._on_result = None
        self._on_error = None
        pool, self._pool = self._pool, None
        if pool is not None:
            pool._forget(self)


class _Runner(QRunnable):
    """The pool's side of one job."""

    def __init__(self, job: Job) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._job: Job | None = job

    def run(self) -> None:
        job, self._job = self._job, None
        if job is not None:
            job._run()


class JobPool(QObject):
    """A `QThreadPool` of its own, and the jobs running on it.

    Its own pool, never `QThreadPool.globalInstance()`, so a host application's work and this
    one never starve each other.
    """

    def __init__(self, max_threads: int = DEFAULT_MAX_THREADS, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max_threads)
        self._lock = threading.Lock()
        self._live: set[Job] = set()

    @property
    def pool(self) -> QThreadPool:
        """The `QThreadPool` the work runs on."""
        return self._pool

    @property
    def max_threads(self) -> int:
        """Threads the pool runs at once."""
        return self._pool.maxThreadCount()

    def set_max_threads(self, count: int) -> None:
        self._pool.setMaxThreadCount(count)

    @property
    def running(self) -> int:
        """Jobs submitted and not yet answered."""
        with self._lock:
            return len(self._live)

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_result: ResultCallback | None = None,
        on_error: ErrorCallback | None = None,
        ticket: TicketRef | None = None,
    ) -> Job:
        """Run `fn(*args)` on the pool and hand the answer back on the calling thread.

        `ticket` is a `(Ticket, n)` pair: the callbacks are dropped once `n` is no longer the
        ticket that holds.
        """
        job = Job(fn, args, on_result=on_result, on_error=on_error, ticket=ticket, pool=self)
        with self._lock:
            self._live.add(job)
        self._pool.start(_Runner(job))
        return job

    def cancel_all(self) -> None:
        """Mark every live job. Work already started runs to its end, unheard."""
        with self._lock:
            jobs = list(self._live)
        for job in jobs:
            job.cancel()

    def wait(self, timeout_ms: int = -1) -> bool:
        """Block until the pool is idle. For teardown, never on a GUI thread."""
        return self._pool.waitForDone(timeout_ms)

    def _forget(self, job: Job) -> None:
        with self._lock:
            self._live.discard(job)


class Debounce(QObject):
    """A single-shot `QTimer` that a further call restarts.

    The pause a search leaves before it asks: long enough that a typist does not fire a request
    a letter, short enough to feel live.
    """

    def __init__(self, delay_ms: int = DEFAULT_DEBOUNCE_MS, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._delay_ms = delay_ms
        self._fn: Callable[[], None] | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fire)

    @property
    def delay_ms(self) -> int:
        """The pause a `call` takes when it names none."""
        return self._delay_ms

    def set_delay_ms(self, delay_ms: int) -> None:
        self._delay_ms = delay_ms

    @property
    def pending(self) -> bool:
        """True while a call is waiting out its pause."""
        return self._timer.isActive()

    def call(self, fn: Callable[[], None], delay_ms: int | None = None) -> None:
        """Run `fn` once the pause has elapsed. A further call replaces it and restarts."""
        self._fn = fn
        self._timer.start(self._delay_ms if delay_ms is None else delay_ms)

    def flush(self) -> None:
        """Run what is waiting now, if anything is."""
        if not self._timer.isActive():
            return
        self._timer.stop()
        self._fire()

    def cancel(self) -> None:
        """Drop what is waiting."""
        self._timer.stop()
        self._fn = None

    def _fire(self) -> None:
        fn, self._fn = self._fn, None
        if fn is not None:
            fn()


def run_later(fn: Callable[[], None], ms: int = 0) -> None:
    """Run `fn` on this thread's event loop, after `ms`. Zero is the next turn of the loop."""
    QTimer.singleShot(ms, fn)


_DEFAULT_POOL: JobPool | None = None


def default_pool() -> JobPool:
    """The pool a widget runs on when its caller names none."""
    global _DEFAULT_POOL
    if _DEFAULT_POOL is None:
        _DEFAULT_POOL = JobPool()
    return _DEFAULT_POOL


class QueryRunner(QObject):
    """The debounce, the ticket and the pool a search or a picker asks through.

    `start` makes whatever is in flight stale at once, then waits out the pause before it asks,
    so the answer to a query the typist has already replaced is never written.
    """

    def __init__(
        self,
        pool: JobPool | None = None,
        ticket: Ticket | None = None,
        delay_ms: int = DEFAULT_DEBOUNCE_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pool = pool if pool is not None else default_pool()
        self._ticket = ticket if ticket is not None else Ticket()
        self._debounce = Debounce(delay_ms, self)
        self._job: Job | None = None

    @property
    def pool(self) -> JobPool:
        return self._pool

    @property
    def ticket(self) -> Ticket:
        return self._ticket

    @property
    def delay_ms(self) -> int:
        return self._debounce.delay_ms

    def set_delay_ms(self, delay_ms: int) -> None:
        self._debounce.set_delay_ms(delay_ms)

    @property
    def pending(self) -> bool:
        """True while a query is waiting out its pause."""
        return self._debounce.pending

    def start(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_result: ResultCallback | None = None,
        on_error: ErrorCallback | None = None,
        delay_ms: int | None = None,
    ) -> None:
        """Ask for `fn(*args)` once the pause has elapsed, dropping the answer it replaces.

        `delay_ms=0` is the plan that asks at once, for a widget that browses rather than
        matching: nothing is debounced there, because no one is typing.
        """
        self._ticket.next()
        self._debounce.call(lambda: self._submit(fn, args, on_result, on_error), delay_ms)

    def flush(self) -> None:
        """Ask now for what is waiting out its pause."""
        self._debounce.flush()

    def cancel(self) -> None:
        """Drop what is waiting and what is in flight."""
        self._debounce.cancel()
        self._ticket.next()
        if self._job is not None:
            self._job.cancel()
            self._job = None

    def _submit(
        self,
        fn: Callable[..., Any],
        args: tuple,
        on_result: ResultCallback | None,
        on_error: ErrorCallback | None,
    ) -> None:
        n = self._ticket.next()
        self._job = self._pool.submit(
            fn, *args, on_result=on_result, on_error=on_error, ticket=(self._ticket, n)
        )
