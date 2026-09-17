"""user-multi-picker: the page as it settles, nothing open.

One state of the shot matrix. `tools/drives/upstream/user-multi-picker-rest.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker-rest.py \\
        --shot shots/user-multi-picker-rest.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_rest  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_rest(page, wait, find, prefs)
