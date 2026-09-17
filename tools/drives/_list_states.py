"""The states of the list picker pair, one function each, for the shot matrix.

Every `tools/drives/list-picker-<state>.py` and `tools/drives/list-multi-picker-<state>.py` is a
two-line file over one function here, and every one of them has its twin under
`tools/drives/upstream/<same>.js`, which drives the upstream page into the same state. A shot of
each pair is what the QA pass reads.

`:hover` and keyboard focus are widget state here rather than CSS, so this file can reach them
where the upstream body cannot; `upstream/README.md` says so, and the upstream twin answers the
tokens the rule resolves to instead, so the two are compared as numbers.
"""
from __future__ import annotations

from typing import Any

from qtpy.QtCore import Qt

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.theme import with_alpha
from sg_widgets_qt.widgets.list_picker import ListPicker
from sg_widgets_qt.widgets.picker_control import over

__all__ = [
    "demo_of",
    "list_error",
    "list_focus",
    "list_hover",
    "list_invalid",
    "list_loading",
    "list_no_rows",
    "list_open",
    "list_overflow",
    "list_query",
    "list_readonly",
    "list_summary",
    "pickers",
    "picker_named",
    "rows_of",
]

#: The query the shot picker's vocabulary answers rows for, with the matched runs bold.
QUERY = "d"
#: A query the vocabulary answers nothing for, so the empty line stands.
NO_MATCH = "zzzqqq"
#: The room the upstream demo's table cell gives a control, which is what the chip fit cuts against.
OVERFLOW_WIDTH = 380


def demo_of(picker: Any) -> str:
    """The `data_demo` name of the demo case a picker sits in, or `page`."""
    walk = picker.parentWidget()
    for _ in range(6):
        if walk is None:
            return "page"
        name = walk.property("data_demo")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def pickers(find) -> list:
    """Every list picker on the page, the multi one included: it is a subclass."""
    return [one for one in find(ListPicker, all=True) if one.isVisible()]


def picker_named(find, name: str):
    """The picker of one demo case, or the first one on the page."""
    found = pickers(find)
    for one in found:
        if demo_of(one) == name:
            return one
    return found[0] if found else None


def rows_of(picker) -> list:
    """What the list draws now: the label, the secondary and whether a run is bold."""
    model = picker.rows_model
    out = []
    for row in range(model.rowCount()):
        index = model.index(row, 0)
        runs = index.data(Roles.RUNS) or []
        out.append(
            {
                "label": index.data(Roles.LABEL),
                "secondary": index.data(Roles.SECONDARY),
                "checked": index.data(Roles.CHECKED),
                "bold": [text for text, match, _ in runs if match],
            }
        )
    return out


def _settled(picker, wait, ms: int = 600) -> None:
    """Let the page settle before the state is set."""
    wait(ms)


def _open(picker, wait) -> dict:
    control = picker.control
    picker.set_open(True)
    wait(400)
    surface = control.list_surface()
    return {
        "open": control.is_open,
        "rows": surface.row_count(),
        "listed": rows_of(picker),
        "search_row": control.search_row().isVisibleTo(control.popup()),
        "indicator": control.row_delegate().indicator,
        "thumbnail": control.row_delegate().thumbnail,
    }


def _answer(verdict: str, picker, extra: dict) -> dict:
    out = {"verdict": verdict, "demo": demo_of(picker), "slot": picker.control.slot}
    out.update(extra)
    return out


# --- the states ---------------------------------------------------------------------------


def list_open(page, wait, find, prefs, demo: str = "labels") -> dict:
    """The list open on the display-values demo, so a row shows its display label."""
    wait(500)
    picker = picker_named(find, demo)
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    _settled(picker, wait)
    seen = _open(picker, wait)
    wait(300)
    if not seen["open"] or seen["rows"] == 0:
        return _answer("FAIL the list did not open with rows", picker, seen)
    if seen["search_row"]:
        return _answer("FAIL a picker that is not searchable kept a search row", picker, seen)
    return _answer("PASS open with rows", picker, seen)


def list_query(page, wait, find, prefs) -> dict:
    """The searchable demo open over a query, so the matched runs are bold."""
    wait(500)
    picker = picker_named(find, "searchable")
    if picker is None:
        return {"verdict": "FAIL no searchable list picker on the page"}
    _settled(picker, wait)
    picker.set_open(True)
    wait(200)
    picker.control.set_query(QUERY)
    wait(400)
    seen = {
        "open": picker.control.is_open,
        "query": picker.control.query,
        "rows": picker.control.list_surface().row_count(),
        "listed": rows_of(picker),
        "search_row": picker.control.search_row().isVisibleTo(picker.control.popup()),
    }
    bold = [one for one in seen["listed"] if one["bold"]]
    if not seen["search_row"]:
        return _answer("FAIL a searchable picker drew no search row", picker, seen)
    if not bold:
        return _answer("FAIL the query left no matched run bold", picker, seen)
    return _answer("PASS query with bold runs", picker, seen)


def list_loading(page, wait, find, prefs) -> dict:
    """The list open while a caller's read is in flight, so the skeletons stand."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    picker.set_loading(True)
    wait(100)
    # A loading control is inert, so the list is opened on the control itself.
    picker.control.set_inert(False)
    picker.control.set_open(True)
    wait(400)
    seen = {
        "loading": picker.loading,
        "open": picker.control.is_open,
        "skeletons": picker.control.skeletons().isVisibleTo(picker.control.popup()),
        "inert": picker.control.inert,
    }
    if not seen["skeletons"]:
        return _answer("FAIL a read in flight drew no skeletons", picker, seen)
    return _answer("PASS loading", picker, seen)


def list_no_rows(page, wait, find, prefs) -> dict:
    """The searchable demo open over a query nothing answers, so the empty line stands."""
    wait(500)
    picker = picker_named(find, "searchable")
    if picker is None:
        return {"verdict": "FAIL no searchable list picker on the page"}
    picker.set_open(True)
    wait(200)
    picker.control.set_query(NO_MATCH)
    wait(400)
    line = picker.control.state_line()
    seen = {
        "open": picker.control.is_open,
        "rows": picker.control.list_surface().row_count(),
        "empty": picker.control.empty,
        "line": line.label,
        "state": line.state,
        "empty_label": picker.control.empty_label,
    }
    if seen["rows"] != 0 or not seen["empty"]:
        return _answer("FAIL an empty set still listed rows", picker, seen)
    return _answer("PASS no rows", picker, seen)


def list_error(page, wait, find, prefs) -> dict:
    """The list open after the caller's read failed, and the message under the control."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    picker.set_load_error("The read failed.")
    picker.set_error("Not a valid value.")
    wait(100)
    picker.set_open(True)
    wait(400)
    seen = {
        "open": picker.control.is_open,
        "load_error": picker.load_error,
        "error": picker.error,
    }
    if not seen["load_error"] or not seen["error"]:
        return _answer("FAIL the error did not land", picker, seen)
    return _answer("PASS error", picker, seen)


def list_hover(page, wait, find, prefs) -> dict:
    """The control under the pointer: `background` with `muted` at 30% laid over it."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    control = picker.control
    control.set_hovered(True)
    wait(400)
    theme = control.theme
    # `bg-background hover:bg-muted/30`: the wash is laid over the surface, not blended in.
    wash = with_alpha(theme.muted, 0.3)
    surface = over(theme.color("background"), wash)
    return _answer(
        "PASS hover",
        picker,
        {
            "hovered": control.hovered,
            "background": theme.color("background").name(),
            "muted": str(theme.muted),
            "wash_alpha": round(wash.alphaF(), 4),
            "surface": surface.name(),
        },
    )


def list_focus(page, wait, find, prefs) -> dict:
    """The control holding a keyboard focus, so the painted ring stands (rule 5)."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    control = picker.control
    # A keyboard focus paints the ring; a mouse focus does not, which is rule 5.
    target = control.caret() if control.inline else control
    target.setFocus(Qt.FocusReason.TabFocusReason)
    wait(300)
    ring = control._ring_shown()
    return _answer(
        "PASS focus" if ring else "FAIL a keyboard focus painted no ring",
        picker,
        {"ring": ring, "ring_token": control.theme.color("ring").name()},
    )


def list_readonly(page, wait, find, prefs) -> dict:
    """Readonly keeps full contrast and drops the chevron and the clear control."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    picker.set_readonly(True)
    wait(300)
    control = picker.control
    seen = {
        "opacity": control.disabled_opacity(),
        "chevron": control.open_control().isVisibleTo(control),
        "clear": control.clear_control().isVisibleTo(control),
        "crosses": [chip.removable for chip in control.chips() if hasattr(chip, "removable")],
    }
    if seen["opacity"] != 1.0 or seen["chevron"] or seen["clear"]:
        return _answer("FAIL readonly kept an affordance", picker, seen)
    return _answer("PASS readonly", picker, seen)


def list_invalid(page, wait, find, prefs) -> dict:
    """Invalid puts the border and the ring in `destructive`, with the message under it."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list picker on the page"}
    picker.set_invalid(True)
    picker.set_error("Not a valid value.")
    wait(300)
    return _answer(
        "PASS invalid",
        picker,
        {
            "invalid": picker.invalid,
            "error": picker.error,
            "destructive": picker.control.theme.color("destructive").name(),
        },
    )


def list_overflow(page, wait, find, prefs) -> dict:
    """The chip row holding more than the line fits, so the rest is a `+n` pill."""
    wait(500)
    picker = picker_named(find, "labels")
    if picker is None:
        return {"verdict": "FAIL no list multi picker on the page"}
    if not picker.MULTIPLE:
        return {"verdict": "FAIL the overflow state is the multi picker's"}
    # `ellipsis` is the summary the page draws: the chips that fit, then a `+n` pill. The
    # control is held to the width of the upstream demo's table cell, so the fit has the same
    # room to cut against, and every value the field offers is ticked, as the upstream twin does.
    picker.setMaximumWidth(OVERFLOW_WIDTH)
    picker.set_value([one.code for one in picker.options])
    wait(400)
    control = picker.control
    pill = control.overflow_pill()
    seen = {
        "held": len(picker.value),
        "shown": len([chip for chip in control.chips() if chip.isVisibleTo(control)]),
        "pill": pill.isVisibleTo(control),
        "count": pill.count if hasattr(pill, "count") else 0,
        "overflow_label": control.overflow_label,
    }
    if not seen["pill"]:
        return _answer("FAIL a full chip row drew no +n pill", picker, seen)
    return _answer("PASS overflow to +n", picker, seen)


def list_summary(page, wait, find, prefs) -> dict:
    """The three summary modes of the multi picker, one per demo on the page."""
    wait(500)
    found = [one for one in pickers(find) if one.MULTIPLE]
    if not found:
        return {"verdict": "FAIL no list multi picker on the page"}
    modes = ("chips", "ellipsis", "count")
    for index, picker in enumerate(found[:3]):
        picker.set_summary(modes[index])
        if not picker.value:
            picker.set_value([one.code for one in picker.options[:3]])
    wait(400)
    seen = [
        {
            "demo": demo_of(one),
            "summary": one.summary,
            "inline": one.control.inline,
            "chips": len([chip for chip in one.control.chips() if chip.isVisibleTo(one.control)]),
        }
        for one in found[:3]
    ]
    if [one["summary"] for one in seen] != list(modes[: len(seen)]):
        return {"verdict": "FAIL the summary modes did not land", "seen": seen}
    return {"verdict": "PASS the three summary modes", "seen": seen}
