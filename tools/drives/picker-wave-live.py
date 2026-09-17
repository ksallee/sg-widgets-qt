"""The picker wave against the test site, read-only.

The live half of this wave's QA, beside `tools/drives/picker-live.py`, which is the entity
picker's. One drive serves the three pages that read something a site alone can answer:

    .venv/bin/python tools/qa.py --page status-picker --live --drive tools/drives/picker-wave-live.py
    .venv/bin/python tools/qa.py --page user-picker    --live --drive tools/drives/picker-wave-live.py
    .venv/bin/python tools/qa.py --page project-picker --live --drive tools/drives/picker-wave-live.py

On a status page it opens the first picker and reads what every option's glyph resolved to: the
stock cells are bundled in core and draw without the site, so the run is only meaningful against
a site for the cells that are not bundled, which is what `sprite` counts here
(`docs/design-rules.md` rule 9, probe 010). On a user or project page it types two letters, waits
for the rows the site answers, takes the highlighted one with Enter and reads the shape of the
reference that landed.

Nothing is written. What it prints is kinds, shapes and counts — never a name, a login or an
address the site holds, which is the rule for anything a run leaves behind.
"""
from __future__ import annotations

import time

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.widgets.entity_picker import EntitySearchPicker
from sg_widgets_qt.widgets.status_picker import StatusPicker

#: The site is slower than the mock, and a first call may open a connection.
READ_MS = 25000

#: A two-letter query, which is what a person types before the list is worth reading.
QUERY = "sh"


def wait_for(read, wait, ms: int = READ_MS) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if read():
            return True
    return False


def shape_of(ref: object) -> dict:
    """What a reference carries, by field and type. Never what it says."""
    return {
        "fields": sorted(
            name for name in ("type", "id", "name") if getattr(ref, name, None) is not None
        ),
        "type_is": type(getattr(ref, "type", None)).__name__,
        "id_is": type(getattr(ref, "id", None)).__name__,
        "named": bool(getattr(ref, "name", "")),
    }


def glyphs_of(picker: StatusPicker) -> dict:
    """What every option's glyph resolved to, by kind, and how many hold a picture.

    The sources are the picker's own, one per code, which is what the row delegate paints
    through, so this reads exactly what the list draws.
    """
    sources = getattr(picker, "_sources", {})
    kinds: dict = {}
    drawn = 0
    for source in sources.values():
        kinds[source.kind] = kinds.get(source.kind, 0) + 1
        pixmap = source.pixmap
        if pixmap is not None and not pixmap.isNull():
            drawn += 1
    return {"codes": len(sources), "kinds": kinds, "with_picture": drawn}


def check_statuses(page, wait, find, note) -> dict:
    """Open the first status picker and read what its glyphs drew."""
    pickers = [
        picker
        for picker in find(StatusPicker, all=True)
        if not picker.disabled and not picker.readonly
    ]
    if not pickers:
        note("no status picker on the page")
        return {}
    picker = pickers[0]
    if not wait_for(lambda: bool(picker.options), wait):
        note("the site answered no status for the field")
        return {}
    picker.control.set_open(True)
    if not wait_for(lambda: picker.control.list_surface().row_count() > 0, wait):
        note("the status list drew no row")
        picker.control.set_open(False)
        return {}
    # A cell is read over http, so the picture lands after the row it belongs to.
    wait_for(lambda: glyphs_of(picker)["with_picture"] > 0, wait, 12000)
    wait(600)
    seen = glyphs_of(picker)
    seen["site"] = bool(picker.site_url)
    if not picker.site_url:
        note("the picker has no site url, so a sprite cell could not be read")
    if seen["with_picture"] == 0:
        note(f"no status glyph drew a picture: {seen['kinds']}")
    picker.control.set_open(False)
    wait(200)
    return seen


def two_letters(picker, wait) -> str:
    """Two letters the site can answer: the opening of a row the browse list already holds.

    A fixed query is a guess about what a site is named, and a site with no `sh` on it would
    fail a run that proves nothing. The browse list is read first and its first row lends its
    own two letters, which are never printed.
    """
    if not wait_for(lambda: bool(picker.state.rows), wait, 12000):
        return QUERY
    name = str(getattr(picker.state.rows[0], "name", "") or "")
    letters = "".join(ch for ch in name if ch.isalnum())[:2]
    return letters if len(letters) == 2 else QUERY


def check_search(page, wait, find, note) -> dict:
    """Type two letters into the page's first picker, wait for the site, and take one row."""
    pickers = [
        picker
        for picker in find(EntitySearchPicker, all=True)
        if not picker.disabled and not picker.readonly and not picker.MULTIPLE
    ]
    if not pickers:
        note("no single entity picker on the page")
        return {}
    picker = pickers[0]
    control = picker.control
    control.set_open(True)
    query = two_letters(picker, wait)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, query)
    if not wait_for(
        lambda: control.list_surface().row_count() > 0 and picker.state.query == query, wait
    ):
        note(f"the site answered no row for a {len(query)}-letter query")
        control.set_open(False)
        return {}
    wait(500)
    counts: dict = {}
    for row in picker.state.rows:
        counts[row.type] = counts.get(row.type, 0) + 1
    before = len(control.keys)
    control.list_surface().highlight_first()
    QTest.keyClick(caret, Qt.Key.Key_Return)
    wait(800)
    seen = {
        "rows": sum(counts.values()),
        "types": counts,
        "chosen": len(control.keys) - before,
        "closed_on_pick": not control.is_open,
    }
    value = picker.value
    seen["ref"] = shape_of(value) if value is not None else None
    if value is None:
        note("Enter on the highlighted row emitted no reference")
    if control.is_open:
        note("a pick left the single picker open")
    control.set_open(False)
    wait(200)
    return seen


def drive(page, wait, find, prefs) -> dict:
    wait(800)
    notes: list = []
    seen: dict = {"page": page.data_name}

    def note(detail: str) -> None:
        notes.append(f"{page.data_name}: {detail}")

    context = page.context
    if context is None or not context.live:
        return {"verdict": "FAIL the page is not reading the site; pass --live"}

    if find(StatusPicker, all=True):
        seen["statuses"] = check_statuses(page, wait, find, note)
    if find(EntitySearchPicker, all=True):
        seen["search"] = check_search(page, wait, find, note)
    if "statuses" not in seen and "search" not in seen:
        return {"verdict": f"FAIL {page.data_name} carries no picker this drive reads"}

    return {
        "verdict": (
            f"PASS {page.data_name} read the site: every glyph resolved and a two-letter query"
            " answered rows one Enter could take"
            if not notes
            else "FAIL " + "; ".join(notes)
        ),
        "notes": notes,
        "seen": seen,
    }
