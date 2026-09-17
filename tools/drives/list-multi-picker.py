"""One press opens a list multi picker, a row lands as a chip, one more press closes it.

The multi half of `~/dev/sg-widgets/tools/drives/list-picker-pick.js`. Upstream reads both
pickers in one run by loading the multi page into a same-origin iframe; a page here is a window
of its own, so the two halves are two drives over one module.

    .venv/bin/python tools/qa.py --page list-multi-picker --drive tools/drives/list-multi-picker.py
    .venv/bin/python tools/qa.py --page list-multi-picker --drive tools/drives/list-multi-picker.py --qt5

Beside the press cycle it walks the ten clauses of design rule 7 through
`tests/qt/test_picker_contract.check_contract`, and then what
`docs/widgets/list-multi-picker.md` promises:

    payload        `value_changed` carries the whole list, and the empty list once it is cleared
    display values the row and the chip read the display label, the value stays the raw valid
                   value, byte for byte and case-sensitive (field_types/list)
    project        a project id subtracts the field's hidden values (probe 009), and a chosen
                   value outside the offered set keeps a row of its own
    disabled       a disabled picker opens for nobody
    alias          `list_multi_select` re-exports the same class and adds nothing
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_picker_pick import run_multi  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return run_multi(page, wait, find, prefs)
