"""The entity table: its columns, its pages, its sort, its selection, its edit and its states.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import QImage, QKeyEvent, QPainter

from sg_widgets_core.collection import EntitySourceOptions, SortSpec, cell_value, create_entity_source
from sg_widgets_core.collection_state import collapse_all
from sg_widgets_core.filter import condition
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_table import (
    ENTITY_TABLE_HEAD,
    ENTITY_TABLE_ROW_HEIGHT,
    ENTITY_TABLE_TEXT,
    EntityTable,
)
from sg_widgets_qt.widgets.state_line import StateLine

from .collections import (
    VERSION_FIELDS,
    FailingClient,
    columns_for,
    mock_context,
    settle,
    source_for,
)


@pytest.fixture
def context():
    return mock_context()


def _table(context, qtbot, **options) -> EntityTable:
    source = options.pop("source", None) or source_for(context)
    columns = options.pop("columns", None)
    table = EntityTable(
        source=source,
        columns=columns if columns is not None else columns_for(context),
        context=context,
        **options,
    )
    apply_theme(table, theme_for("default"))
    qtbot.addWidget(table)
    table.resize(900, 520)
    table.show()
    settle(table, table.control.binding)
    return table


def test_the_columns_resolve_into_the_shared_model(context, qtbot):
    table = _table(context, qtbot)
    assert [column.path for column in table.columns] == list(VERSION_FIELDS)
    # The select column is off, so the model's columns are the field columns alone.
    assert table.model.columnCount() == len(VERSION_FIELDS)
    status = table.model.column_at(1)
    assert status is not None and status.data_type == "status_list"
    # A status cell carries the field schema, so its label comes out of `display_values`.
    assert status.field is not None
    assert table.model.column_index_of("user") == 2


def test_a_page_lands_and_the_footer_counts_the_set(context, qtbot):
    table = _table(context, qtbot, paging="pages")
    table.control.count()
    settle(table, table.control.binding)
    assert len(table.control.rows) == 10
    assert table.model.rowCount() == 10
    pager = table.control.pager
    assert pager.from_ == 1 and pager.to == 10
    # A read carries no total, so the range reads "of N" only once `_summarize` counted it.
    assert pager.total == 60
    assert pager.range_label == "1 to 10 of 60"
    assert table.footer._range.text == "1 to 10 of 60"


def test_load_more_appends_the_next_page(context, qtbot):
    source = source_for(context, mode="infinite", page_size=10)
    table = _table(context, qtbot, source=source, paging="more")
    assert len(table.control.rows) == 10
    assert table.control.bottom() == "more"
    table.control.load_more()
    settle(table, table.control.binding)
    assert len(table.control.rows) == 20
    assert table.model.rowCount() == 20


def test_the_scroller_asks_for_the_next_page(context, qtbot):
    source = source_for(context, mode="infinite", page_size=10)
    table = _table(context, qtbot, source=source, paging="scroll")
    assert table.control.bottom() == "sentinel"
    # The threshold is five rows from the end, so row 5 of ten is far enough down.
    table.control.on_last_visible(5)
    settle(table, table.control.binding)
    assert len(table.control.rows) == 20


def test_a_header_click_sorts_and_reads_the_page_again(context, qtbot):
    table = _table(context, qtbot)
    table.toggle_sort("code")
    settle(table, table.control.binding)
    assert table.control.sort == [SortSpec(path="code", descending=False)]
    codes = [str(cell_value(row, "code")) for row in table.control.rows]
    assert codes == sorted(codes)
    # Ascending, then descending, then unsorted, which is the server's id ascending.
    table.toggle_sort("code")
    settle(table, table.control.binding)
    assert table.control.sort == [SortSpec(path="code", descending=True)]
    table.toggle_sort("code")
    settle(table, table.control.binding)
    assert table.control.sort == []


def test_the_selection_is_tri_state_over_the_loaded_rows(context, qtbot):
    table = _table(context, qtbot, selectable=True)
    assert table.model.select_column is True
    assert table.model.columnCount() == len(VERSION_FIELDS) + 1
    assert table.control.all_selected.all is False
    assert table.control.all_selected.some is False

    table.control.toggle(table.control.rows[0])
    assert table.control.all_selected.some is True
    assert table.control.all_selected.all is False
    assert len(table.selection) == 1

    table.control.toggle_all(True)
    assert table.control.all_selected.all is True
    assert len(table.selection) == len(table.control.rows)

    table.control.toggle_all(False)
    assert table.selection == []


def test_a_cell_edit_commits_and_the_row_is_read_back(context, qtbot):
    table = _table(context, qtbot, editable=True)
    row = table.control.rows[0]
    before = str(cell_value(row, "code"))
    column = next(one for one in table.columns if one.path == "code")
    assert table.can_edit(column, row) is True

    table.commit(table.model.key_of(row), column, before + "_edited")
    settle(table, table.control.binding)

    # The write answers the whole record but resolves no dotted path, so the source reads the
    # row again with its own projection (024_read_after_write).
    fresh = table.control.rows[0]
    assert str(cell_value(fresh, "code")) == before + "_edited"
    assert table.cell_error(table.model.key_of(fresh), "code") == ""


def test_a_refused_write_says_why_in_the_cell(context, qtbot):
    refusing = FailingClient(context.client, fail_update=True)
    source = create_entity_source(
        EntitySourceOptions(
            client=refusing, entity_type="Version", fields=list(VERSION_FIELDS), page_size=10
        )
    )
    table = _table(context, qtbot, source=source, editable=True)
    row = table.control.rows[0]
    column = next(one for one in table.columns if one.path == "code")
    key = table.model.key_of(row)
    before = str(cell_value(row, "code"))
    table.commit(key, column, before + "_refused")
    settle(table, table.control.binding)
    # The cell goes back to what the row still holds and says why beside it.
    assert str(cell_value(table.control.rows[0], "code")) == before
    assert "403" in table.cell_error(key, "code")


def test_the_empty_and_the_error_states_replace_the_rows(context, qtbot):
    empty = source_for(context)
    empty.set_filters(condition("code", "is", "no such version"))
    table = _table(context, qtbot, source=empty, empty_label="No Version here")
    settle(table, table.control.binding)
    assert table.control.view(table.model.rowCount()) == "empty"
    line = table.findChild(StateLine, "entity-table-state")
    assert line is not None and line.isVisible() and line.label == "No Version here"

    failing = FailingClient(context.client, fail_search=True)
    broken = create_entity_source(
        EntitySourceOptions(
            client=failing, entity_type="Version", fields=list(VERSION_FIELDS), page_size=10
        )
    )
    failed = _table(context, qtbot, source=broken)
    settle(failed, failed.control.binding)
    assert failed.control.view(failed.model.rowCount()) == "error"
    said = failed.findChild(StateLine, "entity-table-state")
    assert said is not None and said.state == "error"
    assert "503" in said.label


def test_collapse_shuts_a_group_and_a_later_page_follows_the_mode(context, qtbot):
    source = source_for(context, mode="infinite", page_size=10)
    table = _table(context, qtbot, source=source, paging="more", group_by="sg_status_list")
    settle(table, table.control.binding)
    groups = table.model.groups
    assert len(groups) > 0
    open_lines = table.model.rowCount()
    assert open_lines == len(table.control.rows) + len(groups)

    table._toggle_group(groups[0].key)
    assert table.model.rowCount() == open_lines - len(groups[0].rows)

    # Collapse all is a mode, not a key list, so the groups a later page brings are shut too.
    table.set_collapsed(collapse_all())
    assert table.model.rowCount() == len(table.model.groups)
    table.control.load_more()
    settle(table, table.control.binding)
    assert table.model.rowCount() == len(table.model.groups)


def test_density_halves_the_row_and_the_arrows_walk_the_body(context, qtbot):
    table = _table(context, qtbot, selectable=True)
    assert table.view.verticalHeader().defaultSectionSize() == ENTITY_TABLE_ROW_HEIGHT["default"]
    table.set_density("compact")
    assert table.view.verticalHeader().defaultSectionSize() == ENTITY_TABLE_ROW_HEIGHT["compact"]

    table.view.setFocus()
    down = QKeyEvent(QtCore.QEvent.Type.KeyPress, int(Qt.Key.Key_Down), Qt.KeyboardModifier.NoModifier)
    assert table.on_body_key(down) is True
    assert table.control.cursor == 0
    assert table.on_body_key(down) is True
    assert table.control.cursor == 1


def test_a_disabled_row_refuses_the_selection_and_the_cursor(context, qtbot):
    table = _table(context, qtbot, selectable=True)
    held = table.control.rows[0].id
    table.set_is_row_disabled(lambda row: row.id == held)

    table.control.toggle(table.control.rows[0])
    assert table.selection == []
    table.control.toggle_all(True)
    assert all(ref.id != held for ref in table.selection)
    assert len(table.selection) == len(table.control.rows) - 1
    # A page whose every row is held back is neither all nor some.
    assert table.control.all_selected.all is True
    # The cursor skips it, so the first row it can land on is the second.
    assert table.control.active == 1


def test_hiding_a_column_writes_the_shorter_list_back(context, qtbot):
    table = _table(context, qtbot)
    seen: list = []
    table.columns_changed.connect(seen.append)
    table.hide_column("user")
    assert [column.path for column in table.columns] == ["code", "sg_status_list", "created_at"]
    assert len(seen) == 1
    assert [column.path for column in seen[0]] == ["code", "sg_status_list", "created_at"]


def test_every_region_carries_its_upstream_slot_name(context, qtbot):
    table = _table(context, qtbot, selectable=True)
    table.set_toolbar_start(QtWidgets.QLabel("start", table))
    assert table.objectName() == "entity-table"
    assert table.view.objectName() == "entity-table-scroll"
    assert table.footer.objectName() == "entity-table-footer"
    assert table.findChild(QtWidgets.QWidget, "entity-table-toolbar") is not None
    assert table.findChild(QtWidgets.QWidget, "entity-table-toolbar-start") is not None
    assert table.findChild(QtWidgets.QWidget, "entity-table-toolbar-end") is not None


def test_a_sortable_header_says_so_before_anything_sorts_by_it(context, qtbot):
    # `ChevronsUpDown ... opacity-50` stands on a sortable column before anything sorts by
    # it, and the arrow takes its place once something does.
    from sg_widgets_qt.primitives.table import CELL_PAD_X, SORT_GLYPH

    table = _table(context, qtbot)
    header = table.view.header()
    rect = QtCore.QRect(0, 0, 200, ENTITY_TABLE_HEAD["md"])
    mark = QtCore.QRect(
        rect.right() + 1 - CELL_PAD_X - SORT_GLYPH, rect.top(), SORT_GLYPH, rect.height()
    )

    def drawn(column: int):
        image = QImage(rect.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        header.paintSection(painter, rect, column)
        painter.end()
        return image

    blank = QImage(mark.size(), QImage.Format.Format_ARGB32)
    blank.fill(Qt.GlobalColor.white)
    assert header.sortable(0) is True
    unsorted = drawn(0)
    assert unsorted.copy(mark) != blank
    header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
    ascending = drawn(0)
    assert ascending.copy(mark) != unsorted.copy(mark)
    header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
    assert drawn(0).copy(mark) != ascending.copy(mark)
    # Sorting by another column puts the plain affordance back on this one.
    header.setSortIndicator(1, Qt.SortOrder.AscendingOrder)
    assert drawn(0).copy(mark) == unsorted.copy(mark)


def test_the_header_wears_the_body_step_and_follows_the_size(context, qtbot):
    # `TableHead` is `font-medium text-foreground` at `TEXT[size]`, not a muted 12px line.
    from sg_widgets_qt.primitives.table import CELL_TEXT, HEADER_TEXT

    assert HEADER_TEXT == CELL_TEXT
    table = _table(context, qtbot)
    header = table.view.header()
    assert header._text == ENTITY_TABLE_TEXT["md"]
    table.set_size("lg")
    assert header._text == ENTITY_TABLE_TEXT["lg"]


def test_the_field_path_stands_beside_the_label_under_a_column_menu(context, qtbot):
    # Upstream draws `showCode` inside the head's own row, so the menu never displaces it.
    table = _table(context, qtbot, show_code=True, column_menu=True)
    header = table.view.header()
    paths = [header.suffix(column) for column in range(table.model.columnCount())]
    assert "sg_status_list" in paths


def test_an_editable_cell_says_it_can_be_edited(context, qtbot):
    from sg_widgets_qt.widgets.entity_table import EDIT_HINT

    table = _table(context, qtbot, editable=True)
    row = next(at for at, line in enumerate(table.model.lines) if line.kind == "row")
    editable = next(
        at
        for at, column in enumerate(table.columns)
        if table.can_edit(column, table.model.lines[row].row)
    )
    assert table.edit_hint(table.model.index(row, editable)) == EDIT_HINT
    table.set_editable(False)
    assert table.edit_hint(table.model.index(row, editable)) == ""


def test_a_group_heading_reads_its_count_beside_its_value(context, qtbot):
    # Upstream's heading is one flex row: chevron, value, count. A spanned row is wide, so
    # a count at its far edge would read as a column of its own.
    from qtpy.QtGui import QImage, QPainter

    table = _table(context, qtbot, group_by="sg_status_list")
    settle(table, table.control.binding)
    assert table.model.groups
    rect = QtCore.QRect(0, 0, 900, ENTITY_TABLE_ROW_HEIGHT["default"])
    image = QImage(rect.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = rect
    table.view.itemDelegate().paint(painter, option, table.model.index(0, 0))
    painter.end()
    ink = {
        image.pixel(x, y)
        for x in range(rect.width() // 2, rect.width(), 3)
        for y in range(2, rect.height() - 2, 3)
    }
    assert len(ink) == 1


def test_a_cell_holding_an_editor_paints_no_value_of_its_own(context, qtbot):
    """The editor mounted on the cell draws the value; the delegate leaves the cell bare underneath."""
    table = _table(context, qtbot, editable=True, editor_placement="popover")
    row = table.control.rows[0]
    index = table._index_of(table.model.key_of(row), "code")
    assert index.isValid()
    delegate = table.view.itemDelegate()
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = QtCore.QRect(0, 0, 220, 40)

    def painted() -> QImage:
        image = QImage(220, 40, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        delegate.paint(painter, option, index)
        painter.end()
        return image

    plain = painted()
    table.open_editor(index)
    assert table.is_editing(table.model.key_of(row), "code")
    bare = painted()
    assert plain != bare
    ink = {bare.pixelColor(x, 20).name() for x in range(12, 200)}
    assert len(ink) <= 2, "only the ground and the rule are left under the editor"
    table.close_editor()
    assert painted() == plain


def _head_press(table: EntityTable, column: int) -> None:
    """A press in the middle of one header section, the way a reader presses it."""
    from qtpy.QtTest import QTest

    header = table._header
    QTest.mouseClick(
        header.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(
            header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
            header.height() // 2,
        ),
    )


def test_the_header_box_follows_the_selection_and_a_second_press_clears_it(context, qtbot):
    """The header's tri state is written when the selection moves, not only when a page lands.

    Taking a row moves no snapshot, so a box synced on `changed` alone never drew itself
    full, and the press that should have cleared the selection took every row again.
    """
    table = _table(context, qtbot, selectable=True)
    assert table.control.rows

    _head_press(table, 0)
    assert len(table.selection) == len(table.control.rows)
    assert table._header._all is True

    _head_press(table, 0)
    assert table.selection == []
    assert table._header._all is False
    assert table._header._some is False

    table.control.toggle(table.control.rows[0])
    assert table._header._some is True
    assert table._header._all is False


def test_the_header_box_reports_the_selection_once(context, qtbot):
    """`selection_changed` still reaches the caller, once per move."""
    table = _table(context, qtbot, selectable=True)
    seen: list = []
    table.selection_changed.connect(seen.append)
    _head_press(table, 0)
    assert len(seen) == 1
    assert len(seen[0]) == len(table.control.rows)


@pytest.mark.parametrize("placement", ["popover", "inline"])
def test_escape_in_a_cell_editor_restores_the_value_and_takes_the_editor_off(
    context, qtbot, placement
):
    """Escape cancels: the cell keeps what it held and no editor is left mounted on it.

    A half mounted straight in edit mode records nothing to restore unless it is given the
    value it opened on, so a cancel used to hand the table `None` and the write emptied the
    field. An inline half that closed itself was left on the cell for ever.
    """
    from qtpy.QtGui import QKeyEvent as _QKeyEvent

    table = _table(context, qtbot, editable=True, editor_placement=placement)
    row = table.control.rows[0]
    key = table.model.key_of(row)
    before = cell_value(row, "code")
    index = table._index_of(key, "code")
    table.open_editor(index)
    assert table.is_editing(key, "code")

    editor = table.view.indexWidget(index)
    assert editor is not None
    QtWidgets.QApplication.sendEvent(
        editor,
        _QKeyEvent(QtCore.QEvent.Type.KeyPress, int(Qt.Key.Key_Escape), Qt.KeyboardModifier.NoModifier),
    )
    settle(table, table.control.binding)

    assert table._editing is None
    assert table.view.indexWidget(table._index_of(key, "code")) is None
    assert cell_value(table.control.rows[0], "code") == before


def test_a_cell_editor_mounted_in_edit_mode_knows_what_to_restore(context, qtbot):
    """The half the table mounts holds the cell's value as the one a cancel puts back."""
    from sg_widgets_qt.widgets.field_editor import FieldEditor

    table = _table(context, qtbot, editable=True, editor_placement="inline")
    row = table.control.rows[0]
    index = table._index_of(table.model.key_of(row), "code")
    table.open_editor(index)
    editor = table.view.indexWidget(index)
    assert isinstance(editor, FieldEditor)
    assert editor._original == cell_value(row, "code")
    table.close_editor()


def _head_point(header, column: int) -> QtCore.QPoint:
    """The middle of one header section."""
    return QtCore.QPoint(
        header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
        header.height() // 2,
    )


def _head_drag(header, carried: int, onto: int) -> None:
    """Carry one section onto another, the way a reader drags it."""
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtTest import QTest

    start, end = _head_point(header, carried), _head_point(header, onto)
    QTest.mousePress(
        header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start
    )
    for point in (QtCore.QPoint(start.x() + 8, start.y()), end):
        QtWidgets.QApplication.sendEvent(
            header.viewport(),
            QMouseEvent(
                QMouseEvent.Type.MouseMove,
                QPointF(float(point.x()), float(point.y())),
                QPointF(header.viewport().mapToGlobal(point)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
    QTest.mouseRelease(
        header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end
    )


def _menu_press(table: EntityTable, column: int, text: str) -> None:
    """Open one header's menu and press the row of that name."""
    table._open_column_menu(column, QtCore.QPoint())
    menu = table._menu
    texts = [entry.text for entry in menu.list.entries]
    menu.list.activate(texts.index(text))


def test_pin_left_sticks_a_column_to_the_start_and_unpin_gives_it_back(context, qtbot):
    table = _table(context, qtbot, column_menu=True)
    at = table.model.column_index_of("created_at")
    _menu_press(table, at, "Pin left")
    assert table.pinned_columns == ["created_at"]
    # The pinned column leads the drawn order; the list the caller handed is untouched.
    assert table.column_order == ["created_at", "code", "sg_status_list", "user"]
    assert [column.path for column in table.columns] == list(VERSION_FIELDS)
    assert table.frozen.isVisible()
    assert table.model.column_index_of("created_at") == 0

    _menu_press(table, 0, "Unpin")
    assert table.pinned_columns == []
    assert table.column_order == list(VERSION_FIELDS)
    assert not table.frozen.isVisible()


def test_the_frozen_column_holds_its_place_while_the_body_scrolls(context, qtbot):
    table = _table(context, qtbot)
    table.resize(420, 420)
    table.pin_column("code")
    qtbot.waitUntil(table.frozen.isVisible, timeout=2000)
    across = table.view.horizontalScrollBar()
    assert across.maximum() > 0
    left = table.frozen.x()
    down = table.view.verticalScrollBar()

    across.setValue(across.maximum())
    QtWidgets.QApplication.processEvents()
    assert table.frozen.x() == left
    assert table.body_scrolled() is True
    # The body ran under it, so the two views still show one row per line.
    down.setValue(down.maximum())
    QtWidgets.QApplication.processEvents()
    assert table.frozen.verticalScrollBar().value() == down.value()


def test_a_header_drag_reorders_the_columns_and_does_not_sort(context, qtbot):
    table = _table(context, qtbot)
    before = list(table.control.sort)
    _head_drag(table._header, table.model.column_index_of("created_at"), 0)
    assert table.column_order == ["created_at", "code", "sg_status_list", "user"]
    # A drop is not a click, so the column it ended on does not also sort.
    assert list(table.control.sort) == before
    # The order is the table's own: the list the caller handed is not written back.
    assert [column.path for column in table.columns] == list(VERSION_FIELDS)


def test_a_carried_header_says_where_it_lands(context, qtbot):
    table = _table(context, qtbot)
    header = table._header
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtTest import QTest

    start = _head_point(header, 3)
    QTest.mousePress(
        header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start
    )
    target = _head_point(header, 0)
    QtWidgets.QApplication.sendEvent(
        header.viewport(),
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(float(target.x()), float(target.y())),
            QPointF(header.viewport().mapToGlobal(target)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    assert header._drag == 3 and header._drop == 0
    QTest.mouseRelease(
        header.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target
    )
    assert header._drag == -1 and header._drop == -1


def test_an_edit_in_a_pinned_cell_commits_through_the_same_path(context, qtbot):
    table = _table(context, qtbot, editable=True)
    table.pin_column("code")
    row = table.control.rows[0]
    before = str(cell_value(row, "code"))
    index = table.model.index(0, table.model.column_index_of("code"))
    # The pinned cell is drawn by the frozen view, so the editor mounts there.
    assert table.view_for(index.column()) is table.frozen
    table.open_editor(index)
    assert table.frozen.indexWidget(index) is not None
    column = next(one for one in table.columns if one.path == "code")

    table.commit(table.model.key_of(row), column, before + "_pinned")
    settle(table, table.control.binding)
    assert str(cell_value(table.control.rows[0], "code")) == before + "_pinned"
    assert table.frozen.indexWidget(index) is None


def test_a_re_read_draws_blank_rows_under_the_header_and_keeps_the_box(context, qtbot):
    """A read stands in for the rows it replaces: same header, same room, one bar per cell."""
    slow = mock_context(latency_ms=400)
    table = _table(context, qtbot, source=source_for(slow, page_size=10))
    held_rows = len(table.model.lines)
    held_height = table.view.height()
    assert held_rows == 10

    table.toggle_sort("code")
    qtbot.waitUntil(lambda: table.control.snapshot().status == "loading", timeout=2000)
    QtWidgets.QApplication.processEvents()
    # The header stays where it was, and the blank rows take the body's own room.
    assert table.view.isVisible()
    assert table._header.isVisible()
    assert table._skeleton.isVisible()
    assert table._skeleton.rows == held_rows
    assert table.view.height() == ENTITY_TABLE_HEAD[table.size]
    assert table.view.height() + table._skeleton.height() == held_height
    bars = table._skeleton.blocks()
    assert len(bars) == held_rows * table.model.columnCount()
    assert all(bar.height() == 24 for bar in bars)

    settle(table, table.control.binding)
    assert not table._skeleton.isVisible()
    assert table.view.height() == held_height


def test_a_cold_read_draws_the_eight_blank_rows_upstream_draws(context, qtbot):
    slow = mock_context(latency_ms=400)
    source = source_for(slow, page_size=10)
    table = EntityTable(source=source, columns=columns_for(context), context=slow)
    apply_theme(table, theme_for("default"))
    qtbot.addWidget(table)
    table.resize(900, 520)
    table.show()
    qtbot.waitUntil(lambda: table.control.snapshot().status == "loading", timeout=2000)
    QtWidgets.QApplication.processEvents()
    assert table._skeleton.rows == 8
    settle(table, table.control.binding)
