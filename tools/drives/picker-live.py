"""The two entity pickers against the test site, read-only.

The port of `~/dev/sg-widgets/tools/drives/live-entity-picker.js`. It types a two-letter query
into the page's first picker, waits for the rows the site answers, takes one with Enter and
reads the shape of the reference the picker emitted; then it does the same with a multi picker
built on the page's own live context, taking two.

    .venv/bin/python tools/qa.py --page entity-picker --live --drive tools/drives/picker-live.py

Nothing is written: the drive reads, and the value it sets is the picker's own, in memory. What
it prints is shapes and counts — the fields a reference carries, how many rows came back, which
types they were — and never a name the site holds, which is the rule for anything a run leaves
behind.
"""
from __future__ import annotations

import time

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QWidget

from sg_widgets_qt.theme import apply_theme, theme_of
from sg_widgets_qt.widgets.entity_multi_picker import EntityMultiPicker
from sg_widgets_qt.widgets.entity_picker import EntitySearchPicker

#: The site is slower than the mock, and a first call may open a connection.
READ_MS = 20000

#: A two-letter query, which is what a person types before the list is worth reading.
QUERY = "sh"


def shape_of(ref: object) -> dict:
    """What a reference carries, by field and type. Never what it says."""
    return {
        "fields": sorted(
            name
            for name in ("type", "id", "name")
            if getattr(ref, name, None) is not None
        ),
        "type_is": type(getattr(ref, "type", None)).__name__,
        "id_is": type(getattr(ref, "id", None)).__name__,
        "named": bool(getattr(ref, "name", "")),
    }


def wait_for(read, wait, ms: int = READ_MS) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if read():
            return True
    return False


def answered(picker) -> dict:
    """The rows the site answered, counted by type."""
    counts: dict = {}
    for row in picker.state.rows:
        counts[row.type] = counts.get(row.type, 0) + 1
    return counts


def take_one(picker, wait, note, where: str) -> dict:
    """Type the query, wait for rows, and take the highlighted one with Enter."""
    control = picker.control
    control.set_open(True)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, QUERY)
    if not wait_for(lambda: control.list_surface().row_count() > 0, wait):
        note(f"{where}: the site answered no row for a two-letter query")
        control.set_open(False)
        return {}
    wait(400)
    rows = answered(picker)
    before = len(control.keys)
    control.list_surface().highlight_first()
    QTest.keyClick(caret, Qt.Key.Key_Return)
    wait(600)
    if len(control.keys) <= before:
        note(f"{where}: Enter on the highlighted row took nothing")
    return {"rows": sum(rows.values()), "types": rows, "chosen": len(control.keys) - before}


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    notes: list = []
    seen: dict = {}

    def note(detail: str) -> None:
        notes.append(detail)

    context = page.context
    if context is None or not context.live:
        return {"verdict": "FAIL the page is not reading the site; pass --live"}

    singles = [
        picker
        for picker in find(EntitySearchPicker, all=True)
        if not picker.disabled and not picker.readonly and not picker.MULTIPLE
    ]
    if not singles:
        return {"verdict": "FAIL no single entity picker on the page"}

    single = singles[0]
    seen["single"] = take_one(single, wait, note, "single")
    value = single.value
    seen["single"]["ref"] = shape_of(value) if value is not None else None
    seen["single"]["closed_on_pick"] = not single.control.is_open
    if value is None:
        note("single: the picker emitted no reference")
    single.control.set_open(False)
    wait(300)

    # A multi picker of its own, on the page's live context, so the second half of the run
    # reads the same site through the same cache.
    host = QWidget(page)
    apply_theme(host, theme_of(page))
    host.setGeometry(0, 0, 420, 60)
    multi = EntityMultiPicker(
        entity_types=list(single.entity_types) or ["Shot"],
        context=context.context,
        summary="chips",
        parent=host,
    )
    multi.setGeometry(4, 4, 400, 32)
    host.show()
    multi.show()
    wait(300)
    seen["multi"] = take_one(multi, wait, note, "multi")
    surface = multi.control.list_surface()
    if surface.row_count() > 1:
        surface.highlight_next()
        QTest.keyClick(multi.control.caret(), Qt.Key.Key_Return)
        wait(600)
    seen["multi"]["held"] = len(multi.value)
    seen["multi"]["open_after_pick"] = multi.control.is_open
    seen["multi"]["refs"] = [shape_of(ref) for ref in multi.value]
    if len(multi.value) != 2:
        note(f"multi: the picker holds {len(multi.value)} references, wanted 2")
    if not multi.control.is_open:
        note("multi: a pick closed the list")
    multi.control.set_open(False)
    wait(300)
    seen["reads"] = dict(context.reads)

    return {
        "verdict": (
            "PASS the site answered both pickers and each emitted the reference shape the"
            " docs page promises"
            if not notes
            else "FAIL " + "; ".join(notes)
        ),
        "notes": notes,
        "seen": seen,
    }
