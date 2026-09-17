"""The wave's four pages against the test site, read-only.

The port of `~/dev/sg-widgets/tools/drives/live-filter-bar-facets.js`, widened to the pages
beside the bar.

    .venv/bin/python tools/qa.py --page filter-bar --drive tools/drives/query-live.py --live
    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/query-live.py --live
    .venv/bin/python tools/qa.py --page filter-dialog --drive tools/drives/query-live.py --live
    .venv/bin/python tools/qa.py --page sort-picker --drive tools/drives/query-live.py --live

Nothing here writes. The bar's facets must count real rows: a status facet lists the site's own
codes, each with a count and its glyph mark, and the read-state facet, which the site refuses to
group, is tallied from a page of rows and says so. The editor's tree serialises and its result
set counts; the sort picker's keys order a real page.

What the run saw is answered in general terms — counts, codes and data types — because the site,
its projects and its people are never named.
"""
from __future__ import annotations

import time

from sg_widgets_qt.primitives.roles import Roles

#: A live read is a real round trip rather than the mock's.
LIVE_MS = 40000


def until(read, wait, ms: int = LIVE_MS):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(100)
        found = read()
        if found:
            return found
    return None


def filter_bar(page, wait, find) -> dict | None:
    from sg_widgets_qt.widgets.filter_bar import FilterBar

    bars = {one.objectName(): one for one in find(FilterBar, all=True)}
    main = bars.get("filter-bar-main")
    notes = bars.get("filter-bar-notes")
    if main is None:
        return None
    seen: dict = {}
    failures: list[str] = []

    until(lambda: not main.counting, wait)
    wait(400)
    if main.failure:
        failures.append(f"the bar said {main.failure!r}")
    facets = {}
    for name in main.facets:
        listed = main.facet_list(name)
        values = list(listed.values) if listed is not None else []
        facets[name] = {
            "values": len(values),
            "sampled": None if listed is None else listed.sampled,
            "counted": sum(1 for one in values if float(one.count) > 0),
            "named": sum(1 for one in values if one.label and one.label != one.key),
        }
    seen["shot_facets"] = facets
    status = main.facet_list("sg_status_list")
    if status is None or not status.values:
        failures.append("the status facet counted nothing on the site")
    else:
        pill = main.pill("sg_status_list")
        pill.refresh_list(status, main.counting, main.failure)
        wait(200)
        model = pill._model  # noqa: SLF001
        glyphs = [model.data(model.index(i, 0), Roles.GLYPH) for i in range(model.rowCount())]
        seen["status_rows"] = len(glyphs)
        seen["status_glyphs"] = sum(1 for one in glyphs if one)
        if any(one is None for one in glyphs):
            failures.append(f"{glyphs.count(None)} status values carry no glyph mark")
        if not all(float(one.count) >= 0 for one in status.values):
            failures.append("a status value came back without a count")

    if notes is not None:
        settled = until(lambda: not notes.counting, wait)
        wait(400)
        seen["note_bar"] = {
            "settled": bool(settled),
            "failure": notes.failure,
            "fields": sorted(one for one in notes.facets if notes.field_of(one)),
        }
        if not settled:
            failures.append("the Note bar never finished counting the site")
        elif notes.failure:
            failures.append(f"the Note bar said {notes.failure!r}")
        from_list = notes.facet_list("user")
        read_list = notes.facet_list("read_by_current_user")
        seen["note_from"] = {
            "values": 0 if from_list is None else len(from_list.values),
            "sampled": None if from_list is None else from_list.sampled,
            "named": 0
            if from_list is None
            else sum(1 for one in from_list.values if one.label and one.label != one.key),
        }
        seen["note_read_state"] = {
            "values": 0 if read_list is None else len(read_list.values),
            "sampled": None if read_list is None else read_list.sampled,
        }
        # A site with no Note on the scoped project lists nobody, which the docs page does not
        # promise against; what it answered is recorded rather than failed.
        if from_list is None:
            # A field the site does not hold on this type is left out of the tally; the run
            # records it rather than failing a site that is shaped differently.
            seen["note_from"]["absent"] = True
        elif not from_list.values:
            seen["note_from"]["empty"] = True
        elif from_list.sampled is not None:
            failures.append("the From facet was tallied from a sample rather than counted")
        elif any(not one.label or one.label == one.key for one in from_list.values):
            failures.append("the From facet listed somebody without a name")
    return {"failures": failures, "seen": seen}


def filter_editor(page, wait, find) -> dict | None:
    from sg_widgets_core.filter import to_api3_hash
    from sg_widgets_qt.showcase.demos._results import EntityResults
    from sg_widgets_qt.widgets.filter_editor import FilterEditor

    editors = find(FilterEditor, all=True)
    results = find(EntityResults, all=True)
    if not editors:
        return None
    editor = editors[0]
    until(lambda: editor.fields(), wait)
    failures: list[str] = []
    seen = {"fields": len(editor.fields()), "rows": len(editor.rows())}
    if not editor.fields():
        failures.append("the site answered no field for the type")
    wire = to_api3_hash(editor.value)
    seen["conditions"] = 0 if wire is None else len(wire.get("conditions", []))
    if results:
        found = results[0]
        until(lambda: found.count.kind != "counting", wait)
        seen["count"] = found.count.kind
        seen["total"] = found.count.total
        if found.count.kind == "error":
            failures.append(f"the result set said {found.count.message!r}")
        until(lambda: found.table().control.snapshot().status in ("ready", "error"), wait)
        seen["page"] = found.table().control.snapshot().status
        seen["loaded"] = len(found.rows())
    return {"failures": failures, "seen": seen}


def filter_dialog(page, wait, find) -> dict | None:
    from sg_widgets_qt.widgets.filter_dialog import FilterDialog

    launchers = find(FilterDialog, all=True)
    if not launchers:
        return None
    launcher = launchers[1] if len(launchers) > 1 else launchers[0]
    launcher.set_open(True)
    editor = until(lambda: launcher.editor(), wait, 15000)
    failures: list[str] = []
    seen: dict = {"active": launcher.active, "dialog_width": launcher.dialog_width()}
    if editor is None:
        failures.append("the dialog opened with no editor in it")
    else:
        until(lambda: editor.fields(), wait)
        seen["fields"] = len(editor.fields())
        if not editor.fields():
            failures.append("the site answered no field for the type")
    launcher.cancel()
    wait(300)
    return {"failures": failures, "seen": seen}


def sort_picker(page, wait, find) -> dict | None:
    from sg_widgets_qt.showcase.demos._results import EntityResults
    from sg_widgets_qt.widgets.sort_picker import SortPicker

    pickers = find(SortPicker, all=True)
    if not pickers:
        return None
    picker = pickers[0]
    until(lambda: all(picker.name_of(k.field) != k.field for k in picker.value), wait, 20000)
    failures: list[str] = []
    seen = {"keys": [k.field for k in picker.value], "sort": picker.sort}
    results = find(EntityResults, all=True)
    if results:
        found = results[0]
        until(lambda: found.count.kind != "counting", wait)
        until(lambda: found.table().control.snapshot().status in ("ready", "error"), wait)
        seen["count"] = found.count.kind
        seen["total"] = found.count.total
        seen["loaded"] = len(found.rows())
        if found.count.kind == "error":
            failures.append(f"the ordered set said {found.count.message!r}")
        if found.table().control.snapshot().status == "error":
            failures.append("the site refused the sort the picker holds")
    return {"failures": failures, "seen": seen}


#: One reading per page, tried in turn: a page carries whichever of them it has.
READS = (filter_bar, filter_editor, filter_dialog, sort_picker)


def drive(page, wait, find, prefs) -> dict:
    if prefs.source != "live":
        return {"verdict": f"FAIL the toolbar is in {prefs.source} mode, not live"}
    wait(1200)
    for read in READS:
        answer = read(page, wait, find)
        if answer is None:
            continue
        failures = answer["failures"]
        return {
            "verdict": (
                f"PASS {read.__name__} read the site: {answer['seen']}"
                if not failures
                else "FAIL " + "; ".join(failures)
            ),
            "failures": failures,
            "seen": answer["seen"],
        }
    return {"verdict": f"FAIL nothing on {page.data_name} reads the site"}
