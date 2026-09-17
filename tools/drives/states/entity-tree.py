"""The entity tree's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/entity-tree-<state>.js`, run against
`/widgets/entity-tree/`.

    QA_STATE=searched .venv/bin/python tools/qa.py --page entity-tree \\
        --drive tools/drives/states/entity-tree.py --shot shots/states/entity-tree-searched.png

    rest       the tree as `seed_path` left it, open down to one shot
    expanded   the Shots folder and one sequence under it, two levels by keyboard
    searched   a server search, the hit marked and everything else dimmed
    checked    a branch checked, its children with it and the parent of one mixed
    to-path    `expand_to_path` walked from a shut tree to a shot four levels down
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _collection_states import (  # noqa: E402
    frame,
    images_settled,
    stage_widget,
    state_name,
    wait_for,
)

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = ("rest", "expanded", "searched", "checked", "to-path")

#: What the demo seeds the tree open to, under the project root.
SEED = "/Shot/sg_sequence/Sequence/100/id/862"

#: What the search box is given, which the mock answers with one shot.
QUERY = "sh030_0020"


def snapshot(tree):
    return tree.snapshot()


def described(tree) -> dict:
    state = snapshot(tree)
    return {
        "name": tree.objectName() or "entity-tree",
        "status": state.status,
        "nodes": len(state.rows),
        "paths": [row.node.path for row in state.rows][:12],
        "search": state.search,
        "matches": len(state.matches),
        "cursor": state.cursor,
        "checked": len(tree.checked_refs()),
    }


def rows_of(tree) -> list:
    return list(snapshot(tree).rows)


def path_row(tree, ending: str):
    return next((row for row in rows_of(tree) if row.node.path.endswith(ending)), None)


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    state = state_name(STATES, "rest")
    wait(200)
    holder = stage_widget(page, "entity-tree")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-tree demo"}
    tree = holder.tree
    if not wait_for(lambda: rows_of(tree), wait):
        return {"verdict": "FAIL the tree read no level"}
    if not wait_for(lambda: path_row(tree, SEED) is not None, wait):
        return {"verdict": f"FAIL seed_path did not open the tree to {SEED}"}
    images_settled(wait)
    frame(page, wait, "entity-tree")

    if state == "expanded":
        # Shut the seeded branch, then open two levels again through the engine's own keys.
        folder = path_row(tree, "/Shot")
        if folder is None:
            return {"verdict": "FAIL the tree has no Shots folder"}
        tree.set_expanded([])
        wait_for(lambda: len(rows_of(tree)) <= 3, wait)
        tree.binding.run("expand", folder.node.path)
        if not wait_for(lambda: any("/Sequence/" in r.node.path for r in rows_of(tree)), wait):
            return {"verdict": "FAIL opening the Shots folder read no sequence"}
        branch = next(r for r in rows_of(tree) if "/Sequence/" in r.node.path)
        tree.binding.run("expand", branch.node.path)
        if not wait_for(
            lambda: any(r.node.path.startswith(branch.node.path + "/id/") for r in rows_of(tree)),
            wait,
        ):
            return {"verdict": "FAIL the second level read no shot"}

    elif state == "searched":
        before = len(rows_of(tree))
        tree.set_search(QUERY)
        if not wait_for(lambda: snapshot(tree).matches, wait):
            return {"verdict": f"FAIL the search for {QUERY!r} placed no hit"}
        hit = next(
            (row for row in rows_of(tree) if row.node.path in snapshot(tree).matches), None
        )
        if hit is None:
            return {"verdict": "FAIL the hit is not on the visible list"}
        if len(rows_of(tree)) <= 0:
            return {"verdict": f"FAIL the search left {len(rows_of(tree))} nodes from {before}"}

    elif state == "checked":
        branch = next((r for r in rows_of(tree) if "/Sequence/" in r.node.path), None)
        if branch is None:
            return {"verdict": "FAIL the seeded tree drew no sequence"}
        tree.binding.run("set_checked", branch.node.path, True)
        if not wait_for(lambda: tree.checked_refs(), wait):
            return {"verdict": "FAIL checking the branch checked nothing"}
        leaves = [r for r in rows_of(tree) if r.node.path.startswith(branch.node.path + "/id/")]
        if not leaves:
            return {"verdict": "FAIL the branch holds no leaf to spread to"}
        tree.binding.run("set_checked", leaves[0].node.path, False)
        wait(400)
        mixed = next((r for r in rows_of(tree) if r.node.path == branch.node.path), None)
        if mixed is None or mixed.checked != "mixed":
            return {
                "verdict": f"FAIL the branch reads {None if mixed is None else mixed.checked!r}"
            }

    elif state == "to-path":
        tree.set_expanded([])
        wait_for(lambda: len(rows_of(tree)) <= 3, wait)
        shut = len(rows_of(tree))
        tree.binding.run("expand_to_path", tree.root_path + SEED)
        if not wait_for(lambda: path_row(tree, SEED) is not None, wait):
            return {"verdict": f"FAIL expand_to_path left {len(rows_of(tree))} nodes from {shut}"}
        landed = path_row(tree, SEED)
        # `node.level` counts from the root at 0, which is the `aria-level` upstream reads
        # as 4 (`aria-level={node.level + 1}`).
        if landed.node.level != 3:
            return {"verdict": f"FAIL the shot sits at level {landed.node.level}, expected 3"}

    wait(300)
    return {
        "verdict": f"PASS {state}",
        "state": state,
        "trees": [described(tree), described(holder.loose), described(holder.pictures)],
    }
