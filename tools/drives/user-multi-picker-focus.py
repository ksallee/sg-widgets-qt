"""user-multi-picker: the caret holding a keyboard focus ring.

One state of the shot matrix. `tools/drives/upstream/user-multi-picker-focus.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-multi-picker --drive tools/drives/user-multi-picker-focus.py \\
        --shot shots/user-multi-picker-focus.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_focus  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_focus(page, wait, find, prefs)
