"""context-selector: the size ladder, each control beside a button of the same step.

One state of the shot matrix. `tools/drives/upstream/context-selector-sizes.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page context-selector --drive tools/drives/context-selector-sizes.py \
        --shot shots/context-selector-sizes.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _search_states import context_selector_sizes  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return context_selector_sizes(page, wait, find, prefs)
