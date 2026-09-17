"""Several projects by server-side search: the contract, the preset, the row and the payload.

The project half of the upstream picker drives — `picker-contract.js`, `picker-escape.js`,
`picker-backspace.js`, `picker-armed-chip.js`, `multi-picker-fit.js` and `row-anatomy.js` — run
against the ProjectMultiPicker page, plus what is this picker's own:

    contract        rule 7 on both shapes the page draws: the token field and the summary trigger
    payload         `value_changed` carries `(list[EntityRef], list[PickerRow])`, `([], [])` cleared
    preset          `archived` is the discriminator, `sg_status` is not a liveness filter
    include_archived it flips that one condition and leaves the caller's pre-filter standing
    row             the project picture, the name, and `sg_status` as the sub-label
    fit             the narrow summary control draws whole chips, then `+n`

    .venv/bin/python tools/qa.py --page project-multi-picker \\
        --drive tools/drives/project-multi-picker.py
    .venv/bin/python tools/qa.py --page project-multi-picker \\
        --drive tools/drives/project-multi-picker.py --qt5

`sg_status` is a plain list with no Status row behind it and is null on most projects, so the
listing filters on `archived`; `is_template` and `is_demo` are the other discriminators
(018_project_listing). The docs page says the same under API behaviour.

`picker-pick-releases-chip.js` is not walked here: the mock carries three projects and the token
field demo holds all three, so there is no free row to pick. The upstream drive answers the same
way on this page, and `tools/drives/picker-contract.py` walks the clause on the entity pickers.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sg_widgets_core.filter import EntityRef, condition, group, to_api3_hash  # noqa: E402
from sg_widgets_core.picker import PROJECT_PICKER_FIELDS, PickerRow  # noqa: E402
from sg_widgets_core.row import row_thumbnail  # noqa: E402
from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.project_multi_picker import ProjectMultiPicker  # noqa: E402
from tests.qt.test_picker_contract import PickerShape, check_contract  # noqa: E402

#: The mock's latency plus the debounce, with room for the hop back onto the GUI thread.
SETTLE_MS = 1200

#: The role the row delegate reads a tick from.
CHECKED = Roles.CHECKED


class _Bot:
    """What `check_contract` asks of `qtbot`: a wait that turns the driver's own loop."""

    def __init__(self, wait) -> None:
        self._wait = wait

    def wait(self, ms: int = 0) -> None:
        self._wait(ms)

    def addWidget(self, _widget) -> None:  # noqa: N802
        """The page owns every widget here."""

    def waitExposed(self, _widget, timeout: int = 1000) -> None:  # noqa: N802
        self._wait(50)


def demo_of(picker) -> str:
    walk = picker.parentWidget()
    for _ in range(8):
        if walk is None:
            return "page"
        name = walk.property("data_demo") or walk.property("data_demo_case")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def conditions(picker) -> list:
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def live_pickers(find) -> list:
    return [
        picker
        for picker in find(ProjectMultiPicker, all=True)
        if not picker.disabled and not picker.readonly and picker.isVisible()
    ]


def settle_rows(picker, wait, ms: int = 6000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(60)
        if picker.control.list_surface().row_count() > 0:
            return True
    return False


# --- the clauses this picker owns ---------------------------------------------------------


def preset(picker, note) -> dict:
    """`archived` is the listing rule; `sg_status` is read for the row, never filtered on."""
    where = demo_of(picker)
    flat = [one for one in conditions(picker) if isinstance(one, list)]
    paths = [one[0] for one in flat]
    if not picker.include_archived and ["archived", "is", False] not in flat:
        note(f"{where}: the listing does not hide archived projects")
    if "sg_status" in paths:
        # 018_project_listing: `sg_status` is null on most projects, so it is not a liveness
        # filter. `archived`, `is_template` and `is_demo` are the discriminators.
        note(f"{where}: sg_status is filtered on, which 018_project_listing says it is not")
    if picker.entity_types != ["Project"]:
        note(f"{where}: searches {picker.entity_types}, wanted ['Project']")
    for field in PROJECT_PICKER_FIELDS:
        if field not in picker.rows_model.fields:
            note(f"{where}: the preset does not read {field}")
    return {"demo": where, "conditions": flat}


def include_archived_flips(picker, note) -> dict:
    """The keyword flips the one condition and leaves a caller's pre-filter standing."""
    own = group("and", [condition("is_demo", "is", False)])
    held_filters, held_flag = picker.filters, picker.include_archived
    picker.set_filters(own)
    picker.set_include_archived(False)
    hidden = conditions(picker)
    picker.set_include_archived(True)
    shown = conditions(picker)
    if ["archived", "is", False] not in [one for one in hidden if isinstance(one, list)]:
        note("include_archived False drops the archived condition")
    if ["archived", "is", False] in [one for one in shown if isinstance(one, list)]:
        note("include_archived True keeps the archived condition")
    if not any(isinstance(one, dict) for one in shown):
        note("the caller's pre-filter did not survive the flip")
    picker.set_include_archived(held_flag)
    picker.set_filters(held_filters)
    return {"hidden": len(hidden), "shown": len(shown)}


def row_anatomy(picker, wait, note) -> dict:
    """The row is the project picture, the name, and `sg_status` under it."""
    where = demo_of(picker)
    if picker.rows_model.sub_label_field != "sg_status":
        note(f"{where}: the sub-label reads {picker.rows_model.sub_label_field!r}, wanted sg_status")
    if picker.thumbnail != "image":
        note(f"{where}: the thumbnail field is {picker.thumbnail!r}, wanted 'image'")
    if not picker.control.row_delegate().thumbnail:
        note(f"{where}: the row draws no leading picture slot")
    picker.set_open(True)
    if not settle_rows(picker, wait):
        note(f"{where}: the list drew no row to read")
        picker.set_open(False)
        return {}
    rows = list(picker.state.rows)
    without_status = [row.name for row in rows if not row.values.get("sg_status")]
    without_picture = [
        row.name for row in rows if not row_thumbnail(row.values, picker.rows_model.anatomy())
    ]
    types = sorted({row.type for row in rows})
    if without_status:
        note(f"{where}: {without_status} carry no sg_status to draw under the name")
    if without_picture:
        note(f"{where}: {without_picture} carry no picture")
    if types != ["Project"]:
        note(f"{where}: the list offered {types}, wanted ['Project'] alone")
    picker.set_open(False)
    wait(200)
    return {"rows": len(rows), "types": types, "statuses": [r.values.get("sg_status") for r in rows]}


def payload(picker, wait, note) -> dict:
    """`value_changed` carries `(list[EntityRef], list[PickerRow])`, and two empty lists cleared."""
    where = demo_of(picker)
    seen: list = []
    # The contract walk above leaves a value behind, so the count starts from nothing.
    picker.set_value([])
    wait(200)
    picker.value_changed.connect(lambda refs, rows: seen.append((refs, rows)))
    picker.set_open(True)
    if not settle_rows(picker, wait):
        note(f"{where}: no row to tick, so the payload was never read")
        picker.set_open(False)
        return {}
    surface = picker.control.list_surface()
    surface.activate(0)
    wait(400)
    free = next(
        (
            i
            for i in range(surface.row_count())
            if not surface.is_load_more(i) and surface.model().index(i, 0).data(CHECKED) is not True
        ),
        None,
    )
    if free is None:
        note(f"{where}: one tick left no free row to tick beside it")
        picker.set_open(False)
        picker.value_changed.disconnect()
        return {}
    surface.activate(free)
    wait(400)
    if not seen:
        note(f"{where}: two ticks left no value_changed behind")
        picker.value_changed.disconnect()
        return {}
    refs, rows = seen[-1]
    if not isinstance(refs, list) or not all(isinstance(one, EntityRef) for one in refs):
        note(f"{where}: value_changed sent {type(refs).__name__}, wanted list[EntityRef]")
    elif [one.type for one in refs] != ["Project"] * len(refs):
        note(f"{where}: the references read {[one.type for one in refs]}, wanted Project alone")
    elif len(refs) != 2:
        note(f"{where}: two ticks made a value of {len(refs)}, wanted 2 in the order ticked")
    if not isinstance(rows, list) or not all(isinstance(one, PickerRow) for one in rows):
        note(f"{where}: the second argument is not list[PickerRow]")
    elif len(rows) != len(refs):
        note(f"{where}: {len(refs)} references came with {len(rows)} rows")
    if not picker.control.is_open:
        note(f"{where}: a tick closed a multi picker, which clause 6 forbids")
    took = [str(one) for one in refs]
    picker.set_open(False)
    wait(200)

    # A clear sends the pair the docs promise for an empty value.
    picker.control.cleared.emit()
    wait(300)
    refs, rows = seen[-1]
    if refs != [] or rows != []:
        note(f"{where}: a clear sent {refs!r}, {rows!r}, wanted two empty lists")
    if list(picker.value):
        note(f"{where}: the value survived the clear")
    picker.value_changed.disconnect()
    return {"ticked": took, "cleared": [refs, rows]}


def fit(picker, note) -> dict:
    """`multi-picker-fit.js`: whole chips, `+n` for the rest, on one line."""
    control = picker.control
    chips = control.chips()
    shown = [chip for chip in chips if chip.isVisibleTo(control)]
    hidden = [chip for chip in chips if not chip.isVisibleTo(control)]
    pill = control.overflow_pill()
    if not shown:
        note("fit: the narrow control drew no chip at all")
    if shown != chips[: len(shown)]:
        note("fit: the chips drawn are not the leading ones of the row")
    if hidden and not pill.isVisibleTo(control):
        note(f"fit: {len(hidden)} chips hidden with no +n")
    if pill.isVisibleTo(control) and pill.count != len(hidden):
        note(f"fit: the pill reads +{pill.count} for {len(hidden)} hidden")
    if control.height() > 40:
        note(f"fit: the control is {control.height()}px tall, wanted one line")
    return {"shown": len(shown), "hidden": len(hidden), "pill": pill.count, "h": control.height()}


# --- the walk ------------------------------------------------------------------------------


def drive(page, wait, find, prefs) -> dict:
    wait(1200)
    failures: list = []

    def note(detail: str) -> None:
        failures.append(detail)

    pickers = live_pickers(find)
    if not pickers:
        return {"verdict": f"FAIL {page.data_name}: no project multi picker on the page"}

    seen: dict = {"pickers": len(pickers), "clauses": {}}

    # Rule 7 on both shapes the page draws: the inline token field and the summary trigger.
    walked = set()
    for picker in pickers:
        control = picker.control
        shape_key = "tokens" if control.inline else "summary"
        if shape_key in walked:
            continue
        # Clause 4 needs a chip row to walk, so the token field taken is one holding chips.
        if shape_key == "tokens" and len(control.labels) < 2:
            continue
        walked.add(shape_key)
        shape = PickerShape(
            multiple=True,
            inline=control.inline,
            clearable=control.clearable,
            settle=lambda: wait(SETTLE_MS),
        )
        try:
            seen["clauses"][shape_key] = check_contract(_Bot(wait), picker, shape)
        except AssertionError as failure:
            note(f"contract ({shape_key}): {failure}")
            seen["clauses"][shape_key] = []
        control.set_open(False)
        wait(200)

    seen["preset"] = [preset(picker, note) for picker in pickers[:4]]
    archived = next((p for p in pickers if demo_of(p) == "archived"), pickers[0])
    seen["include_archived"] = include_archived_flips(archived, note)
    seen["row"] = row_anatomy(pickers[0], wait, note)
    seen["payload"] = payload(pickers[0], wait, note)

    narrow = next(
        (
            p
            for p in pickers
            if p.control.summary == "ellipsis" and p.control.overflow_pill().count > 0
        ),
        None,
    )
    if narrow is None:
        note("fit: no narrow summary control with chips to hide")
    else:
        seen["fit"] = fit(narrow, note)

    return {
        "verdict": (
            "PASS the project multi picker keeps rule 7, the preset, the row, the payload and the fit"
            if not failures
            else "FAIL " + "; ".join(failures[:10])
        ),
        "failures": failures,
        "seen": seen,
    }
