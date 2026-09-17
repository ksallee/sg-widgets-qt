"""global-search: a page of rows, the matched runs bold.

One state of the shot matrix. `tools/drives/upstream/global-search-rows.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page global-search --drive tools/drives/global-search-rows.py \
        --shot shots/global-search-rows.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import global_search_rows  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_rows(page, wait, find, prefs)
