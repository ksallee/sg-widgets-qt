"""status-multi-picker: the contract, the option set, the row anatomy and the closed trigger.

The port of `~/dev/sg-widgets/tools/drives/status-multi-picker-summary.js`, with the row half of
`status-picker-rows.js` that belongs to the multi picker. Upstream counts the badges the DOM
leaves on show; here the chips are widgets the control lays out, so the same question is which
of them the control made visible and what its `+n` pill counts.

The codes below are the mock's own (`src/sg_widgets_core/mock.py`, `HIDDEN_VALUES`), which is
`valid_values` minus each project's `hidden_values` (probe 009_status_lists).

    .venv/bin/python tools/qa.py --page status-multi-picker --drive tools/drives/status-multi-picker.py
    .venv/bin/python tools/qa.py --page status-multi-picker --drive tools/drives/status-multi-picker.py --qt5
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.status_badge import StatusBadge  # noqa: E402
from sg_widgets_qt.widgets.status_multi_picker import StatusMultiPicker  # noqa: E402
from sg_widgets_qt.widgets.status_picker import StatusLeadDelegate  # noqa: E402
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

#: The control's own step, which `ellipsis` never grows past because it never wraps.
MD_HEIGHT = 32


class Bot:
    """What `check_contract` wants of pytest-qt: a loop it can turn."""

    def wait(self, ms: int) -> None:
        QApplication.processEvents()


def demo_of(widget) -> str:
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
    return {
        demo_of(one): one for one in (find(StatusMultiPicker, all=True) or []) if demo_of(one)
    }


def settler(picker, wait):
    def settle() -> None:
        for _ in range(40):
            wait(25)
            if not picker.load.loading:
                return

    return settle


def painter_of(picker):
    """The delegate the list actually paints with.

    `ListSurface.row_delegate()` answers the one it was built with rather than the one
    `set_row_delegate` handed the view, so the anatomy is read off the view itself.
    """
    return picker.control.list_surface().itemDelegate()


def option_at(picker, code: str) -> int:
    model = picker.rows_model
    for row in range(model.rowCount()):
        option = model.index(row, 0).data(Roles.ENTITY)
        if getattr(option, "code", None) == code:
            return row
    return -1


def read_row(picker, code: str) -> dict:
    """What one option row is made of, as the anatomy of rule 9, after its checkbox."""
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
        "secondary": index.data(Roles.SECONDARY) or "",
        "checkbox": delegate.indicator == "checkbox",
        "checked": index.data(Roles.CHECKED),
        "runs": [(str(one[0]), bool(one[1])) for one in (index.data(Roles.RUNS) or [])],
    }


def shown_badges(picker) -> list:
    """The badges the control left on show. The ones past the fit stay, hidden."""
    control = picker.control
    return [
        chip
        for chip in control.chips()
        if isinstance(chip, StatusBadge) and not chip.isHidden()
    ]


def summary_of(picker) -> dict:
    control = picker.control
    badges = shown_badges(picker)
    return {
        "badges": len(badges),
        "hidden": len(control.chips()) - len(badges),
        # `count` hides the pill and keeps its number, so what it reads is what it shows.
        "overflow": ""
        if control.overflow_pill().isHidden()
        else f"+{control.overflow_pill().count}",
        "count_label": control._count_label or "",
        # The cross a badge draws, not the one it was asked for: the icon variant has no room.
        "removes": sum(1 for badge in badges if badge._shows_remove()),
        "names": [badge.status_text for badge in badges],
        "height": control.height(),
    }


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(400)
    bad: list = []
    seen: dict = {}
    pickers = by_demo(find)
    if not pickers:
        return {"verdict": "FAIL no status multi picker on the page"}
    for one in pickers.values():
        settler(one, wait)()
    wait(200)

    # --- the option set is `valid_values` minus the project's `hidden_values` (probe 009) ---
    for demo, wanted in (("p70", CODES_70), ("p71", CODES_71), ("both", BOTH)):
        picker = pickers.get(demo)
        if picker is None:
            bad.append(f"no {demo} picker")
            continue
        got = tuple(option.code for option in picker.options)
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
        rows = [option.code for option in unknown.list_picker.shown]
        seen["unknown_rows"] = rows[-3:]
        if unknown.value != ["zz_retired", "rev"]:
            bad.append(f"the selection became {unknown.value}")
        if "zz_retired" not in rows:
            bad.append("a code outside the option set lost its row")

    # --- the row is the checkbox, the glyph, the name and the code, and never a badge ---
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
            if not row["glyph"]:
                bad.append(f"{row['code']} draws no status glyph in its leading slot")
            if not row["checkbox"]:
                bad.append(f"{row['code']} lost its checkbox")
            if not row["label"]:
                bad.append(f"{row['code']} has no text label")
        ip = next((one for one in anatomy if one.get("code") == "ip"), {})
        if ip.get("secondary") != "ip":
            bad.append(f"ip reads {ip.get('secondary')!r} as its secondary, not the code")
        if ip.get("checked") is not True:
            bad.append("the held code is not ticked in the list")
        held = len(picker.control.popup().findChildren(StatusBadge))
        seen["badges_in_popup"] = held
        if held:
            bad.append(f"{held} badges stand inside the option list")

        # The search box narrows the vocabulary here and the matched runs come back bold.
        picker.control.set_query("prog")
        wait(150)
        shown = [option.code for option in picker.list_picker.shown]
        seen["query_rows"] = shown
        if shown != ["ip"]:
            bad.append(f"the query 'prog' left {shown}, wanted ['ip']")
        bold = [run for run in read_row(picker, "ip").get("runs", []) if run[1]]
        seen["matched_runs"] = bold
        if not bold:
            bad.append("no run of In Progress came back matched for 'prog'")
        picker.control.set_query("")
        wait(100)

        # --- the value the signal carries is the whole list, and a pick keeps the list open ---
        answers: list = []
        picker.value_changed.connect(answers.append)
        before = list(picker.value)
        at = option_at(picker, "rev")
        picker.control.list_surface().activate(at)
        wait(200)
        seen["picked"] = answers[-1] if answers else None
        if not answers or not isinstance(answers[-1], list):
            bad.append("value_changed carried something other than the whole list")
        elif answers[-1] != [*before, "rev"]:
            bad.append(f"the pick carried {answers[-1]}, not {[*before, 'rev']}")
        if not picker.control.is_open:
            bad.append("a pick closed the multi picker")
        answers.clear()
        picker.control._clear_pressed()
        wait(150)
        seen["cleared"] = answers[-1] if answers else "nothing"
        if not answers or answers[-1] != []:
            bad.append("the clear control did not carry the empty list")
        picker.set_open(False)
        picker.set_value(before)
        wait(120)

    # --- what the closed trigger shows ---
    wanted = {
        "summary-chips-2": {"badges": 2, "overflow": ""},
        "summary-chips-5": {"badges": 5, "overflow": ""},
        "summary-count-5": {"badges": 0, "count_label": "5 selected", "overflow": ""},
        "max-one": {"badges": 1, "overflow": "+1"},
        "badge-icon-5": {"badges": 5, "removes": 0},
        "badge-text-2": {"names": ["In Progress", "Approved"]},
    }
    for demo, asked in wanted.items():
        one = pickers.get(demo)
        if one is None:
            bad.append(f"no {demo} picker")
            continue
        got = summary_of(one)
        seen[demo] = got
        for key, value in asked.items():
            if got[key] != value:
                bad.append(f"{demo}: {key} reads {got[key]!r}, wanted {value!r}")

    ellipsis = pickers.get("summary-ellipsis-narrow")
    if ellipsis is None:
        bad.append("no narrow ellipsis picker")
    else:
        got = summary_of(ellipsis)
        seen["summary-ellipsis-narrow"] = got
        if got["badges"] + got["hidden"] != 5:
            bad.append(f"ellipsis holds {got['badges'] + got['hidden']} badges, wanted 5")
        if got["badges"] == 0:
            bad.append("ellipsis drew no badge at all")
        if got["overflow"] != (f"+{got['hidden']}" if got["hidden"] else ""):
            bad.append(f"ellipsis read {got['overflow']!r} for {got['hidden']} hidden")
        # `ellipsis` never wraps, so it is never taller than the control's own step.
        if got["height"] != MD_HEIGHT:
            bad.append(f"the narrow ellipsis control is {got['height']}px tall, wanted {MD_HEIGHT}")

    # --- the picker contract, on the trigger and on the token field ---
    checked: dict = {}
    for demo, inline in (("p70", False), ("summary-chips-2", True)):
        one = pickers.get(demo)
        if one is None:
            bad.append(f"no {demo} picker to check the contract on")
            continue
        shape = PickerShape(
            multiple=True,
            inline=inline,
            searchable=True,
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
            "PASS the status multi picker offers valid_values minus the project's hidden values, "
            "keeps a row for a code outside the set, draws the checkbox, the glyph, the name and "
            "the code with no badge in a row and the matched runs bold, carries the whole list on "
            "value_changed, shows every badge under chips, whole badges and a matching +n under "
            "ellipsis, '5 selected' under count, and holds every contract clause"
            if not bad
            else "FAIL " + "; ".join(str(one) for one in bad)
        ),
        "seen": seen,
    }
