"""entity-type-multi-picker: the list open after the schema read was made to fail.

One state of the shot matrix. `tools/drives/upstream/entity-type-multi-picker-error.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads. The walk is
`tools/drives/_entity_type_states.py`, shared by both pages.

    .venv/bin/python tools/qa.py --page entity-type-multi-picker \\
        --drive tools/drives/entity-type-multi-picker-error.py --shot shots/entity-type-multi-picker-error.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_type_states import error  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return error(page, wait, find, prefs)
