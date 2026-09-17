"""The Qt half of the entity picker's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/entity-picker-<state>.js`; the two leave their page
in the same state and the shots are read as a pair.

    QA_STATE=query .venv/bin/python tools/qa.py --page entity-picker \\
        --drive tools/drives/states/entity-picker.py --shot shots/states/entity-picker-query.png

    rest      the page as it settles, nothing open
    open      the list open on the first control, standing rows
    query     the list open over `sh010`, so the matched runs are bold
    loading   the list open with the first read still out, so the skeletons stand
    empty     the list open over a query nothing answers, so the empty line stands
    error     the list open after the demo armed the mock's next call to fail
    more      the paged demo open, so the load-more row is the last row
    focus     the caret holding a keyboard focus ring
    hover     the control under the pointer, so the wash is on
"""
from __future__ import annotations

import os
import time

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.widgets.picker_control import PickerControl

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = (
    "rest",
    "open",
    "query",
    "loading",
    "empty",
    "error",
    "more",
    "focus",
    "hover",
)


def state_name() -> str:
    wanted = os.environ.get("QA_STATE", "rest").strip().lower()
    return wanted if wanted in STATES else "rest"


def demo_of(control: PickerControl) -> str:
    walk = control.parentWidget()
    for _ in range(6):
        if walk is None:
            return "page"
        name = walk.property("data_demo_case")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def controls(find) -> list:
    return [
        control
        for control in find(PickerControl, all=True)
        if not control.disabled and not control.readonly and control.isVisible()
    ]


def wait_for(read, wait, ms: int = 10000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def demo_widget(page):
    for stage in page.stages:
        found = stage.widget
        if found is not None and hasattr(found, "_arm_failure"):
            return found
    return None


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(600)
    state = state_name()
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to drive into {state}"}
    control = found[0]

    if state == "rest":
        return {"verdict": "PASS rest", "state": state, "controls": len(found)}

    if state == "hover":
        control.set_hovered(True)
        wait(400)
        return {"verdict": "PASS hover", "state": state}

    if state == "focus":
        # A keyboard focus paints the ring; a mouse focus does not, which is rule 5.
        control.caret().setFocus(Qt.FocusReason.TabFocusReason)
        wait(300)
        return {"verdict": "PASS focus", "state": state, "ring": control._ring_shown()}

    if state == "error":
        demo = demo_widget(page)
        arm = getattr(demo, "_arm_failure", None)
        failing = getattr(demo, "_failing", None)
        broken = next(
            (
                one
                for one in found
                if demo is not None and demo_of(one) == "error"
            ),
            None,
        )
        if arm is None or broken is None or failing is None:
            return {"verdict": "FAIL no demo whose next call can be armed to fail"}
        arm()
        broken.set_open(True)
        wait_for(lambda: bool(broken.error), wait, 8000)
        wait(400)
        return {"verdict": "PASS error", "state": state, "said": str(broken.error or "")[:60]}

    if state == "more":
        paged = next((one for one in found if demo_of(one) == "more"), control)
        paged.set_open(True)
        wait_for(lambda: paged.list_surface().row_count() > 0, wait)
        wait(500)
        return {
            "verdict": "PASS more",
            "state": state,
            "rows": paged.list_surface().row_count(),
            "load_more": paged.list_surface().load_more_visible(),
        }

    control.set_open(True)
    if state == "loading":
        # The skeletons stand only while the first read is out, so nothing waits for rows.
        wait(60)
        return {
            "verdict": "PASS loading",
            "state": state,
            "skeletons": control.skeletons().isVisibleTo(control.popup()),
        }

    wait_for(lambda: control.list_surface().row_count() > 0, wait)
    if state == "open":
        wait(500)
        return {"verdict": "PASS open", "state": state, "rows": control.list_surface().row_count()}

    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, "sh010" if state == "query" else "zzzqqq")
    if state == "query":
        wait_for(lambda: control.list_surface().row_count() > 0, wait)
    else:
        wait_for(lambda: control.empty, wait)
    wait(600)
    return {
        "verdict": f"PASS {state}",
        "state": state,
        "rows": control.list_surface().row_count(),
        "empty_line": control.state_line().isVisibleTo(control.popup()),
    }
