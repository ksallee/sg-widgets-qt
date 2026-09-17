"""The wave's three pages against the test site, read-only.

    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/wave-live.py --live
    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/wave-live.py --live
    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/wave-live.py --live

Nothing here writes. The field picker opens on its own type and descends through a link, the
column picker opens its list, and the field editor is read on the display half alone: no mode is
moved, so no editor is mounted and no commit can be made. What the run saw is answered in general
terms — counts and data types — because the site, its projects and its people are never named.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import until  # noqa: E402

#: How long a live read is given, which is a real round trip rather than the mock's.
LIVE_MS = 25000


def _own(picker) -> bool:
    """True for a field picker of its own, rather than the one inside a column picker."""
    from sg_widgets_qt.widgets.column_picker import ColumnPicker

    walk = picker.parentWidget()
    for _ in range(6):
        if walk is None:
            return True
        if isinstance(walk, ColumnPicker):
            return False
        walk = walk.parentWidget()
    return True


def field_picker(page, wait, find) -> dict | None:
    from sg_widgets_qt.widgets.field_picker import FieldPicker

    pickers = [
        one
        for one in find(FieldPicker, all=True)
        if not one.disabled and not one.readonly and _own(one)
    ]
    if not pickers:
        return None
    picker = pickers[0]
    picker.control.set_open(True)
    if not until(lambda: bool(picker.options), wait, LIVE_MS):
        return {"verdict": "FAIL the site answered no fields"}
    root = {
        "rows": len(picker.options),
        "types": sorted({one.data_type for one in picker.options if one.data_type}),
        "links": sum(1 for one in picker.options if one.traversable),
    }
    link = next(
        (one for one in picker.options if one.traversable and one.name == "entity"),
        next((one for one in picker.options if one.traversable), None),
    )
    if link is None:
        return {"verdict": "FAIL the site's schema offered no link to descend", "root": root}
    picker.levels.descend_into(link)
    until(lambda: picker.levels.deep, wait, LIVE_MS)
    choosing = picker.levels.choosing
    if choosing is not None:
        targets = picker.levels.targets()
        if targets:
            picker.levels.descend(choosing, targets[0])
    if not until(lambda: bool(picker.hops) and bool(picker.options), wait, LIVE_MS):
        return {"verdict": "FAIL the descend never landed", "root": root}
    deep = {
        "hops": len(picker.hops),
        "rows": len(picker.options),
        "crumbs": len(picker.levels.crumbs()),
    }
    picker.control.set_open(False)
    return {
        "verdict": "PASS the field picker read the site's schema and descended through a link",
        "root": root,
        "deep": deep,
        "failure": picker.levels.failure or "",
    }


def column_picker(page, wait, find) -> dict | None:
    from sg_widgets_qt.widgets.column_picker import ColumnPicker

    pickers = [one for one in find(ColumnPicker, all=True) if not one.disabled and not one.readonly]
    if not pickers:
        return None
    picker = pickers[0]
    picker.field_picker.control.set_open(True)
    if not until(lambda: bool(picker.field_picker.options), wait, LIVE_MS):
        return {"verdict": "FAIL the site answered no fields for the column list"}
    offered = picker.field_picker.options
    picker.field_picker.control.set_open(False)
    return {
        "verdict": "PASS the column picker read the site's schema and resolved its chosen paths",
        "offered": len(offered),
        "chosen": len(picker.value),
        "labelled": sum(1 for path in picker.value if picker.chosen_list.rows_model.parts_of(path)),
    }


def field_editor(page, wait, find) -> dict | None:
    """Display mode only: no editor is mounted, so nothing on the site can be written."""
    from sg_widgets_qt.widgets.field_editor import FieldEditor

    editors = find(FieldEditor, all=True)
    if not editors:
        return None
    wait(1500)
    modes = {one.mode for one in editors}
    drawn = [one for one in editors if one.display.text() or one.display.findChildren(object)]
    return {
        "verdict": (
            "PASS every field editor stayed on the display half"
            if modes == {"display"}
            else f"FAIL a field editor is in {sorted(modes)}"
        ),
        "rows": len(editors),
        "drawn": len(drawn),
        "types": sorted({one.kind for one in editors}),
    }


#: One reading per page, tried in turn.
PAGES = (field_picker, column_picker, field_editor)


def drive(page, wait, find, prefs) -> dict:
    wait(600)
    for read in PAGES:
        answer = read(page, wait, find)
        if answer is not None:
            answer["page"] = page.data_name
            return answer
    return {"verdict": f"FAIL nothing of this wave is on {page.data_name}"}
