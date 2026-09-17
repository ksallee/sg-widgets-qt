"""The entity tree: its levels, its expansion, its search, its checkboxes and its keyboard.

Every test runs on both bindings, offscreen, and never reaches the network: the levels come from
the mock client's hierarchy.
"""
from __future__ import annotations

import gc
import time

import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_tree import ENTITY_TREE_INDENT, EntityTree
from sg_widgets_qt.widgets.state_line import StateLine

from .collections import mock_context, settle

#: The project the mock's hierarchy is built around.
ROOT = "/Project/70"


@pytest.fixture
def context():
    return mock_context()


def _tree(context, qtbot, **options) -> EntityTree:
    tree = EntityTree(context=context, root_path=options.pop("root_path", ROOT), **options)
    apply_theme(tree, theme_for("default"))
    qtbot.addWidget(tree)
    tree.resize(520, 420)
    tree.show()
    settle(tree, tree.binding)
    return tree


def _press(tree: EntityTree, key, text: str = "") -> bool:
    return tree.on_key(
        QKeyEvent(QtCore.QEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier, text)
    )


def test_the_root_reads_one_level_and_the_model_holds_it(context, qtbot):
    tree = _tree(context, qtbot)
    state = tree.snapshot()
    assert state.status == "ready"
    # `_expand` answers one level: the node, and the children under it.
    assert [row.node.path for row in state.rows][0] == ROOT
    assert len(state.rows) > 1
    assert tree.model.rowCount() == 1
    root = tree.model.index(0, 0)
    assert tree.model.rowCount(root) == len(state.rows) - 1
    assert tree.view.indentation() == ENTITY_TREE_INDENT
    assert tree.model.path_of(root) == ROOT
    assert root.data(Roles.LABEL)


def test_expanding_a_branch_reads_the_level_under_it(context, qtbot):
    tree = _tree(context, qtbot)
    folders = [row.node.path for row in tree.snapshot().rows if row.node.has_children]
    branch = next(path for path in folders if path != ROOT)
    before = len(tree.snapshot().rows)

    tree.binding.run("toggle", branch)
    settle(tree, tree.binding)
    assert branch in tree.snapshot().expanded
    assert len(tree.snapshot().rows) > before

    tree.binding.run("toggle", branch)
    settle(tree, tree.binding)
    assert branch not in tree.snapshot().expanded
    assert len(tree.snapshot().rows) == before


def test_expand_to_path_opens_the_tree_down_to_one_row(context, qtbot):
    seed = ROOT + "/Shot/sg_sequence/Sequence/100/id/862"
    tree = _tree(context, qtbot, seed_path=seed)
    settle(tree, tree.binding, rounds=8)
    paths = [row.node.path for row in tree.snapshot().rows]
    # The seed is followed by taking whichever child is a prefix of it, not by parsing it.
    assert any(path.startswith(ROOT + "/Shot") for path in paths)
    assert len(tree.snapshot().expanded) > 1


def test_a_search_marks_the_rows_the_words_found(context, qtbot):
    tree = _tree(context, qtbot, searchable=True)
    tree.binding.run("search", "sh020")
    settle(tree, tree.binding, rounds=8)
    state = tree.snapshot()
    assert state.search == "sh020"
    if state.matches:
        # The tree opens along every answered path and marks the rows the words found.
        marked = {row.node.path for row in state.rows if row.match}
        assert marked == set(state.matches)
    else:
        line = tree.findChild(StateLine, "entity-tree-no-match")
        assert line is not None

    tree.binding.run("search", "")
    settle(tree, tree.binding)
    assert tree.snapshot().search == ""


def test_a_checkbox_spreads_down_and_settles_upwards(context, qtbot):
    tree = _tree(context, qtbot, checkable=True)
    reported: list = []
    tree.checked_changed.connect(reported.append)
    branch = next(
        row.node.path for row in tree.snapshot().rows if row.node.has_children and row.node.path != ROOT
    )
    tree.binding.run("toggle", branch)
    settle(tree, tree.binding)

    tree.engine.toggle_checked(branch)
    settle(tree, tree.binding)
    assert branch in tree.snapshot().checked
    index = tree.model.index_of(branch)
    assert index.isValid()
    assert index.data(Roles.CHECKED) is True

    child = tree.engine.child_paths(branch)
    if child:
        # A branch that is checked checks its level, so a child left out reads `mixed`.
        tree.engine.set_checked(child[0], False)
        settle(tree, tree.binding)
        assert tree.engine.check_state_of(branch) in ("mixed", "unchecked")
    assert reported


def test_the_keyboard_model_is_the_engines_own(context, qtbot):
    tree = _tree(context, qtbot, checkable=True)
    tree.view.setFocus()
    assert tree.snapshot().cursor == ROOT
    assert _press(tree, Qt.Key.Key_Down) is True
    assert tree.snapshot().cursor != ROOT
    assert _press(tree, Qt.Key.Key_Up) is True
    assert tree.snapshot().cursor == ROOT
    # Right on a closed branch opens it; Left on an open one shuts it.
    second = [row.node.path for row in tree.snapshot().rows][1]
    tree.engine.focus(second)
    assert _press(tree, Qt.Key.Key_Right) is True
    settle(tree, tree.binding)
    assert second in tree.snapshot().expanded
    assert _press(tree, Qt.Key.Key_Left) is True
    settle(tree, tree.binding)
    assert second not in tree.snapshot().expanded
    # Space toggles the node's box.
    assert _press(tree, Qt.Key.Key_Space, " ") is True
    assert second in tree.snapshot().checked
    assert _press(tree, Qt.Key.Key_End) is True
    assert _press(tree, Qt.Key.Key_Home) is True
    assert tree.snapshot().cursor == ROOT


def test_the_expanded_and_selected_props_travel_both_ways(context, qtbot):
    tree = _tree(context, qtbot)
    opened: list = []
    tree.expanded_changed.connect(opened.append)
    branch = next(
        row.node.path for row in tree.snapshot().rows if row.node.has_children and row.node.path != ROOT
    )
    tree.set_expanded([ROOT, branch])
    settle(tree, tree.binding, rounds=6)
    assert branch in tree.snapshot().expanded
    assert opened
    # Setting what the tree already holds writes nothing back.
    seen = len(opened)
    tree.set_expanded(tree.expanded)
    settle(tree, tree.binding)
    assert len(opened) == seen


def test_a_tree_deleted_mid_read_leaves_nothing_behind(context, qtbot):
    """A tree taken off the page while a level is in flight must not take Qt with it.

    A level runs on a worker and the engine keeps the listener it was handed, so a widget
    deleted before the answer lands is where a stale callback would fire. Two are built and
    dropped, because a deferred delete lands on a later turn of the loop than the one that
    asked for it.
    """
    for _ in range(2):
        tree = EntityTree(context=context, root_path=ROOT, checkable=True, searchable=True)
        apply_theme(tree, theme_for("default"))
        tree.resize(520, 420)
        tree.show()
        tree.binding.run("search", "sh0")
        qtbot.wait(5)
        tree.close()
        tree.deleteLater()
        del tree

    gc.collect()
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        QtWidgets.QApplication.processEvents()
        qtbot.wait(5)
    QtWidgets.QApplication.processEvents()
