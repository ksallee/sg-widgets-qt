"""entity-type-multi-picker: the control under the pointer, so the `muted` wash at 30% is on.

One state of the shot matrix. `tools/drives/upstream/entity-type-multi-picker-hover.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads. The walk is
`tools/drives/_entity_type_states.py`, shared by both pages.

    .venv/bin/python tools/qa.py --page entity-type-multi-picker \\
        --drive tools/drives/entity-type-multi-picker-hover.py --shot shots/entity-type-multi-picker-hover.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_type_states import hover  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return hover(page, wait, find, prefs)
