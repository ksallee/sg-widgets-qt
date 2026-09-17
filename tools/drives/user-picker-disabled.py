"""user-picker: disabled: the control at half opacity and inert.

One state of the shot matrix. `tools/drives/upstream/user-picker-disabled.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-picker --drive tools/drives/user-picker-disabled.py \\
        --shot shots/user-picker-disabled.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_disabled  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_disabled(page, wait, find, prefs)
