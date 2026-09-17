"""The date editor with its calendar open, measured against the upstream DOM walk."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import click  # noqa: E402
from _leaves import measure_page, measure_popups  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    wait(400)
    trigger = find("date-editor-trigger")
    if trigger is None:
        from sg_widgets_qt.widgets.date_editor import DateTrigger

        found = find(DateTrigger, all=True)
        trigger = found[0] if found else None
    if trigger is None:
        return {"verdict": "FAIL no date trigger on the page"}
    click(trigger)
    wait(400)
    out = measure_page(page)
    out["popups"] = measure_popups()
    out["verdict"] = "PASS the calendar is open" if out["popups"] else "FAIL no popup opened"
    return out
