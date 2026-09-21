"""The grouped list: its groups, its counts, its collapse, its cursor and its paging.

Every test runs on both bindings, offscreen, and never reaches the network: the rows come from
the mock client.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent

from sg_widgets_core.collection import (
    EntitySourceOptions,
    SortSpec,
    cell_value,
    create_entity_source,
    resolve_columns,
)
from sg_widgets_core.collection_state import collapse_all, expand_all
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.grouped_list import GROUPING_REQUIRED, GroupedList

from .collections import mock_context, settle

#: The column the Tasks group on, and what a row reads.
GROUP = "step.Step.code"
FIELDS = ("content", "sg_status_list", GROUP, "sg_description", "due_date")


@pytest.fixture
def context():
    return mock_context()


def _listing(context, qtbot, **options) -> GroupedList:
    source = options.pop("source", None) or create_entity_source(
        EntitySourceOptions(
            client=context.client,
            entity_type="Task",
            fields=list(FIELDS),
            mode="pages",
            page_size=25,
        )
    )
    if "group_by" not in options and "group_key" not in options:
        options["group_by"] = resolve_columns(context.schema, "Task", [GROUP])[0]
    options.setdefault("label_field", "content")
    listing = GroupedList(source=source, context=context, **options)
    apply_theme(listing, theme_for("default"))
    qtbot.addWidget(listing)
    listing.resize(700, 520)
    listing.show()
    settle(listing, listing.control.binding)
    return listing


def test_a_list_given_nothing_to_group_on_says_so(context, qtbot):
    source = create_entity_source(
        EntitySourceOptions(client=context.client, entity_type="Task", fields=list(FIELDS))
    )
    with pytest.raises(ValueError) as raised:
        GroupedList(source=source, context=context)
    assert str(raised.value) == GROUPING_REQUIRED


def test_the_group_path_leads_the_sort_and_the_runs_carry_their_counts(context, qtbot):
    listing = _listing(context, qtbot)
    settle(listing, listing.control.binding)
    # A group is only whole when the server put its rows together, so the path leads the sort.
    assert listing.control.sort[0] == SortSpec(path=GROUP, descending=False)
    groups = listing.model.groups
    assert len(groups) > 1
    assert sum(len(group.rows) for group in groups) == len(listing.control.rows)
    # Every heading takes a line of its own, above the rows it holds.
    assert listing.model.rowCount() == len(listing.control.rows) + len(groups)
    heading = listing.model.index(0, 0)
    assert heading.data(Roles.KIND) == "heading"
    assert heading.data(Roles.SECONDARY) == str(len(groups[0].rows))
    assert heading.data(Roles.CHECKED) is True


def test_collapsing_a_group_takes_its_rows_off_the_list(context, qtbot):
    listing = _listing(context, qtbot)
    settle(listing, listing.control.binding)
    groups = listing.model.groups
    whole = listing.model.rowCount()

    listing.toggle_group(groups[0].key)
    assert listing.model.rowCount() == whole - len(groups[0].rows)
    assert listing.model.index(0, 0).data(Roles.CHECKED) is False

    listing.set_collapsed(collapse_all())
    assert listing.model.rowCount() == len(listing.model.groups)
    listing.set_collapsed(expand_all())
    assert listing.model.rowCount() == whole


def test_a_row_draws_the_anatomy_of_rule_nine(context, qtbot):
    columns = resolve_columns(context.schema, "Task", [GROUP, "sg_description", "due_date"])
    listing = _listing(
        context,
        qtbot,
        group_by=columns[0],
        sub_label_field=columns[1],
        secondary_field=columns[2],
        show_code=True,
        selectable=True,
    )
    settle(listing, listing.control.binding)
    line = next(
        at for at, entry in enumerate(listing.model.lines) if entry.kind == "row"
    )
    index = listing.model.index(line, 0)
    row = listing.model.line_at(line).row
    assert index.data(Roles.LABEL) == str(cell_value(row, "content"))
    assert index.data(Roles.CHECKED) is False
    listing.control.toggle(row)
    assert index.data(Roles.CHECKED) is True
    assert len(listing.selection) == 1


def test_the_arrows_walk_the_rows_across_the_groups(context, qtbot):
    listing = _listing(context, qtbot)
    settle(listing, listing.control.binding)
    first = next(at for at, entry in enumerate(listing.model.lines) if entry.kind == "row")
    listing.view.setCurrentIndex(listing.model.index(first, 0))
    listing.on_key(
        QKeyEvent(QtCore.QEvent.Type.KeyPress, int(Qt.Key.Key_Down), Qt.KeyboardModifier.NoModifier)
    )
    assert listing.control.cursor == 1
    listing.on_key(
        QKeyEvent(QtCore.QEvent.Type.KeyPress, int(Qt.Key.Key_Up), Qt.KeyboardModifier.NoModifier)
    )
    assert listing.control.cursor == 0


def test_a_derived_key_leaves_the_order_to_the_caller(context, qtbot):
    source = create_entity_source(
        EntitySourceOptions(
            client=context.client,
            entity_type="Version",
            fields=["code", "sg_status_list", "entity", "description"],
            sort=[SortSpec(path="code", descending=False)],
            page_size=25,
        )
    )
    listing = _listing(
        context,
        qtbot,
        source=source,
        group_key=lambda row: cell_value(row, "entity"),
        group_label=lambda value: str((value or {}).get("name", "")),
        label_field="code",
    )
    settle(listing, listing.control.binding)
    # A derived key has no path to sort on, so the caller's own sort stands.
    assert listing.control.sort == [SortSpec(path="code", descending=False)]
    assert len(listing.model.groups) > 1


def test_a_page_grows_the_group_it_continues(context, qtbot):
    source = create_entity_source(
        EntitySourceOptions(
            client=context.client, entity_type="Task", fields=list(FIELDS), page_size=10
        )
    )
    listing = _listing(context, qtbot, source=source, paging="more")
    settle(listing, listing.control.binding)
    before = {group.key: len(group.rows) for group in listing.model.groups}
    assert listing.control.bottom() == "more"
    listing.control.load_more()
    settle(listing, listing.control.binding)
    after = {group.key: len(group.rows) for group in listing.model.groups}
    assert len(listing.control.rows) == 20
    # The key is the run's position and its value, so a page continuing the last run grows it.
    last = list(before)[-1]
    assert after[last] >= before[last]


def test_the_count_follows_the_heading_label_in_the_same_line(context, qtbot):
    # Upstream's heading is one flex row: chevron, label, count. The count is read as part
    # of the heading, so it answers the width the label took rather than the row's edge.
    from qtpy.QtGui import QImage, QPainter

    listing = _listing(context, qtbot)
    settle(listing, listing.control.binding)
    group = listing.model.groups[0]
    rect = QtCore.QRect(0, 0, 600, 28)
    image = QImage(rect.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    used = listing.paint_group_value(painter, rect, group)
    painter.end()
    assert 0 < used < rect.width()

    # The heading as the delegate draws it: nothing is painted in the last quarter of the
    # line, because the count sits beside the label instead.
    whole = QImage(QtCore.QSize(600, 28), QImage.Format.Format_ARGB32)
    whole.fill(Qt.GlobalColor.white)
    painter = QPainter(whole)
    option = QtWidgets.QStyleOptionViewItem()
    option.rect = QtCore.QRect(0, 0, 600, 28)
    listing.view.itemDelegate().paint(painter, option, listing.model.index(0, 0))
    painter.end()
    tail = whole.copy(QtCore.QRect(450, 0, 150, 28))
    ink = {tail.pixel(x, y) for x in range(0, 150, 3) for y in range(2, 26, 3)}
    assert len(ink) == 1


def test_the_heading_of_the_group_scrolled_into_stays_at_the_top(context, qtbot):
    """Upstream's heading is `sticky top-0`: it holds the top of the viewport while its rows
    scroll under it, the next heading pushes it up as it arrives, and a press on the pinned
    band is a press on the heading."""
    from qtpy.QtTest import QTest

    listing = _listing(context, qtbot)
    settle(listing, listing.control.binding)
    view = listing.view
    model = listing.model
    groups = model.groups
    assert len(groups) >= 2 and len(groups[0].rows) >= 2
    assert view.pinned_heading() is None, "at the top the first heading sits in its own place"

    first = view.visualRect(model.index(0, 0))
    bar = view.verticalScrollBar()
    bar.setValue(first.height() + 2)
    qtbot.wait(20)
    pinned = view.pinned_heading()
    assert pinned is not None
    heading, band = pinned
    assert heading.row() == 0 and band.top() == 0 and band.height() == first.height()

    # Scrolled to a few pixels short of the second heading, the first is pushed up by that much.
    second_at = next(i for i in range(1, model.rowCount()) if model.line_at(i).kind == "heading")
    bar.setValue(bar.value() + view.visualRect(model.index(second_at, 0)).top() - first.height() + 5)
    qtbot.wait(20)
    heading, band = view.pinned_heading()
    assert heading.row() == 0 and band.top() == -5

    # Once the second heading has passed the top, it is the one pinned.
    bar.setValue(bar.value() + first.height() + 2)
    qtbot.wait(20)
    heading, band = view.pinned_heading()
    assert heading.row() == second_at and band.top() == 0

    # A press on the pinned band collapses that group.
    whole = model.rowCount()
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, band.center())
    qtbot.wait(20)
    assert model.rowCount() == whole - len(groups[1].rows)


def test_a_re_read_stands_behind_rows_that_keep_the_lists_height(qtbot):
    """A sort re-reads the rows; the skeletons that stand in fill the height the rows had.

    Upstream draws eight rows on any read; here a first read draws those eight and a re-read
    draws as many as the rows on screen filled, so the page under the list does not jump.
    """
    slow = mock_context(latency_ms=400)
    listing = _listing(slow, qtbot)
    settle(listing, listing.control.binding)
    before = listing.height()
    rows_height = listing.view.height()
    listing.control.apply_sort([SortSpec(path="content", descending=True)])
    qtbot.wait(40)
    assert listing.control.snapshot().status == "loading"
    skeleton = listing.findChild(QtWidgets.QWidget, "grouped-list-loading")
    assert skeleton.isVisible() and not listing.view.isVisible()
    assert skeleton.rows > 1
    assert abs(skeleton.height() - rows_height) <= listing._row_height // 2
    assert abs(listing.height() - before) <= listing._row_height // 2
    settle(listing, listing.control.binding)
    assert listing.view.isVisible() and abs(listing.height() - before) <= 2


def test_a_first_page_that_fits_the_view_asks_for_the_next_on_its_own(context, qtbot):
    """Upstream's sentinel fires whenever it is visible; a view with no range has it in view."""
    source = create_entity_source(
        EntitySourceOptions(
            client=context.client, entity_type="Task", fields=list(FIELDS), mode="infinite", page_size=10
        )
    )
    listing = _listing(context, qtbot, source=source, paging="scroll")
    listing.resize(900, 1600)
    listing.show()
    settle(listing, listing.control.binding, rounds=8)
    bar = listing.view.verticalScrollBar()
    assert len(listing.control.rows) > 10
    assert bar.maximum() > bar.minimum() or not listing.control.snapshot().has_more


def test_the_read_that_raised_is_reported_as_error():
    """`docs/porting-conventions.md`: a noun event keeps its name, so `onError` is `error`."""
    from sg_widgets_qt.widgets.grouped_list import GroupedList

    assert hasattr(GroupedList, "error")
    assert not hasattr(GroupedList, "failed")
