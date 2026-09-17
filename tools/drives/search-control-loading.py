"""search-control: the skeletons, caught while the first read is in flight.

One state of the shot matrix. `tools/drives/upstream/search-control-loading.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page search-control --drive tools/drives/search-control-loading.py \
        --shot shots/search-control-loading.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import search_control_loading  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return search_control_loading(page, wait, find, prefs)
