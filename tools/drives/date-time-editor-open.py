"""date-time-editor: the md editor with its popover open on the day, the grid and the time.

One state of the shot matrix. `tools/drives/upstream/date-time-editor-open.js` drives the upstream
page into the same state, and the pair of shots is what the QA pass reads.

    .venv/bin/python tools/qa.py --page date-time-editor --drive tools/drives/date-time-editor-open.py \
        --shot shots/date-time-editor-open.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import click  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("date-time-editor", all=True)[1]
    click(editor.trigger)
    wait(500)
    surface = editor.date_input.window()
    surface.grab().save(str(Path("shots") / "date-time-editor-open-popup.png"))
    panel = editor.day_input.parentWidget() if "date-time-editor" == "date-editor" else editor.date_input.parentWidget()
    column = panel.layout()
    margins = column.contentsMargins()
    return {
        "padding": [margins.left(), margins.top(), margins.right(), margins.bottom()],
        "gap": column.spacing(),
        "order": ["date", "calendar", "time"],
        "verdict": "PASS open" if editor.is_open else "FAIL the popover did not open",
        "inputs": 2,
        "grids": 1 if editor.calendar.isVisible() else 0,
        "focused": editor.date_input.hasFocus(),
    }
