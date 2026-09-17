"""The state matrix: the labels marked on a one-word query.

    .venv/bin/python tools/qa.py --page match-text \
      --drive tools/drives/match-text-one-word.py --shot /tmp/match-text-one-word.png

The twin of `tools/drives/upstream/match-text-one-word.js`.
"""
from __future__ import annotations

from sg_widgets_qt.widgets.match_text import MatchText

#: One word, which the endpoint matches wherever it occurs (053_text_search_matching).
WORD = "mo"


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    field = find("match-query")
    if field is None:
        return {"verdict": "FAIL the page has no query box"}
    field.set_text(WORD)
    wait(300)
    marked = [run.text for one in find(MatchText, all=True) for run in one.runs if run.match]
    return {
        "verdict": (
            "PASS a one-word query marks that word wherever it occurs"
            if marked and all(run.lower() == WORD for run in marked)
            else f"FAIL a one-word query marked {marked}"
        ),
        "seen": {"query": WORD, "marked": marked},
    }
