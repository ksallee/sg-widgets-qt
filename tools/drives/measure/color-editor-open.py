"""The colour editor with its picker popover open, measured against the upstream DOM walk.

The twin of `tools/drives/upstream/measure/color-editor-open.js`: the surface, its inset, the
ring it paints and the shadow under it, read off the window the popover stands in.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import click  # noqa: E402
from _leaves import measure_page, measure_popups  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("color-editor", all=True)[0]
    click(editor.swatch)
    wait(600)
    out = measure_page(page)
    out["popups"] = measure_popups()
    out["open"] = editor.is_open
    return out
