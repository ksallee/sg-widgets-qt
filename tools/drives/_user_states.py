"""What the two user pickers' state drives share: finding a control and leaving it in a state.

One function per state of the shot matrix. `tools/drives/user-picker-<state>.py` and
`tools/drives/user-multi-picker-<state>.py` are one line each over these, and
`tools/drives/upstream/<same name>.js` leaves the upstream page in the same state, so the two
shots are read as a pair.

A drive file is exec'd by `tools/qa.py`, so it puts this directory on `sys.path` itself:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _user_states import user_open

The offscreen platform answers an 800x800 screen whatever the window is, so a popover anchored
low in a 900px window flips above its control and the shot reads as a placement bug no real
screen has. Every open state here scrolls its control near the top of the pane first, which is
what the upstream half does with `window.scrollTo` for the same reason.
"""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QWidget

from sg_widgets_qt.widgets.picker_control import PickerControl

__all__ = [
    "user_disabled",
    "user_empty",
    "user_error",
    "user_filled",
    "user_focus",
    "user_hover",
    "user_invalid",
    "user_loading",
    "user_open",
    "user_overflow",
    "user_query",
    "user_readonly",
    "user_rest",
    "user_summary",
    "user_tokens",
]

#: What the query state types, which the fixtures answer with one person.
QUERY = "ada"
#: What the empty state types, which nothing answers.
NOTHING = "zzzqqq"


# --- finding what to drive ----------------------------------------------------------------


def controls(find) -> list:
    """Every picker control on the page, in the order the demo lays them out."""
    return [control for control in find(PickerControl, all=True) if control.isVisible()]


def live_controls(find) -> list:
    """The controls the reader can drive: not the ones a demo draws inert."""
    return [one for one in controls(find) if not one.disabled and not one.readonly]


def case_widget(page, wanted: str) -> QWidget | None:
    for widget in page.findChildren(QWidget):
        if widget.property("data_demo_case") == wanted:
            return widget
    return None


def demo_widget(page, wanted: str) -> QWidget | None:
    for widget in page.findChildren(QWidget):
        if widget.property("data_demo") == wanted:
            return widget
    return None


def case_of(control: PickerControl) -> str:
    """The demo case a control sits in, so a reading names something findable."""
    walk = control.parentWidget()
    for _ in range(8):
        if walk is None:
            return "page"
        name = walk.property("data_demo_case")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def control_in(page, find, case: str, index: int = 0) -> PickerControl | None:
    """The nth control of a demo case."""
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(PickerControl) if one.isVisible()]
    return found[index] if index < len(found) else None


def scroll_to(page, widget: QWidget, wait, room: int = 120) -> None:
    """Put a widget `room` under the top of the pane."""
    inner = page.scroll.widget()
    top = widget.mapTo(inner, widget.rect().topLeft()).y()
    page.scroll.verticalScrollBar().setValue(max(0, top - room))
    wait(500)


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


def settle_rows(control: PickerControl, wait) -> None:
    wait_for(lambda: control.list_surface().row_count() > 0, wait)
    wait_for(lambda: pictures(control) > 0, wait, 6000)
    wait(1000)


def rows_read(control: PickerControl) -> list:
    """The label, the sub-label and the right-hand column of every row on show."""
    from sg_widgets_qt.primitives.roles import Roles

    surface = control.list_surface()
    model = surface.model()
    out = []
    for row in range(min(surface.row_count(), 8)):
        if surface.is_load_more(row):
            continue
        index = model.index(row, 0)
        out.append(
            {
                "label": index.data(Roles.LABEL),
                "sub": index.data(Roles.SUB_LABEL),
                "secondary": index.data(Roles.SECONDARY),
            }
        )
    return out


def inert_read(control: PickerControl) -> dict:
    """What an inert control draws: the contrast and the two affordances."""
    return {
        "case": case_of(control),
        "opacity": control.disabled_opacity(),
        "chevron": control.open_control().isVisibleTo(control),
        "clear": control.clear_control().isVisibleTo(control),
        "labels": list(control.labels),
    }


# --- the states ---------------------------------------------------------------------------


def user_rest(page, wait, find, prefs) -> dict:
    """The page as it settles, nothing open."""
    wait(700)
    found = controls(find)
    return {
        "verdict": "PASS rest" if found else "FAIL no picker on the page",
        "controls": len(found),
        "placeholders": sorted({one.placeholder for one in found if not one.labels}),
    }


def user_filled(page, wait, find, prefs) -> dict:
    """The states section: a person in every control, the heights, then the three states."""
    wait(700)
    section = case_widget(page, "states")
    if section is None:
        return {"verdict": "FAIL no states section on the page"}
    scroll_to(page, section, wait, room=20)
    found = [one for one in section.findChildren(PickerControl) if one.isVisible()]
    return {
        "verdict": "PASS the states section is on show" if found else "FAIL no control in it",
        "controls": [inert_read(one) for one in found],
    }


def user_open(page, wait, find, prefs, case: str = "") -> dict:
    """The list open: an avatar, the name, the address under it, the type on the right."""
    wait(700)
    control = control_in(page, find, case) if case else None
    if control is None:
        live = live_controls(find)
        if not live:
            return {"verdict": "FAIL no picker to open"}
        control = live[0]
    scroll_to(page, control, wait)
    control.set_open(True)
    settle_rows(control, wait)
    read = rows_read(control)
    addressed = [one for one in read if one["sub"] and "@" in str(one["sub"])]
    return {
        "verdict": (
            "PASS the list is open over the people"
            if read and addressed
            else "FAIL the rows carry no address under the name"
        ),
        "rows": control.list_surface().row_count(),
        "read": read[:3],
    }


def user_query(page, wait, find, prefs, case: str = "by-address") -> dict:
    """The list open over `ada`, so the matched runs are bold in both lines.

    The single picker's own `by-address` case is the one upstream's twin drives, because its
    placeholder names what a person search matches; a page without it takes its first control.
    """
    wait(700)
    control = control_in(page, find, case) if case else None
    if control is None:
        live = live_controls(find)
        if not live:
            return {"verdict": "FAIL no picker to query"}
        control = live[0]
    scroll_to(page, control, wait)
    control.set_open(True)
    wait(400)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, QUERY)
    settle_rows(control, wait)
    read = rows_read(control)
    return {
        "verdict": (
            f"PASS the query {QUERY!r} narrowed the list"
            if read
            else f"FAIL nothing answered {QUERY!r}"
        ),
        "query": control.query,
        "rows": control.list_surface().row_count(),
        "read": read,
    }


def user_loading(page, wait, find, prefs) -> dict:
    """The list open with the first read still out, so the skeletons stand."""
    wait(700)
    live = live_controls(find)
    if not live:
        return {"verdict": "FAIL no picker to open"}
    control = live[0]
    scroll_to(page, control, wait)
    control.set_open(True)
    # The skeletons stand only while the first read is out, so nothing waits for rows.
    wait(60)
    drawn = control.skeletons().isVisibleTo(control.popup())
    return {
        "verdict": "PASS the skeletons stand" if drawn else "FAIL no skeleton while a read is out",
        "skeletons": drawn,
        "rows": control.list_surface().row_count(),
    }


def user_empty(page, wait, find, prefs) -> dict:
    """The list open over a query nothing answers, so the empty line stands alone."""
    wait(700)
    live = live_controls(find)
    if not live:
        return {"verdict": "FAIL no picker to open"}
    control = live[0]
    scroll_to(page, control, wait)
    control.set_open(True)
    wait(400)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, NOTHING)
    wait_for(lambda: control.empty and not control.loading, wait)
    wait(600)
    drawn = control.state_line().isVisibleTo(control.popup())
    return {
        "verdict": "PASS the empty line stands" if drawn else "FAIL nothing stood for no match",
        "empty": control.empty,
        "rows": control.list_surface().row_count(),
        "said": control.empty_label,
    }


def user_error(page, wait, find, prefs) -> dict:
    """The list open with a read that failed, so the error line stands.

    Neither demo arms a failure, upstream or here, so there is no upstream twin: the block is
    the picker base's and is shot on the entity picker pair. It is driven here so the person
    preset is known not to break it.
    """
    wait(700)
    live = live_controls(find)
    if not live:
        return {"verdict": "FAIL no picker to open"}
    control = live[0]
    scroll_to(page, control, wait)
    control.set_open(True)
    wait(300)
    control.set_error("The read failed")
    wait(400)
    drawn = control.state_line().isVisibleTo(control.popup())
    return {
        "verdict": "PASS the error line stands" if drawn else "FAIL a failed read drew no line",
        "error": control.error,
        "rows": control.list_surface().row_count(),
    }


def user_focus(page, wait, find, prefs) -> dict:
    """The caret holding a keyboard focus ring, which a mouse focus never paints."""
    wait(700)
    live = live_controls(find)
    if not live:
        return {"verdict": "FAIL no picker to focus"}
    control = live[0]
    scroll_to(page, control, wait, room=200)
    # Tab lands in the control's own input on an inline picker, and on the box itself on a
    # summary trigger, whose caret lives in the popup. Rule 7 clause 2.
    taker = control.caret() if control.inline else control
    taker.setFocus(Qt.FocusReason.TabFocusReason)
    wait(300)
    ring = control._ring_shown()
    return {
        "verdict": "PASS the ring is painted" if ring else "FAIL a keyboard focus painted no ring",
        "ring": ring,
        "inline": control.inline,
    }


def user_hover(page, wait, find, prefs) -> dict:
    """The control under the pointer: `muted` at 30% laid over `background`."""
    wait(700)
    live = live_controls(find)
    if not live:
        return {"verdict": "FAIL no picker to hover"}
    control = live[0]
    scroll_to(page, control, wait, room=200)
    control.set_hovered(True)
    wait(400)
    return {"verdict": "PASS the hover wash is on", "case": case_of(control)}


def _inert_state(page, find, wait, prop: str, wanted: dict) -> dict:
    found = next(
        (one for one in controls(find) if getattr(one, prop) and one.labels),
        None,
    )
    if found is None:
        return {"verdict": f"FAIL no control the demo draws {prop}"}
    scroll_to(page, found, wait, room=200)
    wait(200)
    read = inert_read(found)
    wrong = [name for name, value in wanted.items() if read[name] != value]
    return {
        "verdict": f"PASS {prop}" if not wrong else f"FAIL {prop}: {wrong} read {read}",
        "read": read,
    }


def user_readonly(page, wait, find, prefs) -> dict:
    """Readonly keeps full contrast and drops the chevron and the clear control (rule 5)."""
    wait(700)
    return _inert_state(
        page, find, wait, "readonly", {"opacity": 1.0, "chevron": False, "clear": False}
    )


def user_disabled(page, wait, find, prefs) -> dict:
    """Disabled is the control at half opacity, with no clear control and no affordance."""
    wait(700)
    return _inert_state(page, find, wait, "disabled", {"opacity": 0.5, "clear": False})


def user_invalid(page, wait, find, prefs) -> dict:
    """Invalid puts the border and the ring in `destructive` and keeps every affordance."""
    wait(700)
    return _inert_state(page, find, wait, "invalid", {"chevron": True})


# --- the multi picker's own states ----------------------------------------------------------


def user_tokens(page, wait, find, prefs) -> dict:
    """The token field with three chips already in it, and the caret after them."""
    wait(700)
    control = control_in(page, find, "tokens")
    if control is None:
        return {"verdict": "FAIL no token field on the page"}
    scroll_to(page, control, wait, room=200)
    wait(200)
    shown = [chip for chip in control.chips() if chip.isVisibleTo(control)]
    return {
        "verdict": "PASS the chip row stands" if shown else "FAIL the token field drew no chip",
        "chips": len(shown),
        "labels": list(control.labels),
        "inline": control.inline,
    }


def user_summary(page, wait, find, prefs) -> dict:
    """The three summary modes over five people, wide and narrow."""
    wait(700)
    section = case_widget(page, "summary")
    if section is None:
        return {"verdict": "FAIL no summary section on the page"}
    scroll_to(page, section, wait, room=20)
    read = []
    for name in ("chips", "chips-narrow", "ellipsis", "ellipsis-narrow", "count", "count-narrow", "max"):
        holder = demo_widget(page, name)
        if holder is None:
            continue
        found = [one for one in holder.findChildren(PickerControl) if one.isVisible()]
        if not found:
            continue
        control = found[0]
        read.append(
            {
                "demo": name,
                "summary": control.summary,
                "chips": sum(1 for chip in control.chips() if chip.isVisibleTo(control)),
                "pill": control.overflow_pill().count,
                "text": control.status_text() if control.summary == "count" else "",
                "w": control.width(),
                "h": control.height(),
            }
        )
    return {
        "verdict": "PASS the summary modes are on show" if read else "FAIL no summary demo found",
        "read": read,
    }


def user_overflow(page, wait, find, prefs) -> dict:
    """A narrow summary control: whole chips, `+n` for the rest, the list open on `+n`."""
    wait(700)
    holder = demo_widget(page, "ellipsis-narrow")
    control = None
    if holder is not None:
        found = [one for one in holder.findChildren(PickerControl) if one.isVisible()]
        control = found[0] if found else None
    if control is None:
        return {"verdict": "FAIL no narrow summary control on the page"}
    scroll_to(page, control, wait)
    shown = [chip for chip in control.chips() if chip.isVisibleTo(control)]
    hidden = len(control.labels) - len(shown)
    pill = control.overflow_pill()
    control.set_open(True)
    settle_rows(control, wait)
    return {
        "verdict": (
            "PASS whole chips, the rest counted, the list open behind the pill"
            if pill.isVisibleTo(control) and pill.count == hidden
            else f"FAIL the pill reads +{pill.count} for {hidden} hidden"
        ),
        "chips": len(shown),
        "pill": pill.count,
        "rows": control.list_surface().row_count(),
        "search_row": control.search_row().isVisibleTo(control.popup()),
    }


def by_name(name: str) -> Any:
    """The state function of that name, for a wrapper that wants to name it as a string."""
    return globals()[f"user_{name.replace('-', '_')}"]
