"""list-multi-picker: the three summary modes, one per demo on the page.

One state of the shot matrix. `tools/drives/upstream/list-multi-picker-summary.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-multi-picker --drive tools/drives/list-multi-picker-summary.py \
        --shot shots/list-multi-picker-summary.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_summary  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_summary(page, wait, find, prefs)
