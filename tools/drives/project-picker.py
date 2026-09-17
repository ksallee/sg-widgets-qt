"""One project by server-side search: the contract, the preset, the row and the payload.

The project half of the upstream picker drives — `picker-contract.js`, `picker-escape.js`,
`picker-backspace.js`, `picker-mandatory-clear.js`, `picker-arrow-scroll.js` and `row-anatomy.js`
— run against the ProjectPicker page, plus what is this picker's own and nobody else's:

    contract        rule 7, every clause, through `tests/qt/test_picker_contract.check_contract`
    payload         `value_changed` carries `(EntityRef, PickerRow)`, and `(None, None)` on a clear
    preset          `archived` is the discriminator, `sg_status` is not a liveness filter
    include_archived it flips that one condition and leaves the caller's pre-filter standing
    row             the project picture, the name, and `sg_status` as the sub-label
    types           only Project is searched

    .venv/bin/python tools/qa.py --page project-picker --drive tools/drives/project-picker.py
    .venv/bin/python tools/qa.py --page project-picker --drive tools/drives/project-picker.py --qt5

`sg_status` is a plain list with no Status row behind it and is null on most projects, so the
listing filters on `archived`; `is_template` and `is_demo` are the other discriminators
(018_project_listing). The docs page says the same under API behaviour.
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
from sg_widgets_qt.widgets.project_picker import ProjectPicker  # noqa: E402
from tests.qt.test_picker_contract import PickerShape, check_contract  # noqa: E402

#: The mock's latency plus the debounce, with room for the hop back onto the GUI thread.
SETTLE_MS = 1200

#: The three discriminators a project listing goes by (018_project_listing).
DISCRIMINATORS = ("archived", "is_template", "is_demo")


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
    """The wire conditions the picker's own filter carries."""
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def live_pickers(find) -> list:
    return [
        picker
        for picker in find(ProjectPicker, all=True)
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
    wire = conditions(picker)
    flat = [one for one in wire if isinstance(one, list)]
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
    return {"demo": where, "conditions": flat, "fields": list(picker.rows_model.fields)}


def include_archived_flips(picker, note) -> dict:
    """The keyword flips the one condition and leaves a caller's pre-filter standing."""
    own = group("and", [condition("is_template", "is", False)])
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
    if picker.filters is not own:
        note("the picker forgot the caller's own filter group")
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
    """`value_changed` carries `(EntityRef, PickerRow)`, and `(None, None)` on a clear."""
    where = demo_of(picker)
    seen: list = []
    picker.value_changed.connect(lambda ref, row: seen.append((ref, row)))
    picker.set_open(True)
    if not settle_rows(picker, wait):
        note(f"{where}: no row to pick, so the payload was never read")
        picker.set_open(False)
        return {}
    picker.control.list_surface().activate(0)
    wait(400)
    if not seen:
        note(f"{where}: a pick left no value_changed behind")
        return {}
    ref, row = seen[-1]
    if not isinstance(ref, EntityRef):
        note(f"{where}: value_changed sent {type(ref).__name__}, wanted EntityRef")
    elif ref.type != "Project" or not isinstance(ref.id, int) or not ref.name:
        note(f"{where}: the reference reads {ref}, wanted a named Project reference")
    if not isinstance(row, PickerRow):
        note(f"{where}: the second argument is {type(row).__name__}, wanted PickerRow")
    if picker.control.is_open:
        note(f"{where}: a pick left a single picker open")
    took = str(ref)

    # A clear sends the pair the docs promise for an empty value, the way the clear control does.
    picker.control.cleared.emit()
    wait(300)
    ref, row = seen[-1]
    if ref is not None or row is not None:
        note(f"{where}: a clear sent {ref!r}, {row!r}, wanted None, None")
    if picker.value is not None:
        note(f"{where}: the value survived the clear")
    picker.value_changed.disconnect()
    return {"picked": took, "cleared": [ref, row]}


# --- the walk ------------------------------------------------------------------------------


def drive(page, wait, find, prefs) -> dict:
    wait(1200)
    failures: list = []

    def note(detail: str) -> None:
        failures.append(detail)

    pickers = live_pickers(find)
    if not pickers:
        return {"verdict": f"FAIL {page.data_name}: no project picker on the page"}

    seen: dict = {"pickers": len(pickers)}
    first = pickers[0]

    # Rule 7, every clause, on the shape this page comes in.
    shape = PickerShape(
        multiple=False,
        inline=True,
        clearable=first.control.clearable,
        settle=lambda: wait(SETTLE_MS),
    )
    try:
        seen["clauses"] = check_contract(_Bot(wait), first, shape)
    except AssertionError as failure:
        note(f"contract: {failure}")
        seen["clauses"] = []
    first.control.set_open(False)
    wait(200)

    seen["preset"] = [preset(picker, note) for picker in pickers]
    archived = next((p for p in pickers if demo_of(p) == "archived"), first)
    seen["include_archived"] = include_archived_flips(archived, note)
    seen["row"] = row_anatomy(first, wait, note)
    seen["payload"] = payload(first, wait, note)

    return {
        "verdict": (
            "PASS the project picker keeps rule 7, the project preset, the row and the payload"
            if not failures
            else "FAIL " + "; ".join(failures[:10])
        ),
        "failures": failures,
        "seen": seen,
    }
