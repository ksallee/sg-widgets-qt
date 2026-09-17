"""Port of `packages/core/test/search.test.ts`."""
from __future__ import annotations

import dataclasses
from typing import Any

from sg_widgets_core.search import (
    MatchRun,
    SearchViewState,
    has_more_page,
    match_runs,
    matches_every_word,
    prepend_recent,
    press_gate,
    project_of_path,
    query_plan,
    request_gate,
    search_type_map,
    search_view,
    search_words,
)


def runs(*pairs: tuple[str, bool]) -> list[MatchRun]:
    return [MatchRun(text=text, match=match) for text, match in pairs]


class TestSearchWords:
    def test_splits_on_whitespace_and_drops_the_empties(self) -> None:
        assert search_words("  pub   ke ") == ["pub", "ke"]
        assert search_words("   ") == []


class TestMatchRuns:
    def test_marks_every_occurrence_of_every_word_case_insensitively(self) -> None:
        assert match_runs("Published Ada", "pub ad") == runs(
            ("Pub", True), ("lished ", False), ("Ad", True), ("a", False)
        )

    def test_takes_a_regex_metacharacter_as_the_character_it_is(self) -> None:
        assert match_runs("v001.exr (final)", ". (") == runs(
            ("v001", False), (".", True), ("exr ", False), ("(", True), ("final)", False)
        )
        assert match_runs("plain", ".") == runs(("plain", False))

    def test_ends_on_a_matched_run_when_the_word_closes_the_label(self) -> None:
        assert match_runs("Published", "ed") == runs(("Publish", False), ("ed", True))
        assert match_runs("ed", "ed") == runs(("ed", True))

    def test_merges_overlapping_words_into_one_run(self) -> None:
        assert match_runs("abcdef", "abc bcd") == runs(("abcd", True), ("ef", False))

    def test_rebuilds_the_label_exactly_whatever_the_query(self) -> None:
        label = "sh010_0010 comp"
        for query in ["", "sh", "sh 00 comp", "zzz", "0"]:
            assert "".join(run.text for run in match_runs(label, query)) == label

    def test_is_one_plain_run_when_nothing_matches_or_nothing_is_typed(self) -> None:
        assert match_runs("Blue Moon", "zzz") == runs(("Blue Moon", False))
        assert match_runs("Blue Moon", "  ") == runs(("Blue Moon", False))
        assert match_runs("", "blue") == []


class TestMatchesEveryWord:
    def test_requires_every_word_in_any_order_and_any_position(self) -> None:
        assert matches_every_word("Published Ada", "pub ad") is True
        assert matches_every_word("Published Ada", "ad pub") is True
        assert matches_every_word("Published Ada", "pub zzz") is False
        assert matches_every_word("Published Ada", "") is True


class TestSearchTypeMap:
    def test_gives_a_bare_list_of_names_no_filter(self) -> None:
        assert search_type_map(["Shot", "Asset"]) == {"Shot": None, "Asset": None}

    def test_passes_a_map_through_untouched(self) -> None:
        map_: dict[str, Any] = {"Shot": [["project", "is", {"type": "Project", "id": 7}]]}
        assert search_type_map(map_) is map_


def key_of(ref: dict[str, Any]) -> str:
    return f"{ref['type']}:{ref['id']}"


class TestPrependRecent:
    def test_leads_with_the_new_entry_and_drops_the_one_it_repeats(self) -> None:
        shot = {"type": "Shot", "id": 1}
        asset = {"type": "Asset", "id": 2}
        assert prepend_recent([asset, shot], shot, 5, key_of) == [shot, asset]

    def test_cuts_the_list_to_the_limit(self) -> None:
        made = [{"type": "Shot", "id": id} for id in (1, 2, 3)]
        assert prepend_recent(made, {"type": "Shot", "id": 9}, 2, key_of) == [
            {"type": "Shot", "id": 9},
            {"type": "Shot", "id": 1},
        ]

    def test_leaves_the_list_it_was_given_alone(self) -> None:
        made = [{"type": "Shot", "id": 1}]
        prepend_recent(made, {"type": "Shot", "id": 2}, 5, key_of)
        assert made == [{"type": "Shot", "id": 1}]


class TestHasMorePage:
    def test_reads_a_full_page_as_a_sign_of_another_one(self) -> None:
        assert has_more_page(25, 25) is True
        assert has_more_page(24, 25) is False
        assert has_more_page(0, 25) is False


class TestProjectOfPath:
    def test_reads_the_project_a_root_path_names(self) -> None:
        assert project_of_path("/Project/70") == 70
        assert project_of_path("/Project/70/Shot") == 70

    def test_answers_nothing_on_the_site_root(self) -> None:
        assert project_of_path("/") is None
        assert project_of_path("/Shot/1") is None


class TestQueryPlan:
    def test_debounces_a_query_with_words_in_it(self) -> None:
        assert query_plan("sh010", False) == "debounce"
        assert query_plan("sh010", True) == "debounce"

    def test_empties_the_list_on_an_empty_query_unless_the_widget_reads_on_one(self) -> None:
        assert query_plan("   ", False) == "clear"
        assert query_plan("   ", True) == "now"


STATE = SearchViewState(error=None, loading=False, count=0, asked=True)


class TestSearchView:
    def test_puts_the_error_first(self) -> None:
        assert search_view(dataclasses.replace(STATE, error="boom", loading=True, count=3)) == "error"

    def test_stands_the_skeletons_in_for_a_first_page_only(self) -> None:
        assert search_view(dataclasses.replace(STATE, loading=True)) == "loading"
        assert search_view(dataclasses.replace(STATE, loading=True, count=3)) == "rows"

    def test_holds_the_empty_line_back_until_something_has_been_asked_for(self) -> None:
        assert search_view(STATE) == "empty"
        assert search_view(dataclasses.replace(STATE, asked=False)) == "rows"


class TestRequestGate:
    def test_drops_an_answer_whose_ticket_was_replaced(self) -> None:
        gate = request_gate()
        first = gate.next()
        second = gate.next()
        assert gate.holds(first) is False
        assert gate.holds(second) is True

    def test_cancels_what_is_in_flight_without_starting_anything(self) -> None:
        gate = request_gate()
        ticket = gate.next()
        gate.cancel()
        assert gate.holds(ticket) is False
        assert gate.holds(gate.next()) is True


class TestPressGate:
    def test_answers_a_replacement_the_press_led_to_once(self) -> None:
        gate = press_gate()
        gate.mark()
        assert gate.takes() is True
        assert gate.takes() is False

    def test_answers_nothing_outside_the_window_and_nothing_at_all_without_a_press(self) -> None:
        assert press_gate().takes() is False
        stale = press_gate(0)
        stale.mark()
        assert stale.takes() is False
