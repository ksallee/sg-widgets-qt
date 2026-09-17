"""The entity-tree page, walked the way a reader walks it.

Open Assets against the open count, a chevron opening a branch that was never read, a node and
its children checked against the checked count, a leaf picked and reported, the arrows with
Home, End, Space and Enter, the search narrowing the tree and clearing it, and the loose project
whose shots sit under no sequence.

    .venv/bin/python tools/qa.py --headed --page entity-tree --drive tools/drives/walk/entity-tree.py

A popup dismissing, the focus and the wheel's owner are what a real window decides, so
this drive is run headed; offscreen is for the unit tests.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _walk import Walk, press, stage, wait_until  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

Qt = QtCore.Qt

#: What the mock's own hierarchy holds, and the shot the first tree opens onto.
SEQUENCE = "/Shot/sg_sequence/Sequence/100"
OTHER = "/Shot/sg_sequence/Sequence/101"
QUERY = "sh020_0030"


def paths(tree) -> list[str]:
    return [row.node.path for row in tree.snapshot().rows]


def hit(tree, path: str, where: str) -> QtCore.QPoint:
    rect = tree.view.visualRect(tree.model.index_of(path))
    if where == "chevron":
        return tree._delegate.chevron_rect(rect).center()
    if where == "box":
        return tree._delegate.checkbox_rect(rect).center()
    return QtCore.QPoint(rect.right() - 20, rect.center().y())


def node_press(tree, path: str, where: str) -> None:
    QTest.mouseClick(
        tree.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        hit(tree, path, where),
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    walk = Walk("entity-tree")
    demo = stage(page, "entity-tree")
    if demo is None:
        return {"verdict": "FAIL the page built no entity-tree demo"}
    tree = demo.tree
    if not wait_until(lambda: demo.demo_ready, wait, 30000):
        return {"verdict": "FAIL a tree never settled"}
    rest = lambda: wait_until(lambda: not tree.binding.busy, wait, 10000)  # noqa: E731
    root = tree.root_path
    wait(200)

    walk.check(
        "the tree opens onto the path it was seeded with",
        root + SEQUENCE in tree.expanded,
        tree.expanded,
    )
    walk.check(
        "and the open count says how many branches stand open",
        demo._open_count.text() == f"{len(tree.expanded)} open",
        demo._open_count.text(),
    )

    # --- Open Assets --------------------------------------------------------------------
    press(find("open-assets"))
    rest()
    wait(400)
    walk.check(
        "Open Assets expands to that path and reads its children",
        root + "/Asset" in tree.expanded
        and any(one.startswith(root + "/Asset/") for one in paths(tree)),
        demo._open_count.text(),
    )

    # --- a chevron ------------------------------------------------------------------------
    node_press(tree, root + SEQUENCE, "chevron")
    rest()
    wait(300)
    walk.check(
        "the chevron shuts an open branch",
        root + SEQUENCE not in tree.expanded,
        demo._open_count.text(),
    )
    node_press(tree, root + SEQUENCE, "chevron")
    rest()
    wait(300)
    walk.check("and opens it again", root + SEQUENCE in tree.expanded, demo._open_count.text())

    held = len(paths(tree))
    node_press(tree, root + OTHER, "chevron")
    rest()
    wait(400)
    walk.check(
        "a branch never read before is read when it opens",
        len(paths(tree)) > held and any(one.startswith(root + OTHER + "/") for one in paths(tree)),
        f"{held} -> {len(paths(tree))} rows",
    )

    # --- the boxes --------------------------------------------------------------------------
    children = [one for one in paths(tree) if one.startswith(root + OTHER + "/")]
    node_press(tree, root + OTHER, "box")
    rest()
    wait(300)
    walk.check(
        "checking a branch checks its children with it",
        len(tree.checked_refs()) >= len(children)
        and demo._checked.text() == f"{len(tree.checked_refs())} checked",
        demo._checked.text(),
    )
    node_press(tree, root + OTHER, "box")
    rest()
    wait(300)
    walk.check(
        "unchecking it drops them again",
        not tree.checked_refs() and demo._checked.text() == "0 checked",
        demo._checked.text(),
    )

    # --- a leaf -----------------------------------------------------------------------------
    shot = next((one for one in paths(tree) if one.startswith(root + SEQUENCE + "/id/")), "")
    tree.set_expanded([*tree.expanded, shot])
    rest()
    wait(400)
    under = next((one for one in paths(tree) if one.endswith("/Task")), "")
    tree.set_expanded([*tree.expanded, under])
    rest()
    wait(500)
    leaf = next((one for one in paths(tree) if one.startswith(under + "/")), "")
    if walk.check("a shot opens onto its Tasks", bool(leaf), leaf):
        node_press(tree, leaf, "row")
        rest()
        wait(300)
        walk.check(
            "a press on a leaf reports what was picked",
            demo._picked.text() == tree.model.row_of(leaf).node.label,
            demo._picked.text(),
        )
        demo._picked.set_text("nothing selected")
        tree.view.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(tree.view, Qt.Key.Key_Enter)
        wait(300)
        walk.check(
            "Enter on a leaf reports it too",
            demo._picked.text() != "nothing selected",
            demo._picked.text(),
        )

    # --- the keyboard --------------------------------------------------------------------------
    tree.view.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(tree.view, Qt.Key.Key_Home)
    wait(200)
    walk.check("Home goes to the first node", tree.snapshot().cursor == root, tree.snapshot().cursor)
    QTest.keyClick(tree.view, Qt.Key.Key_Down)
    wait(200)
    walked = tree.snapshot().cursor
    walk.check("Down goes to the next node on show", walked != root, walked)
    QTest.keyClick(tree.view, Qt.Key.Key_Up)
    wait(200)
    walk.check("Up comes back", tree.snapshot().cursor == root, tree.snapshot().cursor)
    QTest.keyClick(tree.view, Qt.Key.Key_End)
    wait(200)
    walk.check(
        "End goes to the last node on show",
        tree.snapshot().cursor == paths(tree)[-1],
        tree.snapshot().cursor,
    )
    QTest.keyClick(tree.view, Qt.Key.Key_Space)
    rest()
    wait(300)
    walk.check(
        "Space checks the node under the cursor",
        bool(tree.checked_refs()) and demo._checked.text() != "0 checked",
        demo._checked.text(),
    )
    QTest.keyClick(tree.view, Qt.Key.Key_Space)
    rest()
    wait(300)
    walk.check("and Space again unchecks it", not tree.checked_refs(), demo._checked.text())

    # --- the search ---------------------------------------------------------------------------
    whole = len(paths(tree))
    tree.set_search(QUERY)
    wait(900)
    rest()
    wait(400)
    marked = [row.node.label for row in tree.snapshot().rows if row.match]
    walk.check(
        "the search places the match, opens the branches over it and marks it",
        QUERY in marked and root + SEQUENCE.rsplit("/", 1)[0] + "/101" in tree.expanded,
        f"{whole} -> {len(paths(tree))} rows, marked {marked}",
    )
    tree.set_search("")
    wait(600)
    rest()
    wait(300)
    walk.check(
        "clearing the search restores the tree, with nothing marked",
        len(paths(tree)) > 1 and not any(row.match for row in tree.snapshot().rows),
        len(paths(tree)),
    )

    # --- the loose project ---------------------------------------------------------------------
    loose = demo.loose
    wait_until(lambda: loose.snapshot().status in ("ready", "error") and not loose.binding.busy, wait)
    walk.check(
        "the loose project draws its shots under no sequence",
        bool(paths(loose)),
        len(paths(loose)),
    )

    # --- the view controls ----------------------------------------------------------------------
    for name, value in (("theme", "dark"), ("size", "lg"), ("density", "compact"), ("motion", "reduced")):
        prefs.set(name, value)
        wait(120)
    wait(300)
    walk.check(
        "the header's view controls leave the page standing",
        tree.snapshot().status in ("ready", "error") and bool(paths(tree)),
        f"{len(paths(tree))} rows",
    )
    return walk.verdict("Open Assets, the chevrons, the boxes, the keyboard and the search")
