from __future__ import annotations

from sg_widgets_core.list_chrome import (
    SEARCHING_LABEL,
    ListStatusState,
    OverflowEdges,
    count_line,
    list_status,
    overflow_edges,
)
from sg_widgets_core.state import StateLabels


class TestListStatus:
    def test_announces_a_failure_ahead_of_anything_else(self) -> None:
        assert list_status(ListStatusState(loading=True, count=3, error="Bad gateway")) == "Bad gateway"
        assert (
            list_status(
                ListStatusState(loading=False, count=0, error="Bad gateway"),
                StateLabels(error_label="Search is down"),
            )
            == "Search is down"
        )

    def test_announces_a_read_in_flight_then_what_it_answered(self) -> None:
        assert list_status(ListStatusState(loading=True, count=0)) == SEARCHING_LABEL
        assert list_status(ListStatusState(loading=False, count=1)) == "1 result"
        assert list_status(ListStatusState(loading=False, count=12)) == "12 results"

    def test_announces_an_answer_of_nothing_with_the_widgets_own_empty_line(self) -> None:
        assert list_status(ListStatusState(loading=False, count=0)) == "No rows"
        assert (
            list_status(ListStatusState(loading=False, count=0), StateLabels(empty_label="No match"))
            == "No match"
        )

    def test_stays_silent_until_something_has_been_asked_for(self) -> None:
        assert list_status(ListStatusState(loading=False, count=0, asked=False)) == ""


class TestCountLine:
    def test_counts_one_row_in_the_singular(self) -> None:
        assert count_line(0) == "0 results"
        assert count_line(1) == "1 result"
        assert count_line(2) == "2 results"


class TestOverflowEdges:
    def test_reads_nothing_past_either_edge_of_a_list_that_fits(self) -> None:
        assert overflow_edges(0, 200, 200) == OverflowEdges(start=0, end=200 - 200)

    def test_reads_the_room_above_and_below_what_is_on_show(self) -> None:
        assert overflow_edges(0, 500, 200) == OverflowEdges(start=0, end=300)
        assert overflow_edges(120, 500, 200) == OverflowEdges(start=120, end=180)
        assert overflow_edges(300, 500, 200) == OverflowEdges(start=300, end=0)

    def test_never_reads_a_negative_edge_whatever_a_rubber_band_scroll_reports(self) -> None:
        assert overflow_edges(-40, 500, 200) == OverflowEdges(start=0, end=340)
        assert overflow_edges(340, 500, 200) == OverflowEdges(start=340, end=0)
