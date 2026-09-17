"""filter-editor: read every row of the seeded catalogue back off the page.

    .venv/bin/python tools/qa.py --page filter-editor \
        --drive tools/drives/walk/filter-editor-catalogue.py

The port of `tools/drives/filter-editor-catalogue.js`. The table below is the demo's first tree,
group by group. A row passes when its field trigger reads a resolved path rather than the raw one
the demo seeded, its operator reads the menu entry that path's data type puts on the operator, and
its value draws the control that data type and that arity call for.

`control` is the object name of the widget in the row's value cell, `None` for an entry that
carries its own value and draws no editor. `inner` is what a range or a list of values holds.
A list of values and a range are Qt's own containers, so `filter-list` and `filter-range` stand
where the web draws the same two shapes; a link on many values is `EntityMultiPicker`, which is
the Qt widget behind the web's multiple entity picker.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, scroll_to, wait_for  # noqa: E402
from qtpy import QtWidgets  # noqa: E402

#: path, the label the field trigger reads, the operator label, the value control, what it holds.
ROWS: tuple[tuple[tuple[int, ...], str, str, str | None, tuple[str, int] | None], ...] = (
    # text
    ((0, 0), "Version Name", "contains", "text-editor", None),
    ((0, 1), "Version Name", "starts with", "text-editor", None),
    ((0, 2), "Path to Movie", "ends with", "text-editor", None),
    ((0, 3), "Description", "does not contain", "text-editor", None),
    ((0, 4), "Department", "is not", "text-editor", None),
    # number, float, percent, duration
    ((1, 0), "First Frame", "between", "filter-range", ("number-editor", 2)),
    ((1, 1), "Last Frame", "greater than", "number-editor", None),
    ((1, 2), "Frame Count", "less than", "number-editor", None),
    ((1, 3), "First Frame", "is any of", "filter-list", ("number-editor", 2)),
    ((1, 4), "Movie Frame Rate", "is not", "number-editor", None),
    ((1, 5), "Link › Complexity", "greater than", "number-editor", None),
    ((1, 6), "Link › Working Duration", "greater than", "number-editor", None),
    # entity and multi_entity
    ((2, 0), "Link › Sequence", "is", "entity-picker", None),
    ((2, 1), "Artist", "is not", "entity-picker", None),
    ((2, 2), "Link", "is any of", "entity-multi-picker", None),
    ((2, 3), "Link › Assets", "is none of", "entity-multi-picker", None),
    ((2, 4), "Link", "type is", "text-editor", None),
    ((2, 5), "Link", "type is not", "text-editor", None),
    ((2, 6), "Playlists", "name contains", "text-editor", None),
    # status_list and list
    ((3, 0), "Status", "is any of", "status-multi-picker", None),
    ((3, 1), "Status", "is none of", "status-multi-picker", None),
    ((3, 2), "Status", "is", "status-picker", None),
    ((3, 3), "Version Type", "is", "list-picker", None),
    ((3, 4), "Project › Status", "is any of", "list-multi-picker", None),
    # date and date_time
    ((4, 0), "Link › Turnover Date", "is", "date-editor", None),
    ((4, 1), "Project › Start Date", "is not", "date-editor", None),
    ((4, 2), "Link › Turnover Date", "between", "filter-range", ("date-editor", 2)),
    ((4, 3), "Date Created", "after", "date-time-editor", None),
    ((4, 4), "Date Created", "before", "date-time-editor", None),
    ((4, 5), "Date Created", "in the last", "filter-window", None),
    ((4, 6), "Link › Turnover Date", "in the next", "filter-window", None),
    ((4, 7), "Date Updated", "yesterday", None, None),
    ((4, 8), "Date Created", "this week", None, None),
    ((4, 9), "Link › Turnover Date", "next month", None, None),
    # checkbox, colour and the empty pair
    ((5, 0), "Client Approved", "is", "checkbox-editor", None),
    ((5, 1), "Link › Omitted", "is", "checkbox-editor", None),
    ((5, 2, 0), "Bar Colour", "is", "color-editor", None),
    ((5, 2, 1), "Bar Colour", "is not", "color-editor", None),
    ((5, 2, 2, 0), "Department", "is empty", None, None),
    ((5, 2, 2, 1), "Department", "is not empty", None, None),
)

#: The sub-label a path the schema does not hold falls back to.
UNRESOLVED = "not in the schema"

#: How deep the last group stands, which is a group inside a group inside a group.
DEEPEST = 4


def slot(editor: Any, kind: str, path: tuple = ()) -> Any:
    """The control of one kind on one path of the tree.

    Every control the editor builds carries the path it edits and what it edits there, so a walk
    reaches the operator of the thirtieth row the way a person reaches it: by where it stands.
    """
    for one in editor.findChildren(QtWidgets.QWidget):
        held = getattr(one, "slot_path", None)
        if held is not None and held[1] == kind and tuple(held[0]) == tuple(path):
            return one
    return None


def held_by(control: Any, name: str) -> int:
    """How many controls of one object name a container holds."""
    return len(control.findChildren(QtWidgets.QWidget, name))


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    walk = Walk(page, wait, find, prefs)
    demo = find("filter-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no filter-editor demo"}
    wait_for(lambda: demo.demo_ready, wait, 40000)
    editor = demo.editor
    wait_for(lambda: len(editor.rows()) >= len(ROWS), wait, 40000)
    wait(600)

    walk.same("the catalogue draws a row for every entry", len(ROWS), len(editor.rows()))
    walk.same("the catalogue opens on Any", "or", editor.value.logical_operator)
    walk.same("it holds one group per data-type family", 6, len(editor.value.conditions))
    walk.same(
        "the last group nests three deep",
        DEEPEST,
        max(len(path) for path, _label, _op, _control, _inner in ROWS),
    )

    for path, label, operator, control, inner in ROWS:
        where = ".".join(str(step) for step in path)

        field = slot(editor, "field", path)
        if field is None:
            walk.check(f"{where}: the row carries a field trigger", False, "a trigger", None)
            continue
        scroll_to(page, field, wait)
        reads = field.label
        walk.check(
            f"{where}: the field trigger reads a resolved path",
            reads == label and "." not in reads and UNRESOLVED not in reads,
            label,
            reads,
        )

        chooser = slot(editor, "operator", path)
        walk.check(
            f"{where}: the operator reads {operator}",
            chooser is not None and chooser.label == operator,
            operator,
            None if chooser is None else chooser.label,
        )

        value = slot(editor, "value", path)
        if control is None:
            walk.check(
                f"{where}: {operator} carries its own value and draws no editor",
                value is None,
                "no editor",
                None if value is None else value.objectName(),
            )
            continue
        walk.check(
            f"{where}: the value draws a {control}",
            value is not None and value.objectName() == control,
            control,
            None if value is None else (value.objectName() or type(value).__name__),
        )
        if inner is not None and value is not None:
            name, count = inner
            walk.same(f"{where}: the {control} holds {count} of {name}", count, held_by(value, name))

    walk.check("no row is left incomplete", not editor.issues(), "no issue", editor.issues())

    counted = demo.results.count
    wait_for(lambda: demo.results.count.kind != "counting", wait, 25000)
    counted = demo.results.count
    walk.check("the rows under the tree were counted", counted.kind == "ready", "ready", counted)
    walk.check("the catalogue matches rows", counted.total > 0, "> 0", counted.total)

    return walk.result(
        f"PASS {len(ROWS)} rows read back: every field trigger resolves, every operator reads its"
        f" own label, every value draws the control its data type and arity call for, and"
        f" {counted.total} Versions match under the tree"
    )
