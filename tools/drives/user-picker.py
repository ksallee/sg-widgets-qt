"""Design rule 7 and the person preset, on every user picker of the page.

The port of the upstream drives this widget carries: `user-picker-address.js` for what a person
search matches and shows, and `picker-contract.js` with `picker-escape.js`, `picker-backspace.js`,
`picker-mandatory-clear.js` and `picker-arrow-scroll.js` behind it, which
`tests/qt/test_picker_contract.check_contract` walks in one piece.

    .venv/bin/python tools/qa.py --page user-picker --drive tools/drives/user-picker.py
    .venv/bin/python tools/qa.py --page user-picker --drive tools/drives/user-picker.py --qt5

What it asserts beside the ten clauses is what `docs/widgets/user-picker.md` promises: the
HumanUser and ApiUser preset, the active condition, the fields a row needs, the query matched on
the display-name chain, the email and — while it holds no whitespace — the login, the address
under the name, `API user` for a script account, and the `EntityRef`, `PickerRow` payload of
`value_changed`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_behaviour import walk  # noqa: E402

from sg_widgets_qt.widgets.user_picker import UserPicker  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return walk(page, wait, find, UserPicker, multiple=False)
