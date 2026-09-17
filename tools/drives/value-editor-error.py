"""value-editor: a frame range that runs backwards, refused.

One state of the shot matrix. `tools/drives/upstream/value-editor-error.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page value-editor --drive tools/drives/value-editor-error.py \
        --shot shots/value-editor-error.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import press_enter, type_text  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("range-editor", all=True)[0]
    type_text(editor.input, "1200-1001")
    wait(120)
    press_enter(editor.input)
    wait(300)
    return {"verdict": "PASS error", "message": editor.message}
