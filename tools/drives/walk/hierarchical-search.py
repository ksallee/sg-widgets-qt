"""hierarchical-search: walk a level, walk back out, search the tree, and read the path a pick carries.

    .venv/bin/python tools/qa.py --page hierarchical-search \
        --drive tools/drives/walk/hierarchical-search.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    arm,
    click_row,
    key,
    orphans,
    scroll_to,
    type_into,
    wait_for,
    wear,
)
from qtpy import QtCore, QtWidgets  # noqa: E402


def settled(tree, wait) -> bool:
    return wait_for(lambda: not tree.search_control().loading, wait)


def rows_of(tree) -> list:
    model = tree.search_control().list_surface().model()
    return [model.index(row, 0) for row in range(model.rowCount())]


def first_child_row(tree) -> int:
    """The first row that opens a level of its own."""
    control = tree.search_control()
    for row in range(control.list_surface().row_count()):
        found = tree._model.row_at(row)
        if getattr(found, "has_children", False) and not getattr(found, "up", False):
            return row
    return -1


def first_leaf_row(tree) -> int:
    control = tree.search_control()
    for row in range(control.list_surface().row_count()):
        found = tree._model.row_at(row)
        if getattr(found, "selectable", False) and getattr(found, "ref", None) is not None:
            return row
    return -1


def path_text(page) -> str:
    holder = page.findChild(QtWidgets.QWidget, "demo-picked")
    if holder is None:
        return ""
    parts = []
    for child in holder.findChildren(QtWidgets.QWidget):
        text = getattr(child, "text", None)
        if callable(text):
            parts.append(str(text()))
        elif isinstance(text, str):
            parts.append(text)
    return " ".join(part for part in parts if part)


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    arm(page, wait)
    tree = find("hierarchical-search")
    control = tree.search_control()
    scroll_to(page, tree, wait)
    settled(tree, wait)

    walk.check("tree: the project's own level is listed", control.list_surface().row_count() > 0, "> 0", control.list_surface().row_count())
    walk.check("tree: it stands on the project it is scoped to", tree.level_path.endswith("/70") or "/Project/" in tree.level_path, "/Project/70", tree.level_path)
    walk.check("tree: nothing is selected yet", "Nothing selected" in path_text(page), "Nothing selected yet.", path_text(page))

    # --- walk a level with the mouse ------------------------------------------------------
    row = first_child_row(tree)
    walk.check("tree: a row that opens a level is offered", row >= 0, "a row", row)
    if row >= 0:
        before = tree.level_path
        walk.check("tree: a press on it opens the level", click_row(control.list_surface(), row), True, False)
        settled(tree, wait)
        wait(400)
        walk.check("tree: the level moved", tree.level_path != before, f"not {before}", tree.level_path)
        walk.check("tree: the new level lists its own rows", control.list_surface().row_count() > 0, "> 0", control.list_surface().row_count())

        # Left walks back out.
        deep = tree.level_path
        key(control.input(), QtCore.Qt.Key.Key_Left)
        settled(tree, wait)
        wait(400)
        walk.same("tree: Left walks back out of the level", before, tree.level_path)

        # Right walks in from the keyboard.
        control.list_surface().set_highlight(row)
        key(control.input(), QtCore.Qt.Key.Key_Right)
        settled(tree, wait)
        wait(400)
        walk.same("tree: Right walks into the level under the cursor", deep, tree.level_path)

    # --- pick a leaf, and read the path it carries -------------------------------------------
    leaf = first_leaf_row(tree)
    if leaf < 0:
        # A level of folders: walk one more in, where the leaves are.
        row = first_child_row(tree)
        if row >= 0:
            click_row(control.list_surface(), row)
            settled(tree, wait)
            wait(400)
            leaf = first_leaf_row(tree)
    walk.check("tree: a leaf is reachable", leaf >= 0, "a leaf", leaf)
    if leaf >= 0:
        walk.check("tree: the leaf is picked with the mouse", click_row(control.list_surface(), leaf), True, False)
        wait(500)
        shown = path_text(page)
        walk.check(
            "tree: the line under the list carries the path it ran through",
            "leaf " in shown,
            "the path and its leaf",
            shown,
        )
        walk.check("tree: nothing is left standing", not orphans(), [], orphans())

    # --- search the tree ------------------------------------------------------------------------
    type_into(control.input(), "sh010", wait)
    settled(tree, wait)
    wait(300)
    walk.check("search: the query answers rows", len(control.items) > 0, "> 0", len(control.items))
    walk.check("search: a query owns the list rather than the level", tree.searching, True, tree.searching)
    from sg_widgets_qt.primitives.roles import Roles

    model = control.list_surface().model()
    hit = next(
        (row for row in range(model.rowCount()) if model.index(row, 0).data(Roles.KIND) != "heading"),
        -1,
    )
    walk.check("search: the results stand under a heading", hit > 0, "> 0", hit)
    index = model.index(hit, 0)
    walk.check(
        "search: a result names the path it sits on",
        len([run for run in (index.data(Roles.RUNS) or []) if run[2]]) > 0,
        "the crumbs before the label",
        index.data(Roles.RUNS),
    )
    walk.check(
        "search: and what kind of row it is",
        bool(index.data(Roles.SUB_LABEL)),
        "a type",
        index.data(Roles.SUB_LABEL),
    )
    shown = path_text(page)
    walk.check("search: a result is picked", click_row(control.list_surface(), hit), True, False)
    wait(500)
    walk.check(
        "search: the pick answers a path of its own",
        path_text(page) != shown,
        f"not {shown}",
        path_text(page),
    )

    control.input().clear()
    settled(tree, wait)
    wait(300)
    walk.check("search: clearing the query gives the level back", not tree.searching, False, tree.searching)

    # A query nothing answers draws the empty line.
    type_into(control.input(), "zzzqqq", wait)
    wait_for(lambda: not control.loading and control.view == "empty", wait)
    walk.same("search: a query nothing matches draws the empty line", "empty", control.view)
    control.input().clear()
    settled(tree, wait)

    # --- the header ---------------------------------------------------------------------------------
    wear(prefs, wait, theme="dark")
    walk.same("header: the page wears dark", "dark", prefs.theme)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1400)
    rebuilt = find("hierarchical-search")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the tree wears the size step", "lg", rebuilt.size)
        scroll_to(page, rebuilt, wait)
        settled(rebuilt, wait)
        walk.check(
            "header: the rebuilt tree still lists its level",
            rebuilt.search_control().list_surface().row_count() > 0,
            "> 0",
            rebuilt.search_control().list_surface().row_count(),
        )
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1400)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
