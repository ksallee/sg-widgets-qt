"""number-editor: the duration field one Up step on, 480 minutes to 495.

One state of the shot matrix. `tools/drives/upstream/number-editor-stepped.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page number-editor --drive tools/drives/number-editor-stepped.py \
        --shot shots/number-editor-stepped.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from qtpy import QtCore

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import key  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    duration = next(e for e in find("number-editor", all=True) if e.data_type == "duration")
    key(duration.input, QtCore.Qt.Key.Key_Up)
    wait(300)
    return {"verdict": "PASS stepped", "shown": duration.input.text(), "value": duration.value}
