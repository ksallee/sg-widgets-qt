"""global-search: the trigger with the keyboard focus ring.

One state of the shot matrix. `tools/drives/upstream/global-search-trigger-focus.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page global-search --drive tools/drives/global-search-trigger-focus.py \
        --shot shots/global-search-trigger-focus.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import global_search_trigger_focus  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_trigger_focus(page, wait, find, prefs)
