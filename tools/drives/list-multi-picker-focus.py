"""list-multi-picker: the control holding a keyboard focus, so the ring is painted.

One state of the shot matrix. `tools/drives/upstream/list-multi-picker-focus.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-multi-picker --drive tools/drives/list-multi-picker-focus.py \
        --shot shots/list-multi-picker-focus.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_focus  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_focus(page, wait, find, prefs)
