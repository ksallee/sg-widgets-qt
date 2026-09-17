"""project-picker: the list open on standing rows: picture, name, status under it.

One state of the shot matrix. `tools/drives/upstream/project-picker-open.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page project-picker --drive tools/drives/project-picker-open.py \
        --shot shots/project-picker-open.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _project_states import open_rows  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return open_rows(page, wait, find, prefs)
