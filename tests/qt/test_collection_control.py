"""The collection base: the source binding, the shared model, the selection and the cursor.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import pytest

from sg_widgets_core.collection import SortSpec, describe_paging
from sg_widgets_core.collection_state import collapse_all
from sg_widgets_core.filter import condition
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.collection_control import CollectionControl
from sg_widgets_qt.widgets.collection_footer import CollectionFooter

from .collections import columns_for, mock_context, settle, source_for


@pytest.fixture
def context():
    return mock_context()


def _control(context, **options) -> CollectionControl:
    control = CollectionControl(source_for(context, **options.pop("source_options", {})), **options)
    settle(None, control.binding)
    return control


def test_the_source_loads_itself_and_publishes_on_the_gui_thread(context, qtbot):
    control = _control(context)
    assert control.snapshot().status == "ready"
    assert len(control.rows) == 10
    # The rows the source published are the rows the shared model holds.
    assert control.model.rowCount() == 10
    assert control.model.row_at(0) is control.rows[0]


def test_the_columns_and_the_select_column_shape_the_model(context, qtbot):
    control = _control(context)
    control.model.set_columns(columns_for(context))
    assert control.model.columnCount() == 4
    control.model.set_select_column(True)
    assert control.model.columnCount() == 5
    assert control.model.column_at(0) is None
    assert control.model.select_offset == 1
    assert control.model.column_index_of("code") == 1


def test_the_selection_reports_once_and_a_prop_write_does_not(context, qtbot):
    control = _control(context)
    seen: list = []
    control.selection_changed.connect(seen.append)
    control.toggle(control.rows[0])
    assert len(seen) == 1
    # Taking a selection from a prop is the other direction, and writes nothing back.
    control.set_selection([])
    assert len(seen) == 1
    assert control.selection == []


def test_the_cursor_skips_a_disabled_row_and_stops_at_the_ends(context, qtbot):
    held = None

    def disabled(row):
        return row.id == held

    control = _control(context, is_row_disabled=disabled)
    held = control.rows[0].id
    assert control.active == 1
    assert control.step_cursor(1, 1) == 2
    assert control.step_cursor(-1, 1) == 1
    assert control.step_cursor(1, len(control.rows) - 1) == len(control.rows) - 1


def test_the_sort_travels_out_of_the_source(context, qtbot):
    control = _control(context)
    seen: list = []
    control.sort_changed.connect(seen.append)
    # A sort the caller pushes in is what the caller already knows, so nothing travels back.
    control.set_sort([SortSpec(path="code", descending=True)])
    settle(None, control.binding)
    assert control.sort == [SortSpec(path="code", descending=True)]
    assert seen == []
    # A sort the widget's own control makes is reported, so a `sort` prop follows it.
    control.apply_sort([SortSpec(path="code", descending=False)])
    settle(None, control.binding)
    assert seen and seen[-1] == [SortSpec(path="code", descending=False)]


def test_grouping_puts_a_heading_line_before_every_run(context, qtbot):
    control = _control(context, source_options={"page_size": 25})
    control.model.set_columns(columns_for(context))
    control.model.set_group_by("sg_status_list")
    groups = control.model.groups
    assert len(groups) > 1
    assert control.model.rowCount() == len(control.rows) + len(groups)
    assert control.model.line_at(0).kind == "heading"
    control.model.set_collapsed(collapse_all())
    assert control.model.rowCount() == len(groups)


def test_the_footer_reads_the_range_in_pages_and_the_count_otherwise(context, qtbot):
    control = _control(context, paging="pages")
    control.count()
    settle(None, control.binding)
    footer = CollectionFooter(control.binding, control.pager, page_sizes=(10, 20), slot_name="demo")
    apply_theme(footer, theme_for("default"))
    qtbot.addWidget(footer)
    footer.show()
    assert footer.objectName() == "demo-footer"
    assert footer._range.text == "1 to 10 of 60"
    assert footer._of.text == "of 6"

    control.set_paging("more")
    settle(None, control.binding)
    footer.set_pager(control.pager)
    assert footer._loaded.text.endswith("loaded")
    # The loaded count is the only thing on the line, so it sits at its start: upstream's
    # `justify-between` row leaves a lone child on the left.
    footer.resize(600, 32)
    footer.layout().activate()
    assert footer._loaded.geometry().left() < footer.width() // 2


def test_the_view_and_the_bottom_name_what_the_body_shows(context, qtbot):
    control = _control(context, paging="more", source_options={"mode": "infinite"})
    assert control.view(len(control.rows)) == "rows"
    assert control.bottom() == "more"

    control.set_filters(condition("code", "is", "no such version"))
    settle(None, control.binding)
    assert control.view(len(control.rows)) == "empty"
    assert control.bottom() is None
    assert describe_paging(control.snapshot()).to == 0
