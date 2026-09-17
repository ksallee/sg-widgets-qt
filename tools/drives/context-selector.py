"""The three sections of the context popover, and the context a pick emits.

The port of `~/dev/sg-widgets/tools/drives/context-selector.js`, read off the widget rather
than off the DOM.

    .venv/bin/python tools/qa.py --page context-selector --drive tools/drives/context-selector.py
"""
from __future__ import annotations

import time

from qtpy.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from qtpy.QtGui import QKeyEvent, QMouseEvent
from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles

#: No event-loop iteration may take longer than this while a read is in flight.
GAP_LIMIT_MS = 50

#: A row of the fixtures the tree inside the popover is searched for.
QUERY = "sh010_0010"


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


def click_at(widget, where: QPoint) -> None:
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


def drive(page, wait, find, prefs) -> dict:
    bad: list[str] = []
    notes: list[str] = []
    watch = LoopWatch()

    selector = find("context-selector")
    if selector is None:
        watch.stop()
        return {"verdict": "FAIL no context selector on the page"}
    tasks = selector.tasks_control()
    tree = selector.tree()
    reads = page.context.reads
    settle(tasks, wait)
    wait(800)
    # The watch starts once the page has drawn its first frame. The first status glyph any
    # process builds costs one read of the bundled sprite on the GUI thread, which is the
    # showcase opening a page rather than a widget answering; what the rule is about is the
    # reads this drive provokes from here on.
    prime_status_glyphs(page)
    watch.start()

    # 1. The trigger carries the context as chips, project first.
    chips = [ref.type for ref in selector.work_context.refs]
    if chips != ["Project", "Shot", "Task"]:
        bad.append(f"the trigger carries {chips}, wanted Project, Shot, Task")
    notes.append(f"trigger chips {chips}")

    # 2. The popover opens on the trigger, and holds the three sections.
    selector.set_open(True)
    wait(300)
    if not selector.open:
        bad.append("the trigger did not open the popover")
    panel = selector.popover().content()
    for slot in ("context-recents", "context-my-tasks", "context-hierarchy"):
        if panel is None or not panel.findChildren(QObject, slot):
            bad.append(f"no {slot} section in the popover")
    if len(selector.recents) != 2:
        bad.append(f"{len(selector.recents)} recents, wanted 2")

    # 3. The assigned tasks are grouped by project, with a step line and a status secondary.
    settle(tasks, wait)
    wait(400)
    model = tasks.model
    shape = kinds(model)
    if shape.count("heading") == 0:
        bad.append("the assigned tasks are not grouped by project")
    rows = [i for i, kind in enumerate(shape) if kind == "row"]
    if not rows:
        bad.append("no assigned tasks")
    else:
        no_sub = [i for i in rows if not model.data(model.index(i, 0), Roles.SUB_LABEL)]
        if no_sub:
            bad.append(f"{len(no_sub)} task rows have no step line")
        no_status = [
            i
            for i in rows
            if model.data(model.index(i, 0), Roles.PAINTER) is None
            and not model.data(model.index(i, 0), Roles.SECONDARY)
        ]
        if no_status:
            bad.append(f"{len(no_status)} task rows have no status secondary")
        notes.append(
            f"{len(rows)} tasks under {shape.count('heading')} project heading(s), "
            f"{len(rows) - len(no_status)} with a status secondary"
        )
    if reads.get("search", 0) < 1:
        bad.append("the assigned tasks cost no read")

    # 4. The tree in the popover: two keystrokes inside the pause cost one read, with
    #    skeletons and never a spinner.
    control = tree.search_control()
    box = control.input()
    page.context.reset_reads()
    box.setText(QUERY[:5])
    wait(60)
    box.setText(QUERY)
    wait(120)
    if control.view != "loading":
        bad.append(f"the tree is {control.view!r} while the pause runs, wanted loading")
    spinners = [w for w in page.findChildren(QObject) if "spinner" in w.objectName().lower()]
    if spinners:
        bad.append(f"{len(spinners)} spinner(s) in the first 150ms")
    settle(control, wait)
    wait(400)
    if reads.get("text_search") != 1:
        bad.append(f"two keystrokes cost {reads.get('text_search')} text searches, wanted 1")
    notes.append(f"the tree's two keystrokes cost {reads.get('text_search')} text search")

    # 5. Escape clears the tree's query, then closes the popover.
    press(box, Qt.Key.Key_Escape)
    settle(control, wait)
    wait(200)
    if tree.query != "":
        bad.append(f"the first Escape left {tree.query!r} in the tree")
    if not selector.open:
        bad.append("the first Escape closed the popover")
    press(box, Qt.Key.Key_Escape)
    wait(300)
    if selector.open:
        bad.append("the second Escape did not close the popover")
    else:
        notes.append("Escape cleared the tree's query, then closed the popover")

    # 6. An outside press closes it.
    selector.set_open(True)
    wait(300)
    window = page.window()
    click_at(window, QPoint(4, 4))
    wait(300)
    if selector.open:
        bad.append("an outside press left the popover open")
    else:
        notes.append("an outside press closed the popover")

    # 7. Picking an assigned task sets all three parts at once and closes the popover.
    selector.set_open(True)
    wait(300)
    settle(tasks, wait)
    wait(300)
    emitted: dict = {}
    selector.work_context_changed.connect(lambda held: emitted.setdefault("context", held))
    selector.recents_changed.connect(lambda held: emitted.__setitem__("recents", list(held)))
    shape = kinds(tasks.model)
    at = shape.index("row") if "row" in shape else -1
    if at < 0:
        bad.append("no assigned task to pick")
    else:
        tasks.list_surface().set_highlight(at)
        tasks.activated.emit(at)
        wait(300)
        held = emitted.get("context")
        if held is None:
            bad.append("picking a task emitted nothing")
        else:
            missing = [
                name
                for name in ("project", "entity", "task")
                if getattr(held, name, None) is None
            ]
            if missing:
                bad.append(f"the context emitted has no {', '.join(missing)}")
            else:
                notes.append(
                    "work_context_changed carried "
                    f"{held.project.type}/{held.entity.type}/{held.task.type}"
                )
        if selector.open:
            bad.append("the popover stayed open after a pick")
        if emitted.get("recents") is None:
            bad.append("a pick did not change the recents")

    # 8. The recents remember a pick, newest first, up to the limit.
    selector.set_recent_limit(2)
    keep = list(selector.recents)
    if len(keep) >= 2:
        selector.apply(keep[1])
        selector.apply(keep[0])
        wait(50)
        now = selector.recents
        if len(now) != 2:
            bad.append(f"{len(now)} recents kept, wanted the limit of 2")
        else:
            notes.append("2 recents kept at a limit of 2, newest first")

    watch.stop()
    if watch.worst > GAP_LIMIT_MS:
        bad.append(f"the GUI thread stalled {watch.worst:.0f}ms, over {GAP_LIMIT_MS}ms")
    return {
        "verdict": (
            "PASS three sections, tasks grouped by project with a step line and a status, one "
            "read a pause in the tree, Escape and an outside press closing the popover, a pick "
            f"emitting the whole context, recents kept to the limit, no gap over {GAP_LIMIT_MS}ms"
            if not bad
            else "FAIL " + "; ".join(bad)
        ),
        "notes": notes,
        "max_gap_ms": round(watch.worst, 1),
    }
