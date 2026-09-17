"""The skeletons a search draws while its read is in flight, shaped like the rows."""
from __future__ import annotations

import pytest
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QWidget

from sg_widgets_core.state import LOADING_LABEL
from sg_widgets_qt.primitives.base import THUMB_SIZE
from sg_widgets_qt.primitives.skeleton import Skeleton
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.search_skeleton import SearchSkeleton


@pytest.fixture
def host(qtbot):
    widget = QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(320, 240)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def test_it_draws_one_row_per_line(host):
    block = SearchSkeleton(host, lines=3)
    assert len(block.findChildren(QWidget, "search-skeleton-row")) == 3
    assert block.lines == 3


def test_the_line_count_is_settable(host):
    block = SearchSkeleton(host, lines=3)
    block.set_lines(1)
    assert block.lines == 1
    assert len(block.findChildren(QWidget, "search-skeleton-row")) == 1


def test_the_leading_slot_follows_the_thumbnail_ladder(host):
    block = SearchSkeleton(host, size="sm")
    assert block.lead == QSize(THUMB_SIZE["sm"], THUMB_SIZE["sm"])
    block.set_size("lg")
    assert block.lead == QSize(THUMB_SIZE["lg"], THUMB_SIZE["lg"])


def test_a_caller_names_the_leading_slot_itself(host):
    block = SearchSkeleton(host, lead=(40, 24))
    assert block.lead == QSize(40, 24)


def test_the_block_carries_the_loading_line_as_its_name(host):
    block = SearchSkeleton(host, label=LOADING_LABEL)
    assert block.accessibleName() == LOADING_LABEL
    block.set_label("Reading the crew…")
    assert block.accessibleName() == "Reading the crew…"


def test_the_slot_name_is_the_object_name(host):
    block = SearchSkeleton(host, slot_name="search-loading")
    assert block.objectName() == "search-loading"
    block.set_slot_name("context-tasks-loading")
    assert block.objectName() == "context-tasks-loading"


def test_the_rows_stand_at_a_row_height_and_take_no_gap(host):
    block = SearchSkeleton(host, lines=2)
    one = SearchSkeleton(host, lines=1)
    assert block.sizeHint().height() == 2 * one.sizeHint().height()
    assert block.layout().spacing() == 0


def test_the_shimmer_can_be_held_still(host):
    block = SearchSkeleton(host, lines=1)
    block.set_animated(False)
    assert not block.animated
    assert all(not bar.running for bar in block.findChildren(Skeleton))
