"""global-search: the open-query state, measured.

The Qt half of the parity pass. Its twin is
`tools/drives/upstream/measure/global-search-open-query.js`, which reads the same numbers off the
upstream DOM.

    .venv/bin/python tools/qa.py --page global-search \\
        --drive tools/drives/measure/global-search-open-query.py \\
        > tools/drives/measure/global-search-open-query.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _measure import global_search_open_query  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_open_query(page, wait, find, prefs)
