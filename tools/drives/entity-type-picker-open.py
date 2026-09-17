"""entity-type-picker: the list open on the first control, the glyph leading every row.

One state of the shot matrix. `tools/drives/upstream/entity-type-picker-open.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads. The walk is
`tools/drives/_entity_type_states.py`, shared by both pages.

    .venv/bin/python tools/qa.py --page entity-type-picker \\
        --drive tools/drives/entity-type-picker-open.py --shot shots/entity-type-picker-open.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_type_states import open_rows  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return open_rows(page, wait, find, prefs)
