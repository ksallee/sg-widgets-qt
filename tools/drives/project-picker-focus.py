"""project-picker: the caret holding a keyboard focus, so the ring is painted.

One state of the shot matrix. `tools/drives/upstream/project-picker-focus.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page project-picker --drive tools/drives/project-picker-focus.py \
        --shot shots/project-picker-focus.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _project_states import focus  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return focus(page, wait, find, prefs)
