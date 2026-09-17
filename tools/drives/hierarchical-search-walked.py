"""hierarchical-search: one level down the tree: the crumbs and the row back up.

One state of the shot matrix. `tools/drives/upstream/hierarchical-search-walked.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page hierarchical-search --drive tools/drives/hierarchical-search-walked.py \
        --shot shots/hierarchical-search-walked.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import hierarchical_search_walked  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return hierarchical_search_walked(page, wait, find, prefs)
