"""The list, calendar and table primitives: the highlight, the fade, the filter and the row."""
from __future__ import annotations

import datetime

import pytest
from qtpy.QtCore import QAbstractListModel, QAbstractTableModel, QEvent, QModelIndex, QSize, Qt
from qtpy.QtGui import QColor, QKeyEvent, QPainter, QPixmap
from qtpy.QtWidgets import QStyle, QStyleOptionViewItem

from sg_widgets_qt.primitives.calendar import (
    CELL,
    HEADING_HEIGHT,
    MAX_WEEKS,
    WEEK_GAP,
    WEEK_PITCH,
    Calendar,
)
from sg_widgets_qt.primitives.command import Command
from sg_widgets_qt.primitives.list_view import FADE_SIZE, ListSurface
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.primitives.row_delegate import RowDelegate
from sg_widgets_qt.primitives.scrollbar import overlay_scrollbars_of
from sg_widgets_qt.primitives.table import TableSurface
from sg_widgets_qt.theme import apply_theme, theme_for


class RowModel(QAbstractListModel):
    """Rows carrying the roles the delegate reads."""

    def __init__(self, labels, runs=None, kinds=None, pixmaps=None):
        super().__init__()
        self.labels = list(labels)
        self.runs = runs or {}
        self.kinds = kinds or {}
        self.pixmaps = pixmaps or {}

    def rowCount(self, parent=QModelIndex()):  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.labels)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return self.labels[row]
        if role == Roles.RUNS:
            return self.runs.get(row)
        if role == Roles.KIND:
            return self.kinds.get(row)
        if role == Roles.SUB_LABEL:
            return f"{self.labels[row].lower()}@example.test"
        if role == Roles.SECONDARY:
            return "Shot"
        if role == Roles.PIXMAP:
            return self.pixmaps.get(row)
        return None


class TableModel(QAbstractTableModel):
    """Six rows and three columns, the first of which sorts."""

    HEADERS = ("Name", "Status", "Updated")

    def __init__(self, rows):
        super().__init__()
        self.rows = rows

    def rowCount(self, parent=QModelIndex()):  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):  # noqa: B008, N802
        return 0 if parent.isValid() else 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.rows[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        if role == Roles.SORTABLE:
            return section == 0
        return None


@pytest.fixture
def themed(qtbot):
    """A factory putting the light theme on a widget and showing it."""

    def make(widget, dark=False):
        apply_theme(widget, theme_for("default", dark=dark))
        qtbot.addWidget(widget)
        widget.show()
        return widget

    return make


def key(code, modifiers=Qt.KeyboardModifier.NoModifier):
    return QKeyEvent(QEvent.Type.KeyPress, code, modifiers)


# --- the list ---------------------------------------------------------------------------


def test_the_highlight_walks_down_and_holds_at_the_last_row(themed):
    view = themed(ListSurface())
    view.setModel(RowModel([f"Row {i}" for i in range(5)]))
    view.resize(320, 288)

    assert view.highlight_first() is True
    assert view.highlighted() == 0
    for _ in range(4):
        view.handle_key(key(Qt.Key.Key_Down))
    assert view.highlighted() == 4

    # No wrap: `loop` is off, as the upstream Command is.
    assert view.handle_key(key(Qt.Key.Key_Down)) is True
    assert view.highlighted() == 4


def test_the_highlight_skips_a_heading_and_a_separator(themed):
    view = themed(ListSurface())
    view.setModel(RowModel(["People", "Ada", "-", "Anna"], kinds={0: "heading", 2: "separator"}))
    view.resize(320, 288)
    view.highlight_first()
    assert view.highlighted() == 1
    view.highlight_next()
    assert view.highlighted() == 3


def test_the_first_highlight_leaves_the_list_at_its_top(themed):
    """A group heading sits over the first row, and must not be scrolled out under it."""
    view = themed(ListSurface())
    view.setModel(
        RowModel(["People", *[f"Row {i}" for i in range(20)]], kinds={0: "heading"})
    )
    view.resize(320, 120)
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    assert view.highlight_first() is True
    assert view.highlighted() == 1
    assert view.verticalScrollBar().value() == 0


def test_the_load_more_row_activates(themed):
    view = themed(ListSurface())
    view.setModel(RowModel(["Ada", "Anna"]))
    view.resize(320, 288)
    view.set_load_more(True, "Load more")
    assert view.row_count() == 3
    assert view.is_load_more(2) is True

    asked = []
    chosen = []
    view.load_more_requested.connect(lambda: asked.append(True))
    view.activated.connect(chosen.append)

    view.highlight_last()
    assert view.highlighted() == 2
    view.handle_key(key(Qt.Key.Key_Return))
    assert asked == [True]
    assert chosen == []

    view.set_load_more(False)
    assert view.row_count() == 2


def test_the_edge_fade_is_there_only_where_content_is_past_the_edge(themed, qtbot):
    view = themed(ListSurface())
    view.setModel(RowModel(["Ada", "Anna"]))
    view.resize(320, 288)
    qtbot.waitExposed(view)
    assert view.fade_sizes() == (0, 0)

    view.setModel(RowModel([f"Row {i}" for i in range(60)]))
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)
    view.verticalScrollBar().setValue(0)
    top, bottom = view.fade_sizes()
    assert top == 0
    assert bottom == FADE_SIZE

    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    top, bottom = view.fade_sizes()
    assert top == FADE_SIZE
    assert bottom == 0


def test_the_overlay_scrollbar_shows_on_a_tall_list_and_fades(themed, qtbot):
    view = themed(ListSurface())
    view.setModel(RowModel([f"Row {i}" for i in range(60)]))
    view.resize(320, 288)
    qtbot.waitExposed(view)
    qtbot.waitUntil(lambda: view.verticalScrollBar().maximum() > 0)

    bars = overlay_scrollbars_of(view)
    assert bars is not None
    vertical = bars[0]
    assert vertical.scrollable() is True
    qtbot.waitUntil(vertical.isVisible)

    vertical.fade_delay_ms = 20
    view.verticalScrollBar().setValue(40)
    assert vertical.opacity() == pytest.approx(1.0)
    qtbot.waitUntil(lambda: vertical.opacity() < 0.05, timeout=3000)


def test_a_short_list_keeps_no_scrollbar(themed, qtbot):
    view = themed(ListSurface())
    view.setModel(RowModel(["Ada"]))
    view.resize(320, 288)
    qtbot.waitExposed(view)
    bars = overlay_scrollbars_of(view)
    assert bars[0].scrollable() is False
    assert bars[0].isVisible() is False


# --- the row ---------------------------------------------------------------------------


ROW_BOX = QSize(320, 48)


def paint_row(delegate, model, row, size=None, widget=None, state=None):
    """Draw one row into a pixmap and give back the image."""
    picture = QPixmap(size if size is not None else ROW_BOX)
    picture.fill(QColor("#ffffff"))
    option = QStyleOptionViewItem()
    option.rect = picture.rect()
    if widget is not None:
        option.widget = widget
    if state is not None:
        option.state |= state
    painter = QPainter(picture)
    delegate.paint(painter, option, model.index(row, 0))
    painter.end()
    return picture.toImage()


def ink(image):
    """How many pixels the row put down."""
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            if QColor(image.pixel(x, y)) != QColor("#ffffff"):
                count += 1
    return count


def test_the_row_delegate_paints_a_picture_runs_and_a_secondary(themed):
    view = themed(ListSurface())
    picture = QPixmap(32, 32)
    picture.fill(QColor("#334455"))
    model = RowModel(
        ["Ada Lovelace"],
        runs={0: [("Ada", True), (" Lovelace", False)]},
        pixmaps={0: picture},
    )
    view.setModel(model)
    image = paint_row(view.row_delegate(), view.model(), 0, widget=view)
    assert ink(image) > 0


def test_the_matched_run_is_bolder_than_the_plain_label(themed):
    # The weight the delegate hands the painter, not the pixels that come back: a family whose
    # DemiBold face the platform cannot supply draws the two runs alike, and the row asks for
    # the heavier face and never puts less ink down for a match.
    view = themed(ListSurface())
    plain = RowModel(["Lovelace"], runs={0: [("Lovelace", False)]})
    matched = RowModel(["Lovelace"], runs={0: [("Lovelace", True)]})
    delegate = RowDelegate(view, thumbnail=False)

    quiet, bold = delegate.run_font(False), delegate.run_font(True)
    assert bold.weight() > quiet.weight()
    assert (bold.family(), bold.pixelSize()) == (quiet.family(), quiet.pixelSize())
    light = ink(paint_row(delegate, plain, 0, widget=view))
    heavy = ink(paint_row(delegate, matched, 0, widget=view))
    assert heavy >= light > 0


def test_a_row_with_a_sub_label_takes_the_tighter_inset(themed):
    view = themed(ListSurface())
    view.setModel(RowModel(["Ada"]))
    delegate = view.row_delegate()
    option = QStyleOptionViewItem()
    option.rect = QPixmap(320, 48).rect()
    option.widget = view
    hint = delegate.sizeHint(option, view.model().index(0, 0))
    assert hint.height() >= 40


class GrowingModel(RowModel):
    """Rows a page can be appended to, which is what a load-more answer does."""

    def append(self, labels):
        first = len(self.labels)
        self.beginInsertRows(QModelIndex(), first, first + len(labels) - 1)
        self.labels.extend(labels)
        self.endInsertRows()


def test_a_page_landing_leaves_the_list_where_the_reader_left_it(themed):
    # The page lands under the rows already read, so the view keeps its scroll position and
    # its keyboard cursor rather than being reset back to the top.
    view = themed(ListSurface())
    model = GrowingModel([f"Row {i}" for i in range(20)])
    view.setModel(model)
    view.resize(320, 120)
    view.set_load_more(True)
    view.highlight_first()
    for _ in range(19):
        view.highlight_next()
    held = view.verticalScrollBar().value()
    assert held > 0

    model.append([f"Row {i}" for i in range(20, 30)])
    assert view.verticalScrollBar().value() == held
    assert view.highlighted() == 19


def test_the_cursor_takes_the_seat_the_load_more_row_was_in(themed):
    view = themed(ListSurface())
    model = GrowingModel([f"Row {i}" for i in range(5)])
    view.setModel(model)
    view.resize(320, 288)
    view.set_load_more(True)
    view.highlight_last()
    seat = view.highlighted()
    assert view.is_load_more(seat)

    view.activate(seat)
    model.append([f"Row {i}" for i in range(5, 10)])
    assert view.highlighted() == seat
    assert not view.is_load_more(seat)


def test_the_cursor_holds_when_the_last_page_takes_the_load_more_row_away(themed):
    view = themed(ListSurface())
    view.setModel(RowModel([f"Row {i}" for i in range(5)]))
    view.resize(320, 288)
    view.set_load_more(True)
    view.highlight_last()
    assert view.is_load_more(view.highlighted())

    view.set_load_more(False)
    assert view.load_more_visible() is False
    assert view.highlighted() == 4


def test_a_hovered_row_wears_the_highlight_and_nothing_else(themed):
    # Upstream's row carries `data-highlighted:bg-accent` alone: the pointer moves the cursor
    # onto the row it is over, so hover is the cursor rather than a second, weaker fill.
    view = themed(ListSurface())
    view.setModel(RowModel(["Ada"]))
    delegate = RowDelegate(view, thumbnail=False)
    plain = paint_row(delegate, view.model(), 0, widget=view)
    hovered = paint_row(
        delegate, view.model(), 0, widget=view, state=QStyle.StateFlag.State_MouseOver
    )
    assert ink(hovered) == ink(plain)


# --- the command -------------------------------------------------------------------------


def test_the_command_filters_client_side(themed):
    command = themed(Command())
    command.set_model(RowModel(["Alpha", "Beta", "Alphabet"]))
    command.resize(360, 320)
    assert command.list_surface().row_count() == 3

    command.set_query("alpha")
    assert command.list_surface().row_count() == 2

    command.set_query("zzz")
    assert command.list_surface().row_count() == 0


def test_the_command_leaves_the_rows_alone_without_a_filter(themed):
    command = themed(Command(should_filter=False))
    command.set_model(RowModel(["Alpha", "Beta", "Alphabet"]))
    command.resize(360, 320)
    command.set_query("zzz")
    assert command.list_surface().row_count() == 3


def test_the_command_reports_the_row_in_the_model_it_was_given(themed):
    command = themed(Command())
    command.set_model(RowModel(["Alpha", "Beta", "Alphabet"]))
    command.resize(360, 320)
    chosen = []
    command.activated.connect(chosen.append)

    command.set_query("alphabet")
    command.list_surface().highlight_first()
    command.handle_key(key(Qt.Key.Key_Return))
    assert chosen == [2]


def test_escape_clears_the_query_before_it_dismisses(themed):
    command = themed(Command())
    command.set_model(RowModel(["Alpha"]))
    gone = []
    command.dismissed.connect(lambda: gone.append(True))

    command.set_query("al")
    command.handle_key(key(Qt.Key.Key_Escape))
    assert command.query == ""
    assert gone == []

    command.handle_key(key(Qt.Key.Key_Escape))
    assert gone == [True]


# --- the calendar ------------------------------------------------------------------------


def test_the_calendar_picks_a_day_on_enter_and_emits_iso(themed):
    calendar = themed(Calendar(value="2026-03-04"))
    picked = []
    calendar.value_changed.connect(picked.append)

    calendar.handle_key(key(Qt.Key.Key_Right))
    calendar.handle_key(key(Qt.Key.Key_Return))
    assert picked == ["2026-03-05"]
    assert calendar.value == "2026-03-05"


def test_the_calendar_walks_weeks_and_months(themed):
    calendar = themed(Calendar(value="2026-03-04"))
    calendar.handle_key(key(Qt.Key.Key_Down))
    assert calendar.grid().cursor == datetime.date(2026, 3, 11)
    calendar.handle_key(key(Qt.Key.Key_PageDown))
    assert calendar.grid().cursor == datetime.date(2026, 4, 11)
    assert (calendar.grid().year, calendar.grid().month) == (2026, 4)


def test_a_range_keeps_two_ends(themed):
    calendar = themed(Calendar(mode="range"))
    calendar.grid().picked.emit(datetime.date(2026, 3, 9))
    calendar.grid().picked.emit(datetime.date(2026, 3, 4))
    assert calendar.value == ("2026-03-04", "2026-03-09")


def test_the_caption_is_a_centred_label_between_the_two_step_buttons(themed):
    """`calendar.tsx` defaults to `captionLayout="label"`: one line, not two selects."""
    calendar = themed(Calendar(value="2026-03-04"))
    assert calendar.caption_layout == "label"
    assert calendar.caption_label().isVisible()
    assert calendar.caption_label().text == "March 2026"

    calendar.step_month(1)
    assert calendar.caption_label().text == "April 2026"


def test_the_dropdown_layout_puts_the_two_selects_back(themed):
    """`captionLayout="dropdown"` is the other layout react-day-picker offers."""
    calendar = themed(Calendar(value="2026-03-04", caption_layout="dropdown"))
    assert not calendar.caption_label().isVisible()
    calendar.set_caption_layout("label")
    assert calendar.caption_label().isVisible()


def test_the_grid_stands_on_the_upstream_cell_ladder(themed):
    """`--cell-size` is 28, a week clears the one over it by `mt-2`, and the row is 7 wide."""
    calendar = themed(Calendar(value="2026-03-04"))
    grid = calendar.grid()
    first = grid.cell_rect(0, 0)
    assert (first.width(), first.height()) == (CELL, CELL)
    assert first.top() == HEADING_HEIGHT + WEEK_GAP
    assert grid.cell_rect(0, 1).top() - first.top() == WEEK_PITCH
    assert grid.sizeHint().width() == 7 * CELL
    assert grid.cell_rect(6, 0).right() + 1 == grid.sizeHint().width()


def test_the_grid_draws_the_month_s_own_number_of_weeks(themed):
    """react-day-picker draws four to six rows, and `calendar.tsx` leaves it to."""
    # February 2027 begins on a Monday and is not a leap year, so it is exactly four rows.
    calendar = themed(Calendar(value="2027-02-10", locale="fr-FR"))
    grid = calendar.grid()
    assert grid.weeks == 4
    four = grid.sizeHint().height()
    assert four == HEADING_HEIGHT + 4 * WEEK_PITCH

    # August 2026 begins on a Saturday and runs 31 days, which spills onto a sixth row.
    calendar.set_month(2026, 8)
    assert grid.weeks == 6
    assert grid.sizeHint().height() == HEADING_HEIGHT + 6 * WEEK_PITCH
    assert grid.sizeHint().height() > four


def test_fixed_weeks_keeps_the_six_row_grid(themed):
    """A caller who wants one height whatever the month says so."""
    calendar = themed(Calendar(value="2027-02-10", locale="fr-FR", fixed_weeks=True))
    grid = calendar.grid()
    assert grid.weeks == MAX_WEEKS
    calendar.set_month(2026, 8)
    assert grid.weeks == MAX_WEEKS

    grid.set_fixed_weeks(False)
    calendar.set_month(2027, 2)
    assert grid.weeks == 4


def test_the_week_starts_on_monday_outside_en_us(themed):
    calendar = themed(Calendar(value="2026-03-04", locale="fr-FR"))
    assert calendar.grid().headings()[0] == "Mo"
    calendar.set_locale("en-US")
    assert calendar.grid().headings()[0] == "Su"


# --- the table ---------------------------------------------------------------------------


def test_the_table_paints_a_header_and_its_rows(themed, qtbot):
    table = themed(TableSurface())
    table.setModel(
        TableModel([(f"Shot {i}", "ip", "2026-03-04") for i in range(6)])
    )
    table.resize(480, 260)
    qtbot.waitExposed(table)

    picture = QPixmap(table.size())
    picture.fill(QColor("#ffffff"))
    table.render(picture)
    assert ink(picture.toImage()) > 0
    assert table.header().isVisible() is True
    assert table.showGrid() is False


def test_the_table_reports_a_sort_click(themed):
    table = themed(TableSurface())
    table.setModel(TableModel([("Shot 1", "ip", "2026-03-04")]))
    asked = []
    table.sort_requested.connect(lambda column, order: asked.append((column, order)))

    table.header().sectionClicked.emit(0)
    assert asked == [(0, Qt.SortOrder.AscendingOrder)]

    table.header().sectionClicked.emit(0)
    assert asked[-1] == (0, Qt.SortOrder.DescendingOrder)

    # The second column does not sort, so a press on it says nothing.
    table.header().sectionClicked.emit(1)
    assert len(asked) == 2


def test_compact_density_halves_the_row(themed):
    table = themed(TableSurface())
    table.setModel(TableModel([("Shot 1", "ip", "2026-03-04")]))
    tall = table.verticalHeader().defaultSectionSize()
    table.set_density("compact")
    assert table.verticalHeader().defaultSectionSize() < tall
