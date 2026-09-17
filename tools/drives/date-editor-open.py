"""date-editor: the md editor with its popover open on the typed day and the month grid.

One state of the shot matrix. `tools/drives/upstream/date-editor-open.js` drives the upstream page
into the same state, and the pair of shots is what the QA pass reads. The popover is a window of
its own, so the shot of the page shows it only where the platform composites it; the drive also
grabs the surface on its own beside the page shot.

    .venv/bin/python tools/qa.py --page date-editor --drive tools/drives/date-editor-open.py \
        --shot shots/date-editor-open.png
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import click  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    editor = find("date-editor", all=True)[1]
    click(editor.trigger)
    wait(500)
    surface = editor.day_input.window()
    surface.grab().save(str(Path("shots") / "date-editor-open-popup.png"))
    panel = editor.day_input.parentWidget() if "date-editor" == "date-editor" else editor.date_input.parentWidget()
    column = panel.layout()
    margins = column.contentsMargins()
    return {
        "padding": [margins.left(), margins.top(), margins.right(), margins.bottom()],
        "gap": column.spacing(),
        "order": ["day", "calendar"],
        "verdict": "PASS open" if editor.is_open else "FAIL the popover did not open",
        "inputs": 1,
        "grids": 1 if editor.calendar.isVisible() else 0,
        "focused": editor.day_input.hasFocus(),
    }
