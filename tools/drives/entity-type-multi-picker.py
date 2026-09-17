"""entity-type-multi-picker: the combobox behaviour, the payload and the two sets.

The same walk as `tools/drives/entity-type-picker.py`, which is the port of
`~/dev/sg-widgets/tools/drives/entity-type-picker-combobox.js`: the upstream drive runs one body
on both pages, so this file is the multi picker's entry point into the shared walk. The payload
is a list here, a pick keeps the list open and every row draws a checkbox.

    .venv/bin/python tools/qa.py --page entity-type-multi-picker --drive tools/drives/entity-type-multi-picker.py
    .venv/bin/python tools/qa.py --page entity-type-multi-picker --drive tools/drives/entity-type-multi-picker.py --qt5
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_types import combobox  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return combobox(page, wait, find, prefs, multiple=True)
