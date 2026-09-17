"""The GUI thread while a collection works: no long iteration, and a smooth scroll.

A read runs on a worker, so the loop must keep turning while a page lands and while a tree
expands. This drive spins the loop itself and times every iteration: none may take longer than
`SLOW_MS`. It then scrolls the body 20 wheel steps and times each paint.

    QA_TARGET=entity-table .venv/bin/python tools/qa.py --page entity-table \
        --drive tools/drives/collection-gui-thread.py
    QA_TARGET=entity-tree .venv/bin/python tools/qa.py --page entity-tree \
        --drive tools/drives/collection-gui-thread.py

`QA_TARGET` picks what is timed; it defaults to the page's own name.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget  # noqa: E402
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402

#: The longest one turn of the loop may take while a page lands, in milliseconds.
SLOW_MS = 50.0

#: The longest one paint may take while the body is scrolled, in milliseconds.
PAINT_MS = 30.0

#: How many wheel steps the smoothness measurement takes, and how far each one goes.
WHEEL_STEPS = 20
WHEEL_DELTA = 120


def _app():
    return QtWidgets.QApplication.instance()


def spin_until(read, limit_ms: float = 30000.0) -> tuple:
    """Turn the loop until `read` answers, timing every turn. Answers (landed, worst, turns)."""
    app = _app()
    worst = 0.0
    turns = 0
    end = time.perf_counter() + limit_ms / 1000.0
    while time.perf_counter() < end:
        started = time.perf_counter()
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 10)
        took = (time.perf_counter() - started) * 1000.0
        worst = max(worst, took)
        turns += 1
        if read():
            return True, worst, turns
        time.sleep(0.002)
    return bool(read()), worst, turns


def wheel(view, steps: int) -> list:
    """Scroll the body with the wheel, timing the paint each step costs."""
    app = _app()
    taken: list[float] = []
    port = view.viewport()
    where = QtCore.QPointF(port.rect().center())
    for _ in range(steps):
        event = QtGui.QWheelEvent(
            where,
            view.mapToGlobal(port.rect().center()),
            QtCore.QPoint(0, -WHEEL_DELTA),
            QtCore.QPoint(0, -WHEEL_DELTA),
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            QtCore.Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        started = time.perf_counter()
        app.sendEvent(port, event)
        port.repaint()
        taken.append((time.perf_counter() - started) * 1000.0)
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 5)
    return taken


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    target = os.environ.get("QA_TARGET", page.data_name.rsplit("/", 1)[-1])
    notes: list[str] = []

    if target == "entity-tree":
        holder = stage_widget(page, "entity-tree")
        if holder is None:
            return {"verdict": "FAIL the page built no entity-tree demo"}
        tree = holder.tree
        rows = lambda: list(tree.snapshot().rows)  # noqa: E731
        landed, worst, turns = spin_until(lambda: len(rows()) > 3)
        if not landed:
            return {"verdict": "FAIL the tree read no level", "notes": notes}
        notes.append(f"the seeded read: {turns} turns, the slowest {worst:.1f}ms")
        if worst > SLOW_MS:
            return {"verdict": f"FAIL a turn took {worst:.1f}ms while the tree opened", "notes": notes}

        # A whole branch is a read per level; the loop must keep turning through all of them.
        # `expand_all` over the Shots folder opens every sequence and every shot under it,
        # which is the deepest thing this tree does.
        tree.set_expanded([])
        spin_until(lambda: len(rows()) <= 3, 10000)
        folder = next(row for row in rows() if row.node.path.endswith("/Shot"))
        held = len(rows())
        tree.binding.run("expand_all", folder.node.path, 3)
        landed, worst, turns = spin_until(lambda: len(rows()) > held + 20, 40000)
        if not landed:
            return {"verdict": f"FAIL the branch opened {len(rows())} nodes from {held}", "notes": notes}
        # Whatever is still in flight keeps arriving; the loop is timed through that too.
        _, tail, more = spin_until(lambda: False, 3000)
        worst = max(worst, tail)
        notes.append(
            f"a whole branch opened to {len(rows())} nodes: {turns + more} turns, "
            f"the slowest {worst:.1f}ms"
        )
        if worst > SLOW_MS:
            return {"verdict": f"FAIL a turn took {worst:.1f}ms while the tree expanded", "notes": notes}
        view = tree.view
    else:
        holder = stage_widget(page, "entity-table")
        if holder is None:
            return {"verdict": "FAIL the page built no entity-table demo"}
        table = holder.table
        settled = lambda: table.control.snapshot().status in ("ready", "error")  # noqa: E731
        landed, worst, turns = spin_until(lambda: settled() and table.control.rows)
        if not landed:
            return {"verdict": "FAIL the first page never landed", "notes": notes}
        notes.append(f"the first page: {turns} turns, the slowest {worst:.1f}ms")
        if worst > SLOW_MS:
            return {"verdict": f"FAIL a turn took {worst:.1f}ms while the page landed", "notes": notes}

        # 320 rows on the mock, walked by the scroller so every page lands on this loop.
        holder._paging["scroll"].set_checked(True)
        if not spin_until(lambda: settled() and table.control.bottom() == "sentinel")[0]:
            return {"verdict": f"FAIL scroll draws {table.control.bottom()!r}", "notes": notes}
        worst_page = 0.0
        while len(table.control.rows) < 320:
            spin_until(settled, 20000)
            held = len(table.control.rows)
            table.control.on_last_visible(held - 1)
            landed, worst, turns = spin_until(
                lambda mark=held: len(table.control.rows) > mark, 20000
            )
            worst_page = max(worst_page, worst)
            if not landed:
                return {"verdict": f"FAIL the scroller stopped at {held} rows", "notes": notes}
        notes.append(f"320 rows walked page by page, the slowest turn {worst_page:.1f}ms")
        if worst_page > SLOW_MS:
            return {"verdict": f"FAIL a turn took {worst_page:.1f}ms while the pages landed", "notes": notes}
        view = table.view

    images_settled(wait)
    wait(200)
    # One paint first, off the measurement: the glyph and thumbnail caches are cold until
    # something has been drawn once, and that cost is not what a scroll costs.
    view.viewport().repaint()
    wait(100)
    taken = wheel(view, WHEEL_STEPS)
    worst_paint = max(taken)
    notes.append(
        f"{len(taken)} wheel steps, the slowest paint {worst_paint:.1f}ms, "
        f"the median {sorted(taken)[len(taken) // 2]:.1f}ms, "
        f"each: {', '.join(f'{one:.0f}' for one in taken)}"
    )
    if worst_paint > PAINT_MS:
        return {"verdict": f"FAIL a paint took {worst_paint:.1f}ms, over {PAINT_MS:.0f}ms", "notes": notes}

    return {
        "verdict": (
            f"PASS {target}: no turn of the loop over {SLOW_MS:.0f}ms while the reads landed, "
            f"and no paint over {PAINT_MS:.0f}ms over {WHEEL_STEPS} wheel steps"
        ),
        "notes": notes,
    }
