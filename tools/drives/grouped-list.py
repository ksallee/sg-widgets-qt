"""The port of `~/dev/sg-widgets/tools/drives/grouped-list.js`.

Collapse a group, count its rows, select two, and read the list grouped on a derived key: every
row under a heading belongs to the record the heading names, and the sort stays the caller's.

    .venv/bin/python tools/qa.py --page grouped-list --drive tools/drives/grouped-list.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import stage_widget, wait_for  # noqa: E402

from sg_widgets_core.collection import cell_value  # noqa: E402


def settled(listing) -> bool:
    return listing.control.snapshot().status in ("ready", "error")


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "grouped-list")
    if holder is None:
        return {"verdict": "FAIL the page built no grouped-list demo"}
    listing = holder.listing
    if not wait_for(lambda: settled(listing) and listing.model.groups, wait):
        return {"verdict": "FAIL the list rendered no groups", "notes": notes}
    groups = listing.model.groups
    notes.append(f"groups: {len(groups)}, rows: {len(listing.control.rows)}")
    if len(groups) < 2:
        return {"verdict": "FAIL fewer than two groups", "notes": notes}

    # The heading count is the rows loaded under it.
    heading = listing.model.index(0, 0)
    from sg_widgets_qt.primitives.roles import Roles

    stated = int(heading.data(Roles.SECONDARY))
    shown = len(groups[0].rows)
    notes.append(f"the first group states {stated} and holds {shown}")
    if stated != shown:
        return {"verdict": f"FAIL the heading count is {stated} against {shown} rows", "notes": notes}

    before = listing.model.rowCount()
    listing.toggle_group(groups[0].key)
    wait(300)
    if listing.model.rowCount() != before - shown:
        return {
            "verdict": f"FAIL collapsing left {listing.model.rowCount()} lines, expected {before - shown}",
            "notes": notes,
        }
    notes.append(f"collapsing the first group hid {shown} rows")
    listing.toggle_group(groups[0].key)
    wait(300)

    for row in listing.control.rows[:2]:
        listing.control.toggle(row)
    wait(300)
    count = holder._count.text()
    notes.append(f"selection: {count}")
    if not count.startswith("2 "):
        return {"verdict": f'FAIL selection reads "{count}", expected 2', "notes": notes}

    # The derived key: the heading names the record, and its count is the rows under it.
    derived = holder.derived
    if not wait_for(lambda: settled(derived) and len(derived.model.groups) > 1, wait):
        return {"verdict": "FAIL the derived list drew fewer than two groups", "notes": notes}
    keyed = derived.model.groups
    heads = [(derived.group_label(group.value), len(group.rows)) for group in keyed]
    notes.append("derived groups: " + ", ".join(f"{label}/{count}" for label, count in heads[:6]))
    if any(not label for label, _ in heads):
        return {"verdict": "FAIL a derived heading drew no label", "notes": notes}
    if len({label for label, _ in heads}) != len(heads):
        return {"verdict": "FAIL a record is split over two derived groups", "notes": notes}

    # A Version's code opens on the code of the record it is of, so every row under a
    # heading carries that heading's label.
    for label, _count in heads:
        group = next(one for one in keyed if derived.group_label(one.value) == label)
        strays = [
            str(cell_value(row, "code") or "")
            for row in group.rows
            if not str(cell_value(row, "code") or "").startswith(label + "_")
        ]
        if strays:
            return {
                "verdict": f'FAIL derived group "{label}" holds rows of another record: {strays[:3]}',
                "notes": notes,
            }
    notes.append("every row under a derived heading is a version of its record")

    # A derived key leaves the source's sort as the caller set it: on code, not on the record.
    line = holder._sorted.text()
    notes.append(f"derived list: {line}")
    if line != "Sorted on code":
        return {"verdict": f'FAIL the derived list reads "{line}", expected "Sorted on code"', "notes": notes}

    return {
        "verdict": "PASS grouping, counts, collapse, selection, the derived key, its rows and its sort",
        "notes": notes,
    }
