"""global-search: the no-match state, measured.

The Qt half of the parity pass. Its twin is
`tools/drives/upstream/measure/global-search-no-match.js`, which reads the same numbers off the
upstream DOM.

    .venv/bin/python tools/qa.py --page global-search \\
        --drive tools/drives/measure/global-search-no-match.py \\
        > tools/drives/measure/global-search-no-match.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _measure import global_search_no_match  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_no_match(page, wait, find, prefs)
