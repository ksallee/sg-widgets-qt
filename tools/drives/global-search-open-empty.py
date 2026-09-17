"""global-search: the palette open on an empty query, where the recents show.

One state of the shot matrix. `tools/drives/upstream/global-search-open-empty.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page global-search --drive tools/drives/global-search-open-empty.py \
        --shot shots/global-search-open-empty.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import global_search_open_empty  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_open_empty(page, wait, find, prefs)
