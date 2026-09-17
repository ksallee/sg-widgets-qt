"""The demo tree's relative-date rows, and what the mock answers for the tree holding them.

The port of `~/dev/sg-widgets/tools/drives/filter-editor-dates.js`.

    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/filter-editor-dates.py
    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/filter-editor-dates.py --qt5

The tree opens with `created_at in_last [3, MONTH]` and `entity.Shot.sg_turnover_date in_next
[2, WEEK]`. It passes when both rows draw their count and their unit, the serialised filter names
both relations, and the result set under the editor answers a count of rows rather than a refusal.

Upstream stops there. The calendar presets are the other half of the date vocabulary and the
docs page promises what each one sends, so the drive walks the `created_at` row through every
calendar entry its menu offers and checks the wire against that table: a signed offset from the
current bucket, `0` being this one, never a count (field_types/date).
"""
from __future__ import annotations

import time

from sg_widgets_core.filter import to_api3_hash
from sg_widgets_core.filter_ux import operator_menu, preset_by_id, relative_window
from sg_widgets_qt.showcase.demos._results import EntityResults
from sg_widgets_qt.widgets.filter_editor import FilterEditor

#: What the docs page promises each calendar entry sends: the operator and the signed offset.
CALENDAR: dict[str, tuple[str, int]] = {
    "today": ("in_calendar_day", 0),
    "yesterday": ("in_calendar_day", -1),
    "tomorrow": ("in_calendar_day", 1),
    "this_week": ("in_calendar_week", 0),
    "last_week": ("in_calendar_week", -1),
    "next_week": ("in_calendar_week", 1),
    "this_month": ("in_calendar_month", 0),
    "last_month": ("in_calendar_month", -1),
    "next_month": ("in_calendar_month", 1),
    "this_year": ("in_calendar_year", 0),
    "last_year": ("in_calendar_year", -1),
    "next_year": ("in_calendar_year", 1),
}


def wait_for(read, wait, ms: int = 15000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def relative_rows(editor: FilterEditor) -> list[dict]:
    """Every row of the tree on `in the last` or `in the next`, with what its controls hold."""
    found: list[dict] = []
    for node in _walk(editor.value):
        if node.kind != "condition" or node.operator not in ("in_last", "in_next"):
            continue
        window = relative_window(node.value)
        found.append(
            {
                "path": node.path,
                "operator": node.operator,
                "count": window.count,
                "unit": window.unit,
            }
        )
    return found


def _walk(node):
    if node.kind == "condition":
        yield node
        return
    for child in node.conditions:
        yield from _walk(child)


def index_of(editor: FilterEditor, path: str) -> int:
    for i, child in enumerate(editor.value.conditions):
        if child.kind == "condition" and child.path == path:
            return i
    return -1


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(600)
    editor = find("filter-editor-main")
    if not isinstance(editor, FilterEditor):
        every = find(FilterEditor, all=True)
        editor = every[0] if every else None
    results = find(EntityResults, all=True)
    if editor is None or not results:
        return {"verdict": "FAIL the page has no filter editor with a result set under it"}
    count_line = results[0]
    wait_for(lambda: editor.fields(), wait, 8000)
    # The count line is debounced and the first read is a summarize, so the set settles late.
    wait_for(lambda: count_line.count.kind != "counting", wait, 20000)
    wait(300)

    failures: list[str] = []
    rows = relative_rows(editor)
    if len(rows) != 2:
        failures.append(f"{len(rows)} relative rows, wanted 2")
    for row in rows:
        if not row["count"] or float(row["count"]) < 1:
            failures.append(f"{row['operator']} has no count")
        if str(row["unit"]).upper() not in ("MONTH", "WEEK", "DAY", "HOUR", "YEAR"):
            failures.append(f"{row['operator']} has no unit")

    wire = to_api3_hash(editor.value)
    text = str(wire)
    if "in_last" not in text or "in_next" not in text:
        failures.append("the serialised filter names neither in_last nor in_next")

    count = count_line.count
    if count.kind == "error":
        failures.append(f"the count line reads {count.message!r}")
    elif count.kind != "ready":
        failures.append(f"the count line never answered: {count.kind}")
    elif count.total == 0:
        failures.append("the tree matched no rows")
    if editor.error:
        failures.append(f"the editor reads {editor.error!r}")

    # The calendar half: every entry of the `created_at` menu, against the docs page's table.
    at = index_of(editor, "created_at")
    if at < 0:
        # The relative rows sit in the nested group; the root's own date row is the one walked.
        for i, child in enumerate(editor.value.conditions):
            if child.kind == "condition" and editor.data_type_of(child.path) in ("date", "date_time"):
                at = i
                break
    calendar: list[dict] = []
    if at < 0:
        node = None
        for i, child in enumerate(editor.value.conditions):
            if child.kind == "condition":
                node = child
                at = i
                break
        if node is not None:
            editor.pick_field([at], node, "created_at")
            wait_for(lambda: (editor.node_at([at]) or node).path == "created_at", wait, 8000)
    node = editor.node_at([at]) if at >= 0 else None
    if node is None or node.kind != "condition":
        failures.append("no date row to walk the calendar entries on")
    else:
        data_type = editor.data_type_of(node.path)
        offered = [
            preset.id
            for run in operator_menu(data_type)
            for preset in run.presets
            if preset.id in CALENDAR
        ]
        if not offered:
            failures.append(f"the {data_type} menu offers no calendar entry")
        for preset_id in offered:
            here = editor.node_at([at])
            editor.pick_preset([at], here, preset_id)
            wait(80)
            after = editor.node_at([at])
            operator, offset = CALENDAR[preset_id]
            got = (after.operator, after.value) if after is not None else ("", None)
            calendar.append({"preset": preset_id, "operator": got[0], "value": got[1]})
            if got[0] != operator or got[1] != offset:
                failures.append(
                    f"{preset_id} sends {got[0]} {got[1]!r}, wanted {operator} {offset}"
                )
            if preset_by_id(data_type, preset_id) is None:
                failures.append(f"{preset_id} is not a preset of {data_type}")

    label = f"{count.total} Versions match" if count.kind == "ready" else count.kind
    return {
        "verdict": (
            f"PASS both relative rows draw a count and a unit, the filter names in_last and"
            f" in_next, {len(calendar)} calendar entries send the offset the docs page promises,"
            f" and the set reads {label}"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "relative": rows,
        "calendar": calendar,
        "count": label,
    }
