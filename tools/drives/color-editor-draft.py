"""color-editor: a typed hex code, uncommitted, with the swatch previewing it.

One state of the shot matrix. `tools/drives/upstream/color-editor-draft.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page color-editor --drive tools/drives/color-editor-draft.py \
        --shot shots/color-editor-draft.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import type_text  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("color-editor", all=True)[0]
    type_text(editor.input, "#00ff00")
    wait(250)
    colour = editor.swatch.color
    return {"verdict": "PASS draft", "swatch": colour.name() if colour else None}
