"""One entity by server-side search: the read, the ticket, the hydration and the contract."""
from __future__ import annotations

import time

from qtpy.QtCore import Qt, QTimer
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_core.picker import PageResult, PickerRow
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_picker import EntityPicker

from .test_picker_contract import PickerShape, check_contract, spin

#: A shot and an asset the fixtures always carry.
SHOT = 866
ASSET = 1226


class Counting:
    """A client that counts the calls that reached it, by method name."""

    def __init__(self, client):
        self._client = client
        self.reads: dict = {}

    def __getattr__(self, name):
        value = getattr(self._client, name)
        if not callable(value):
            return value

        def counted(*args, **kwargs):
            self.reads[name] = self.reads.get(name, 0) + 1
            return value(*args, **kwargs)

        return counted


def context_for(latency_ms: int = 20):
    """A context over the mock, at a latency a loading state is visible at."""
    client = Counting(MockClient(seed=1, latency_ms=latency_ms, now=MOCK_NOW))
    return create_sg_context(client, SgContextOptions()), client


def build(qtbot, latency_ms: int = 20, **props):
    """One picker on a themed window, sized so the chip row has room.

    The fixtures point their pictures at a public host, so the rows here draw no thumbnail:
    a test never reaches the network.
    """
    props.setdefault("thumbnail", False)
    context, client = context_for(latency_ms)
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(520, 140)
    picker = EntityPicker(context=context, parent=root, **props)
    picker.setGeometry(10, 10, 500, 40)
    root.show()
    qtbot.waitExposed(root)
    picker.test_root = root
    picker.test_client = client
    return picker


def settled(qtbot, picker, ms: int = 900):
    """Spin until the read in flight has landed."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)
        if not picker.state.loading and picker.control.items:
            return
    QApplication.processEvents()


def test_the_contract(qtbot):
    picker = build(qtbot, entity_types=["Shot"])
    checked = check_contract(
        qtbot, picker, PickerShape(settle=lambda: settled(qtbot, picker, 600))
    )
    assert "press toggles" in checked
    assert "pick" in checked
    assert "escape" in checked


def test_an_open_picker_lists_the_rows_worked_on_most_recently(qtbot):
    picker = build(qtbot, entity_types=["Shot"])
    picker.set_open(True)
    settled(qtbot, picker)
    assert len(picker.state.rows) > 0
    assert picker.control.items == [f"{row.type}:{row.id}" for row in picker.state.rows]


def test_the_read_is_debounced(qtbot):
    picker = build(qtbot, entity_types=["Shot"])
    picker.set_open(True)
    settled(qtbot, picker)
    before = picker.test_client.reads.get("search", 0)
    for text in ("s", "sh", "sh0"):
        picker.control.set_query(text)
        qtbot.wait(20)
    settled(qtbot, picker)
    spin(qtbot, 400)
    # Three keystrokes inside one pause cost one read, not three.
    assert picker.test_client.reads.get("search", 0) - before == 1


def test_the_read_never_blocks_the_gui_thread(qtbot):
    """A tick every 10ms, and the longest gap between two ticks under the mock's own latency."""
    latency = 300
    picker = build(qtbot, entity_types=["Shot"], latency_ms=latency)
    ticks: list = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start()
    picker.set_open(True)
    settled(qtbot, picker, 2000)
    timer.stop()
    assert len(picker.state.rows) > 0
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert gaps, "the timer never ticked"
    assert max(gaps) * 1000 < latency, f"the GUI thread stalled for {max(gaps) * 1000:.0f}ms"


def test_a_stale_answer_is_dropped(qtbot):
    picker = build(qtbot, entity_types=["Shot"], latency_ms=200)
    picker.set_debounce_ms(0)
    picker.set_open(True)
    settled(qtbot, picker, 1200)
    seen: list = []
    picker.search.subscribe(lambda state: seen.append((state.query, state.loading)))
    picker.control.set_query("sh0")
    qtbot.wait(20)
    picker.control.set_query("zzzz")
    spin(qtbot, 1200)
    assert picker.state.query == "zzzz"
    assert picker.state.rows == []
    assert ("sh0", False) not in seen, "the answer to the query that was replaced was written"


def test_hydration_resolves_a_bare_reference(qtbot):
    picker = build(qtbot, entity_types=["Shot"], value=EntityRef(type="Shot", id=SHOT))
    spin(qtbot, 600)
    label = picker.control.labels[0]
    assert label and label != f"Shot {SHOT}"
    assert picker.search.known[f"Shot:{SHOT}"].name == label


def test_the_value_and_its_row_reach_the_signal(qtbot):
    picker = build(qtbot, entity_types=["Shot"])
    answers: list = []
    picker.value_changed.connect(lambda ref, row: answers.append((ref, row)))
    picker.set_open(True)
    settled(qtbot, picker)
    picker.control.list_surface().highlight_first()
    picker.control.list_surface().activate(0)
    spin(qtbot, 50)
    ref, row = answers[-1]
    assert isinstance(ref, EntityRef) and isinstance(row, PickerRow)
    assert ref.type == row.type and ref.id == row.id
    assert not picker.control.is_open, "a pick closes a single picker"


def test_a_failed_read_surfaces_on_the_error_signal_and_the_line(qtbot):
    picker = build(qtbot, entity_types=["Shot"])
    failures: list = []
    picker.error.connect(failures.append)
    picker.test_client.fail_next()
    picker.set_open(True)
    spin(qtbot, 700)
    assert failures, "the failure never reached the signal"
    assert picker.control.state_line().state == "error"
    assert picker.control.state_line().label


def secondary_of(picker, row: int = 0):
    """What the first row draws on the right: its text, and the painter under it."""
    index = picker.control.list_surface().model().index(row, 0)
    return index.data(Roles.SECONDARY), index.data(Roles.PAINTER)


def test_the_type_is_the_secondary_on_a_polymorphic_list(qtbot):
    picker = build(qtbot, entity_types=["Shot", "Asset"])
    picker.set_open(True)
    settled(qtbot, picker)
    text, _paint = secondary_of(picker)
    assert text == picker.state.rows[0].type


def test_a_caller_secondary_wins(qtbot):
    picker = build(qtbot, entity_types=["Shot"], secondary=lambda row: f"#{row.id}")
    picker.set_open(True)
    settled(qtbot, picker)
    text, paint = secondary_of(picker)
    assert text == f"#{picker.state.rows[0].id}"
    assert paint is None, "the caller's own text is not drawn by the field"


def test_a_field_secondary_is_drawn_from_the_field(qtbot):
    """The column a `secondary_field` names is drawn, and by the field's own data type.

    The picker used to hand the model a renderer of its own whatever it had been given, and a
    renderer standing in that column takes the field's rendering away from it: the status badge
    never appeared, and a plain field drew nothing at all.
    """
    picker = build(qtbot, entity_types=["Shot"], secondary_field="id")
    # Opened by hand, the way a person opens it.
    QTest.mouseClick(
        picker.control,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        picker.control.rect().center(),
    )
    settled(qtbot, picker)
    text, _paint = secondary_of(picker)
    assert text == str(picker.state.rows[0].id), "the field the caller named is not drawn"


def test_a_status_secondary_draws_its_badge(qtbot):
    """A status is a glyph and a name, which no string renders: rule 9 of the design rules."""
    picker = build(qtbot, entity_types=["Shot"], secondary_field="sg_status_list")
    QTest.mouseClick(
        picker.control,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        picker.control.rect().center(),
    )
    settled(qtbot, picker)
    # The field's schema and the status table land on threads of their own.
    end = time.time() + 2.0
    while time.time() < end and not callable(secondary_of(picker)[1]):
        QApplication.processEvents()
        qtbot.wait(10)
    text, paint = secondary_of(picker)
    assert callable(paint), "the status secondary drew no badge"
    assert text == "", "a status is drawn as a badge, never as its raw code"


def test_a_page_of_five_offers_a_load_more_row(qtbot):
    picker = build(qtbot, entity_types=["Shot"], page_size=5)
    picker.set_open(True)
    settled(qtbot, picker)
    assert picker.state.has_more
    surface = picker.control.list_surface()
    assert surface.is_load_more(surface.row_count() - 1)
    first = len(picker.state.rows)
    surface.activate(surface.row_count() - 1)
    spin(qtbot, 700)
    assert len(picker.state.rows) > first, "the load-more row read the next page"
    assert picker.control.is_open, "paging is not a selection"


def test_the_deliver_step_writes_only_a_ticket_that_still_holds(qtbot):
    picker = build(qtbot, entity_types=["Shot"])
    picker.set_open(True)
    settled(qtbot, picker)
    rows = list(picker.state.rows)
    stale = picker.search.begin() - 1
    picker.search.deliver(
        stale, "x", 1, PageResult(rows=[PickerRow(type="Shot", id=1, name="never")], has_more=False)
    )
    assert [row.id for row in picker.state.rows] == [row.id for row in rows]


def test_the_caret_beside_a_chip_invites_the_next_query(qtbot):
    # Upstream passes `inputPlaceholder={chipEntity ? searchPlaceholder : placeholder}`, so a
    # filled single picker reads "Search…" beside its chip rather than nothing.
    picker = build(qtbot, entity_types=["Shot"], placeholder="Pick a shot")
    settled(qtbot, picker)
    caret = picker.control.caret()
    assert caret.placeholderText() == "Pick a shot"

    picker.set_value(EntityRef(type="Shot", id=SHOT, name="sh010_0050"))
    spin(qtbot, 60)
    assert picker.control.labels
    assert caret.placeholderText() == picker.search_placeholder

    picker.set_search_placeholder("Search shots…")
    assert caret.placeholderText() == "Search shots…"

    picker.set_value(None)
    spin(qtbot, 60)
    assert caret.placeholderText() == "Pick a shot"
