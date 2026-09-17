"""What the two status pickers' state drives share: find a control, and put it in one state.

One state of the shot matrix per file. `tools/drives/upstream/status-<picker>-<state>.js` is the
upstream half of the same state, and the pair of shots is what the QA pass reads.

Three of the states are not drivable upstream, which `tools/drives/upstream/README.md` already
says of hover and focus: a drive runs inside the page and cannot make the browser hover or give a
`:focus-visible` ring, and neither status demo arms a failing read, so `loading` and `error` have
no hook there either. Their upstream halves read the classes of the block instead, and the Qt
half below puts the widget in the state its own read would.
"""
from __future__ import annotations

from qtpy.QtCore import Qt

from sg_widgets_qt.widgets.status_picker import StatusPicker

#: What a failed status read is drawn as, in place of the list.
ERROR_TEXT = "The status read could not be made."

#: A query no status label or code carries, which is what the empty line stands behind.
NO_MATCH_QUERY = "zzqq"

#: The query whose runs come back bold in "In Progress".
QUERY = "prog"


def demo_of(widget) -> str:
    """The `data-demo` name of the box a picker stands in."""
    walk = widget
    for _ in range(6):
        walk = walk.parentWidget()
        if walk is None:
            return ""
        name = walk.property("data_demo")
        if name:
            return str(name)
    return ""


def pickers(find) -> dict:
    """Every status picker on the page that stands in a named box."""
    return {demo_of(one): one for one in (find(StatusPicker, all=True) or []) if demo_of(one)}


def settle(picker, wait, ms: int = 1000) -> None:
    """Spin until the picker's own read has landed."""
    for _ in range(max(1, ms // 25)):
        wait(25)
        if not picker.load.loading:
            return


def chosen(find, demo: str = "p70"):
    """The picker the state is driven on: the first project's, which is filled and interactive."""
    found = pickers(find)
    return found.get(demo) or next(iter(found.values()), None)


def state(page, wait, find, name: str, demo: str = "p70") -> dict:
    """Leave the page in `name` and answer what the shot carries."""
    wait(400)
    picker = chosen(find, demo)
    if picker is None:
        return {"verdict": f"FAIL no status picker to drive into {name}"}
    settle(picker, wait)
    control = picker.control

    if name == "open":
        control.set_open(True)
        wait(350)
        return _answer(name, picker, rows=control.list_surface().row_count())

    if name == "query":
        control.set_open(True)
        wait(250)
        control.set_query(QUERY)
        wait(300)
        return _answer(name, picker, rows=control.list_surface().row_count(), query=control.query)

    if name == "empty":
        control.set_open(True)
        wait(250)
        control.set_query(NO_MATCH_QUERY)
        wait(300)
        return _answer(
            name, picker, rows=control.list_surface().row_count(), empty=control.empty
        )

    if name == "loading":
        # What the read itself sets while it is out: skeletons in the popup, the control inert.
        picker.list_picker.set_loading(True)
        control.set_open(True)
        wait(350)
        return _answer(name, picker, loading=control.loading, inert=control.inert)

    if name == "error":
        picker.list_picker.set_loading(False)
        picker.list_picker.set_load_error(ERROR_TEXT)
        control.set_open(True)
        wait(350)
        return _answer(name, picker, error=control.error)

    if name == "focus":
        # A keyboard focus paints the ring; a mouse focus does not, which is rule 5. A closed
        # summary trigger is the tab stop itself: its search box lives inside the popup.
        target = control.caret() if control.inline else control
        target.setFocus(Qt.FocusReason.TabFocusReason)
        wait(300)
        return _answer(name, picker, ring=control._ring_shown())

    if name == "hover":
        control.set_hovered(True)
        wait(300)
        return _answer(name, picker, hovered=True)

    return _answer("rest", picker)


def _answer(name: str, picker, **notes) -> dict:
    notes["demo"] = demo_of(picker)
    notes["size"] = picker.size
    return {"verdict": f"PASS {name}", "state": name, **notes}
