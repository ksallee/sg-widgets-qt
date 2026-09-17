"""The site-wide palette: the debounce, the stale answer, the page, the groups and the keys."""
from __future__ import annotations

import threading

import pytest
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QWidget

from sg_widgets_core.filter import EntityRef
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.global_search import GlobalSearch, GlobalSearchRow
from sg_widgets_qt.workers import default_pool

DEBOUNCE_MS = 30
SETTLE_MS = 6000
TYPES = ["Shot", "Asset"]


class Counting:
    """The mock client with the text searches counted, and one that can be held."""

    def __init__(self, client) -> None:
        self._client = client
        self.searches: list[str] = []
        self.gates: dict[str, threading.Event] = {}

    def __getattr__(self, name):
        return getattr(self._client, name)

    def gate(self, query: str) -> threading.Event:
        self.gates[query] = threading.Event()
        return self.gates[query]

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
    widget.resize(520, 520)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def context():
    return demo_context(latency_ms=0)


def make(host, qtbot, context, **props) -> GlobalSearch:
    props.setdefault("entity_types", TYPES)
    props.setdefault("inline", True)
    search = GlobalSearch(host, context=context.context, **props)
    search.search_control().set_debounce_ms(DEBOUNCE_MS)
    qtbot.addWidget(search)
    search.show()
    return search


def settle(qtbot, search: GlobalSearch) -> None:
    qtbot.waitUntil(lambda: not search.search_control().loading, timeout=SETTLE_MS)


def test_the_debounce_coalesces_two_keystrokes_into_one_read(host, qtbot, context):
    counted = Counting(context.context.client)
    context.context.client = counted
    search = make(host, qtbot, context)
    search.search_control().input().setText("sh")
    search.search_control().input().setText("sh0")
    settle(qtbot, search)
    assert counted.searches == ["sh0"]


def test_a_stale_answer_is_dropped_when_a_second_query_starts_first(host, qtbot, context):
    counted = Counting(context.context.client)
    context.context.client = counted
    search = make(host, qtbot, context)
    held = counted.gate("sh010")
    search.set_query("sh010")
    qtbot.waitUntil(lambda: counted.searches == ["sh010"], timeout=SETTLE_MS)
    search.set_query("charAda")
    qtbot.waitUntil(lambda: len(counted.searches) == 2, timeout=SETTLE_MS)
    held.set()
    settle(qtbot, search)
    qtbot.wait(80)
    names = [hit.ref.name for hit in search.search_control().items]
    assert names and all("sh010" not in (name or "") for name in names)


def test_load_more_appends_a_page(host, qtbot, context):
    # A full page is the only sign of another one, so the query has to fill one (006_pagination).
    search = make(host, qtbot, context, entity_types=["Shot"])
    search.set_query("0")
    settle(qtbot, search)
    first = len(search.search_control().items)
    assert search.search_control().has_more
    search.search_control().load_more()
    settle(qtbot, search)
    assert len(search.search_control().items) > first


def test_the_empty_line_shows_when_nothing_matches(host, qtbot, context):
    search = make(host, qtbot, context, empty_label="No match")
    search.set_query("zzzznothing")
    settle(qtbot, search)
    assert search.search_control().view == "empty"
    assert search.search_control().findChild(QWidget, "search-empty").isVisible()


def test_the_error_line_shows_what_the_failed_read_said(host, qtbot, context):
    class Failing(Counting):
        def text_search(self, text, entity_types, page=None):
            raise RuntimeError("the site is not answering")

    context.context.client = Failing(context.context.client)
    search = make(host, qtbot, context)
    with qtbot.waitSignal(search.search_control().error, timeout=SETTLE_MS) as caught:
        search.set_query("sh")
    assert "not answering" in caught.args[0]
    assert search.search_control().view == "error"


def test_the_results_are_grouped_by_type_under_a_heading(host, qtbot, context):
    search = make(host, qtbot, context)
    search.set_query("0")
    settle(qtbot, search)
    model = search.search_control().model
    kinds = [model.data(model.index(i, 0), Roles.KIND) for i in range(model.rowCount())]
    assert kinds.count("heading") >= 1
    assert kinds[0] == "heading"


def test_up_and_down_and_enter_pick_a_row(host, qtbot, context):
    search = make(host, qtbot, context)
    search.set_query("sh010")
    settle(qtbot, search)
    taken: list[EntityRef] = []
    search.selected.connect(taken.append)
    control = search.search_control()
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Up))
    control.handle_key(_key(Qt.Key.Key_Return))
    assert len(taken) == 1
    assert taken[0].type in TYPES


def test_a_pick_leads_the_recents_and_clears_the_query(host, qtbot, context):
    search = make(host, qtbot, context, recent_limit=2)
    picked = EntityRef(type="Shot", id=862, name="sh010_0010")
    with qtbot.waitSignal(search.recents_changed, timeout=SETTLE_MS) as caught:
        search.choose(picked)
    assert caught.args[0][0] is picked
    assert search.query == ""


def test_the_recents_show_on_an_empty_query(host, qtbot, context):
    recent = EntityRef(type="Shot", id=862, name="sh010_0010")
    search = make(host, qtbot, context, recents=[recent])
    qtbot.wait(4 * DEBOUNCE_MS)
    model = search.search_control().model
    rows = [model.row_at(i) for i in range(model.rowCount())]
    named = [r for r in rows if isinstance(r, GlobalSearchRow)]
    assert named and named[0].recent
    assert named[0].name == "sh010_0010"


def test_escape_clears_the_query_and_then_closes_the_palette(host, qtbot, context):
    search = make(host, qtbot, context, inline=False)
    search.search_control().set_debounce_ms(DEBOUNCE_MS)
    search.set_open(True)
    search.set_query("sh")
    settle(qtbot, search)
    control = search.search_control()
    control.handle_key(_key(Qt.Key.Key_Escape))
    assert search.query == ""
    control.handle_key(_key(Qt.Key.Key_Escape))
    assert not search.open


def test_the_trigger_carries_the_shortcut_it_opens_on(host, qtbot, context):
    search = make(host, qtbot, context, inline=False, hotkey="k")
    assert search.trigger() is not None
    assert search.trigger().hint.endswith("K")
    search.set_hotkey(False)
    assert search.trigger().hint == ""


def _key(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier)
