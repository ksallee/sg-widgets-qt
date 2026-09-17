"""What a facet counts, what a pill names, and what the checklist emits.

The port of `~/dev/sg-widgets/tools/drives/filter-bar-facets.js`.

    .venv/bin/python tools/qa.py --page filter-bar --drive tools/drives/filter-bar-facets.py
    .venv/bin/python tools/qa.py --page filter-bar --drive tools/drives/filter-bar-facets.py --qt5

Clause by clause:

  * a facet counted through the site's groups reads the mock's own `summarize` of the same
    filter, value by value (020_summarize), and its counts sum to the type's total; a facet the
    mock refuses to group is tallied from one page of rows and its list says so;
  * two statuses ticked narrow the Kind facet to the rows under them and leave the status
    facet's own counts where they were, which is what "counted under the other facets alone"
    means;
  * a status facet marks each checklist row with its glyph and draws no badge there, while the
    pill badges what it holds;
  * a facet takes the caller's name over the schema's;
  * a capped pill names `max_values` of them, reads `+n` for the rest, and holds the cap;
  * the read-state field evaluates no `in`, so one ticked value emits `is` and two an `or` of
    `is`, under a comma-joined pill.
"""
from __future__ import annotations

import time

from qtpy import QtWidgets

from sg_widgets_core.client import SummarizeOptions, SummaryField
from sg_widgets_core.filter import condition, group, to_api3_hash
from sg_widgets_core.filter_ux import facet_scopes, find_facet
from sg_widgets_core.picker import as_filter_group
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.filter_bar import VALUE_WIDTH, FilterBar
from sg_widgets_qt.widgets.status_badge import StatusBadge

READ = "read_by_current_user"

#: How many of a facet's values are checked against `summarize`, so the run stays a minute.
SAMPLE_VALUES = 6


def wait_for(read, wait, ms: int = 15000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def settled(bar: FilterBar, wait, ms: int = 25000) -> bool:
    return wait_for(lambda: not bar.counting, wait, ms)


def listed(bar: FilterBar, name: str) -> list:
    found = bar.facet_list(name)
    return list(found.values) if found is not None else []


def total_of(bar: FilterBar, wire) -> int:
    """What the mock's `summarize` answers for one filter (020_summarize)."""
    summary = bar.context.client.summarize(
        bar.entity_type,
        SummarizeOptions(filters=wire, summary_fields=[SummaryField(field="id", type="count")]),
    )
    found = summary.summaries.get("id")
    return int(found) if isinstance(found, (int, float)) and not isinstance(found, bool) else 0


def scope_of(bar: FilterBar, name: str):
    """The filter one facet is counted against: the tree less its own condition."""
    base = as_filter_group(bar.base_filter)
    return facet_scopes(bar.value, base, list(bar.facets)).get(name)


def under(bar: FilterBar, name: str, value) -> int:
    """The rows one value of one facet would leave, under that facet's own scope."""
    one = to_api3_hash(group("and", [condition(name, "is", value)]))
    scope = scope_of(bar, name)
    wire = one if scope is None else {"logical_operator": "and", "conditions": [scope, one]}
    return total_of(bar, wire)


def named(root: QtWidgets.QWidget, name: str) -> list[QtWidgets.QWidget]:
    return [one for one in root.findChildren(QtWidgets.QWidget) if one.objectName() == name]


def pill_label(pill: QtWidgets.QWidget) -> str:
    """What a pill's value slot names, run by run, the overflow left out."""
    holders = named(pill, "filter-pill-values")
    if not holders:
        return ""
    runs = [
        child.text()
        for child in holders[0].findChildren(QtWidgets.QWidget)
        if hasattr(child, "text") and child.objectName() != "filter-pill-overflow"
    ]
    return " ".join(one for one in runs if one)


def overflow_of(pill: QtWidgets.QWidget) -> str:
    found = named(pill, "filter-pill-overflow")
    return found[0].text() if found else ""


def node_on(node, path):
    """The condition or group the wire holds on one path, wherever it sits."""
    if node is None:
        return None
    if isinstance(node, list):
        return node if node and node[0] == path else None
    children = node.get("conditions", [])
    if len(children) > 1 and all(isinstance(c, list) and c[0] == path for c in children):
        return node
    for child in children:
        found = node_on(child, path)
        if found is not None:
            return found
    return None


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0912, PLR0915
    wait(600)
    bars = {one.objectName(): one for one in find(FilterBar, all=True)}
    main = bars.get("filter-bar-main")
    notes = bars.get("filter-bar-notes")
    seeded = bars.get("filter-bar-seeded")
    if main is None or notes is None or seeded is None:
        return {"verdict": f"FAIL the page drew {sorted(bars)} rather than the demo's bars"}

    failures: list[str] = []
    said: list[str] = []
    settled(main, wait)
    wait(300)

    # 1. A facet counted through the site's groups reads the mock's own summarize.
    settled(notes, wait)
    wait(300)
    from_list = notes.facet_list("user")
    if from_list is None or not from_list.values:
        failures.append("the From facet listed nobody")
    else:
        if from_list.sampled is not None:
            failures.append(f"the From facet was tallied from a sample of {from_list.sampled}")
        checked = 0
        for option in from_list.values[:SAMPLE_VALUES]:
            want = under(notes, "user", option.value)
            checked += 1
            if int(option.count) != want:
                failures.append(
                    f"From/{option.key} counts {option.count}, summarize answers {want}"
                )
        total = total_of(notes, to_api3_hash(notes.value))
        summed = sum(int(one.count) for one in from_list.values)
        if summed != total:
            failures.append(f"From sums to {summed} over {total} Notes")
        unnamed = [one.key for one in from_list.values if not one.label or one.label == one.key]
        if unnamed:
            failures.append(f"the From facet listed {unnamed} without a name")
        said.append(
            "From lists " + ", ".join(f"{one.label} {one.count}" for one in from_list.values)
            + f", {checked} of them against summarize"
        )

    # The read-state facet: the mock refuses to group it, so it is tallied and says so.
    read_list = notes.facet_list(READ)
    if read_list is None:
        failures.append("the read-state facet listed nothing")
    elif read_list.sampled is None:
        failures.append("the read-state facet did not say it was tallied from a sample")
    else:
        said.append(f"the read-state facet reads a sample of {read_list.sampled} rows")

    # 2. A status facet's rows carry the glyph, and the quiet pill draws no badge.
    pill = main.pill("sg_status_list")
    pill.refresh_list(main.facet_list("sg_status_list"), main.counting, main.failure)
    wait(100)
    model = pill._model  # noqa: SLF001
    glyphs = [model.data(model.index(i, 0), Roles.GLYPH) for i in range(model.rowCount())]
    if not glyphs or any(one is None for one in glyphs):
        failures.append(f"{glyphs.count(None)} of {len(glyphs)} status rows carry no glyph mark")
    if pill.findChildren(StatusBadge):
        failures.append("the quiet status pill draws a badge before anything is ticked")
    said.append(f"{len(glyphs)} status rows carry a glyph mark")

    # 3. A facet takes the caller's name over the schema's.
    if main.label_of("sg_shot_type") != "Kind":
        failures.append(f"the named facet reads {main.label_of('sg_shot_type')!r}, wanted 'Kind'")

    # 4. Two statuses ticked narrow the Kind facet and leave the status facet's counts alone.
    status = listed(main, "sg_status_list")
    if len(status) < 2:
        failures.append("fewer than two statuses to tick")
    else:
        before = {one.key: one.count for one in status}
        for one in status[:2]:
            main.toggle("sg_status_list", one.key, one.value)
            settled(main, wait)
        wait(200)
        after = {one.key: one.count for one in listed(main, "sg_status_list")}
        if after != before:
            failures.append(f"the status facet's own counts moved: {after} from {before}")
        kinds = listed(main, "sg_shot_type")
        summed = sum(int(one.count) for one in kinds)
        want = total_of(main, scope_of(main, "sg_shot_type"))
        said.append(
            f"{status[0].key} and {status[1].key} ticked:"
            f" the Kind facet sums to {summed} over {want}"
        )
        if summed != want:
            failures.append(f"the Kind facet sums to {summed}, the status filter matches {want}")
        if want >= total_of(main, None):
            failures.append("the status filter did not narrow the Kind facet")
        main.clear_all_button().click()
        settled(main, wait)
        wait(200)
        if any(find_facet(main.value, name, main.field_of(name)) for name in main.facets):
            failures.append("Clear all left a ticked facet behind")

    # 5. A capped pill names two values, reads `+n`, and holds the cap.
    settled(seeded, wait)
    wait(200)
    capped = seeded.pill("sg_status_list")
    marks = capped.findChildren(StatusBadge)
    held = len(seeded.selected_of("sg_status_list"))
    over = overflow_of(capped)
    if len(marks) != seeded.max_values:
        failures.append(f"the capped pill names {len(marks)}, wanted {seeded.max_values}")
    if over != f"+{held - seeded.max_values}":
        failures.append(f"the capped pill reads {over!r}, wanted +{held - seeded.max_values}")
    holders = named(capped, "filter-pill-values")
    if holders and holders[0].width() > VALUE_WIDTH:
        failures.append(f"the pill's value reached {holders[0].width()}px, over {VALUE_WIDTH}")
    if capped.width() > seeded.width() + 1:
        failures.append("a pill runs the bar past the width it was given")
    if not capped.toolTip() and not holders[0].toolTip():
        failures.append("the capped pill carries no title with the whole list")
    said.append(f"the seeded pill names {len(marks)} of {held} and reads {over!r}")

    # 6. The read-state field takes no `in`: one value emits `is`, two an `or` of `is`.
    notes.toggle(READ, "read", "read")
    settled(notes, wait)
    wait(200)
    one_value = node_on(to_api3_hash(notes.value), READ)
    if one_value != [READ, "is", "read"]:
        failures.append(f"one ticked value emits {one_value}")
    said.append(f"one value emits {one_value}")
    notes.toggle(READ, "unread", "unread")
    settled(notes, wait)
    wait(200)
    two_values = node_on(to_api3_hash(notes.value), READ)
    wanted = {
        "logical_operator": "or",
        "conditions": [[READ, "is", "read"], [READ, "is", "unread"]],
    }
    if two_values != wanted:
        failures.append(f"two ticked values emit {two_values}")
    said.append(f"two values emit {two_values}")
    text = pill_label(notes.pill(READ))
    if text != "read, unread":
        failures.append(f"the read-state pill reads {text!r}, wanted 'read, unread'")
    said.append(f"the read-state pill reads {text!r}")

    return {
        "verdict": (
            "PASS the site-counted facet reads the mock's own summarize and sums to the total,"
            " each facet is counted under the other facets alone, status rows carry the glyph,"
            " the pill badges and caps what it holds, the tallied facet says it is a sample, and"
            " the read-state facet emits `is` and an `or` of `is` under a comma-joined pill"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "notes": said,
    }
