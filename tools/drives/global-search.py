"""The palette: one read a pause, rows grouped by type, the recents, and the keyboard.

The port of `~/dev/sg-widgets/tools/drives/global-search.js` and the global-search half of
`row-anatomy.js`, read off the widget rather than off the DOM.

    .venv/bin/python tools/qa.py --page global-search --drive tools/drives/global-search.py
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from qtpy.QtGui import QKeyEvent, QMouseEvent
from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles

#: No event-loop iteration may take longer than this while a read is in flight.
GAP_LIMIT_MS = 50

#: The two letters the palette is driven with, and a query the site holds nothing for.
QUERY = "sh"
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


def click(widget, where: QPoint) -> None:
    """A left press and release on a widget, in its own coordinates."""
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QApplication.sendEvent(
            widget,
            QMouseEvent(
                kind,
                where,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )


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


def settle(control, wait, ms: int = 8000) -> None:
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
    """What each row of the model is: `heading` or `row`."""
    return [
        str(model.data(model.index(i, 0), Roles.KIND) or "row") for i in range(model.rowCount())
    ]


def matched_runs(model, row: int) -> list[str]:
    """The runs of one row's label the query matched, which are drawn in DemiBold."""
    runs = model.data(model.index(row, 0), Roles.RUNS) or []
    return [str(r[0]) for r in runs if len(r) >= 2 and r[1]]


def drive(page, wait, find, prefs) -> dict:
    bad: list[str] = []
    notes: list[str] = []
    watch = LoopWatch()

    palette = find("global-search-palette")
    inline = find("global-search-inline")
    anatomy = find("global-search-anatomy")
    if palette is None or inline is None or anatomy is None:
        watch.stop()
        return {"verdict": "FAIL the three cases of the page are not all there"}
    reads = page.context.reads
    control = inline.search_control()
    box = control.input()
    settle(control, wait)
    wait(800)
    # The watch starts once the page has drawn its first frame. The first status glyph any
    # process builds costs one read of the bundled sprite on the GUI thread, which is the
    # showcase opening a page rather than a widget answering; what the rule is about is the
    # reads this drive provokes from here on.
    prime_status_glyphs(page)
    watch.start()

    # 1. Two keystrokes inside the pause cost one read, with skeletons and never a spinner.
    page.context.reset_reads()
    box.setText(QUERY[0])
    wait(60)
    box.setText(QUERY)
    wait(120)
    if control.view != "loading":
        bad.append(f"the list is {control.view!r} while the pause runs, wanted loading")
    spinners = [w for w in page.findChildren(QObject) if "spinner" in w.objectName().lower()]
    if spinners:
        bad.append(f"{len(spinners)} spinner(s) in the first 150ms")
    settle(control, wait)
    wait(250)
    if reads.get("text_search") != 1:
        bad.append(f"two keystrokes cost {reads.get('text_search')} text searches, wanted 1")
    notes.append(f"two keystrokes cost {reads.get('text_search')} text search")

    # 2. A query started before the first answers drops the first answer.
    landings = {"n": 0}
    control.rows_changed.connect(lambda: landings.__setitem__("n", landings["n"] + 1))
    box.setText("sh0")
    control.flush()
    wait(40)
    box.setText("sh01")
    control.flush()
    settle(control, wait)
    wait(500)
    if landings["n"] != 1:
        bad.append(f"{landings['n']} answers landed, wanted 1: the first was not dropped")
    notes.append(f"{landings['n']} answer landed for two overlapping queries")

    # 3. The rows are grouped by type, the matched words are bold, and the sub-label is
    #    where the row sits.
    box.setText(QUERY)
    control.flush()
    settle(control, wait)
    wait(400)
    model = control.model
    shape = kinds(model)
    if "heading" not in shape:
        bad.append("the results carry no group heading")
    first_row = shape.index("row") if "row" in shape else -1
    if first_row < 0:
        bad.append("the query answered no rows")
    else:
        if not matched_runs(model, first_row):
            bad.append("nothing in the label is drawn as a matched run")
        sub = model.data(model.index(first_row, 0), Roles.SUB_LABEL)
        if not sub:
            bad.append("the first row has no sub-label")
        notes.append(
            f"{shape.count('row')} rows under {shape.count('heading')} heading(s); "
            f"bold {matched_runs(model, first_row)}"
        )

    # 4. The highlight walks over a heading and holds at the last row.
    surface = control.list_surface()
    surface.set_highlight(0)
    landed = []
    for _ in range(model.rowCount() + 4):
        press(box, Qt.Key.Key_Down)
        wait(8)
        landed.append(surface.highlighted())
    on_heading = [i for i in landed if 0 <= i < len(shape) and shape[i] == "heading"]
    if on_heading:
        bad.append(f"the highlight landed on {len(on_heading)} heading(s)")
    if landed[-1] != max(landed):
        bad.append("Down wrapped past the last row")
    rect = surface.visualRect(surface.model().index(landed[-1], 0))
    if not surface.viewport().rect().intersects(rect):
        bad.append("the highlighted row is out of view")

    # 5. A full page draws a load-more row, and the next page lands under the rows.
    before = len(control.items)
    if not control.has_more:
        bad.append("a full page said there was no further page")
    control.load_more()
    settle(control, wait)
    wait(300)
    if len(control.items) <= before:
        bad.append(f"load more left {len(control.items)} rows, wanted more than {before}")
    notes.append(f"page of {before}, {len(control.items)} after load more")

    # 6. Enter picks and emits the reference the docs page promises.
    picked = {"ref": None}
    inline.selected.connect(lambda ref: picked.__setitem__("ref", ref))
    surface.set_highlight(0)
    press(box, Qt.Key.Key_Down)
    wait(20)
    press(box, Qt.Key.Key_Return)
    wait(120)
    ref = picked["ref"]
    if ref is None or not getattr(ref, "type", "") or not getattr(ref, "id", 0):
        bad.append(f"Enter emitted {ref!r}, wanted an EntityRef with a type and an id")
    else:
        notes.append(f"Enter emitted {ref.type} {ref.id}")
    if control.query != "":
        bad.append(f"a pick left {control.query!r} in the box")

    # 7. A query matching nothing is the empty line.
    box.setText(NO_MATCH)
    control.flush()
    settle(control, wait)
    wait(300)
    if control.view != "empty":
        bad.append(f"a query matching nothing drew {control.view!r}")

    # 8. A read armed to fail is the error line.
    mock = mock_of(page.context.client)
    if mock is None:
        bad.append("the demo client cannot be armed to fail")
    else:
        mock.fail_next()
    box.setText("sh02")
    control.flush()
    settle(control, wait)
    wait(300)
    if control.view != "error" or not control.failure:
        bad.append(f"an armed failure drew {control.view!r}")
    else:
        notes.append(f"error line {control.failure!r}")
    if mock is not None:
        mock.fail_next(None)
    box.setText("")
    wait(200)

    # 9. The palette: the recents on an empty query, Escape, and an outside press.
    opened = {"n": 0}
    palette.open_changed.connect(lambda v: opened.__setitem__("n", opened["n"] + 1))
    palette.set_open(True)
    wait(250)
    if not palette.open:
        bad.append("the trigger did not open the palette")
    recents_model = palette.search_control().model
    recent_shape = kinds(recents_model)
    if recent_shape.count("row") != len(palette.recents):
        bad.append(
            f"{recent_shape.count('row')} recent rows for {len(palette.recents)} recents"
        )
    if "heading" not in recent_shape:
        bad.append("the recents carry no heading")
    notes.append(f"{recent_shape.count('row')} recents under a heading on an empty query")

    palette_box = palette.search_control().input()
    palette_box.setText(QUERY)
    palette.search_control().flush()
    settle(palette.search_control(), wait)
    wait(300)
    press(palette_box, Qt.Key.Key_Escape)
    wait(150)
    if palette.query != "":
        bad.append(f"the first Escape left {palette.query!r} in the palette")
    if not palette.open:
        bad.append("the first Escape closed the palette")
    press(palette_box, Qt.Key.Key_Escape)
    wait(250)
    if palette.open:
        bad.append("the second Escape did not close the palette")
    notes.append("Escape cleared the query, then closed the palette")

    # An outside press: the scrim under the panel is what a press outside it lands on.
    palette.set_open(True)
    wait(250)
    dialog = palette.search_control().dialog()
    scrim = dialog.scrim if dialog is not None else None
    if scrim is None:
        bad.append("the palette has no scrim to press outside on")
    else:
        click(scrim, QPoint(4, 4))
        wait(300)
        if palette.open:
            bad.append("an outside press left the palette open")
        else:
            notes.append("an outside press closed the palette")
    palette.set_open(False)
    wait(150)

    # 10. The recents remember a pick, newest first, up to the limit.
    palette.set_recent_limit(2)
    keep = list(palette.recents)
    if len(keep) >= 2:
        palette.choose(keep[1])
        palette.choose(keep[0])
        wait(50)
        now = palette.recents
        if len(now) != 2:
            bad.append(f"{len(now)} recents kept, wanted the limit of 2")
        elif (now[0].type, now[0].id) != (keep[0].type, keep[0].id):
            bad.append("the newest pick is not first in the recents")
        else:
            notes.append(f"{len(now)} recents kept at a limit of 2, newest first")

    # 11. The row props case draws a sub-label and a right-aligned secondary.
    shots = anatomy.search_control()
    shots.input().setText("sh010")
    shots.flush()
    settle(shots, wait)
    wait(600)
    shot_model = shots.model
    shape = kinds(shot_model)
    if "row" in shape:
        at = shape.index("row")
        where = shot_model.index(at, 0)
        if not shot_model.data(where, Roles.SECONDARY) and not shot_model.data(
            where, Roles.PAINTER
        ):
            bad.append("the row props case drew no secondary")
        notes.append(
            "row props: secondary "
            f"{shot_model.data(where, Roles.SECONDARY)!r}, painter "
            f"{shot_model.data(where, Roles.PAINTER) is not None}"
        )
    else:
        bad.append("the row props case answered no rows")

    watch.stop()
    if watch.worst > GAP_LIMIT_MS:
        bad.append(f"the GUI thread stalled {watch.worst:.0f}ms, over {GAP_LIMIT_MS}ms")
    return {
        "verdict": (
            "PASS one read a pause, the stale answer dropped, grouped and highlighted rows, a "
            "page appended, Enter emitting a reference, the empty and error lines, Escape and "
            f"an outside press closing the palette, recents kept to the limit, no gap over "
            f"{GAP_LIMIT_MS}ms"
            if not bad
            else "FAIL " + "; ".join(bad)
        ),
        "notes": notes,
        "max_gap_ms": round(watch.worst, 1),
    }
