"""project-multi-picker: the list open on a picker whose rows are already ticked.

One state of the shot matrix. `tools/drives/upstream/project-multi-picker-ticked.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page project-multi-picker --drive tools/drives/project-multi-picker-ticked.py \
        --shot shots/project-multi-picker-ticked.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _project_states import ticked  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return ticked(page, wait, find, prefs)
