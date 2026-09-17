"""list-picker: the list open while a caller's read is in flight.

One state of the shot matrix. `tools/drives/upstream/list-picker-loading.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker-loading.py \
        --shot shots/list-picker-loading.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_loading  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_loading(page, wait, find, prefs)
