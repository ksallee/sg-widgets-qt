"""list-picker: readonly: full contrast, no chevron and no clear control.

One state of the shot matrix. `tools/drives/upstream/list-picker-readonly.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker-readonly.py \
        --shot shots/list-picker-readonly.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_readonly  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_readonly(page, wait, find, prefs)
