"""entity-type-multi-picker: the height ladder of rule 3, at whatever size the view wears.

One state of the shot matrix. `tools/drives/upstream/entity-type-multi-picker-sizes.js` reads the same heights off
the upstream page, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page entity-type-multi-picker --size sm \\
        --drive tools/drives/entity-type-multi-picker-sizes.py --shot shots/entity-type-multi-picker-sm.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _entity_type_states import sizes  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return sizes(page, wait, find, prefs)
