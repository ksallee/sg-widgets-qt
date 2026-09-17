"""column-picker: a row carried by its grip, before the release.

One state of the wave's shot matrix. Its twin under `tools/drives/upstream/` drives the
upstream page into the same state where upstream can be driven there, and the pair of shots is
what the QA pass reads.

    .venv/bin/python tools/qa.py --page column-picker --drive tools/drives/column-picker-dragging.py \
        --shot shots/states/column-picker-dragging.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import column_picker_dragging  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return column_picker_dragging(page, wait, find, prefs)
