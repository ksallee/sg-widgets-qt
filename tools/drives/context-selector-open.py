"""context-selector: the popover open on its three sections.

One state of the shot matrix. `tools/drives/upstream/context-selector-open.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page context-selector --drive tools/drives/context-selector-open.py \
        --shot shots/context-selector-open.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import context_selector_open  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return context_selector_open(page, wait, find, prefs)
