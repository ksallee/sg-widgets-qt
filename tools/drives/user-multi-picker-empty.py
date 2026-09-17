"""user-multi-picker: the list open over a query nothing answers.

One state of the shot matrix. `tools/drives/upstream/user-multi-picker-empty.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker-empty.py \\
        --shot shots/user-multi-picker-empty.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_empty  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_empty(page, wait, find, prefs)
