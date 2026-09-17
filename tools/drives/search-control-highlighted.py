"""search-control: the keyboard highlight, two rows down the page.

One state of the shot matrix. `tools/drives/upstream/search-control-highlighted.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page search-control --drive tools/drives/search-control-highlighted.py \
        --shot shots/search-control-highlighted.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import search_control_highlighted  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return search_control_highlighted(page, wait, find, prefs)
