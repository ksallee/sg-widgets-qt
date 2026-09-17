"""The port of `~/dev/sg-widgets/tools/drives/collapse-all-paging.js`.

Collapse all holds across a page of the grouped list: the groups the next page brings arrive
shut, and the one opened by hand is still open.

    .venv/bin/python tools/qa.py --page grouped-list --drive tools/drives/collapse-all-paging.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import stage_widget, wait_for  # noqa: E402

from sg_widgets_core.collection_state import collapse_all, expand_all, is_collapsed  # noqa: E402


def settled(listing) -> bool:
    return listing.control.snapshot().status in ("ready", "error")


def keys_of(listing) -> list:
    return [group.key for group in listing.model.groups]


def open_keys(listing) -> list:
    return [
        group.key
        for group in listing.model.groups
        if not is_collapsed(listing.collapsed, group.key)
    ]


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "grouped-list")
    if holder is None:
        return {"verdict": "FAIL the page built no grouped-list demo"}
    # The derived-key list is the one that pages with a load-more row.
    listing = holder.derived
    if not wait_for(lambda: settled(listing) and len(listing.model.groups) > 1, wait):
        return {"verdict": "FAIL the derived list drew fewer than two groups", "notes": notes}
    before = keys_of(listing)
    notes.append(f"{len(before)} groups before the next page")

    listing.set_collapsed(collapse_all())
    wait(300)
    if open_keys(listing):
        return {
            "verdict": f"FAIL Collapse all left {len(open_keys(listing))} groups open",
            "notes": notes,
        }
    notes.append(f"Collapse all shut all {len(before)}")

    kept = before[0]
    listing.toggle_group(kept)
    wait(300)
    if open_keys(listing) != [kept]:
        return {
            "verdict": f"FAIL one group could not be opened against Collapse all: {open_keys(listing)}",
            "notes": notes,
        }

    # The next page. Its groups were never named, and must arrive shut.
    if listing.control.bottom() != "more":
        return {"verdict": f"FAIL the list draws {listing.control.bottom()!r}, not a load-more row", "notes": notes}
    listing.control.load_more()
    if not wait_for(lambda: settled(listing) and len(keys_of(listing)) > len(before), wait):
        return {"verdict": "FAIL the load-more row loaded no further group", "notes": notes}
    wait(400)
    grown = keys_of(listing)
    arrived = [key for key in grown if key not in before]
    still_open = open_keys(listing)
    notes.append(
        f"the next page brought {len(arrived)} groups, {len(grown)} in all, open: "
        f"{', '.join(still_open) or 'none'}"
    )
    opened_by_page = [key for key in arrived if key in still_open]
    if opened_by_page:
        return {
            "verdict": f"FAIL {len(opened_by_page)} groups arrived open under Collapse all",
            "notes": notes,
        }
    if kept not in still_open:
        return {"verdict": "FAIL the group opened by hand was shut by the page", "notes": notes}
    if len(still_open) != 1:
        return {"verdict": f"FAIL {len(still_open)} groups are open, expected the one", "notes": notes}

    listing.set_collapsed(expand_all())
    wait(300)
    if len(open_keys(listing)) != len(grown):
        return {
            "verdict": f"FAIL Expand all left {len(open_keys(listing))} of {len(grown)} open",
            "notes": notes,
        }
    notes.append(f"Expand all opened all {len(grown)}")

    listing.set_collapsed(collapse_all())
    wait(200)
    listing.toggle_group(grown[0])
    wait(200)
    return {
        "verdict": (
            "PASS Collapse all holds across a page: the groups it brings arrive shut, and the "
            "one opened by hand stays open"
        ),
        "notes": notes,
    }
