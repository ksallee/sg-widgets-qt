"""The entity table: its columns, its pages, its sort, its selection, its edit and its states.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent

from sg_widgets_core.collection import EntitySourceOptions, SortSpec, cell_value, create_entity_source
from sg_widgets_core.collection_state import collapse_all
from sg_widgets_core.filter import condition
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_table import (
    ENTITY_TABLE_ROW_HEIGHT,
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
