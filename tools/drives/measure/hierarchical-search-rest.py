"""hierarchical-search: the rest state, measured.

The Qt half of the parity pass. Its twin is
`tools/drives/upstream/measure/hierarchical-search-rest.js`, which reads the same numbers off the
upstream DOM.

    .venv/bin/python tools/qa.py --page hierarchical-search \\
        --drive tools/drives/measure/hierarchical-search-rest.py \\
        > tools/drives/measure/hierarchical-search-rest.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _measure import hierarchical_search_rest  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return hierarchical_search_rest(page, wait, find, prefs)
