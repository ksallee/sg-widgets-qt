"""search-control: a page of rows, the matched runs bold.

One state of the shot matrix. `tools/drives/upstream/search-control-rows.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page search-control --drive tools/drives/search-control-rows.py \
        --shot shots/search-control-rows.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import search_control_rows  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return search_control_rows(page, wait, find, prefs)
