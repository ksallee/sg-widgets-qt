"""checkbox-editor: the first switch toggled off, so the word beside it follows.

One state of the shot matrix. `tools/drives/upstream/checkbox-editor-toggled.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page checkbox-editor --drive tools/drives/checkbox-editor-toggled.py \
        --shot shots/checkbox-editor-toggled.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import click  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("checkbox-editor", all=True)[0]
    click(editor.switch)
    wait(300)
    return {"verdict": "PASS toggled", "value": editor.value, "label": editor._label.text}
