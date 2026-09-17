"""The Qt half of the user picker's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/user-picker-<state>.js`; the two leave their page in
the same state and the shots are read as a pair.

    QA_STATE=query .venv/bin/python tools/qa.py --page user-picker \\
        --drive tools/drives/states/user-picker.py --shot shots/states/user-picker-query.png

    rest      the page as it settles, nothing open
    filled    the page scrolled to the states section, where every control holds a person
    open      the list open on the first control: an avatar, a name and the address under it
    query     the list open over `ada`, so the matched runs are bold in both lines
    loading   the list open with the first read still out, so the skeletons stand
    empty     the list open over a query nothing answers, so the empty line stands
    error     the list open with a read that failed, so the error line stands
    more      the list open with a page behind it, so the load-more row is the last row
    focus     the caret holding a keyboard focus ring
    hover     the control under the pointer, so the `muted` wash at 30% is on

`error` has no upstream twin: the user picker demo arms no failure, upstream or here, and the
block itself is the picker base's, shot on the entity picker pair. It is driven here so the
preset is known not to break it.
"""
from __future__ import annotations

import os
import time

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QWidget

from sg_widgets_qt.widgets.picker_control import PickerControl

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = (
    "rest",
    "filled",
    "open",
    "query",
    "loading",
    "empty",
    "error",
    "more",
    "focus",
    "hover",
)

#: What the query state types, which the fixtures answer with one person.
QUERY = "ada"
#: What the empty state types, which nothing answers.
NOTHING = "zzzqqq"


def state_name() -> str:
    wanted = os.environ.get("QA_STATE", "rest").strip().lower()
    return wanted if wanted in STATES else "rest"


def live_controls(find) -> list:
    """Every control the reader can drive: not the ones a demo draws inert."""
    return [
        control
        for control in find(PickerControl, all=True)
        if not control.disabled and not control.readonly and control.isVisible()
    ]


def case_widget(page, wanted: str) -> QWidget | None:
    for widget in page.findChildren(QWidget):
        if widget.property("data_demo_case") == wanted:
            return widget
    return None


def scroll_to(page, wanted: str, wait) -> bool:
    """Put a demo case at the top of the pane, which is what the upstream half does."""
    target = case_widget(page, wanted)
    if target is None:
        return False
    inner = page.scroll.widget()
    top = target.mapTo(inner, target.rect().topLeft()).y()
    page.scroll.verticalScrollBar().setValue(max(0, top - 20))
    wait(500)
    return True


def wait_for(read, wait, ms: int = 10000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def pictures(control: PickerControl) -> int:
    """How many rows on show have their picture, which the shot waits for."""
    model = control.list_surface().source_model()
    held = getattr(model, "_pictures", None)
    return len(held) if held is not None else 1


def settled_rows(control: PickerControl, wait) -> None:
    wait_for(lambda: control.list_surface().row_count() > 0, wait)
    wait_for(lambda: pictures(control) > 0, wait, 6000)
    wait(1000)


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(700)
    state = state_name()
    found = live_controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to drive into {state}"}
    control = found[0]

    if state == "rest":
        return {"verdict": "PASS rest", "state": state, "controls": len(found)}

    if state == "filled":
        if not scroll_to(page, "states", wait):
            return {"verdict": "FAIL no states section on the page"}
        return {"verdict": "PASS filled", "state": state}

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
        control.set_open(True)
        wait(200)
        control.set_error("The read failed")
        wait(400)
        drawn = control.state_line().isVisibleTo(control.popup())
        return {
            "verdict": "PASS error" if drawn else "FAIL the error line is not drawn",
            "state": state,
            "said": control.state_line().text() if hasattr(control.state_line(), "text") else "",
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

    if state == "more":
        settled_rows(control, wait)
        return {
            "verdict": "PASS more",
            "state": state,
            "rows": control.list_surface().row_count(),
            "load_more": control.list_surface().load_more_visible(),
        }

    if state == "open":
        settled_rows(control, wait)
        return {"verdict": "PASS open", "state": state, "rows": control.list_surface().row_count()}

    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, QUERY if state == "query" else NOTHING)
    if state == "query":
        settled_rows(control, wait)
    else:
        wait_for(lambda: control.empty, wait)
        wait(600)
    return {
        "verdict": f"PASS {state}",
        "state": state,
        "rows": control.list_surface().row_count(),
        "empty_line": control.state_line().isVisibleTo(control.popup()),
    }
