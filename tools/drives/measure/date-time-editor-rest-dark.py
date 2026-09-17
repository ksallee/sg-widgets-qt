"""The date-time-editor page, rest-dark, measured against the upstream DOM walk."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _leaves import measure_page, measure_popups  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    wait(700)
    out = measure_page(page)
    out["popups"] = measure_popups()
    return out
