"""list-multi-picker: the list open on the display-values demo, every row a plain label.

One state of the shot matrix. `tools/drives/upstream/list-multi-picker-open.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-multi-picker --drive tools/drives/list-multi-picker-open.py \
        --shot shots/list-multi-picker-open.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_open  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_open(page, wait, find, prefs)
