"""Design rule 7 and the person preset, on every user multi picker of the page.

The port of the upstream drives this widget carries: `user-picker-address.js` for what a person
search matches and shows, `multi-picker-fit.js` and `picker-armed-chip.js` for the chip row, and
`picker-contract.js` with `picker-escape.js`, `picker-backspace.js` and
`picker-pick-releases-chip.js` behind it, which `tests/qt/test_picker_contract.check_contract`
walks in one piece over both shapes the page draws: the token field and the summary trigger.

    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker.py
    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker.py --qt5

What it asserts beside the ten clauses is what `docs/widgets/user-multi-picker.md` promises: the
same person preset as the single picker, and the `EntityRef[]`, `PickerRow[]` payload of
`value_changed`, in the order the rows were ticked.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_behaviour import walk  # noqa: E402

from sg_widgets_qt.widgets.user_multi_picker import UserMultiPicker  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return walk(page, wait, find, UserMultiPicker, multiple=True)
