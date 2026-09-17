"""list-picker: a failed read in place of the list, and the message under the control.

One state of the shot matrix. `tools/drives/upstream/list-picker-error.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker-error.py \
        --shot shots/list-picker-error.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_error  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_error(page, wait, find, prefs)
