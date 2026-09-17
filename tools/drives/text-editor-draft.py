"""text-editor: a typed, uncommitted draft in the single-line input.

One state of the shot matrix. `tools/drives/upstream/text-editor-draft.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page text-editor --drive tools/drives/text-editor-draft.py \
        --shot shots/text-editor-draft.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import type_text  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("text-editor", all=True)[0]
    type_text(editor.control, "typed, not committed")
    wait(200)
    return {"verdict": "PASS draft", "value": editor.control.text()}
