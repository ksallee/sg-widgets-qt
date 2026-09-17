"""The Qt half of the two entity-type pickers' state matrix.

One function per state. `tools/drives/entity-type-picker-<state>.py` and
`tools/drives/entity-type-multi-picker-<state>.py` are the entry points, and
`tools/drives/upstream/<same>.js` leaves the upstream page in the same state, so the pair of
shots is what the QA pass reads.

The states neither page draws at rest are made here rather than waited for: the vocabulary is one
cached schema read, so a loading or a failed read is made by handing the picker's schema service
a call that sleeps or raises and asking it to read again, which is the widget's own path.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from qtpy import QtCore, QtGui
from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.theme import theme_of, with_alpha  # noqa: E402
from sg_widgets_qt.widgets.entity_type_picker import EntityTypePicker  # noqa: E402
from sg_widgets_qt.widgets.picker_control import over  # noqa: E402

__all__ = [
    "error",
    "focus",
    "hover",
    "loading",
    "no_match",
    "open_rows",
    "overflow",
    "query",
    "rest",
    "summary",
]

#: The query the matrix narrows with, and the one nothing answers.
QUERY = "ver"
NO_MATCH_QUERY = "zzzqqq"


def pickers(find) -> list:
    """Every entity-type picker a reader can work, in the order the page draws them."""
    return [
        one
        for one in find(EntityTypePicker, all=True)
        if one.isVisible() and not one.readonly and not one.disabled
    ]


def wait_for(read, wait, ms: int = 6000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def first(find, note) -> object:
    found = pickers(find)
    if not found:
        note("no entity-type picker a reader can work")
        return None
    return found[0]


def _verdict(state: str, bad: list, seen: dict) -> dict:
    out = {"state": state, **seen}
    out["verdict"] = f"PASS {state}" if not bad else "FAIL " + "; ".join(bad)
    return out


# --- the states ------------------------------------------------------------------------------


def rest(page, wait, find, prefs) -> dict:
    wait(400)
    found = pickers(find)
    bad: list = []
    if not found:
        bad.append("no picker on the page")
    return _verdict("rest", bad, {"pickers": len(found)})


def hover(page, wait, find, prefs) -> dict:
    """The wash is `muted` at 30% laid over the surface, never a blend towards the token."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("hover", bad, {})
    control = picker.control
    control.set_hovered(True)
    wait(400)
    theme = theme_of(control)
    wanted = over(theme.color("background"), with_alpha(theme.muted, 0.3))
    shot = control.grab().toImage()
    # A pixel inside the box and away from the border, the chip and the trailing controls.
    seen = QtGui.QColor(shot.pixel(control.width() // 2, control.height() // 2))
    off = max(
        abs(seen.red() - wanted.red()),
        abs(seen.green() - wanted.green()),
        abs(seen.blue() - wanted.blue()),
    )
    if off > 1:
        bad.append(f"the wash is {seen.name()}, wanted muted at 30% over the surface {wanted.name()}")
    return _verdict("hover", bad, {"seen": seen.name(), "wanted": wanted.name(), "off": off})


def focus(page, wait, find, prefs) -> dict:
    """A keyboard focus paints the ring; a mouse focus does not, which is rule 5."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("focus", bad, {})
    control = picker.control
    control.caret().setFocus(Qt.FocusReason.TabFocusReason)
    wait(300)
    if not control._ring_shown():
        bad.append("a keyboard focus painted no ring")
    return _verdict("focus", bad, {"ring": control._ring_shown()})


def open_rows(page, wait, find, prefs) -> dict:
    """The list open on the first control: the glyph leads every row, the chosen one is ticked."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("open", bad, {})
    control = picker.control
    control.set_open(True)
    if not wait_for(lambda: control.list_surface().row_count() > 0, wait):
        bad.append("the list opened with no row")
        return _verdict("open", bad, {})
    wait(400)
    model = control.list_surface().source_model()
    glyphs = sum(1 for row in range(model.rowCount()) if model.index(row, 0).data(Roles.GLYPH))
    ticked = [
        row for row in range(model.rowCount()) if model.index(row, 0).data(Roles.CHECKED) is True
    ]
    if glyphs != model.rowCount():
        bad.append(f"{model.rowCount() - glyphs} rows carry no type glyph")
    if control.keys and not ticked:
        bad.append("the chosen row carries no indicator")
    return _verdict(
        "open",
        bad,
        {
            "rows": model.rowCount(),
            "glyphs": glyphs,
            "ticked": ticked,
            "indicator": control.row_delegate().indicator,
        },
    )


def query(page, wait, find, prefs) -> dict:
    """The list open over a query, so the matched runs are drawn in DemiBold."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("query", bad, {})
    control = picker.control
    control.set_open(True)
    wait_for(lambda: control.list_surface().row_count() > 0, wait)
    every = control.list_surface().row_count()
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, QUERY)
    wait(500)
    model = control.list_surface().source_model()
    bold = sum(
        1
        for row in range(model.rowCount())
        if any(bool(run[1]) for run in (model.index(row, 0).data(Roles.RUNS) or []))
    )
    if model.rowCount() >= every:
        bad.append(f"{QUERY!r} narrowed nothing out of {every} types")
    if bold == 0:
        bad.append("no row drew a matched run")
    return _verdict("query", bad, {"rows": model.rowCount(), "bold": bold, "of": every})


def no_match(page, wait, find, prefs) -> dict:
    """The list open over a query nothing answers: the empty line stands alone."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("no-match", bad, {})
    control = picker.control
    control.set_open(True)
    wait_for(lambda: control.list_surface().row_count() > 0, wait)
    caret = control.caret()
    caret.setFocus()
    QTest.keyClicks(caret, NO_MATCH_QUERY)
    wait_for(lambda: control.empty, wait)
    wait(400)
    if not control.empty:
        bad.append(f"{NO_MATCH_QUERY!r} still matched a type")
    if not control.state_line().isVisibleTo(control.popup()):
        bad.append("nothing was drawn in place of the rows")
    return _verdict(
        "no-match",
        bad,
        {"rows": control.list_surface().row_count(), "line": control.state_line().text()},
    )


class _Slow:
    """A schema read that never lands while the shot is taken."""

    def __init__(self, held) -> None:
        self._held = held

    def __call__(self):
        time.sleep(30)
        return self._held()


def _fails():
    raise RuntimeError("the site answered 503 for /schema")


def _reread(picker, wait, swap) -> None:
    """Hand the picker's schema service `swap` and ask it to read again."""
    schema = picker.context.schema
    held = schema.entity_types
    schema.entity_types = swap(held)
    try:
        picker.set_context(picker.context)
        wait(60)
    finally:
        # The service is shared, so the real call goes back before anything else reads it.
        QtCore.QTimer.singleShot(0, lambda: setattr(schema, "entity_types", held))


def loading(page, wait, find, prefs) -> dict:
    """The list open while the one schema read is out, so the skeletons stand."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("loading", bad, {})
    control = picker.control
    _reread(picker, wait, lambda held: _Slow(held))
    control.set_open(True)
    wait(120)
    standing = control.skeletons().isVisibleTo(control.popup())
    if not control.loading:
        bad.append("the control is not loading while its read is out")
    if not standing:
        bad.append("the skeletons are not on show while the read is out")
    return _verdict("loading", bad, {"skeletons": standing, "rows": control.list_surface().row_count()})


def error(page, wait, find, prefs) -> dict:
    """The list open after the schema read was made to fail: what it said, on one line."""
    wait(400)
    bad: list = []
    picker = first(find, bad.append)
    if picker is None:
        return _verdict("error", bad, {})
    control = picker.control
    _reread(picker, wait, lambda _held: _fails)
    control.set_open(True)
    if not wait_for(lambda: bool(control.error), wait, 4000):
        bad.append("a read made to fail drew no error")
    wait(400)
    if control.error and not control.state_line().isVisibleTo(control.popup()):
        bad.append("the error is held but the line is not drawn")
    return _verdict("error", bad, {"said": str(control.error or "")[:80]})


def overflow(page, wait, find, prefs) -> dict:
    """The narrow ellipsis control: whole chips, `+n` for the rest, one line."""
    wait(400)
    bad: list = []
    narrow = next(
        (
            one.control
            for one in pickers(find)
            if one.control.summary == "ellipsis" and one.control.overflow_pill().count > 0
        ),
        None,
    )
    if narrow is None:
        bad.append("no narrow summary control with chips to hide")
        return _verdict("overflow", bad, {})
    shown = [chip for chip in narrow.chips() if chip.isVisibleTo(narrow)]
    hidden = [chip for chip in narrow.chips() if not chip.isVisibleTo(narrow)]
    pill = narrow.overflow_pill()
    if pill.count != len(hidden):
        bad.append(f"the pill reads +{pill.count} for {len(hidden)} hidden chips")
    if narrow.height() > 40:
        bad.append(f"the control is {narrow.height()}px tall, wanted one line")
    return _verdict(
        "overflow",
        bad,
        {"shown": len(shown), "hidden": len(hidden), "pill": pill.count, "h": narrow.height()},
    )


def summary(page, wait, find, prefs) -> dict:
    """The three summary modes, wide and narrow, as the demo lays them out."""
    wait(500)
    bad: list = []
    modes: dict = {}
    for one in pickers(find):
        control = one.control
        if not control.multiple or not control.keys:
            continue
        held = modes.setdefault(control.summary, [])
        held.append(
            {
                "width": control.width(),
                "chips": sum(1 for chip in control.chips() if chip.isVisibleTo(control)),
                "pill": control.overflow_pill().count,
                "inline": control.inline,
                "h": control.height(),
            }
        )
    for wanted in ("chips", "ellipsis", "count"):
        if wanted not in modes:
            bad.append(f"the page draws no {wanted} control holding a value")
    if "chips" in modes and not all(one["inline"] for one in modes["chips"]):
        bad.append("a chips control is not a token field")
    if "ellipsis" in modes and any(one["inline"] for one in modes["ellipsis"]):
        bad.append("an ellipsis control still holds an inline caret")
    if "count" in modes and any(one["chips"] for one in modes["count"]):
        bad.append("a count control draws chips rather than a count")
    return _verdict("summary", bad, {"modes": modes})
