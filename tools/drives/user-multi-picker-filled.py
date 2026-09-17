"""user-multi-picker: a person in every control, the heights, then the three states.

One state of the shot matrix. `tools/drives/upstream/user-multi-picker-filled.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker-filled.py \\
        --shot shots/user-multi-picker-filled.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_filled  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_filled(page, wait, find, prefs)
