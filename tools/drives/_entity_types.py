"""What the two entity-type drives share: the combobox walk, the payload and the two sets.

The port of `~/dev/sg-widgets/tools/drives/entity-type-picker-combobox.js`. The upstream drive
runs the same body on both pages, so this module is that body and the two drive files beside it
are the two entry points.

Beside the upstream clauses it checks what the docs pages promise and the upstream drive does
not: the shape of the `value_changed` payload, and that `allow` and `deny` narrow the derived
options rather than the read, `deny` winning where both name a type.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.entity_type_picker import EntityTypePicker  # noqa: E402
from tests.qt.test_picker_contract import (  # noqa: E402
    CLAUSES,
    PickerShape,
    check_contract,
    press_control,
)

__all__ = ["combobox", "pickers_of"]

#: The mock's latency, with room for the hop back onto the GUI thread.
SETTLE_MS = 600

#: The query the upstream drive narrows with, and the type it must still offer.
QUERY = "ver"
WANTED = "Version"


class _Bot:
    """What `check_contract` asks of `qtbot`: a wait that turns the driver's own loop."""

    def __init__(self, wait) -> None:
        self._wait = wait

    def wait(self, ms: int = 0) -> None:
        self._wait(ms)

    def addWidget(self, _widget) -> None:  # noqa: N802
        """The page owns every widget here; nothing is handed to the bot to keep."""

    def waitExposed(self, _widget, timeout: int = 1000) -> None:  # noqa: N802
        self._wait(50)


def pickers_of(find) -> list:
    """Every entity-type picker the page draws, the multi picker included."""
    return [one for one in find(EntityTypePicker, all=True) if one.isVisible()]


def demo_of(picker) -> str:
    """The demo case a picker sits in, so a failure names something a reader can find."""
    walk = picker.parentWidget()
    for _ in range(6):
        if walk is None:
            return "page"
        name = walk.property("data_demo_case") or walk.property("data_demo")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def wait_for(read, wait, ms: int = 6000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def live_ones(pickers: list) -> list:
    """Those a reader can work: not readonly, not disabled."""
    return [one for one in pickers if not one.readonly and not one.disabled]


def runs_bold(model, query: str) -> int:
    """Rows whose label carries a matched run, which is what is drawn in DemiBold."""
    found = 0
    for row in range(model.rowCount()):
        runs = model.index(row, 0).data(Roles.RUNS) or []
        if any(bool(run[1]) for run in runs):
            found += 1
    return found


# --- the clauses ---------------------------------------------------------------------------


def contract(pickers: list, wait, note) -> list:
    """Rule 7, every clause, once per shape the page draws."""
    walked: list = []
    done = set()
    bot = _Bot(wait)
    for picker in pickers:
        control = picker.control
        where = demo_of(picker)
        if picker.readonly or picker.disabled:
            if picker.readonly and control.disabled_opacity() != 1.0:
                note("readonly", f"{where}: drawn at less than full contrast")
            if picker.readonly and control.open_control().isVisibleTo(control):
                note("readonly", f"{where}: keeps its chevron")
            if picker.disabled and control.disabled_opacity() != 0.5:
                note("disabled", f"{where}: not at half opacity")
            press_control(control)
            wait(150)
            if control.is_open:
                note("readonly" if picker.readonly else "disabled", f"{where}: opened its list")
                control.set_open(False)
            walked.append({"demo": where, "ran": "readonly" if picker.readonly else "disabled"})
            continue
        key = f"{control.multiple}|{control.inline}|{control.clearable}"
        if key in done:
            continue
        done.add(key)
        shape = PickerShape(
            multiple=control.multiple,
            inline=control.inline,
            searchable=True,
            clearable=control.clearable,
            settle=lambda: wait(SETTLE_MS),
        )
        try:
            checked = check_contract(bot, picker, shape)
        except AssertionError as failure:
            note("contract", f"{where}: {failure}")
            checked = []
        except Exception as failure:  # noqa: BLE001
            note("contract", f"{where}: {type(failure).__name__}: {failure}")
            checked = []
        missed = [
            clause for clause in CLAUSES if clause not in checked and clause != "value keys"
        ]
        if missed:
            note("contract", f"{where}: never reached {missed}")
        walked.append({"demo": where, "shape": key, "clauses": checked})
        control.set_open(False)
        wait(120)
    return walked


def combobox_walk(picker, wait, note) -> dict:  # noqa: C901
    """`entity-type-picker-combobox.js`: open from the field, narrow, pick, tick, close."""
    control = picker.control
    caret = control.caret()
    seen: dict = {}

    press_control(control)
    wait(SETTLE_MS)
    if not control.is_open:
        note("combobox", "a press on the field did not open the list")
        return seen
    if not wait_for(lambda: control.list_surface().row_count() > 0, wait):
        note("combobox", "the list opened with no row")
        return seen
    every = list(control.items)
    seen["types"] = len(every)

    caret.setFocus()
    QTest.keyClicks(caret, QUERY)
    wait(SETTLE_MS)
    narrowed = list(control.items)
    seen["narrowed"] = narrowed
    if not narrowed:
        note("combobox", f'"{QUERY}" narrowed every one of {len(every)} types away')
    elif len(narrowed) >= len(every):
        note("combobox", f'"{QUERY}" narrowed nothing out of {len(every)} types')
    if WANTED not in narrowed:
        note("combobox", f'"{QUERY}" did not offer {WANTED}')
    model = control.list_surface().source_model()
    bold = runs_bold(model, QUERY)
    seen["bold"] = bold
    if bold == 0:
        note("combobox", "no row drew a matched run for the query")

    # The leading mark and the trailing indicator, which is rule 9's row anatomy.
    first = model.index(0, 0)
    seen["glyph"] = first.data(Roles.GLYPH) or ""
    if not seen["glyph"]:
        note("row", "a row carries no type glyph in its leading slot")
    wanted_indicator = "checkbox" if control.multiple else "tick"
    if control.row_delegate().indicator != wanted_indicator:
        note("row", f"the rows draw a {control.row_delegate().indicator}, wanted {wanted_indicator}")

    row = next(
        (i for i in range(control.list_surface().row_count()) if control.items[i] == WANTED),
        0,
    )
    before = list(control.keys)
    control.list_surface().activate(row)
    wait(SETTLE_MS)
    seen["picked"] = list(control.keys)
    if list(control.keys) == before:
        note("combobox", "the pick changed nothing")
    if WANTED not in control.keys:
        note("combobox", f"the pick did not take {WANTED}")
    if control.is_open is not bool(control.multiple):
        note("combobox", "a pick closes a single picker and keeps a multi one open")

    # The tick, or the ticked checkbox, on the chosen row.
    chosen = next(
        (
            i
            for i in range(model.rowCount())
            if model.index(i, 0).data(Roles.LABEL) == picker.label_of(WANTED)
        ),
        None,
    )
    if chosen is None:
        note("row", f"{WANTED} left the list once it was chosen")
    elif model.index(chosen, 0).data(Roles.CHECKED) is not True:
        note("row", f"the chosen row draws no {wanted_indicator}")

    if not control.is_open:
        press_control(control)
        wait(SETTLE_MS)
    QTest.keyClick(control.caret(), Qt.Key.Key_Escape)
    wait(SETTLE_MS)
    if control.is_open:
        note("combobox", "Escape did not close the list")
        control.set_open(False)
    if control.query:
        note("combobox", f"the query still reads {control.query!r} after Escape")
    return seen


def payload(picker, wait, note, multiple: bool) -> dict:
    """The `value_changed` payload, exactly as the docs page promises it."""
    control = picker.control
    answers: list = []

    def took_one(value) -> None:
        answers.append(value)

    picker.value_changed.connect(took_one)
    try:
        control.set_open(True)
        if not wait_for(lambda: control.list_surface().row_count() > 0, wait):
            note("payload", "the list drew no row to pick")
            return {}
        control.list_surface().activate(0)
        wait(SETTLE_MS)
        control.set_open(False)
        wait(120)
        if not answers:
            note("payload", "a pick emitted no value_changed")
            return {}
        took = answers[-1]
        if multiple:
            if not isinstance(took, list) or not all(isinstance(one, str) for one in took):
                note("payload", f"a pick emitted {took!r}, wanted list[str]")
        elif not isinstance(took, str):
            note("payload", f"a pick emitted {took!r}, wanted str")

        picker.set_clearable(True)
        control.cleared.emit()
        wait(200)
        cleared = answers[-1]
        if multiple:
            if cleared != []:
                note("payload", f"a clear emitted {cleared!r}, wanted []")
        elif cleared is not None:
            note("payload", f"a clear emitted {cleared!r}, wanted None")
        return {"picked": took, "cleared": cleared, "emits": len(answers)}
    finally:
        picker.value_changed.disconnect(took_one)


def sets(page, picker, wait, note) -> dict:
    """`allow` and `deny` narrow the DERIVED options, `deny` winning, with no second read."""
    context = page.context
    reads = context.reads if context is not None else {}
    before = reads.get("entity_types", 0)
    if before != 1:
        note("sets", f"the page cost {before} schema reads, wanted one for every picker")
    held = (picker.allow, picker.deny)
    seen: dict = {"reads_before": before}
    try:
        picker.set_allow(["Shot", "Asset", "Task"])
        picker.set_deny(None)
        wait(120)
        allowed = [one.name for one in picker.types]
        seen["allow"] = allowed
        if sorted(allowed) != ["Asset", "Shot", "Task"]:
            note("sets", f"allow offered {allowed}, wanted Asset, Shot and Task")

        picker.set_deny(["Asset"])
        wait(120)
        denied = [one.name for one in picker.types]
        seen["deny_wins"] = denied
        if "Asset" in denied:
            note("sets", "deny did not win over allow where both name a type")
        if "Shot" not in denied:
            note("sets", "deny took a type neither set named")

        picker.set_allow(None)
        picker.set_deny(None)
        wait(120)
        every = [one.name for one in picker.types]
        seen["every"] = len(every)
        if len(every) <= len(allowed):
            note("sets", f"dropping both sets offered {len(every)} types, wanted more than 3")

        after = reads.get("entity_types", 0)
        seen["reads_after"] = after
        if after != before:
            note("sets", f"switching the sets cost {after - before} further schema reads")
    finally:
        picker.set_allow(held[0])
        picker.set_deny(held[1])
        wait(120)
    return seen


# --- the walk ------------------------------------------------------------------------------


def combobox(page, wait, find, prefs, multiple: bool) -> dict:
    """Every clause of the upstream drive, plus the payload and the two sets."""
    wait(500)
    failures: list = []

    def note(clause: str, detail: str) -> None:
        failures.append(f"{page.data_name}: {clause} — {detail}")

    pickers = pickers_of(find)
    if not pickers:
        return {"verdict": f"FAIL {page.data_name}: no entity-type picker on the page"}
    if any(one.control.multiple is not multiple for one in pickers) and not multiple:
        note("page", "a multi picker stands on the single picker's page")

    seen: dict = {"pickers": len(pickers)}
    seen["walked"] = contract(pickers, wait, note)

    live = live_ones(pickers)
    if not live:
        note("page", "every picker on the page is readonly or disabled")
        return {"verdict": "FAIL " + "; ".join(failures), "failures": failures, "seen": seen}

    field = next((one for one in live if one.control.inline), live[0])
    seen["combobox"] = combobox_walk(field, wait, note)
    seen["payload"] = payload(live[0], wait, note, multiple)
    seen["sets"] = sets(page, live[0], wait, note)

    for one in live:
        one.control.set_open(False)
    wait(150)
    return {
        "verdict": (
            f"PASS the field opens the list, the query narrows it, the payload and the two "
            f"sets hold on {page.data_name}"
            if not failures
            else "FAIL " + "; ".join(failures[:10])
        ),
        "failures": failures,
        "seen": seen,
    }
