"""field-picker: a schema read armed to fail.

One state of the wave's shot matrix. Its twin under `tools/drives/upstream/` drives the
upstream page into the same state where upstream can be driven there, and the pair of shots is
what the QA pass reads.

    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/field-picker-error.py \
        --shot shots/states/field-picker-error.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _wave_states import field_picker_error  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return field_picker_error(page, wait, find, prefs)
