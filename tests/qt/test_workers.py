"""The threading layer: the thread an answer lands on, the ticket, the cancel and the pause."""
from __future__ import annotations

import threading
import time

import pytest
from qtpy.QtCore import QThread

from sg_widgets_qt.workers import (
    DEFAULT_DEBOUNCE_MS,
    DEFAULT_MAX_THREADS,
    Debounce,
    JobPool,
    QueryRunner,
    Ticket,
    default_pool,
    run_later,
)


@pytest.fixture
def pool(qapp):
    made = JobPool()
    yield made
    made.cancel_all()
    made.wait(5000)


def idle(pool: JobPool):
    return lambda: pool.running == 0


def test_the_pool_is_its_own_and_runs_four_threads(pool):
    assert pool.max_threads == DEFAULT_MAX_THREADS == 4
    assert pool.pool is not None


def test_default_pool_is_one_pool():
    assert default_pool() is default_pool()


def test_a_result_arrives_on_the_thread_that_submitted(qtbot, pool):
    caller = QThread.currentThread()
    seen = {}

    def work():
        seen["worker"] = QThread.currentThread()
        return 21 * 2

    def on_result(value):
        seen["callback"] = QThread.currentThread()
        seen["value"] = value

    pool.submit(work, on_result=on_result)
    qtbot.waitUntil(lambda: "value" in seen, timeout=5000)

    assert seen["value"] == 42
    assert seen["callback"] is caller
    assert seen["worker"] is not caller


def test_an_exception_reaches_on_error_with_the_exception(qtbot, pool):
    raised = RuntimeError("the read failed")
    seen = []

    def work():
        raise raised

    pool.submit(work, on_result=lambda value: seen.append(("result", value)), on_error=seen.append)
    qtbot.waitUntil(lambda: bool(seen), timeout=5000)

    assert seen == [raised]
    assert str(seen[0]) == "the read failed"


def test_the_job_signals_carry_the_answer(qtbot, pool):
    released = threading.Event()

    def work():
        released.wait(5)
        return "answer"

    job = pool.submit(work)
    with qtbot.waitSignal(job.done, timeout=5000) as blocker:
        released.set()
    assert blocker.args == ["answer"]


def test_a_stale_ticket_drops_the_answer(qtbot, pool):
    ticket = Ticket()
    n = ticket.next()
    seen = []

    def work():
        time.sleep(0.2)
        return "stale"

    pool.submit(work, on_result=seen.append, ticket=(ticket, n))
    # The next query takes the next ticket, which is the cancellation.
    ticket.next()
    qtbot.waitUntil(idle(pool), timeout=5000)
    qtbot.wait(50)

    assert seen == []
    assert ticket.is_current(n) is False


def test_a_current_ticket_delivers(qtbot, pool):
    ticket = Ticket()
    n = ticket.next()
    seen = []

    pool.submit(lambda: "fresh", on_result=seen.append, ticket=(ticket, n))
    qtbot.waitUntil(lambda: bool(seen), timeout=5000)

    assert seen == ["fresh"]


def test_a_cancelled_job_drops_the_answer(qtbot, pool):
    released = threading.Event()
    seen = []

    def work():
        released.wait(5)
        return "late"

    job = pool.submit(work, on_result=seen.append, on_error=seen.append)
    job.cancel()
    released.set()
    qtbot.waitUntil(idle(pool), timeout=5000)
    qtbot.wait(50)

    assert job.cancelled is True
    assert seen == []


def test_the_debounce_coalesces(qtbot):
    debounce = Debounce(30)
    calls = []

    debounce.call(lambda: calls.append("first"))
    debounce.call(lambda: calls.append("second"))
    debounce.call(lambda: calls.append("third"))
    assert debounce.pending is True

    qtbot.waitUntil(lambda: bool(calls), timeout=2000)
    qtbot.wait(80)

    assert calls == ["third"]
    assert debounce.pending is False


def test_the_debounce_defaults_to_the_upstream_pause():
    assert Debounce().delay_ms == DEFAULT_DEBOUNCE_MS == 250


def test_the_debounce_flushes_and_cancels(qtbot):
    debounce = Debounce(5000)
    calls = []

    debounce.call(lambda: calls.append("flushed"))
    debounce.flush()
    assert calls == ["flushed"]
    assert debounce.pending is False

    debounce.call(lambda: calls.append("dropped"))
    debounce.cancel()
    qtbot.wait(50)
    assert calls == ["flushed"]

    debounce.flush()
    assert calls == ["flushed"]


def test_run_later_runs_on_the_event_loop(qtbot):
    calls = []
    run_later(lambda: calls.append("later"))
    assert calls == []
    qtbot.waitUntil(lambda: bool(calls), timeout=2000)
    assert calls == ["later"]


def test_the_query_runner_drops_the_answer_its_next_query_replaced(qtbot, pool):
    runner = QueryRunner(pool, delay_ms=10)
    seen = []

    def slow(tag):
        time.sleep(0.4)
        return tag

    def quick(tag):
        return tag

    runner.start(slow, "first", on_result=seen.append)
    # The first read is on its way before the second query is typed.
    qtbot.waitUntil(lambda: pool.running == 1, timeout=2000)
    runner.start(quick, "second", on_result=seen.append)

    qtbot.waitUntil(lambda: idle(pool)() and bool(seen), timeout=5000)
    qtbot.wait(100)

    assert seen == ["second"]


def test_the_query_runner_waits_out_the_pause(qtbot, pool):
    runner = QueryRunner(pool, delay_ms=60)
    seen = []

    runner.start(lambda: "asked", on_result=seen.append)
    assert runner.pending is True
    qtbot.wait(20)
    assert seen == []

    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    assert seen == ["asked"]


def test_the_query_runner_cancels_what_is_waiting_and_what_is_in_flight(qtbot, pool):
    runner = QueryRunner(pool, delay_ms=10)
    seen = []

    runner.start(lambda: time.sleep(0.3) or "in flight", on_result=seen.append)
    qtbot.waitUntil(lambda: pool.running == 1, timeout=2000)
    runner.cancel()

    qtbot.waitUntil(idle(pool), timeout=5000)
    qtbot.wait(50)
    assert seen == []


def test_a_ticket_holds_only_its_latest(qtbot):
    ticket = Ticket()
    first = ticket.next()
    assert ticket.is_current(first) is True
    second = ticket.next()
    assert ticket.is_current(first) is False
    assert ticket.is_current(second) is True
    ticket.cancel()
    assert ticket.is_current(second) is False
    assert ticket.current == second + 1
