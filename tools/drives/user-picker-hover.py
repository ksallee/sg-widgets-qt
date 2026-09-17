"""user-picker: the control under the pointer, `muted` at 30% over `background`.

One state of the shot matrix. `tools/drives/upstream/user-picker-hover.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page user-picker --drive tools/drives/user-picker-hover.py \\
        --shot shots/user-picker-hover.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _user_states import user_hover  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return user_hover(page, wait, find, prefs)
