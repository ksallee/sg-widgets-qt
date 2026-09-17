"""status-multi-picker: the list open on the first control, its ten options standing.

One state of the shot matrix. `tools/drives/upstream/status-multi-picker-open.js` drives the
upstream page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page status-multi-picker \
        --drive tools/drives/status-multi-picker-open.py \
        --shot shots/states/status-multi-picker-open.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _status_states import state  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return state(page, wait, find, "open")
