from __future__ import annotations

from sg_widgets_core.state import (
    ERROR_LABEL,
    LOADING_LABEL,
    NO_MATCH_LABEL,
    NO_ROWS_LABEL,
    StateLabels,
    error_text,
    state_line,
)


class TestStateLine:
    def test_shows_the_widget_label_for_an_empty_state(self) -> None:
        assert state_line("empty", StateLabels(empty_label=NO_MATCH_LABEL)) == "No match"

    def test_falls_back_to_the_rows_label_when_a_widget_names_none(self) -> None:
        assert state_line("empty", StateLabels()) == NO_ROWS_LABEL

    def test_names_the_loading_state_for_a_reader_who_cannot_see_skeletons(self) -> None:
        assert state_line("loading", StateLabels()) == LOADING_LABEL
        assert state_line("loading", StateLabels(loading_label="Reading Shots")) == "Reading Shots"

    def test_shows_what_the_read_said_when_the_caller_names_no_error_label(self) -> None:
        assert state_line("error", StateLabels(), "Flow PT API error 503") == "Flow PT API error 503"

    def test_replaces_the_reads_message_with_the_callers_error_label(self) -> None:
        assert (
            state_line("error", StateLabels(error_label="Could not read Shots"), "API error 503")
            == "Could not read Shots"
        )

    def test_never_leaves_an_error_state_blank(self) -> None:
        assert state_line("error", StateLabels()) == ERROR_LABEL
        assert state_line("error", StateLabels(), "   ") == ERROR_LABEL
        assert state_line("error", StateLabels(), None) == ERROR_LABEL

    def test_trims_what_the_read_said(self) -> None:
        assert state_line("error", StateLabels(), " timeout ") == "timeout"


class TestErrorText:
    def test_gives_an_errors_message(self) -> None:
        assert error_text(Exception("Flow PT API error 503")) == "Flow PT API error 503"

    def test_renders_anything_else_as_itself(self) -> None:
        assert error_text("timeout") == "timeout"
        assert error_text(404) == "404"
        # Python renders nothing as None where JavaScript renders it as null.
        assert error_text(None) == "None"

    def test_feeds_a_state_line_so_a_rejection_is_never_a_blank_block(self) -> None:
        assert state_line("error", StateLabels(), error_text(Exception(" timeout "))) == "timeout"
        assert state_line("error", StateLabels(), error_text(Exception(""))) == ERROR_LABEL
