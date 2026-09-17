"""user-multi-picker: a narrow summary control: whole chips, then `+n`.

One state of the shot matrix. `tools/drives/upstream/user-multi-picker-overflow.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker-overflow.py \\
        --shot shots/user-multi-picker-overflow.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_overflow  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_overflow(page, wait, find, prefs)
