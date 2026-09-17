"""The date editor with its calendar popover open, measured against the upstream DOM walk.

The twin of `tools/drives/upstream/measure/date-editor-open.js`. The popover is a window of its
own here, so the surface is read through `measure_popups`, which is where the upstream portalled
`popover-content` lands.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import click  # noqa: E402
from _leaves import measure_page, measure_popups  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("date-editor", all=True)[1]
    click(editor.trigger)
    wait(600)
    out = measure_page(page)
    out["popups"] = measure_popups()
    out["open"] = editor.is_open
    return out
