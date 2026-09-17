from __future__ import annotations

import pytest

from sg_widgets_core.sortable import (
    SortableModelOptions,
    SortablePoint,
    SortableRect,
    SortableScrollOptions,
    create_sortable,
    sortable_announcements,
    sortable_drop_index,
    sortable_scroll_step,
    sortable_stride,
)

IDS = ["code", "status", "due", "artist", "cut_in"]


def rows(count: int = 5, height: float = 32, gap: float = 8, top: float = 100) -> list[SortableRect]:
    """Five rows of 32px with an 8px gap, starting at y=100."""
    return [
        SortableRect(
            top=top + i * (height + gap),
            bottom=top + i * (height + gap) + height,
            left=0,
            right=200,
        )
        for i in range(count)
    ]


class TestCreateSortable:
    def test_moves_an_entry_and_leaves_the_source_alone(self) -> None:
        model = create_sortable(IDS)
        assert model.move_to(0, 2) == ["status", "due", "code", "artist", "cut_in"]
        assert model.move_to(4, 1) == ["code", "cut_in", "status", "due", "artist"]
        assert model.ids == IDS

    def test_leaves_the_order_alone_for_an_index_off_either_end(self) -> None:
        model = create_sortable(IDS)
        assert model.move_to(0, -1) == IDS
        assert model.move_to(0, 5) == IDS
        assert model.move_to(-1, 2) == IDS
        assert model.move_to(2, 2) == IDS

    def test_moves_one_place_by_keyboard_and_stops_at_the_ends(self) -> None:
        model = create_sortable(IDS)
        assert model.keyboard_move("due", "up") == ["code", "due", "status", "artist", "cut_in"]
        assert model.keyboard_move("due", "down") == ["code", "status", "artist", "due", "cut_in"]
        assert model.keyboard_move("code", "up") == IDS
        assert model.keyboard_move("cut_in", "down") == IDS
        assert model.keyboard_move("missing", "down") == IDS

    def test_announces_a_position_as_one_of_the_count(self) -> None:
        model = create_sortable(IDS, SortableModelOptions(label=lambda id_: id_.upper()))
        assert model.picked_up("status") == "Picked up STATUS, position 2 of 5"
        assert model.moved_to("status", 2) == "Moved STATUS to position 3 of 5"
        assert model.dropped("status") == "Dropped STATUS"
        assert model.cancelled() == "Cancelled"

    def test_announces_the_id_itself_with_no_label(self) -> None:
        assert create_sortable(IDS).picked_up("code") == "Picked up code, position 1 of 5"
        assert sortable_announcements.move("code", 4, 5) == "Moved code to position 5 of 5"


class TestSortableDropIndex:
    def test_holds_its_place_until_a_midpoint_is_crossed(self) -> None:
        rects = rows()
        # Row 1 runs 140..172, midpoint 156; row 2 runs 180..212, midpoint 196.
        assert sortable_drop_index(rects, 1, SortablePoint(x=0, y=156)) == 1
        assert sortable_drop_index(rects, 1, SortablePoint(x=0, y=195)) == 1
        assert sortable_drop_index(rects, 1, SortablePoint(x=0, y=197)) == 2

    def test_takes_the_last_place_whose_midpoint_is_passed(self) -> None:
        rects = rows()
        assert sortable_drop_index(rects, 0, SortablePoint(x=0, y=300)) == 4
        assert sortable_drop_index(rects, 0, SortablePoint(x=0, y=1000)) == 4

    def test_takes_the_first_place_whose_midpoint_is_passed_going_up(self) -> None:
        rects = rows()
        assert sortable_drop_index(rects, 4, SortablePoint(x=0, y=115)) == 0
        assert sortable_drop_index(rects, 4, SortablePoint(x=0, y=150)) == 1
        assert sortable_drop_index(rects, 4, SortablePoint(x=0, y=-50)) == 0

    def test_reads_the_other_axis_when_horizontal(self) -> None:
        columns = [
            SortableRect(top=0, bottom=40, left=0, right=100),
            SortableRect(top=0, bottom=40, left=100, right=200),
            SortableRect(top=0, bottom=40, left=200, right=300),
        ]
        assert sortable_drop_index(columns, 0, SortablePoint(x=149, y=20), "horizontal") == 0
        assert sortable_drop_index(columns, 0, SortablePoint(x=151, y=20), "horizontal") == 1
        assert sortable_drop_index(columns, 2, SortablePoint(x=49, y=20), "horizontal") == 0

    def test_answers_with_the_source_for_an_index_off_the_list(self) -> None:
        assert sortable_drop_index(rows(), 9, SortablePoint(x=0, y=150)) == 9
        assert sortable_drop_index([], 0, SortablePoint(x=0, y=0)) == 0


class TestSortableStride:
    def test_is_the_distance_to_the_next_row_gap_included(self) -> None:
        assert sortable_stride(rows(), 0) == 40
        assert sortable_stride(rows(), 4) == 40

    def test_falls_back_to_the_row_height_for_a_list_of_one(self) -> None:
        assert sortable_stride(rows(1), 0) == 32
        assert sortable_stride([], 0) == 0


class TestSortableScrollStep:
    BOUNDS = SortableRect(top=0, bottom=400, left=0, right=200)

    def test_is_zero_away_from_the_edges(self) -> None:
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=200)) == 0
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=60)) == 0
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=340)) == 0

    def test_grows_towards_the_edge_and_stops_at_the_speed(self) -> None:
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=24)) == pytest.approx(-6)
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=0)) == pytest.approx(-12)
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=-100)) == pytest.approx(-12)
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=376)) == pytest.approx(6)
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=0, y=400)) == pytest.approx(12)

    def test_leaves_a_container_shorter_than_two_thresholds_alone(self) -> None:
        bounds = SortableRect(top=0, bottom=80, left=0, right=200)
        assert sortable_scroll_step(bounds, SortablePoint(x=0, y=4)) == 0

    def test_reads_the_other_axis_when_horizontal(self) -> None:
        options = SortableScrollOptions(orientation="horizontal")
        assert sortable_scroll_step(self.BOUNDS, SortablePoint(x=8, y=200), options) == pytest.approx(-10)
