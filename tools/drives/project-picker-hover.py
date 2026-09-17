"""project-picker: the control under the pointer, so the muted wash is on.

One state of the shot matrix. `tools/drives/upstream/project-picker-hover.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page project-picker --drive tools/drives/project-picker-hover.py \
        --shot shots/project-picker-hover.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _project_states import hover  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return hover(page, wait, find, prefs)
