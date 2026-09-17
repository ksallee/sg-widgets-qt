"""The grouped list's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/grouped-list-<state>.js`, run against
`/widgets/grouped-list/`.

    QA_STATE=collapsed .venv/bin/python tools/qa.py --page grouped-list \\
        --drive tools/drives/states/grouped-list.py --shot shots/states/grouped-list-collapsed.png

    rest       every heading open, each stating the rows loaded under it
    collapsed  the first heading shut, its rows off the list
    all-shut   Collapse all, so only the headings stand
    cursor     the cursor walked from the last row of one group into the next
    selected   two rows taken, the count reading 2
    compact    the row padding halved
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _collection_states import (  # noqa: E402
    frame,
    images_settled,
    stage_widget,
    state_name,
    wait_for,
)
from qtpy import QtCore, QtGui  # noqa: E402

from sg_widgets_core.collection_state import collapse_all  # noqa: E402

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = ("rest", "collapsed", "all-shut", "cursor", "selected", "compact")


def settled(listing) -> bool:
    return listing.control.snapshot().status in ("ready", "error")


def described(listing) -> dict:
    groups = listing.model.groups
    return {
        "name": listing.objectName() or "grouped-list",
        "groups": [(group.key, len(group.rows)) for group in groups],
        "lines": listing.model.rowCount(),
        "rows": len(listing.control.rows),
        "selection": len(listing.selection),
        "cursor": listing.control.active,
        "density": listing.density,
        "view": listing.control.view(len(listing.control.rows)),
    }


def key(listing, code) -> None:
    listing.on_key(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), QtCore.Qt.KeyboardModifier.NoModifier)
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    state = state_name(STATES, "rest")
    wait(200)
    holder = stage_widget(page, "grouped-list")
    if holder is None:
        return {"verdict": "FAIL the page built no grouped-list demo"}
    listing = holder.listing
    derived = holder.derived
    if not wait_for(lambda: settled(listing) and listing.model.groups, wait):
        return {"verdict": "FAIL the list drew no group"}
    wait_for(lambda: settled(derived) and derived.model.groups, wait)
    images_settled(wait)
    frame(page, wait, "grouped-list")

    if state == "collapsed":
        whole = listing.model.rowCount()
        first = listing.model.groups[0]
        listing.toggle_group(first.key)
        wait(250)
        if listing.model.rowCount() != whole - len(first.rows):
            return {"verdict": f"FAIL collapsing left {listing.model.rowCount()} lines"}

    elif state == "all-shut":
        listing.set_collapsed(collapse_all())
        derived.set_collapsed(collapse_all())
        wait(250)
        if listing.model.rowCount() != len(listing.model.groups):
            return {"verdict": "FAIL Collapse all left rows on the list"}

    elif state == "cursor":
        listing.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
        wait(150)
        first = listing.model.groups[0]
        # The cursor is a view cursor: the list reads it off `currentIndex`, so it is put
        # on the last row of the first group the way a press would.
        listing._focus(len(first.rows) - 1)
        wait(150)
        before = listing.control.active
        key(listing, QtCore.Qt.Key.Key_Down)
        wait(250)
        if listing.control.active != before + 1:
            return {
                "verdict": (
                    f"FAIL the cursor went {before} -> {listing.control.active}, "
                    "so it did not step over the heading"
                )
            }

    elif state == "selected":
        for row in listing.control.rows[:2]:
            listing.control.toggle(row)
        wait(250)
        if not holder._count.text().startswith("2 "):
            return {"verdict": f"FAIL the count reads {holder._count.text()!r}"}

    elif state == "compact":
        holder._compact.set_checked(True)
        wait(300)
        if listing.density != "compact":
            return {"verdict": f"FAIL the density reads {listing.density!r}"}

    wait(300)
    return {
        "verdict": f"PASS {state}",
        "state": state,
        "lists": [described(listing), described(derived), described(holder.empty)],
    }
