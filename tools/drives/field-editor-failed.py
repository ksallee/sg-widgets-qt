"""field-editor: a refused write.

One state of the wave's shot matrix. Its twin under `tools/drives/upstream/` drives the
upstream page into the same state where upstream can be driven there, and the pair of shots is
what the QA pass reads.

    .venv/bin/python tools/qa.py --page field-editor --drive tools/drives/field-editor-failed.py \
        --shot shots/states/field-editor-failed.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import field_editor_failed  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return field_editor_failed(page, wait, find, prefs)
