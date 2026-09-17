"""column-picker: design rule 7, every clause, on the field picker inside it.

`tools/drives/picker-contract.py` walks every picker of a page, and on this one it reads the
embedded field picker as a picker that keeps its value. This one does not: `docs/widgets/
column-picker.md` says a pick appends the path to the list and clears the picker for the next
one, so the control is empty again a turn after Enter. The clause is watched on what the picker
emitted instead, which is what `tests/qt/test_column_picker.py` does with the same checker.

A picker whose list opens on a link rather than on a field is left out: the contract's pick
clause presses Enter on the highlighted row, and Enter on a link descends rather than choosing,
which is what the docs page promises and what `tools/drives/field-picker-keys.py` reads.

    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/column-picker-contract.py
    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/column-picker-contract.py --qt5
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from qtpy.QtWidgets import QWidget

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sg_widgets_qt.widgets.column_picker import ColumnPicker  # noqa: E402
from tests.qt.test_picker_contract import PickerShape, check_contract  # noqa: E402

#: The mock's latency plus the debounce, with room for the hop back onto the GUI thread.
SETTLE_MS = 1200


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


def settled(picker, wait, ms: int = 8000) -> bool:
    """Turn the loop until the embedded picker has a field to offer."""
    end = time.time() + ms / 1000.0
    inner = picker.field_picker
    while time.time() < end:
        wait(60)
        if inner.derived:
            return True
    return False


def drive(page, wait, find, prefs) -> dict:
    bot = _Bot(wait)
    failures: list[str] = []
    seen: dict = {}

    for picker in find(ColumnPicker, all=True):
        name = picker.objectName() or "column-picker"
        if picker.readonly or picker.disabled or picker.layout_kind == "dual":
            continue
        if not settled(picker, wait):
            failures.append(f"{name} — the field list never answered")
            continue
        inner = picker.field_picker
        if not inner.derived[0].selectable:
            seen[name] = {"skipped": "the list opens on a link, which Enter descends into"}
            continue
        # The column picker consumes a pick at once and clears the picker, which leaves the
        # control's own keys where they were, so the pick clause is watched on the signal.
        inner.value_changed.disconnect()
        picked: list = []
        inner.value_changed.connect(picked.append)
        try:
            checked = check_contract(
                bot,
                inner,
                PickerShape(
                    inline=False,
                    clearable=False,
                    keeps_value=False,
                    settle=lambda: wait(SETTLE_MS),
                ),
            )
        except AssertionError as error:
            failures.append(f"{name} — {error}")
            continue
        finally:
            inner.value_changed.connect(picker._append)  # noqa: SLF001
        seen[name] = {"clauses": list(checked), "picked": picked}
        if not picked:
            failures.append(f"{name} — Enter did not take the highlighted field")
        for clause in ("press toggles", "caret on open", "outside press", "readonly"):
            if clause not in checked:
                failures.append(f"{name} — {clause} was never reached")

    if not seen and not failures:
        return {"verdict": "FAIL no column picker with a field picker on this page"}
    return {
        "verdict": (
            "PASS the field picker inside every column picker keeps the contract"
            if not failures
            else "FAIL " + "; ".join(failures[:6])
        ),
        "failures": failures,
        "seen": seen,
    }
