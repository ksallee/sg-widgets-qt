"""match-text: type a query and read it marked across every label under it.

    .venv/bin/python tools/qa.py --page match-text --drive tools/drives/walk/match-text.py

Every word of a query is marked wherever it occurs, so the walk types into the box and reads the
runs each label answers with: a query that matches, one that matches nothing, an empty one that
leaves every label whole, and one whose case differs from the label's. The muted line is marked the
same way, because weight is the only mark it has.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, case_widget, popups, retype, set_view  # noqa: E402

from sg_widgets_qt.widgets.match_text import MatchText  # noqa: E402


def labels_in(page, case: str) -> list:
    holder = case_widget(page, case)
    return list(holder.findChildren(MatchText)) if holder is not None else []


def marked(label) -> list:
    """The runs of a label the query marked, in order."""
    return [run.text for run in label.runs if run.match]


def whole(label) -> str:
    """The label rebuilt from its runs, which must be the label itself."""
    return "".join(run.text for run in label.runs)


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("match-text-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no match-text demo"}
    box = demo.query
    listed = labels_in(page, "labels")
    muted = labels_in(page, "muted")
    walk.check("the example lists labels to mark", len(listed) >= 5, ">= 5", len(listed))
    walk.check("the muted line stands under them", len(muted) == 1, 1, len(muted))

    walk.same("the box opens on the demo's own query", "ad mo", box.text())
    walk.check(
        "the labels open marked by it",
        any(marked(label) for label in listed),
        "a marked run",
        [marked(label) for label in listed],
    )

    # --- a query that matches one word in several labels ------------------------------------
    retype(box.input, "sh010")
    wait(250)
    walk.check(
        "typing re-marks every label under the box",
        all(label.query == "sh010" for label in (*listed, *muted)),
        "sh010 everywhere",
        sorted({label.query for label in (*listed, *muted)}),
    )
    hit = [label for label in listed if marked(label)]
    walk.check("the query marks the labels holding it", len(hit) >= 1, ">= 1", len(hit))
    walk.check(
        "every marked run is the query itself",
        all(run.lower() == "sh010" for label in hit for run in marked(label)),
        "sh010",
        [marked(label) for label in hit],
    )
    walk.check(
        "the muted line is marked the same way",
        bool(marked(muted[0])),
        "a marked run",
        marked(muted[0]),
    )

    # --- every word of the query is marked, wherever it occurs --------------------------------
    retype(box.input, "ada 006")
    wait(250)
    both = [label for label in listed if len(marked(label)) >= 1]
    walk.check("both words of a query are looked for", len(both) >= 2, ">= 2", [marked(one) for one in both])

    # --- the case of the query does not matter ------------------------------------------------
    retype(box.input, "ADA")
    wait(250)
    walk.check(
        "a query in another case still marks",
        any(marked(label) for label in listed),
        "a marked run",
        [marked(label) for label in listed],
    )

    # --- a query that matches nothing, and an empty one ----------------------------------------
    retype(box.input, "zzzz")
    wait(250)
    walk.same("a query that matches nothing marks nothing", [], [run for label in listed for run in marked(label)])
    walk.check(
        "the labels are still drawn whole",
        all(whole(label) == label.text for label in listed),
        "every label whole",
        [label.text for label in listed if whole(label) != label.text],
    )

    retype(box.input, "")
    wait(250)
    walk.same("an empty query marks nothing", [], [run for label in listed for run in marked(label)])
    walk.check(
        "an empty query leaves every label whole",
        all(whole(label) == label.text for label in listed),
        "every label whole",
        [label.text for label in listed if whole(label) != label.text],
    )

    # --- the address, which is where a match runs across a separator -----------------------------
    retype(box.input, "van der")
    wait(250)
    address = [label for label in listed if "@" in label.text]
    walk.check("the address is on the page", len(address) == 1, 1, len(address))
    walk.check(
        "a query marks inside an address too",
        bool(marked(address[0])),
        "a marked run",
        marked(address[0]),
    )

    # --- the view controls -----------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("match-text-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        walk.same("header: the box came back on the demo's own query", "ad mo", again.query.text())
        rebuilt = labels_in(page, "labels")
        walk.check(
            "header: the labels wear the size step",
            all(label.size == "lg" for label in rebuilt),
            "lg",
            sorted({label.size for label in rebuilt}),
        )
        walk.same("header: the muted line keeps the step it named", "sm", labels_in(page, "muted")[0].size)
        retype(again.query.input, "crate")
        wait(250)
        walk.check(
            "header: the rebuilt box still re-marks",
            any(marked(label) for label in labels_in(page, "labels")),
            "a marked run",
            [marked(label) for label in labels_in(page, "labels")],
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the query box re-marks every label under it, each word is marked wherever it occurs"
        " whatever its case, a query that matches nothing and an empty one leave the labels whole,"
        " and the muted line is marked the same way"
    )
