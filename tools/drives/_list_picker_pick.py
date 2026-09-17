"""What `list-picker.py` and `list-multi-picker.py` share: the press cycle and the promises.

The port of `~/dev/sg-widgets/tools/drives/list-picker-pick.js`. Upstream reads both pickers in
one run by loading the multi page into a same-origin iframe; a page here is a window of its own,
so the two halves are two drives over this one module.

Order matters: the promises are read first and the contract walk last, because clause 4 clears a
single picker's value and clauses 9 and 10 leave the control readonly and disabled on the way.
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QWidget

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402
from sg_widgets_qt.widgets.list_multi_picker import ListMultiPicker  # noqa: E402
from sg_widgets_qt.widgets.list_picker import ListPicker  # noqa: E402
from tests.qt.test_picker_contract import (  # noqa: E402
    PickerShape,
    check_contract,
    press_control,
)

__all__ = ["run_multi", "run_single"]

#: What each demo picks, and the label that must land in the control. The upstream twin's table.
SINGLE = (
    ("values", "Type C", "Type C"),
    ("labels", "Full CG", "Full CG"),
    ("project", "VFX", "VFX"),
    ("searchable", "2D", "Two D"),
)
#: What each demo picks, and how many chips the control must then hold.
MULTI = (
    ("values", "Type B", 2),
    ("labels", "Full CG", 3),
    ("project", "VFX", 2),
    ("searchable", "2D", 1),
)

#: The vocabulary is fixed, so nothing is ever in flight: a turn of the loop is enough.
SETTLE_MS = 120


class _Bot:
    """What `check_contract` asks of `qtbot`: a wait that turns the driver's own loop."""

    def __init__(self, wait) -> None:
        self._wait = wait

    def wait(self, ms: int = 0) -> None:
        self._wait(ms)

    def addWidget(self, _widget: QWidget) -> None:  # noqa: N802
        """The page owns every widget here; nothing is handed to the bot to keep."""

    def waitExposed(self, _widget: QWidget, timeout: int = 1000) -> None:  # noqa: N802
        self._wait(50)


def demo_of(picker: ListPicker) -> str:
    """The demo case a picker sits in, so a failure names something a reader can find."""
    walk = picker.parentWidget()
    for _ in range(6):
        if walk is None:
            return "page"
        name = walk.property("data_demo")
        if name:
            return str(name)
        walk = walk.parentWidget()
    return "page"


def pickers_of(find) -> dict:
    """Every list picker on the page, by the demo case it sits in."""
    return {demo_of(one): one for one in find(ListPicker, all=True) if one.isVisible()}


def rows_open(control, wait, ms: int = 2000) -> bool:
    """Turn the loop until the list has a row to press, or give up."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(40)
        if control.list_surface().row_count() > 0:
            return True
    return False


def click_row(control, row: int) -> None:
    """A press on a row, where a reader's pointer would land on it."""
    surface = control.list_surface()
    index = surface.model().index(row, 0)
    surface.scrollTo(index)
    QTest.mouseClick(
        surface.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        surface.visualRect(index).center(),
    )


def row_of(picker: ListPicker, code: str) -> int:
    """Where a value sits in the list on show, or -1."""
    shown = [one.code for one in picker.shown]
    return shown.index(code) if code in shown else -1


def label_at(picker: ListPicker, row: int) -> str:
    """What the row draws as its main text."""
    return picker.rows_model.index(row, 0).data(Roles.LABEL)


def cycle(picker: ListPicker, code: str, note, where: str, wait) -> dict:
    """Open with one press, take a row, and close with one more (the upstream cycle)."""
    control = picker.control
    seen: dict = {"demo": where}
    if control.is_open:
        control.set_open(False)
        wait(SETTLE_MS)

    press_control(control)
    wait(SETTLE_MS)
    if not control.is_open or not rows_open(control, wait):
        note(f"{where}: one press did not open the list")
        return seen
    seen["opened"] = True

    row = row_of(picker, code)
    if row < 0:
        note(f"{where}: no row for {code} among {len(picker.shown)}")
        control.set_open(False)
        return seen
    seen["row_label"] = label_at(picker, row)
    click_row(control, row)
    wait(SETTLE_MS)
    seen["value"] = picker.value
    seen["labels"] = list(control.labels)
    seen["chips"] = len([chip for chip in control.chips() if chip.isVisibleTo(control)])

    # A single picker closes on the pick, so it is reopened before the closing press.
    if not control.is_open:
        seen["reopened"] = True
        press_control(control)
        wait(SETTLE_MS)
        if not control.is_open:
            note(f"{where}: one press did not reopen the list")
            return seen
    press_control(control)
    wait(SETTLE_MS)
    seen["closed"] = not control.is_open
    if control.is_open:
        note(f"{where}: one press did not close the list")
        control.set_open(False)
    return seen


def disabled_opens_for_nobody(found: dict, note, wait) -> bool:
    """The demo the page draws disabled takes a press and stays shut."""
    picker = found.get("disabled")
    if picker is None:
        note("no disabled demo on the page")
        return False
    control = picker.control
    press_control(control)
    wait(SETTLE_MS)
    if control.is_open:
        note("the disabled picker opened")
        control.set_open(False)
        return False
    if control.disabled_opacity() != 0.5:
        note("the disabled picker is not at half opacity")
    return True


def display_values(picker: ListPicker, note, where: str) -> dict:
    """The row and the control read the label; the value stays the raw string.

    A write outside `valid_values` is a 400 and the comparison is case-sensitive, so the label a
    reader sees is never what a write sends (field_types/list).
    """
    row = row_of(picker, "2D")
    if row < 0:
        note(f"{where}: the display-values demo offers no 2D")
        return {}
    seen = {
        "row_label": label_at(picker, row),
        "row_secondary": picker.rows_model.index(row, 0).data(Roles.SECONDARY),
        "label_of": picker.label_of("2D"),
        "codes": [one.code for one in picker.shown],
    }
    if seen["row_label"] != "Two D":
        note(f"{where}: the row reads {seen['row_label']!r}, not the display value 'Two D'")
    if seen["label_of"] != "Two D":
        note(f"{where}: the control would read {seen['label_of']!r}, not 'Two D'")
    # Byte for byte and case-sensitive: the value is the raw valid value, never the label.
    if "2D" not in seen["codes"]:
        note(f"{where}: the raw value '2D' is not among the codes on offer")
    if "Two D" in seen["codes"] or "2d" in seen["codes"]:
        note(f"{where}: a label or a lowercased value reached the vocabulary")
    return seen


def project_rows(picker: ListPicker, note, where: str) -> dict:
    """A project id subtracts the field's hidden values (probe 009)."""
    codes = [one.code for one in picker.options]
    seen = {"codes": codes, "project_id": picker.project_id}
    hidden = list(getattr(picker.field, "hidden_values", None) or [])
    valid = list(getattr(picker.field, "valid_values", None) or [])
    seen["hidden"] = hidden
    if picker.project_id is None:
        note(f"{where}: the scoped demo carries no project id")
        return seen
    wanted = [code for code in valid if code not in hidden]
    if codes != wanted:
        note(f"{where}: the offered set is {codes}, wanted {wanted}")
    for code in hidden:
        if code in codes:
            note(f"{where}: the hidden value {code!r} is still offered")

    # A stored value outside the offered set is legal, so it keeps a row of its own (probe 009).
    held = picker.value if picker.MULTIPLE else picker.value
    outside = hidden[0] if hidden else None
    if outside is None:
        return seen
    picker.set_value([outside] if picker.MULTIPLE else outside)
    shown = [one.code for one in picker.shown]
    seen["with_outside"] = shown
    seen["outside_label"] = picker.label_of(outside)
    if outside not in shown:
        note(f"{where}: the stored value {outside!r} outside the set kept no row")
    if list(picker.control.labels) != [outside]:
        note(f"{where}: the control reads {picker.control.labels}, not [{outside!r}]")
    picker.set_value(held)
    return seen


def payload(picker: ListPicker, note, where: str, multiple: bool, wait) -> dict:
    """What `value_changed` carries, against the shape the docs page promises."""
    control = picker.control
    seen: list = []
    before = picker.value

    def took(value) -> None:
        seen.append(value)

    picker.value_changed.connect(took)
    try:
        control.set_open(True)
        if not rows_open(control, wait):
            note(f"{where}: the list drew no row to take")
            return {}
        # A pick of the value already held changes nothing, so the drive takes another row.
        held = picker.value if picker.MULTIPLE else [picker.value]
        row = next(
            (
                index
                for index, one in enumerate(picker.shown)
                if one.code not in (held or [])
            ),
            0,
        )
        click_row(control, row)
        wait(SETTLE_MS)
        control.set_open(False)
        wait(SETTLE_MS)
        clear = control.clear_control()
        if not clear.isVisibleTo(control):
            note(f"{where}: a filled control draws no clear")
            return {"payloads": [repr(one) for one in seen]}
        QTest.mouseClick(
            clear,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            clear.rect().center(),
        )
        wait(SETTLE_MS)
    finally:
        picker.value_changed.disconnect(took)
        # The cycle below reads this demo too, so it is handed back what it started with.
        picker.set_value(before)
    out = {"payloads": [repr(one) for one in seen]}
    if len(seen) != 2:
        note(f"{where}: a pick and a clear emitted {len(seen)} payloads, wanted 2")
        return out
    chose, cleared = seen
    if multiple:
        if not isinstance(chose, list) or not all(isinstance(one, str) for one in chose):
            note(f"{where}: a pick carried {chose!r}, not a list of strings")
        if cleared != []:
            note(f"{where}: the clear carried {cleared!r}, not the empty list")
    else:
        if not isinstance(chose, str):
            note(f"{where}: a pick carried {chose!r}, not the chosen string")
        if cleared is not None:
            note(f"{where}: the clear carried {cleared!r}, not None")
    return out


def alias(note, multiple: bool) -> dict:
    """The deprecated module re-exports the same class and adds nothing of its own."""
    if multiple:
        from sg_widgets_qt.widgets import list_multi_select as module

        wanted, name = ListMultiPicker, "ListMultiSelect"
    else:
        from sg_widgets_qt.widgets import list_select as module

        wanted, name = ListPicker, "ListSelect"
    got = getattr(module, name, None)
    if got is not wanted:
        note(f"{module.__name__}: {name} is not the picker class")
    own = sorted(
        key
        for key, value in vars(module).items()
        if not key.startswith("_") and key not in ("annotations",) and not isinstance(value, type(sys))
    )
    from_picker = sorted(module.__all__)
    if own != from_picker:
        note(f"{module.__name__}: it carries {own} beside its re-exports {from_picker}")
    return {"module": module.__name__, "exports": from_picker}


def walk_contract(found: dict, note, wait, multiple: bool) -> dict:
    """The ten clauses of rule 7, on every demo the page does not draw inert.

    Clause 4 walks the chip row with the arrows, so a multi picker is given two values first
    where the demo holds fewer: `ArrowRight` past the last chip gives the caret back, and a row
    of one chip has no walk to check. What the demo held is handed back afterwards.
    """
    bot = _Bot(wait)
    out: dict = {}
    for where, picker in found.items():
        control = picker.control
        if control.disabled or control.readonly:
            continue
        held = picker.value
        if multiple and len(control.labels) < 2:
            picker.set_value([one.code for one in picker.options[:2]])
            wait(SETTLE_MS)
        control.set_open(False)
        wait(SETTLE_MS)
        shape = PickerShape(
            multiple=multiple,
            inline=control.inline,
            searchable=control.searchable if not control.inline else True,
            clearable=control.clearable,
            settle=lambda: wait(SETTLE_MS),
        )
        try:
            out[where] = check_contract(bot, picker, shape)
        except AssertionError as error:
            frame = traceback.extract_tb(error.__traceback__)[-1]
            said = str(error) or frame.line
            state = (
                f"open={control.is_open} query={control.query!r} labels={control.labels} "
                f"armed={control.armed} interactive={control.interactive}"
            )
            note(f"{where}: contract clause failed at line {frame.lineno}: {said} [{state}]")
            out[where] = []
        picker.set_value(held)
        control.set_open(False)
        wait(SETTLE_MS)
    return out


def _run(page, wait, find, prefs, multiple: bool) -> dict:
    wait(600)
    failures: list = []
    note = failures.append
    found = pickers_of(find)
    if not found:
        return {"verdict": "FAIL no list picker on the page"}

    seen: dict = {"demos": sorted(found)}
    table = MULTI if multiple else SINGLE

    # The promises first: the contract walk leaves the demos cleared, readonly and disabled.
    seen["display_values"] = (
        display_values(found["labels"], note, "labels") if "labels" in found else {}
    )
    seen["project"] = project_rows(found["project"], note, "project") if "project" in found else {}
    seen["payload"] = (
        payload(found["values"], note, "values", multiple, wait) if "values" in found else {}
    )
    seen["alias"] = alias(note, multiple)
    seen["disabled"] = disabled_opens_for_nobody(found, note, wait)

    cycles = []
    for where, code, wanted in table:
        picker = found.get(where)
        if picker is None:
            note(f"{where}: no demo")
            continue
        answer = cycle(picker, code, note, where, wait)
        cycles.append(answer)
        if not answer.get("closed"):
            continue
        if multiple:
            if answer.get("chips") != wanted:
                note(f"{where}: {answer.get('chips')} chips, wanted {wanted}")
            if code not in (picker.value or []):
                note(f"{where}: {code!r} did not land in the value {picker.value!r}")
        else:
            if picker.value != code:
                note(f"{where}: the value is {picker.value!r}, not {code!r}")
            if list(answer.get("labels") or []) != [wanted]:
                note(f"{where}: the control reads {answer.get('labels')}, not [{wanted!r}]")
    seen["cycles"] = cycles

    seen["contract"] = walk_contract(found, note, wait, multiple)

    kind = "multi picker" if multiple else "picker"
    return {
        "verdict": (
            f"PASS one press opens each list {kind}, a row lands as "
            f"{'a chip' if multiple else 'text'}, one more press closes it, and the contract holds"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }


def run_single(page, wait, find, prefs) -> dict:
    """The single picker's half of the upstream drive."""
    return _run(page, wait, find, prefs, multiple=False)


def run_multi(page, wait, find, prefs) -> dict:
    """The multi picker's half of the upstream drive."""
    return _run(page, wait, find, prefs, multiple=True)
