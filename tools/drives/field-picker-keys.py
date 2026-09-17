"""field-picker: the descend keys, and the props that keep a field off the list.

The port of the field-picker half of `~/dev/sg-widgets/tools/drives/filter-editor-stress.js`
and of what `field-picker.tsx`'s own `onKeys` promises, run against the demo rather than
against a picker built for the check.

    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/field-picker-keys.py
    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/field-picker-keys.py --qt5

Five readings:

    right       Right on a link descends and the popup stays open
    enter       Enter on a link that cannot be chosen descends and the popup stays open
    left        Left goes back up a level and clears the query
    data_types  a picker bound to dates offers no date-less field, and still lists the links
    filterable  `filterable_only` drops the types the API refuses in a filter (017)
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtCore import Qt

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import opened, picker_of, press, until  # noqa: E402

#: The data types the restricted example binds, and the ones the API takes no filter on (017).
DATES = ("date", "date_time")
UNFILTERABLE = ("url", "calculated", "password", "serializable", "summary")


def caret_of(picker):
    """Where the keys the levels own are typed: the popup's own search box."""
    from qtpy.QtWidgets import QLineEdit

    return picker.control.search_row().findChild(QLineEdit) or picker.control.caret()


def a_link(picker):
    return next((row for row in picker.derived if row.traversable), None)


def highlight(picker, row) -> int:
    """Put the cursor on a row of the list. `options` answers a fresh list, so paths match."""
    surface = picker.control.list_surface()
    where = next(
        (i for i, one in enumerate(picker.rows_model.rows) if one.path == row.path), -1
    )
    if where >= 0:
        surface.set_highlight(where)
    return where


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    failures: list[str] = []
    seen: dict = {}

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    picker = picker_of(find, "field-picker-free")
    if not opened(picker, wait):
        return {"verdict": "FAIL the field list never answered"}
    caret = caret_of(picker)

    # 1. Right on a link descends, and the popup never closes under it.
    link = a_link(picker)
    if link is None:
        return {"verdict": "FAIL Version offered no link to descend"}
    if highlight(picker, link) < 0:
        return {"verdict": "FAIL the link is not on the list"}
    press(caret, Qt.Key.Key_Right)
    until(lambda: picker.levels.deep, wait, 8000)
    seen["right"] = {"deep": picker.levels.deep, "open": picker.control.is_open}
    if not picker.levels.deep:
        note("right", "Right on a link did not descend")
    if not picker.control.is_open:
        note("right", "Right on a link closed the popup")

    # 2. Left goes back up, and takes the query with it.
    picker.control.set_query("dat")
    wait(120)
    press(caret, Qt.Key.Key_Left)
    until(lambda: not picker.levels.deep, wait, 8000)
    seen["left"] = {
        "deep": picker.levels.deep,
        "query": picker.control.query,
        "open": picker.control.is_open,
    }
    if picker.levels.deep:
        note("left", "Left did not go back up")
    if picker.control.query:
        note("left", f"Left left {picker.control.query!r} in the search box")
    if not picker.control.is_open:
        note("left", "Left closed the popup")

    picker.control.set_open(False)

    # 3. Enter on a link that cannot be chosen descends rather than choosing. A link is
    #    selectable at the root, so the reading is taken on the date-bound picker, where a
    #    link stays on the list without being a date.
    dated = picker_of(find, "field-picker-dates")
    if not opened(dated, wait):
        return {"verdict": "FAIL the date-bound list never answered"}
    link = next((row for row in dated.derived if row.traversable and not row.selectable), None)
    if link is None:
        note("enter", "the date-bound list offered no link that cannot be chosen")
    else:
        highlight(dated, link)
        before = dated.value
        press(caret_of(dated), Qt.Key.Key_Return)
        until(lambda: dated.levels.deep, wait, 8000)
        seen["enter"] = {
            "row": link.name,
            "deep": dated.levels.deep,
            "open": dated.control.is_open,
            "value": dated.value,
        }
        if not dated.levels.deep:
            note("enter", "Enter on a link that cannot be chosen did not descend")
        if not dated.control.is_open:
            note("enter", "Enter on a link closed the popup")
        if dated.value != before:
            note("enter", "Enter on a link that cannot be chosen still chose it")
        dated.levels.reset()
        until(lambda: not dated.levels.deep, wait, 8000)

    # 4. A picker bound to dates offers no date-less field, and keeps the links.
    offered = dated.derived
    wrong = [row.name for row in offered if row.selectable and row.data_type not in DATES]
    links = [row.name for row in offered if row.traversable]
    seen["data_types"] = {"rows": len(offered), "wrong": wrong[:4], "links": len(links)}
    if wrong:
        note("data_types", f"a date picker offers {', '.join(wrong[:4])}")
    if not links:
        note("data_types", "a date picker dropped the links, so a nested date is unreachable")
    dated.control.set_open(False)

    # 5. `filterable_only` drops the types the API takes no filter on (017_filter_operators).
    computed = picker_of(find, "field-picker-computed")
    if not opened(computed, wait):
        return {"verdict": "FAIL the filterable list never answered"}
    rows = computed.derived
    refused = [row.name for row in rows if row.data_type in UNFILTERABLE]
    hidden = [row.name for row in rows if row.data_type == "image"]
    extra = [row.name for row in rows if row.computed]
    seen["filterable"] = {
        "rows": len(rows),
        "refused": refused[:4],
        "hidden": hidden[:4],
        "computed": extra,
    }
    if refused:
        note("filterable", f"filterable_only still offers {', '.join(refused[:4])}")
    if hidden:
        note("filterable", f"hide_paths still offers {', '.join(hidden[:4])}")
    if sorted(extra) != ["note_count", "row_number"]:
        note("filterable", f"the computed columns read {extra}")
    computed.control.set_open(False)

    return {
        "verdict": (
            "PASS Right and Enter descend without closing the popup, Left goes up and clears the"
            " query, and data_types, hide_paths and filterable_only keep their fields off the list"
            if not failures
            else "FAIL " + "; ".join(failures[:6])
        ),
        "failures": failures,
        "seen": seen,
    }
