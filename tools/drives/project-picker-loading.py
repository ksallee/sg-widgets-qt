"""project-picker: the list open with the first read still out, so the skeletons stand.

One state of the shot matrix. `tools/drives/upstream/project-picker-loading.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page project-picker --drive tools/drives/project-picker-loading.py \
        --shot shots/project-picker-loading.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _project_states import loading  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return loading(page, wait, find, prefs)
