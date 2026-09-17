"""The states the two project picker pages are shot in, one function per state.

Each `tools/drives/project-picker-<state>.py` and `tools/drives/project-multi-picker-<state>.py`
is a three-line file calling one of these, the way the search states sit in `_search_states.py`.
The upstream half of each pair is `tools/drives/upstream/<same name>.js`, which leaves the React
page in the same state, so the two shots are read side by side.

A drive file is exec'd by `tools/qa.py`, so it puts this directory on `sys.path` itself:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _project_states import open_rows

The mock carries three projects, so the load-more row is out of reach on both sides: a page is
twenty rows. The matrix says so rather than pretending to shoot it.
"""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.widgets.picker_control import PickerControl

__all__ = [
    "armed",
    "error",
    "focus",
    "hover",
    "loading",
    "no_match",
    "open_rows",
    "overflow",
    "query",
    "rest",
    "ticked",
]

#: The mock's latency plus the debounce, with room for the hop back onto the GUI thread.
SETTLE_MS = 1200


def demo_of(control: PickerControl) -> str:
    """The demo case a control sits in, so a verdict names something a reader can find."""
    walk = control.parentWidget()
    for _ in range(8):
        if walk is None:
            return "page"
        name = walk.property("data_demo") or walk.property("data_demo_case")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def controls(find) -> list:
    """Every live control on the page, in the order the demo lays them out."""
    return [
        control
        for control in find(PickerControl, all=True)
        if not control.disabled and not control.readonly and control.isVisible()
    ]


def until(read, wait, ms: int = 10000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def pictures(control: PickerControl) -> int:
    """How many rows on show hold their picture, which a shot waits for."""
    model = control.list_surface().source_model()
    held = getattr(model, "_pictures", None)
    return len(held) if held is not None else 1


def first(found: list, where: str = "") -> PickerControl | None:
    """The first control, or the first one in the demo case named."""
    if not where:
        return found[0] if found else None
    return next((one for one in found if demo_of(one) == where), None)


def fail_next_of(client: object):
    """The mock's `fail_next`, through whatever caches and counters wrap it."""
    seen = 0
    while client is not None and seen < 8:
        arm = getattr(client, "fail_next", None)
        if callable(arm):
            return arm
        client = getattr(client, "_client", None)
        seen += 1
    return None


# --- the states --------------------------------------------------------------------------


def rest(page, wait, find, prefs) -> dict:
    """The page as it settles: one empty control, then the ones holding a value."""
    wait(2500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker on the page"}
    filled = [one for one in found if one.labels]
    return {
        "verdict": "PASS rest",
        "controls": len(found),
        "empty": len(found) - len(filled),
        "filled": len(filled),
    }


def hover(page, wait, find, prefs) -> dict:
    """The control under the pointer, so the `muted` wash of rule 5 is on."""
    wait(1500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to hover"}
    found[0].set_hovered(True)
    wait(400)
    return {"verdict": "PASS hover", "demo": demo_of(found[0])}


def focus(page, wait, find, prefs) -> dict:
    """The caret holding a keyboard focus, which is the only focus that paints a ring."""
    wait(1500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to focus"}
    control = found[0]
    control.caret().setFocus(Qt.FocusReason.TabFocusReason)
    wait(300)
    if not control._ring_shown():
        return {"verdict": "FAIL a keyboard focus painted no ring"}
    return {"verdict": "PASS focus", "ring": True, "demo": demo_of(control)}


def loading(page, wait, find, prefs) -> dict:
    """The list open while the first read is still out, so the skeletons stand."""
    wait(1500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to open"}
    control = found[0]
    control.set_open(True)
    # The skeletons stand only while the read is out, so nothing waits for rows here.
    wait(60)
    return {
        "verdict": "PASS loading",
        "skeletons": control.skeletons().isVisibleTo(control.popup()),
    }


def open_rows(page, wait, find, prefs) -> dict:
    """The list open on standing rows: the project picture, the name, the status under it."""
    wait(1500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to open"}
    control = found[0]
    control.set_open(True)
    if not until(lambda: control.list_surface().row_count() > 0, wait):
        return {"verdict": "FAIL the list drew no row"}
    until(lambda: pictures(control) > 0, wait, 6000)
    wait(1200)
    return {
        "verdict": "PASS open",
        "rows": control.list_surface().row_count(),
        "pictures": pictures(control),
    }


def query(page, wait, find, prefs) -> dict:
    """The list open over a query, so the matched runs stand in DemiBold."""
    wait(1500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to open"}
    control = found[0]
    control.set_open(True)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, "har")
    if not until(lambda: control.list_surface().row_count() > 0, wait):
        return {"verdict": "FAIL a query that matches drew no row"}
    until(lambda: pictures(control) > 0, wait, 6000)
    wait(1200)
    return {
        "verdict": "PASS query",
        "query": control.query,
        "rows": control.list_surface().row_count(),
    }


def no_match(page, wait, find, prefs) -> dict:
    """The empty line, under a query no project answers."""
    wait(1500)
    found = controls(find)
    if not found:
        return {"verdict": f"FAIL {page.data_name}: no picker to open"}
    control = found[0]
    control.set_open(True)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, "zzzqqq")
    if not until(lambda: control.empty, wait):
        return {"verdict": "FAIL a query nothing answers drew no empty line"}
    wait(600)
    return {
        "verdict": "PASS no-match",
        "line": control.state_line().isVisibleTo(control.popup()),
        "said": control.empty_label,
    }


def error(page, wait, find, prefs) -> dict:
    """The error line, with the page's own mock armed to fail its next call.

    The upstream project demos hold no armed-failure case, so this state has no twin on the
    React page; `tools/drives/upstream/entity-picker-error.js` is where the line itself is
    compared. What is checked here is that the project preset draws it like any other picker.
    """
    wait(1500)
    found = controls(find)
    context = getattr(page, "context", None)
    if not found or context is None:
        return {"verdict": f"FAIL {page.data_name}: no picker and mock to arm"}
    arm = fail_next_of(context.client)
    if arm is None:
        return {"verdict": "FAIL the page reads a client with no fail_next"}
    control = found[0]
    arm()
    control.set_open(True)
    if not until(lambda: bool(control.error), wait, 8000):
        return {"verdict": "FAIL a read armed to fail drew no error"}
    wait(400)
    return {
        "verdict": "PASS error",
        "line": control.state_line().isVisibleTo(control.popup()),
        "said": str(control.error or "")[:60],
    }


def armed(page, wait, find, prefs) -> dict:
    """The token field with the caret on its last chip, which is clause 4 standing still."""
    wait(2000)
    found = controls(find)
    tokens = first(found, "tokens")
    if tokens is None or len(tokens.labels) < 2:
        return {"verdict": "FAIL no token field with chips to arm"}
    caret = tokens.caret()
    caret.setFocus()
    QTest.keyClick(caret, Qt.Key.Key_Backspace)
    wait(300)
    if tokens.armed != len(tokens.labels) - 1:
        return {"verdict": f"FAIL Backspace armed {tokens.armed}"}
    return {"verdict": "PASS armed", "armed": tokens.armed, "chips": len(tokens.chips())}


def overflow(page, wait, find, prefs) -> dict:
    """The narrow summary control: whole chips, then `+n` for the rest, on one line."""
    wait(2000)
    found = controls(find)
    narrow = next(
        (one for one in found if one.summary == "ellipsis" and one.overflow_pill().count > 0),
        None,
    )
    if narrow is None:
        return {"verdict": "FAIL no narrow summary control with chips to hide"}
    wait(200)
    shown = sum(1 for chip in narrow.chips() if chip.isVisibleTo(narrow))
    return {
        "verdict": "PASS overflow",
        "shown": shown,
        "pill": narrow.overflow_pill().count,
        "height": narrow.height(),
        "width": narrow.width(),
    }


def ticked(page, wait, find, prefs) -> dict:
    """The list open on a multi picker whose rows are already ticked."""
    wait(2000)
    found = controls(find)
    multi = next((one for one in found if one.multiple and one.labels), None)
    if multi is None:
        return {"verdict": "FAIL no multi picker holding a value"}
    multi.set_open(True)
    if not until(lambda: multi.list_surface().row_count() > 0, wait):
        return {"verdict": "FAIL the list drew no row"}
    until(lambda: pictures(multi) > 0, wait, 6000)
    wait(1200)
    return {
        "verdict": "PASS ticked",
        "rows": multi.list_surface().row_count(),
        "ticked": len(multi.keys),
    }


def state(name: str) -> Any:
    """The function a per-state drive file names."""
    return {
        "rest": rest,
        "hover": hover,
        "focus": focus,
        "loading": loading,
        "open": open_rows,
        "query": query,
        "no-match": no_match,
        "error": error,
        "armed": armed,
        "overflow": overflow,
        "ticked": ticked,
    }[name]
