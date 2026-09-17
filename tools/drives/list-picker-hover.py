"""list-picker: the control under the pointer, `muted` at 30% over `background`.

One state of the shot matrix. `tools/drives/upstream/list-picker-hover.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker-hover.py \
        --shot shots/list-picker-hover.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_hover  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_hover(page, wait, find, prefs)
