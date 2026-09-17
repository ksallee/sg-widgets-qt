"""entity-type-picker: the combobox behaviour, the payload and the two sets.

The port of `~/dev/sg-widgets/tools/drives/entity-type-picker-combobox.js`, with the ten clauses
of rule 7 run from `tests/qt/test_picker_contract.check_contract` on every shape the page draws,
and the two things the docs page promises that the upstream drive does not check: the
`value_changed` payload, and that `allow` and `deny` narrow the derived options rather than the
read. The walk itself is `tools/drives/_entity_types.py`, shared with the multi picker.

    .venv/bin/python tools/qa.py --page entity-type-picker --drive tools/drives/entity-type-picker.py
    .venv/bin/python tools/qa.py --page entity-type-picker --drive tools/drives/entity-type-picker.py --qt5
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_types import combobox  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return combobox(page, wait, find, prefs, multiple=False)
