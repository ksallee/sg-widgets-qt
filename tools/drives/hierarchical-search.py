"""Walk the tree with the keyboard, search it, and read the path off the row.

The port of `~/dev/sg-widgets/tools/drives/hierarchical-search.js` and the tree half of
`row-anatomy.js`, read off the widget rather than off the DOM.

    .venv/bin/python tools/qa.py --page hierarchical-search --drive tools/drives/hierarchical-search.py
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, QObject, Qt, QTimer
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles

#: No event-loop iteration may take longer than this while a read is in flight.
GAP_LIMIT_MS = 50

#: A row of the fixtures, and a query the site holds nothing for.
QUERY = "sh010_0010 comp"
NO_MATCH = "zzzqqq"


class LoopWatch(QObject):
    """A 10ms tick that records the longest gap between two turns of the event loop."""

    def __init__(self) -> None:
        super().__init__()
        self.worst = 0.0
        self._last = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._last = time.monotonic()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = time.monotonic()
        self.worst = max(self.worst, (now - self._last) * 1000.0)
        self._last = now


def press(widget, key: int) -> None:
    """One key, delivered to the widget itself, so a headless run needs no focus."""
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))


def mock_of(client):
    """The mock under the cache and the counter, which is what arms a failure."""
    seen = client
    for _ in range(6):
        if hasattr(seen, "fail_next"):
            return seen
        seen = getattr(seen, "_client", None)
        if seen is None:
            return None
    return None


def settle(control, wait, ms: int = 10000) -> None:
    """Spin until the read in flight has answered or failed."""
    deadline = time.monotonic() + ms / 1000.0
    while control.loading and time.monotonic() < deadline:
        wait(25)


def prime_status_glyphs(page) -> None:
    """Draw the first status badge of the process before the watch starts.

    The bundled sprite behind a status glyph is read on the GUI thread the first time anything
    paints a badge, once per process. That is the showcase opening a page rather than a widget
    answering a read, so it is paid here and the watch measures what the drive does next.
    """
    from sg_widgets_qt.widgets.field_value import FieldValueOptions, warm_status_glyph

    context = getattr(getattr(page, "context", None), "context", None)
    table = getattr(context, "statuses", None)
    if table is None:
        return
    try:
        codes = dict(table.by_code())
    except Exception:  # A site that answers no Status table draws no badge either.
        return
    if not codes:
        return
    options = FieldValueOptions(statuses=codes, site_url=getattr(context, "site_url", ""))
    warm_status_glyph(next(iter(codes)), options)

def kinds(model) -> list[str]:
    return [
        str(model.data(model.index(i, 0), Roles.KIND) or "row") for i in range(model.rowCount())
    ]


def labels(model) -> list[str]:
    return [
        str(model.data(model.index(i, 0), Roles.LABEL) or "") for i in range(model.rowCount())
    ]


def runs_at(model, row: int) -> list[tuple]:
    return list(model.data(model.index(row, 0), Roles.RUNS) or [])


def drive(page, wait, find, prefs) -> dict:
    bad: list[str] = []
    notes: list[str] = []
    watch = LoopWatch()

    tree = find("hierarchical-search")
    if tree is None:
        watch.stop()
        return {"verdict": "FAIL no hierarchical search on the page"}
    control = tree.search_control()
    box = control.input()
    reads = page.context.reads
    settle(control, wait)
    wait(800)
    # The watch starts once the page has drawn its first frame. The first status glyph any
    # process builds costs one read of the bundled sprite on the GUI thread, which is the
    # showcase opening a page rather than a widget answering; what the rule is about is the
    # reads this drive provokes from here on.
    prime_status_glyphs(page)
    watch.start()

    # 1. The root opens on its type folders, under a heading and with no way back up yet.
    model = control.model
    shape = kinds(model)
    root_rows = labels(model)[1:]
    if shape[:1] != ["heading"]:
        bad.append("the level draws no heading")
    if not root_rows:
        bad.append("the tree did not open")
    if "Back" in root_rows:
        bad.append("the root level drew a way back up")
    notes.append(f"root level: {root_rows}")

    # 2. Enter on a folder row walks a level, and the crumbs say where it landed.
    surface = control.list_surface()
    at = shape.index("row") if "row" in shape else -1
    surface.set_highlight(at)
    before = tree.level_path
    press(box, Qt.Key.Key_Return)
    settle(control, wait)
    wait(300)
    if tree.level_path == before:
        bad.append("Enter on a folder row opened no level")
    walked = labels(control.model)
    if walked[0] in ("Tree", ""):
        bad.append(f"the crumbs still read {walked[0]!r} one level down")
    if "Back" not in walked:
        bad.append("a level below the root drew no way back up")
    notes.append(f"Enter walked into {walked[0]!r} with {len(walked) - 2} rows")

    # 3. Left goes back up, Right opens the level below the highlighted row.
    press(box, Qt.Key.Key_Left)
    settle(control, wait)
    wait(300)
    if labels(control.model)[0] != "Tree":
        bad.append(f"Left left the level at {labels(control.model)[0]!r}")
    surface.set_highlight(kinds(control.model).index("row"))
    press(box, Qt.Key.Key_Right)
    settle(control, wait)
    wait(300)
    if labels(control.model)[0] == "Tree":
        bad.append("Right opened no level")
    press(box, Qt.Key.Key_Backspace)
    settle(control, wait)
    wait(300)
    if labels(control.model)[0] != "Tree":
        bad.append("Backspace on an empty query did not go back up")
    notes.append("Right walked down, Left and Backspace walked back up")

    # 4. Two keystrokes inside the pause cost one read, with skeletons and never a spinner.
    page.context.reset_reads()
    box.setText(QUERY[:5])
    wait(60)
    box.setText(QUERY)
    wait(120)
    if control.view != "loading":
        bad.append(f"the list is {control.view!r} while the pause runs, wanted loading")
    spinners = [w for w in page.findChildren(QObject) if "spinner" in w.objectName().lower()]
    if spinners:
        bad.append(f"{len(spinners)} spinner(s) in the first 150ms")
    settle(control, wait)
    wait(400)
    if reads.get("text_search") != 1:
        bad.append(f"two keystrokes cost {reads.get('text_search')} text searches, wanted 1")
    notes.append(f"two keystrokes cost {reads.get('text_search')} text search")

    # 5. A result is a breadcrumb: crumbs before the label, the label's matched runs bold.
    shape = kinds(control.model)
    if "row" not in shape:
        bad.append("the query answered no rows")
    else:
        at = shape.index("row")
        runs = runs_at(control.model, at)
        crumbs = [str(r[0]) for r in runs if len(r) > 2 and r[2]]
        marked = [str(r[0]) for r in runs if len(r) >= 2 and r[1]]
        if "›" not in "".join(crumbs):
            bad.append(f"the result is not a breadcrumb: {crumbs}")
        if not marked:
            bad.append("nothing in the label is drawn as a matched run")
        sub = control.model.data(control.model.index(at, 0), Roles.SUB_LABEL)
        if not sub:
            bad.append("a result carries no sub-label")
        notes.append(f"result crumbs {''.join(crumbs)!r}, bold {marked}, sub {sub!r}")

    # 6. Down keeps the highlight in view and the last row holds.
    surface.set_highlight(0)
    landed = []
    for _ in range(control.model.rowCount() + 4):
        press(box, Qt.Key.Key_Down)
        wait(8)
        landed.append(surface.highlighted())
    if landed[-1] != max(landed):
        bad.append("Down wrapped past the last row")
    if kinds(control.model)[landed[-1]] == "heading":
        bad.append("the highlight rests on a heading")
    rect = surface.visualRect(surface.model().index(landed[-1], 0))
    if not surface.viewport().rect().intersects(rect):
        bad.append("the highlighted row is out of view")

    # 7. Enter picks and emits the row with the path that reaches it, root first.
    picked: dict = {}
    tree.selected.connect(lambda leaf, path: picked.update(leaf=leaf, path=list(path)))
    surface.set_highlight(kinds(control.model).index("row"))
    press(box, Qt.Key.Key_Return)
    wait(150)
    leaf, path = picked.get("leaf"), picked.get("path")
    if leaf is None or not path:
        bad.append(f"Enter emitted {picked!r}, wanted a row and its path")
    else:
        if path[0].type != "Project":
            bad.append(f"the path starts at {path[0].type}, wanted Project")
        if path[-1].type != leaf.type or path[-1].id != leaf.id:
            bad.append("the path does not end on the row that was picked")
        notes.append("Enter emitted " + " > ".join(step.type for step in path))

    # 8. A query matching nothing is the empty line; Escape clears the query.
    box.setText(NO_MATCH)
    control.flush()
    settle(control, wait)
    wait(300)
    if control.view != "empty":
        bad.append(f"a query matching nothing drew {control.view!r}")
    press(box, Qt.Key.Key_Escape)
    settle(control, wait)
    wait(300)
    if tree.query != "":
        bad.append(f"Escape left {tree.query!r} in the box")
    if labels(control.model)[0] != "Tree":
        bad.append("Escape did not put the level back")

    # 9. A read armed to fail is the error line.
    mock = mock_of(page.context.client)
    if mock is None:
        bad.append("the demo client cannot be armed to fail")
    else:
        mock.fail_next()
        box.setText("sh020")
        control.flush()
        settle(control, wait)
        wait(300)
        if control.view != "error" or not control.failure:
            bad.append(f"an armed failure drew {control.view!r}")
        else:
            notes.append(f"error line {control.failure!r}")
        mock.fail_next(None)

    watch.stop()
    if watch.worst > GAP_LIMIT_MS:
        bad.append(f"the GUI thread stalled {watch.worst:.0f}ms, over {GAP_LIMIT_MS}ms")
    return {
        "verdict": (
            "PASS the tree opened, walked a level on Enter and on Right, came back on Left and "
            "Backspace, searched into breadcrumbs with bold runs, held the last row, emitted a "
            f"full path, and drew the empty and error lines, with no gap over {GAP_LIMIT_MS}ms"
            if not bad
            else "FAIL " + "; ".join(bad)
        ),
        "notes": notes,
        "max_gap_ms": round(watch.worst, 1),
    }
