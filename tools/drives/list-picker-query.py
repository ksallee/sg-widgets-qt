"""list-picker: the searchable demo open over a query, the matched runs bold.

One state of the shot matrix. `tools/drives/upstream/list-picker-query.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page list-picker --drive tools/drives/list-picker-query.py \
        --shot shots/list-picker-query.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _list_states import list_query  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return list_query(page, wait, find, prefs)
