"""global-search: the loading state, measured.

The Qt half of the parity pass. Its twin is
`tools/drives/upstream/measure/global-search-loading.js`, which reads the same numbers off the
upstream DOM.

    .venv/bin/python tools/qa.py --page global-search \\
        --drive tools/drives/measure/global-search-loading.py \\
        > tools/drives/measure/global-search-loading.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _measure import global_search_loading  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return global_search_loading(page, wait, find, prefs)
