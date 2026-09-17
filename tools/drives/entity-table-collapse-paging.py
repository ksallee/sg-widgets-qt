"""The port of `~/dev/sg-widgets/tools/drives/entity-table-collapse-paging.js`.

Collapse all holds across a page of the grouped table: the headings the next page brings arrive
shut, and the state the table emits is still `{all: True, except_: []}`. Then one heading opened
by hand is the exception, and Expand all opens the rest.

    .venv/bin/python tools/qa.py --page entity-table \
        --drive tools/drives/entity-table-collapse-paging.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget, wait_for  # noqa: E402

from sg_widgets_core.collection_state import collapse_all, expand_all  # noqa: E402


def settled(table) -> bool:
    return table.control.snapshot().status in ("ready", "error")


def open_headings(table) -> list:
    shut = set(_shut_keys(table))
    return [group.key for group in table.model.groups if group.key not in shut]


def _shut_keys(table) -> list:
    from sg_widgets_core.collection_state import is_collapsed

    return [group.key for group in table.model.groups if is_collapsed(table.collapsed, group.key)]


def state_of(table) -> tuple:
    return (table.collapsed.all, list(table.collapsed.except_))


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-table")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-table demo"}
    table = holder.table
    if not wait_for(lambda: settled(table) and table.control.rows, wait):
        return {"verdict": "FAIL the table drew no first page", "notes": notes}
    images_settled(wait)

    holder._grouped.set_checked(True)
    if not wait_for(
        lambda: settled(table)
        and len(table.model.groups) > 1
        and table.control.sort
        and table.control.sort[0].path == "sg_status_list",
        wait,
    ):
        return {"verdict": "FAIL the table drew fewer than two headings", "notes": notes}
    wait(400)
    before = len(table.model.groups)
    notes.append(f"{before} headings on page 1, {len(open_headings(table))} open")

    table.set_collapsed(collapse_all())
    wait(300)
    if open_headings(table) or table.model.rowCount() != before:
        return {
            "verdict": f"FAIL Collapse all left {len(open_headings(table))} headings open",
            "notes": notes,
        }
    if state_of(table) != (True, []):
        return {"verdict": f"FAIL it emits {state_of(table)} after Collapse all", "notes": notes}
    notes.append(f"Collapse all shut all {before} and the state is {state_of(table)}")

    # The next page is a data change; its headings were never named and arrive shut.
    table.footer._next.clicked.emit()
    if not wait_for(lambda: settled(table) and table.control.pager.page == 2, wait):
        return {"verdict": f'FAIL it did not turn the page: "{table.control.pager.range_label}"', "notes": notes}
    wait(500)
    arrived = len(table.model.groups)
    if arrived == 0:
        return {"verdict": "FAIL no heading on page 2", "notes": notes}
    if open_headings(table):
        return {
            "verdict": f"FAIL {len(open_headings(table))} headings arrived open on page 2",
            "notes": notes,
        }
    if state_of(table) != (True, []):
        return {"verdict": f"FAIL it emits {state_of(table)} after the page", "notes": notes}
    notes.append(
        f'page 2 reads "{table.control.pager.range_label}" with {arrived} headings, '
        f"0 open, state {state_of(table)}"
    )

    # One heading opened by hand is the exception the mode carries.
    table._toggle_group(table.model.groups[0].key)
    wait(300)
    if len(open_headings(table)) != 1:
        return {
            "verdict": f"FAIL {len(open_headings(table))} headings are open against Collapse all",
            "notes": notes,
        }
    if state_of(table)[0] is not True or len(state_of(table)[1]) != 1:
        return {"verdict": f"FAIL it emits {state_of(table)} with one opened by hand", "notes": notes}
    notes.append(f"one heading opened by hand emits {state_of(table)}")

    table.set_collapsed(expand_all())
    wait(300)
    if len(open_headings(table)) != len(table.model.groups):
        return {
            "verdict": f"FAIL Expand all left {len(open_headings(table))} of {len(table.model.groups)} open",
            "notes": notes,
        }
    if state_of(table) != (False, []):
        return {"verdict": f"FAIL it emits {state_of(table)} after Expand all", "notes": notes}

    table.set_collapsed(collapse_all())
    wait(300)
    return {
        "verdict": (
            "PASS Collapse all holds across a page of the grouped table: its headings arrive "
            "shut and the emitted state stays all-shut"
        ),
        "notes": notes,
    }
