"""url-editor: a url with a raw space, refused.

One state of the shot matrix. `tools/drives/upstream/url-editor-error.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page url-editor --drive tools/drives/url-editor-error.py \
        --shot shots/url-editor-error.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import press_enter, type_text  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("url-editor", all=True)[0]
    type_text(editor.url_input, "https://example.com/a b.mov")
    wait(120)
    press_enter(editor.url_input)
    wait(300)
    return {
        "verdict": "PASS error",
        "message": editor.message,
        "invalid": editor.reads_invalid,
    }
