"""The tree: the level it browses, the breadcrumbs a query answers, and the keys that walk it."""
from __future__ import annotations

import threading

import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QWidget

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.hierarchical_search import HierarchicalSearch, HierarchicalSearchRow
from sg_widgets_qt.workers import default_pool

DEBOUNCE_MS = 30
SETTLE_MS = 8000
ROOT = "/Project/70"
TYPES = ["Shot", "Asset", "Sequence", "Task"]


class Counting:
    """The mock client with its two reads counted, and a text search that can be held."""

    def __init__(self, client) -> None:
        self._client = client
        self.expands: list[str] = []
        self.searches: list[str] = []
        self.fail = False
        self.gates: dict[str, threading.Event] = {}

    def __getattr__(self, name):
        return getattr(self._client, name)

    def gate(self, query: str) -> threading.Event:
        self.gates[query] = threading.Event()
        return self.gates[query]

    def hierarchy_expand(self, path):
        self.expands.append(path)
        if self.fail:
            raise RuntimeError("the tree is not answering")
        return self._client.hierarchy_expand(path)

    def text_search(self, text, entity_types, page=None):
        self.searches.append(text)
        held = self.gates.get(text)
        if held is not None:
            held.wait(5.0)
        return self._client.text_search(text, entity_types, page)


@pytest.fixture(autouse=True)
def drain_the_pool():
    """Let every read answer before the next test, so a job never outlives its widget."""
    yield
    default_pool().wait(5000)


@pytest.fixture
def host(qtbot):
    widget = QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(520, 480)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def context():
    built = demo_context(latency_ms=0)
    built.context.client = Counting(built.context.client)
    return built


def make(host, qtbot, context, **props) -> HierarchicalSearch:
    props.setdefault("root_path", ROOT)
    props.setdefault("entity_types", TYPES)
    tree = HierarchicalSearch(host, context=context.context, **props)
    tree.search_control().set_debounce_ms(DEBOUNCE_MS)
    qtbot.addWidget(tree)
    tree.show()
    return tree


def settle(qtbot, tree: HierarchicalSearch) -> None:
    qtbot.waitUntil(lambda: not tree.search_control().loading, timeout=SETTLE_MS)


def rows(tree: HierarchicalSearch) -> list:
    model = tree.search_control().model
    return [model.row_at(i) for i in range(model.rowCount())]


def test_an_empty_query_browses_one_level_of_the_tree(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    assert context.context.client.expands == [ROOT]
    assert [r.label for r in rows(tree) if isinstance(r, HierarchicalSearchRow)]


def test_the_debounce_coalesces_two_keystrokes_into_one_read(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    tree.search_control().input().setText("sh")
    tree.search_control().input().setText("sh0")
    settle(qtbot, tree)
    assert context.context.client.searches == ["sh0"]


def test_a_stale_answer_is_dropped_when_a_second_query_starts_first(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    counted = context.context.client
    held = counted.gate("sh010")
    tree.set_query("sh010")
    qtbot.waitUntil(lambda: counted.searches == ["sh010"], timeout=SETTLE_MS)
    tree.set_query("charAda")
    qtbot.waitUntil(lambda: len(counted.searches) == 2, timeout=SETTLE_MS)
    held.set()
    settle(qtbot, tree)
    qtbot.wait(80)
    found = [r for r in rows(tree) if isinstance(r, HierarchicalSearchRow)]
    assert all("sh010" not in r.label for r in found)


def test_a_searched_row_carries_the_breadcrumb_that_reaches_it(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    tree.set_query("sh010")
    settle(qtbot, tree)
    found = [r for r in rows(tree) if isinstance(r, HierarchicalSearchRow) and not r.up]
    assert found
    assert any(r.crumbs for r in found)
    model = tree.search_control().model
    runs = model.data(model.index(1, 0), Roles.RUNS)
    assert any(muted for _text, _matched, muted in runs)


def test_right_drills_and_left_goes_back_up(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    control = tree.search_control()
    control.list_surface().highlight_first()
    while not isinstance(tree.search_control().model.row_at(
        control.list_surface().highlighted()
    ), HierarchicalSearchRow):
        control.list_surface().highlight_next()
    control.handle_key(_key(Qt.Key.Key_Right))
    settle(qtbot, tree)
    assert tree.level_path != ROOT
    control.handle_key(_key(Qt.Key.Key_Left))
    settle(qtbot, tree)
    assert tree.level_path == ROOT


def test_enter_picks_a_row_and_answers_its_path(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    tree.set_query("sh010_0010")
    settle(qtbot, tree)
    taken: list = []
    tree.selected.connect(lambda ref, path: taken.append((ref, path)))
    control = tree.search_control()
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Return))
    assert taken
    ref, path = taken[0]
    assert ref.type in TYPES
    assert [step.type for step in path]


def test_the_empty_line_shows_when_a_query_matches_nothing(host, qtbot, context):
    tree = make(host, qtbot, context, no_match_label="No match")
    settle(qtbot, tree)
    tree.set_query("zzzznothing")
    settle(qtbot, tree)
    assert tree.search_control().view == "empty"
    assert tree.search_control().empty_label == "No match"


def test_the_error_line_shows_what_the_failed_read_said(host, qtbot, context):
    context.context.client.fail = True
    tree = make(host, qtbot, context)
    with qtbot.waitSignal(tree.search_control().error, timeout=SETTLE_MS) as caught:
        tree.set_root_path("/")
    assert "not answering" in caught.args[0]
    assert tree.search_control().view == "error"


def test_escape_clears_the_query_and_returns_to_the_level(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    tree.set_query("sh010")
    settle(qtbot, tree)
    assert tree.searching
    tree.search_control().handle_key(_key(Qt.Key.Key_Escape))
    settle(qtbot, tree)
    assert not tree.searching
    assert tree.search_control().view == "rows"


def test_a_level_carries_the_back_row_and_a_heading(host, qtbot, context):
    tree = make(host, qtbot, context)
    settle(qtbot, tree)
    model = tree.search_control().model
    assert model.data(model.index(0, 0), Roles.KIND) == "heading"
    control = tree.search_control()
    control.list_surface().highlight_first()
    while not isinstance(model.row_at(control.list_surface().highlighted()), HierarchicalSearchRow):
        control.list_surface().highlight_next()
    control.handle_key(_key(Qt.Key.Key_Right))
    settle(qtbot, tree)
    assert any(isinstance(r, HierarchicalSearchRow) and r.up for r in rows(tree))


def _key(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier)
