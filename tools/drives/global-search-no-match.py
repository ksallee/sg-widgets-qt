"""global-search: the empty line, on a query the read answers nothing for.

One state of the shot matrix. `tools/drives/upstream/global-search-no-match.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page global-search --drive tools/drives/global-search-no-match.py \
        --shot shots/global-search-no-match.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import global_search_no_match  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_no_match(page, wait, find, prefs)
