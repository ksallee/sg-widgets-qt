"""context-selector: the open state, measured.

The Qt half of the parity pass. Its twin is
`tools/drives/upstream/measure/context-selector-open.js`, which reads the same numbers off the
upstream DOM.

    .venv/bin/python tools/qa.py --page context-selector \\
        --drive tools/drives/measure/context-selector-open.py \\
        > tools/drives/measure/context-selector-open.json
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _measure import context_selector_open  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    return context_selector_open(page, wait, find, prefs)
