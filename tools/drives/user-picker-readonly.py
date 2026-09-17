"""user-picker: read-only: full contrast, no chevron and no clear control.

One state of the shot matrix. `tools/drives/upstream/user-picker-readonly.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-picker --drive tools/drives/user-picker-readonly.py \\
        --shot shots/user-picker-readonly.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_readonly  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_readonly(page, wait, find, prefs)
