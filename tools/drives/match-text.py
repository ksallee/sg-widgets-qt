"""The matched runs: every word of the query, wherever it occurs, in DemiBold and nothing else.

    .venv/bin/python tools/qa.py --page match-text --drive tools/drives/match-text.py
    .venv/bin/python tools/qa.py --page match-text --drive tools/drives/match-text.py --qt5

The port of `~/dev/sg-widgets/tools/drives/match-text.js`, which reads the runs off the DOM and
their weight off the computed style. Here the label is one painted widget, so the runs come from
the `runs` property and the weight from the two fonts the widget draws with: the matched runs at
`QFont.Weight.DemiBold`, the rest at the body weight, and emphasis is weight and never colour
(`docs/design-rules.md` rule 6).
"""
from __future__ import annotations

from qtpy import QtGui

from sg_widgets_qt.widgets.match_text import MatchText

#: The query the page starts on: two words, which is what the search endpoint matches on.
QUERY = "ad mo"

#: A query no label on the page carries.
NOTHING = "zzz"


def _marked(label: MatchText) -> list[str]:
    return [run.text for run in label.runs if run.match]


def _rebuilt(label: MatchText) -> str:
    return "".join(run.text for run in label.runs)


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    failures: list[str] = []
    seen: dict = {}

    labels = find(MatchText, all=True)
    if len(labels) < 5:
        return {"verdict": f"FAIL the page drew {len(labels)} labels, wanted at least 5"}
    seen["labels"] = len(labels)

    field = find("match-query")
    if field is None:
        failures.append("the page has no query box")

    # --- the page's own two-word query ---

    words = QUERY.split()
    marks: list[str] = []
    for label in labels:
        if _rebuilt(label) != label.text:
            failures.append(f"the runs lost text: {_rebuilt(label)!r} against {label.text!r}")
        marks.extend(_marked(label))
    seen["query"] = {"text": QUERY, "marked": sorted(set(marks)), "runs": len(marks)}
    if not marks:
        failures.append("nothing was marked on the page's own query")
    for run in marks:
        if run.lower() not in words:
            failures.append(f"{run!r} is marked and is no word of the query")
    # Every word of the query is marked, not just the first: both words occur on the page.
    for word in words:
        if not any(run.lower() == word for run in marks):
            failures.append(f"the word {word!r} of the query was never marked")

    # --- the weight, and nothing but the weight ---

    label = labels[0]
    base, bold = label._fonts()
    seen["weights"] = {"plain": int(base.weight()), "matched": int(bold.weight())}
    if int(bold.weight()) != int(QtGui.QFont.Weight.DemiBold):
        failures.append(f"the matched runs are drawn at weight {int(bold.weight())}, wanted DemiBold")
    if int(base.weight()) >= int(bold.weight()):
        failures.append("the plain runs are no lighter than the matched ones")
    if base.pointSizeF() != bold.pointSizeF() or base.family() != bold.family():
        failures.append("a matched run is drawn in another face, not another weight")

    # --- a query no label carries ---

    if field is not None:
        marked_now = field.text()
        # A label the query never touched draws the same either way, so the one read here is one
        # the query marks.
        marked_label = next((one for one in labels if _marked(one)), labels[0])
        with_marks = marked_label.grab().toImage()
        field.set_text(NOTHING)
        wait(250)
        after = [run for one in find(MatchText, all=True) for run in _marked(one)]
        whole = all(_rebuilt(one) == one.text for one in find(MatchText, all=True))
        seen["nothing"] = {"text": NOTHING, "marked": after, "labels_whole": whole}
        if after:
            failures.append(f"a query no label carries marked {after}")
        if not whole:
            failures.append("a query that matches nothing lost text")
        if marked_label.grab().toImage() == with_marks:
            failures.append("the label drew the same with marks and without them")
        field.set_text(marked_now)
        wait(250)

    return {
        "verdict": (
            "PASS every word of a two-word query is marked wherever it occurs, the runs rebuild "
            "each label, the mark is DemiBold and nothing else, and a query no label carries "
            "leaves every label whole"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
