"""One press opens a list picker, a row lands in the control as text, one more press closes it.

The port of `~/dev/sg-widgets/tools/drives/list-picker-pick.js`, whose multi half lives in
`tools/drives/list-multi-picker.py` because a page here is a window rather than an iframe.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker.py
    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker.py --qt5

Beside the press cycle it walks the ten clauses of design rule 7 through
`tests/qt/test_picker_contract.check_contract`, so the drive and the test check the same code
against the real demos, and then what `docs/widgets/list-picker.md` promises:

    payload        `value_changed` carries the chosen string, and None once it is cleared
    display values the row and the control read the display label, the value stays the raw
                   valid value, byte for byte and case-sensitive (field_types/list)
    project        a project id subtracts the field's hidden values (probe 009), and a stored
                   value outside the offered set keeps a row of its own
    disabled       a disabled picker opens for nobody
    alias          `list_select` re-exports the same class and adds nothing
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_picker_pick import run_single  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return run_single(page, wait, find, prefs)
