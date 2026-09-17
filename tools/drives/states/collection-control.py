"""The collection control's state matrix, one state per `QA_STATE`.

The page is the base every collection is built on, drawn as a review queue of the caller's own,
so what is read here is the shared parts: the source, the selection, the footer and the block
under the rows. The upstream half is `tools/drives/upstream/collection-control-<state>.js`.

    QA_STATE=more .venv/bin/python tools/qa.py --page collection-control \\
        --drive tools/drives/states/collection-control.py \\
        --shot shots/states/collection-control-more.png

    pages       the first page, the footer reading "1 to N of M" off `summarize`
    more        the set walked with a load-more row under the rows
    scroll      the set walked by the scroller
    selected    every loaded row taken, the head's box full
    page-two    the next page, the range moved with it
    empty       a filter no row answers
    error       a read that failed, with its retry under the rows
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

from sg_widgets_core.filter import condition  # noqa: E402

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = (
    "pages",
    "more",
    "scroll",
    "selected",
    "page-two",
    "empty",
    "error",
)


def settled(control) -> bool:
    return control.snapshot().status in ("ready", "error")


def described(holder) -> dict:
    control = holder.control
    pager = control.pager
    return {
        "rows": len(control.rows),
        "range": pager.range_label,
        "loaded": pager.loaded_label,
        "page": pager.page,
        "page_count": pager.page_count,
        "has_next": pager.has_next,
        "bottom": control.bottom(),
        "view": control.view(len(control.rows)),
        "selection": len(control.selection),
        "paging": control.paging,
        "footer": holder.footer.objectName(),
    }


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    state = state_name(STATES, "pages")
    wait(200)
    holder = stage_widget(page, "collection-control")
    if holder is None:
        return {"verdict": "FAIL the page built no collection-control demo"}
    control = holder.control
    if not wait_for(lambda: settled(control) and control.rows, wait):
        return {"verdict": "FAIL the first page never landed"}
    # The count is a call of its own, so the range only reads "of N" once it answers.
    wait_for(lambda: control.pager.page_count is not None, wait)
    images_settled(wait)
    frame(page, wait, "collection-control")

    if state in ("more", "scroll"):
        holder._toggles[state].set_checked(True)
        wait(400)
        wait_for(lambda: settled(control), wait)
        wanted = "more" if state == "more" else "sentinel"
        if control.bottom() != wanted:
            return {"verdict": f"FAIL {state} draws {control.bottom()!r} under the rows"}

    elif state == "selected":
        control.toggle_all(True)
        wait(250)
        if len(control.selection) != len(control.rows):
            return {"verdict": f"FAIL {len(control.selection)} of {len(control.rows)} taken"}
        if not control.all_selected.all:
            return {"verdict": "FAIL the head's box did not fill"}

    elif state == "page-two":
        first = control.pager.range_label
        control.binding.set_page(2)
        if not wait_for(
            lambda: settled(control) and control.pager.range_label != first, wait
        ):
            return {"verdict": f"FAIL the range stayed at {first!r}"}

    elif state == "empty":
        control.apply_filters(condition("code", "is", "no such version"))
        wait_for(lambda: control.view(len(control.rows)) == "empty", wait)
        if control.view(len(control.rows)) != "empty":
            return {"verdict": "FAIL the empty filter still drew rows"}

    elif state == "error":
        _break_reads(holder)
        control.apply_filters(condition("code", "contains", "sh01"))
        wait_for(lambda: control.snapshot().status == "error", wait)
        if control.snapshot().status != "error":
            return {"verdict": "FAIL the read did not fail"}
        if control.bottom() != "error":
            return {"verdict": f"FAIL the block under the rows reads {control.bottom()!r}"}

    wait(300)
    return {"verdict": f"PASS {state}", "state": state, "queue": described(holder)}


def _break_reads(holder) -> None:
    client = holder._context.client

    def fail(*_args, **_kwargs):
        raise RuntimeError("503 Service Unavailable: qa broke this read")

    client.search = fail  # type: ignore[assignment]
