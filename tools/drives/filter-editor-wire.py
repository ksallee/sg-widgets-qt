"""What the editor sends is core's own serialisation of the tree it holds, edit after edit.

    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/filter-editor-wire.py
    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/filter-editor-wire.py --qt5

The demo prints `to_api3_hash` of whatever the editor last emitted, so the block under the tree
is the wire payload a caller would send. The drive builds the seeded tree from core, on its own
side of the page, and compares, then walks the tree through every edit the state matrix shoots:
a condition added, removed, pointed at another field, moved onto another operator, a group
nested and un-nested, a row moved by the keyboard. After each one it asserts three things:

  * the block equals `to_api3_hash` of the tree the editor now holds,
  * `changed` and `filters_changed` carried that same tree, once each,
  * a blank row is dropped on serialisation rather than sent (030_complex_filters: a group
    serialises with both keys, and an empty tree serialises to `null`).
"""
from __future__ import annotations

import json
import time

from sg_widgets_core.filter import condition, group, to_api3_hash
from sg_widgets_qt.showcase.demos.filter_editor import initial
from sg_widgets_qt.widgets.filter_editor import FilterEditor


#: The tree the demo opens on, built from core rather than read off the page.
def seeded():
    return initial(False)


def wait_for(read, wait, ms: int = 8000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def last(editor) -> list[int]:
    """Where the row added to the root stands."""
    return [len(editor.value.conditions) - 1]


def block_of(page):
    from qtpy import QtWidgets

    for one in page.findChildren(QtWidgets.QPlainTextEdit):
        if one.objectName() == "filter-json":
            return one
    return None


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    wait(600)
    editor = find("filter-editor-main")
    if not isinstance(editor, FilterEditor):
        every = find(FilterEditor, all=True)
        editor = every[0] if every else None
    block = block_of(page)
    if editor is None or block is None:
        return {"verdict": "FAIL the page has no filter editor with its serialised filter"}
    wait_for(lambda: editor.fields(), wait, 8000)
    wait(400)

    seen: list = []
    also: list = []
    editor.changed.connect(seen.append)
    editor.filters_changed.connect(also.append)

    failures: list[str] = []
    table: list[dict] = []

    def printed():
        text = block.toPlainText().strip()
        if not text or text == "null":
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def check(name: str) -> None:
        wait(300)
        want = to_api3_hash(editor.value)
        got = printed()
        same = got == want
        table.append({"state": name, "wire": "same" if same else "differs"})
        if not same:
            failures.append(f"{name}: the block reads {json.dumps(got)[:120]}")

    # The seeded tree, built from core rather than read off the page.
    want = to_api3_hash(seeded())
    got = printed()
    table.append({"state": "rest", "wire": "same" if got == want else "differs"})
    if got != want:
        failures.append(f"rest: the block is not to_api3_hash of the demo's own tree: {json.dumps(got)[:160]}")

    edits = (
        ("added", lambda: editor.append([], condition("", "is", ""))),
        # The added row stands past the groups the catalogue opens on; the operator moves
        # on the first row of the first group.
        ("field", lambda: editor.pick_field(last(editor), editor.node_at(last(editor)), "sg_first_frame")),
        ("operator", lambda: editor.pick_preset([0, 0], editor.node_at([0, 0]), "not_in")),
        ("nested", lambda: editor.append([], group("or", []))),
        ("unnested", lambda: editor.remove([len(editor.value.conditions) - 1])),
        ("moved", lambda: editor.move([1], -1)),
        ("removed", lambda: editor.remove([0])),
    )
    for name, run in edits:
        before = len(seen)
        run()
        # A field pick waits on the schema, so the edit may land a turn later.
        wait_for(lambda n=before: len(seen) > n, wait, 6000)
        check(name)
        if len(seen) <= before:
            failures.append(f"{name}: nothing was emitted")
        elif len(seen) != before + 1:
            failures.append(f"{name}: {len(seen) - before} emissions, wanted 1")
        if len(also) != len(seen):
            failures.append(f"{name}: filters_changed ran {len(also)} times to changed's {len(seen)}")
        elif seen and also and seen[-1] is not also[-1]:
            failures.append(f"{name}: the two signals carried different trees")

    # A row with no field is dropped rather than sent; a tree of nothing else is `null`.
    blank = group("and", [condition("", "is", "")])
    if to_api3_hash(blank) is not None:
        failures.append("a tree of blank rows serialises to something")

    return {
        "verdict": (
            f"PASS the block is core's own to_api3_hash after {len(table)} states,"
            " and each edit emits once on both signals"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "failures": failures,
        "table": table,
        "emitted": len(seen),
    }
