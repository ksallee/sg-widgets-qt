"""The query lifecycle: the debounce, the stale answer, the page, and the three state blocks."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest
from qtpy.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from qtpy.QtGui import QFontMetrics, QKeyEvent, QMouseEvent
from qtpy.QtWidgets import QApplication, QStyleOptionViewItem, QWidget

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.primitives.row_delegate import ROW_PAD_Y, ROW_TEXT
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.picker_row import PickerRowModel
from sg_widgets_qt.widgets.search_control import SearchAnswer, SearchControl, SearchRequest
from sg_widgets_qt.widgets.search_skeleton import SearchSkeleton
from sg_widgets_qt.workers import default_pool

DEBOUNCE_MS = 30
SETTLE_MS = 3000


@dataclass
class Row:
    """The shape the row model reads."""

    type: str
    id: int
    name: str
    values: dict = field(default_factory=dict)


class Reads:
    """A read that counts the calls that reached it, and can be held or made to fail."""

    def __init__(self, page_size: int = 2, total: int = 5) -> None:
        self.count = 0
        self.queries: list[str] = []
        self.page_size = page_size
        self.total = total
        self.fail = False
        self.gates: dict[str, threading.Event] = {}

    def gate(self, query: str) -> threading.Event:
        """Hold the read for that query until the event is set."""
        self.gates[query] = threading.Event()
        return self.gates[query]

    def __call__(self, request: SearchRequest) -> SearchAnswer:
        self.count += 1
        self.queries.append(request.query)
        held = self.gates.get(request.query)
        if held is not None:
            held.wait(5.0)
        if self.fail:
            raise RuntimeError("the crew list is not answering")
        start = (request.page - 1) * self.page_size
        rows = [
            Row(type="Shot", id=n, name=f"{request.query or 'row'}-{n}")
            for n in range(start, min(start + self.page_size, self.total))
        ]
        return SearchAnswer(items=rows, has_more=start + self.page_size < self.total)


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
    widget.resize(420, 400)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def make(host, qtbot, reads, **props) -> SearchControl:
    props.setdefault("debounce_ms", DEBOUNCE_MS)
    control = SearchControl(host, load=reads, model=PickerRowModel([], host), **props)
    qtbot.addWidget(control)
    control.show()
    return control


def settle(qtbot, control: SearchControl) -> None:
    qtbot.waitUntil(lambda: not control.loading, timeout=SETTLE_MS)


def test_the_debounce_coalesces_two_keystrokes_into_one_read(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads)
    control.input().setText("s")
    control.input().setText("sh")
    settle(qtbot, control)
    assert reads.count == 1
    assert reads.queries == ["sh"]


def test_a_stale_answer_is_dropped_when_a_second_query_starts_first(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads)
    held = reads.gate("slow")
    control.set_query("slow")
    qtbot.waitUntil(lambda: reads.count == 1, timeout=SETTLE_MS)
    control.set_query("fast")
    qtbot.waitUntil(lambda: reads.count == 2, timeout=SETTLE_MS)
    held.set()
    settle(qtbot, control)
    qtbot.wait(50)
    assert [row.name.split("-")[0] for row in control.items] == ["fast", "fast"]


def test_load_more_appends_a_page(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads, paging=True)
    control.set_query("sh")
    settle(qtbot, control)
    assert len(control.items) == 2
    assert control.has_more
    control.load_more()
    settle(qtbot, control)
    assert len(control.items) == 4
    assert control.model.rowCount() == 4
    assert control.page == 2


def test_the_empty_line_shows_when_the_read_answers_nothing(host, qtbot):
    reads = Reads(total=0)
    control = make(host, qtbot, reads, empty_label="No one by that name")
    control.set_query("nobody")
    settle(qtbot, control)
    assert control.view == "empty"
    assert control.findChild(QWidget, "search-empty").isVisible()
    assert control.status == "No one by that name"


def test_the_error_line_shows_what_the_failed_read_said(host, qtbot):
    reads = Reads()
    reads.fail = True
    control = make(host, qtbot, reads)
    with qtbot.waitSignal(control.error, timeout=SETTLE_MS) as caught:
        control.set_query("sh")
    assert "not answering" in caught.args[0]
    assert control.view == "error"
    assert control.findChild(QWidget, "search-error").isVisible()


def test_the_skeletons_stand_in_while_the_first_page_is_in_flight(host, qtbot):
    reads = Reads()
    held = reads.gate("sh")
    control = make(host, qtbot, reads)
    control.set_query("sh")
    qtbot.waitUntil(lambda: control.view == "loading", timeout=SETTLE_MS)
    assert control.findChild(SearchSkeleton, "search-loading").isVisible()
    assert control.status == "Searching…"
    held.set()
    settle(qtbot, control)


def test_up_and_down_and_enter_pick_a_row(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads)
    control.set_query("sh")
    settle(qtbot, control)
    taken: list[int] = []
    control.activated.connect(taken.append)
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Down))
    control.handle_key(_key(Qt.Key.Key_Up))
    assert control.list_surface().highlighted() == 0
    control.handle_key(_key(Qt.Key.Key_Return))
    assert taken == [0]


def test_escape_clears_the_query_and_then_leaves_the_key_to_the_shell(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads)
    control.set_query("sh")
    settle(qtbot, control)
    assert control.handle_key(_key(Qt.Key.Key_Escape))
    assert control.query == ""
    with qtbot.waitSignal(control.dismissed, timeout=SETTLE_MS):
        control.handle_key(_key(Qt.Key.Key_Escape))


def test_an_empty_query_reads_nothing_unless_reads_empty_is_on(host, qtbot):
    reads = Reads()
    make(host, qtbot, reads)
    qtbot.wait(4 * DEBOUNCE_MS)
    assert reads.count == 0
    browsing = make(host, qtbot, Reads(), reads_empty=True)
    settle(qtbot, browsing)
    assert len(browsing.items) == 2


def test_a_change_of_request_reads_again_at_once(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads, reads_empty=True)
    settle(qtbot, control)
    assert reads.count == 1
    control.set_request("/Project/70")
    settle(qtbot, control)
    assert reads.count == 2


def test_nothing_is_read_while_the_control_is_held_back(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads, reads_empty=True, enabled=False)
    qtbot.wait(4 * DEBOUNCE_MS)
    assert reads.count == 0
    control.set_enabled(True)
    settle(qtbot, control)
    assert reads.count == 1


def _key(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier)


def test_the_query_reaches_the_model_so_the_matched_runs_are_marked(host, qtbot):
    reads = Reads()
    control = make(host, qtbot, reads)
    control.input().setText("sh")
    settle(qtbot, control)
    assert control.model.query == "sh"
    runs = control.model.data(control.model.index(0, 0), Roles.RUNS)
    assert [text for text, matched, *_ in runs if matched] == ["sh"]


def test_the_dialog_shell_draws_no_header_and_no_close_control(host, qtbot):
    control = make(host, qtbot, Reads(), shell="dialog", title="Search", description="By name.")
    dialog = control.dialog()
    assert dialog is not None
    # Upstream's command dialog keeps its title and description `sr-only`.
    assert dialog.accessibleName() == "Search"
    assert dialog.accessibleDescription() == "By name."
    assert not dialog.findChild(QWidget, "dialog-close")
    for child in dialog.findChildren(QWidget):
        assert child.property("text") != "Search" or not child.isVisible()
    control.set_title("Find")
    assert dialog.accessibleName() == "Find"


def test_a_press_outside_the_panel_dismisses_the_dialog(host, qtbot):
    control = make(host, qtbot, Reads(), shell="dialog")
    dialog = control.dialog()
    control.set_open(True)
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=SETTLE_MS)
    outside = dialog.mapToGlobal(dialog.rect().topLeft()) - QPoint(200, 200)
    QApplication.sendEvent(
        dialog,
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(outside),
            QPointF(outside),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    qtbot.waitUntil(lambda: not control.open, timeout=SETTLE_MS)


def test_the_load_more_row_stands_at_the_body_step(host, qtbot):
    control = make(host, qtbot, Reads(), paging=True)
    control.set_query("sh")
    settle(qtbot, control)
    surface = control.list_surface()
    qtbot.waitUntil(lambda: surface.load_more_visible(), timeout=SETTLE_MS)
    delegate = surface.row_delegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 300, 40)
    last = surface.model().index(surface.row_count() - 1, 0)
    theme = theme_for("default")
    wanted = QFontMetrics(theme.font(ROW_TEXT["md"])).height() + 2 * ROW_PAD_Y
    assert delegate.sizeHint(option, last).height() == wanted
