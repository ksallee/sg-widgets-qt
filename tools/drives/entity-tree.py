"""The port of `~/dev/sg-widgets/tools/drives/entity-tree.js`.

Seed, two levels by keyboard, checkbox propagation, type-ahead, the search, `*` and the bucket.

    .venv/bin/python tools/qa.py --page entity-tree --drive tools/drives/entity-tree.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

import re  # noqa: E402

from _collection_states import stage_widget, wait_for  # noqa: E402
from qtpy import QtCore, QtGui  # noqa: E402

SEED = "/Shot/sg_sequence/Sequence/100/id/862"


def rows(tree) -> list:
    return list(tree.snapshot().rows)


def at(tree, ending: str):
    return next((row for row in rows(tree) if row.node.path.endswith(ending)), None)


def cursor(tree) -> str:
    return tree.snapshot().cursor or ""


def press(tree, code, text: str = "") -> None:
    tree.on_key(
        QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress, int(code), QtCore.Qt.KeyboardModifier.NoModifier, text
        )
    )


def type_ahead(tree, word: str, wait) -> None:
    for letter in word:
        press(tree, QtCore.Qt.Key.Key_A, letter)
        wait(40)


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-tree")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-tree demo"}
    tree = holder.tree
    if not wait_for(lambda: rows(tree), wait):
        return {"verdict": "FAIL the tree rendered no nodes", "notes": notes}
    if not wait_for(lambda: at(tree, SEED) is not None, wait):
        return {"verdict": "FAIL seed_path did not open the tree to the shot", "notes": notes}
    seeded = at(tree, SEED)
    if seeded.node.level != 3:
        return {"verdict": f"FAIL the seeded shot sits at level {seeded.node.level}", "notes": notes}
    notes.append(f"seed_path opened {len(rows(tree))} nodes down to {seeded.node.label!r} at level 4")

    # Shut the seeded branch, then open two levels with the keyboard alone.
    tree.set_expanded([])
    wait_for(lambda: len(rows(tree)) <= 3, wait)
    shut = len(rows(tree))
    if shut != 3:
        return {"verdict": f"FAIL collapsing left {shut} nodes, expected 3", "notes": notes}

    tree.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    press(tree, QtCore.Qt.Key.Key_Home)
    wait(200)
    for _ in range(2):
        press(tree, QtCore.Qt.Key.Key_Down)
        wait(200)
    if not cursor(tree).endswith("/Shot"):
        return {"verdict": f"FAIL ArrowDown landed on {cursor(tree)}", "notes": notes}
    press(tree, QtCore.Qt.Key.Key_Right)
    if not wait_for(lambda: any("/Sequence/" in row.node.path for row in rows(tree)), wait):
        return {"verdict": "FAIL opening the Shots folder read no sequence", "notes": notes}
    press(tree, QtCore.Qt.Key.Key_Right)
    wait(300)
    if "/Sequence/" not in cursor(tree):
        return {"verdict": f"FAIL the second ArrowRight landed on {cursor(tree)}", "notes": notes}
    branch = cursor(tree)
    press(tree, QtCore.Qt.Key.Key_Right)
    if not wait_for(
        lambda: any(row.node.path.startswith(branch + "/id/") for row in rows(tree)), wait
    ):
        return {"verdict": "FAIL expanding the sequence by keyboard produced no shots", "notes": notes}
    leaves = [row for row in rows(tree) if row.node.path.startswith(branch + "/id/")]
    notes.append(f"two levels by keyboard: the sequence holds {len(leaves)} shots")

    # Space checks the branch the cursor sits on, and every child under it reads checked.
    tree.binding.run("focus", branch)
    wait(200)
    press(tree, QtCore.Qt.Key.Key_Space)
    if not wait_for(lambda: at(tree, branch) and at(tree, branch).checked != "unchecked", wait):
        return {"verdict": "FAIL Space checked nothing", "notes": notes}
    unchecked = [
        row.node.path
        for row in rows(tree)
        if row.node.path.startswith(branch + "/id/") and row.checked != "checked"
    ]
    if unchecked:
        return {"verdict": f"FAIL {len(unchecked)} children stayed unchecked", "notes": notes}
    notes.append(f"checking the branch checked all {len(leaves)} children")

    # Unchecking one child leaves the branch mixed.
    one = leaves[0].node.path
    tree.binding.run("set_checked", one, False)
    if not wait_for(lambda: at(tree, branch) and at(tree, branch).checked == "mixed", wait):
        return {
            "verdict": f"FAIL the branch reads {at(tree, branch).checked!r}, expected mixed",
            "notes": notes,
        }
    notes.append(f"unchecking one shot left the branch mixed; the demo reports {holder._checked.text()!r}")

    # Type-ahead walks the labels of the visible list.
    tree.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    press(tree, QtCore.Qt.Key.Key_Home)
    wait(200)
    wanted = leaves[1].node.label
    type_ahead(tree, wanted, wait)
    wait(400)
    landed = at(tree, cursor(tree))
    if landed is None or landed.node.label != wanted:
        return {
            "verdict": f"FAIL type-ahead landed on {None if landed is None else landed.node.label!r}, "
            f"expected {wanted!r}",
            "notes": notes,
        }
    notes.append(f"type-ahead reached {wanted}")

    # `*` opens every branch at the focus level.
    tree.binding.run("focus", branch)
    wait(300)
    # A sequence is a node whose path *ends* in one, not every shot under one.
    def level() -> list:
        return [row for row in rows(tree) if re.search(r"/Sequence/\d+$", row.node.path)]
    shut_before = [row for row in level() if not row.expanded]
    nodes_before = len(rows(tree))
    press(tree, QtCore.Qt.Key.Key_Asterisk, "*")
    if not wait_for(
        lambda: all(row.expanded for row in level()) and len(rows(tree)) > nodes_before, wait, 30000
    ):
        still = [row.node.path for row in level() if not row.expanded]
        return {"verdict": f"FAIL * left {len(still)} of {len(level())} sequences shut", "notes": notes}
    notes.append(f"* opened {len(shut_before)} shut sequences, {nodes_before} nodes to {len(rows(tree))}")

    # The search asks the server, opens the tree onto the hit and marks it.
    tree.set_expanded([])
    wait_for(lambda: len(rows(tree)) <= 3, wait)
    shut_again = len(rows(tree))
    tree.set_search("sh030_0020")
    if not wait_for(lambda: tree.snapshot().matches, wait):
        return {"verdict": f"FAIL the search opened {len(rows(tree))} nodes and placed no hit", "notes": notes}
    marked = [row for row in rows(tree) if row.match]
    dimmed = [row for row in rows(tree) if not row.match]
    if not marked or not dimmed:
        return {"verdict": f"FAIL {len(marked)} marked and {len(dimmed)} dimmed", "notes": notes}
    notes.append(
        f"searching opened {shut_again} nodes to {len(rows(tree))}, marked {len(marked)} and dimmed {len(dimmed)}"
    )

    # Clearing puts the tree back as it was.
    tree.set_search("")
    if not wait_for(lambda: len(rows(tree)) == shut_again, wait):
        return {"verdict": f"FAIL clearing the search left {len(rows(tree))} nodes, expected {shut_again}", "notes": notes}
    notes.append("clearing the search restored the expansion it opened onto")

    # A project whose shots sit under no sequence answers them all the same.
    loose = holder.loose
    if not wait_for(lambda: rows(loose), wait):
        return {"verdict": "FAIL the second project read no level", "notes": notes}
    folder = at(loose, "/Shot")
    if folder is None:
        return {"verdict": "FAIL the second project has no Shots folder", "notes": notes}
    loose.binding.run("expand", folder.node.path)
    if not wait_for(lambda: any("__none__" in row.node.path for row in rows(loose)), wait):
        return {"verdict": "FAIL the ungrouped shots did not come back", "notes": notes}
    under = [row for row in rows(loose) if "__none__" in row.node.path]
    notes.append(f"a project with no sequences opened {len(under)} ungrouped nodes")

    # The thumbnail tree draws a thumbnail and a sub-label per row.
    shown = holder.pictures
    if not wait_for(lambda: rows(shown), wait):
        return {"verdict": "FAIL the thumbnail tree read no level", "notes": notes}
    assets = at(shown, "/Asset")
    if assets is None:
        return {"verdict": "FAIL the thumbnail tree has no Assets folder", "notes": notes}
    shown.binding.run("expand", assets.node.path)
    if not wait_for(
        lambda: any(row.node.path.startswith(assets.node.path + "/") for row in rows(shown)), wait
    ):
        return {"verdict": "FAIL the Assets folder read no level", "notes": notes}
    notes.append(f"with thumbnails on: {len(rows(shown))} nodes")

    return {
        "verdict": "PASS seed, keyboard levels, propagation, type-ahead, *, the search, the bucket and thumbnails",
        "notes": notes,
    }
