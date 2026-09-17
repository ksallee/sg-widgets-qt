"""status-picker: the contract, the option set, the row anatomy and the value signal.

The port of `~/dev/sg-widgets/tools/drives/status-picker-rows.js`. Upstream reads one DOM and
asks what a row is made of; here the row is painted from a model, so the anatomy is read off the
roles `RowDelegate` draws and off the widgets the popup holds: a status offered as an option is
the glyph, the name and the code, and the badge lives in the control (rule 9).

The codes below are the mock's own (`src/sg_widgets_core/mock.py`, `HIDDEN_VALUES`), which is
`valid_values` minus each project's `hidden_values` (probe 009_status_lists).

    .venv/bin/python tools/qa.py --page status-picker --drive tools/drives/status-picker.py
    .venv/bin/python tools/qa.py --page status-picker --drive tools/drives/status-picker.py --qt5
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.status_badge import StatusBadge  # noqa: E402
from sg_widgets_qt.widgets.status_glyph import StatusGlyph  # noqa: E402
from sg_widgets_qt.widgets.status_picker import StatusLeadDelegate, StatusPicker  # noqa: E402
from tests.qt.test_picker_contract import PickerShape, check_contract  # noqa: E402

#: Version's usable codes in project 70: `valid_values` minus that project's `hidden_values`.
CODES_70 = ("na", "rev", "vwd", "apr", "custom", "fin", "ip", "clsd", "cmpt", "cfrm")
#: The same in project 71, which hides two codes only.
CODES_71 = (
    "na", "rev", "vwd", "apr", "custom", "fin", "ip", "clsd", "cmpt", "cfrm",
    "pndad", "part", "pass", "pndng",
)
#: What both projects allow, in the first project's order.
BOTH = CODES_70


class Bot:
    """What `check_contract` wants of pytest-qt: a loop it can turn."""

    def wait(self, ms: int) -> None:
        QApplication.processEvents()


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


def by_demo(find) -> dict:
    return {demo_of(one): one for one in (find(StatusPicker, all=True) or []) if demo_of(one)}


def settler(picker, wait):
    """Spin until the picker's own read has landed, so a clause reads standing rows."""

    def settle() -> None:
        for _ in range(40):
            wait(25)
            if not picker.load.loading:
                return

    return settle


def option_at(picker, code: str) -> int:
    model = picker.rows_model
    for row in range(model.rowCount()):
        option = model.index(row, 0).data(Roles.ENTITY)
        if getattr(option, "code", None) == code:
            return row
    return -1


def painter_of(picker):
    """The delegate the list actually paints with.

    `ListSurface.row_delegate()` answers the one it was built with rather than the one
    `set_row_delegate` handed the view, so the anatomy is read off the view itself.
    """
    return picker.control.list_surface().itemDelegate()


def read_row(picker, code: str) -> dict:
    """What one option row is made of, as the anatomy of rule 9."""
    row = option_at(picker, code)
    if row < 0:
        return {}
    index = picker.rows_model.index(row, 0)
    delegate = painter_of(picker)
    source = delegate._source_for(index) if isinstance(delegate, StatusLeadDelegate) else None
    return {
        "code": code,
        "label": index.data(Roles.LABEL) or "",
        "glyph": source is not None and source.draws(True),
        "kind": source.kind if source is not None else "",
        "secondary": index.data(Roles.SECONDARY) or "",
        "runs": [(str(one[0]), bool(one[1])) for one in (index.data(Roles.RUNS) or [])],
        "lead": bool(delegate.thumbnail),
        "delegate": type(delegate).__name__,
    }


def badges_in(popup) -> int:
    """Badges standing inside the popup. A row is never one of them (rule 9)."""
    return len(popup.findChildren(StatusBadge)) if popup is not None else 0


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(400)
    bad: list = []
    seen: dict = {}
    pickers = by_demo(find)
    if not pickers:
        return {"verdict": "FAIL no status picker on the page"}

    # --- the option set is `valid_values` minus the project's `hidden_values` (probe 009) ---
    for demo, wanted in (("p70", CODES_70), ("p71", CODES_71), ("both", BOTH)):
        picker = pickers.get(demo)
        if picker is None:
            bad.append(f"no {demo} picker")
            continue
        settler(picker, wait)()
        got = tuple(one.code for one in picker.options)
        seen[demo] = list(got)
        if got != wanted:
            bad.append(f"{demo} offers {got}, wanted {wanted}")
    if "pndad" in seen.get("both", []):
        bad.append("the intersection kept a code project 70 hides")

    # --- a selected code outside the option set keeps a row of its own ---
    unknown = pickers.get("unknown")
    if unknown is None:
        bad.append("no unknown-code picker")
    else:
        settler(unknown, wait)()
        rows = [one.code for one in unknown.list_picker.shown]
        seen["unknown_rows"] = rows[-3:]
        if unknown.value != "zz_retired":
            bad.append(f"the unknown code became {unknown.value!r}")
        if "zz_retired" not in rows:
            bad.append("a code outside the option set lost its row")
        if unknown.control.labels != ["zz_retired"]:
            bad.append(f"the control reads {unknown.control.labels}, not the stored code")

    # --- the row is the glyph, the name and the code, and never a badge ---
    picker = pickers.get("p70")
    if picker is not None:
        picker.set_open(True)
        wait(250)
        anatomy = [read_row(picker, code) for code in ("ip", "apr", "vwd")]
        seen["rows"] = anatomy
        for row in anatomy:
            if not row:
                bad.append("a wanted option has no row")
                continue
            if not row["lead"] or not row["glyph"]:
                bad.append(f"{row['code']} draws no status glyph in its leading slot")
            if not row["label"]:
                bad.append(f"{row['code']} has no text label")
        ip = next((one for one in anatomy if one.get("code") == "ip"), {})
        if ip.get("secondary") != "ip":
            bad.append(f"ip reads {ip.get('secondary')!r} as its secondary, not the code")
        if ip.get("label") != "In Progress":
            bad.append(f"ip reads {ip.get('label')!r}, not its display name")
        # The badge is what a status is as a value, so no row holds one.
        held = badges_in(picker.control.popup())
        seen["badges_in_popup"] = held
        if held:
            bad.append(f"{held} badges stand inside the option list")
        glyphs = len(picker.control.popup().findChildren(StatusGlyph))
        if glyphs:
            bad.append(f"{glyphs} glyph widgets stand in the list, which the delegate paints")
        # There is no search row on a single status picker, so the query is put on the model.
        picker.rows_model.set_query("prog")
        wait(60)
        bold = [run for run in read_row(picker, "ip")["runs"] if run[1]]
        seen["matched_runs"] = bold
        if not bold:
            bad.append("no run of In Progress came back matched for 'prog'")
        picker.rows_model.set_query("")
        picker.set_open(False)
        wait(150)

    # --- the value the signal carries is the code, or None (the docs page's promise) ---
    if picker is not None:
        answers: list = []
        picker.value_changed.connect(answers.append)
        picker.set_open(True)
        wait(200)
        at = option_at(picker, "apr")
        picker.control.list_surface().activate(at)
        wait(200)
        seen["picked"] = answers[-1] if answers else None
        if not answers or answers[-1] != "apr":
            bad.append(f"the pick carried {answers[-1] if answers else None!r}, not 'apr'")
        if not isinstance(answers[-1] if answers else None, str):
            bad.append("value_changed carried something other than the code")
        if picker.control.is_open:
            bad.append("a pick left the single picker open")
        chips = picker.control.chips()
        seen["value_chip"] = type(chips[0]).__name__ if chips else ""
        if not chips or not isinstance(chips[0], StatusBadge) or chips[0].code != "apr":
            bad.append("the picked status is not a badge in the control")
        answers.clear()
        picker.control._clear_pressed()
        wait(150)
        seen["cleared"] = answers[-1] if answers else "nothing"
        if not answers or answers[-1] is not None:
            bad.append("the clear control did not carry None")
        # The contract wants a filled control for its value keys, so the value goes back.
        picker.set_open(False)
        picker.set_value("ip")
        wait(120)

    # --- the picker contract, clause by clause ---
    checked: dict = {}
    for demo in ("p70", "no-code", "mandatory"):
        one = pickers.get(demo)
        if one is None:
            bad.append(f"no {demo} picker to check the contract on")
            continue
        shape = PickerShape(
            multiple=False,
            inline=False,
            searchable=False,
            clearable=bool(one.control.clearable),
            settle=settler(one, wait),
        )
        try:
            checked[demo] = check_contract(Bot(), one, shape)
        except AssertionError as error:
            bad.append(f"{demo}: {error}")
    seen["contract"] = {demo: len(done) for demo, done in checked.items()}

    return {
        "verdict": (
            "PASS the status picker offers valid_values minus the project's hidden values, keeps "
            "a row for a code outside the set, draws the glyph, the name and the code with no "
            "badge in a row, carries the code on value_changed and holds every contract clause"
            if not bad
            else "FAIL " + "; ".join(str(one) for one in bad)
        ),
        "seen": seen,
    }
