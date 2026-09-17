"""entity-type-picker: the caret holding a keyboard focus ring.

One state of the shot matrix. `tools/drives/upstream/entity-type-picker-focus.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads. The walk is
`tools/drives/_entity_type_states.py`, shared by both pages.

    .venv/bin/python tools/qa.py --page entity-type-picker \\
        --drive tools/drives/entity-type-picker-focus.py --shot shots/entity-type-picker-focus.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_type_states import focus  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return focus(page, wait, find, prefs)
