from __future__ import annotations

from typing import Any

from sg_widgets_core.picker_keys import (
    PickerKeyIntent,
    PickerKeyState,
    SearchKeyIntent,
    SearchKeyState,
    picker_key_intent,
    search_key_intent,
)


def state(**over: Any) -> PickerKeyState:
    fields: dict[str, Any] = {
        "open": True,
        "query": "",
        "count": 3,
        "focused": None,
        "editable": True,
        "multiple": True,
    }
    fields.update(over)
    return PickerKeyState(**fields)


class TestPickerKeyIntentFromTheInput:
    def test_reaches_the_last_chip_on_backspace_and_on_arrow_left(self) -> None:
        assert picker_key_intent("Backspace", state()) == PickerKeyIntent("focus", index=2)
        assert picker_key_intent("ArrowLeft", state()) == PickerKeyIntent("focus", index=2)

    def test_leaves_a_backspace_alone_while_the_query_has_text(self) -> None:
        assert picker_key_intent("Backspace", state(query="sh0")) == PickerKeyIntent("nothing")
        assert picker_key_intent("ArrowLeft", state(query="sh0")) == PickerKeyIntent("nothing")

    def test_leaves_a_backspace_alone_with_no_chip_to_take_and_on_a_control_that_takes_no_edits(self) -> None:
        assert picker_key_intent("Backspace", state(count=0)) == PickerKeyIntent("nothing")
        assert picker_key_intent("Backspace", state(editable=False)) == PickerKeyIntent("nothing")
        assert picker_key_intent("Backspace", state(multiple=False, count=0)) == PickerKeyIntent("nothing")

    def test_clears_a_single_picker_in_one_press_and_leaves_its_other_keys_alone(self) -> None:
        assert picker_key_intent("Backspace", state(multiple=False, count=1)) == PickerKeyIntent(
            "remove", index=0, then=None
        )
        assert picker_key_intent("ArrowLeft", state(multiple=False, count=1)) == PickerKeyIntent("nothing")
        assert picker_key_intent("Delete", state(multiple=False, count=1)) == PickerKeyIntent("nothing")

    def test_reaches_the_one_chip_of_a_multi_picker_rather_than_removing_it(self) -> None:
        assert picker_key_intent("Backspace", state(count=1)) == PickerKeyIntent("focus", index=0)

    def test_works_the_same_with_the_popup_closed(self) -> None:
        assert picker_key_intent("Backspace", state(open=False)) == PickerKeyIntent("focus", index=2)

    def test_has_nothing_to_say_about_delete_enter_or_a_character(self) -> None:
        for key in ["Delete", "Enter", "Tab", "a", " ", "ArrowRight"]:
            assert picker_key_intent(key, state()) == PickerKeyIntent("nothing")


def on_chip(**over: Any) -> PickerKeyState:
    fields: dict[str, Any] = {"focused": 1}
    fields.update(over)
    return state(**fields)


class TestPickerKeyIntentFromAChip:
    def test_walks_the_row_on_the_arrows_and_steps_off_the_last_chip_into_the_input(self) -> None:
        assert picker_key_intent("ArrowLeft", on_chip()) == PickerKeyIntent("focus", index=0)
        assert picker_key_intent("ArrowRight", on_chip()) == PickerKeyIntent("focus", index=2)
        assert picker_key_intent("ArrowLeft", on_chip(focused=0)) == PickerKeyIntent("focus", index=0)
        assert picker_key_intent("ArrowRight", on_chip(focused=2)) == PickerKeyIntent("focus", index=None)

    def test_removes_on_backspace_and_on_delete_and_takes_the_neighbour(self) -> None:
        assert picker_key_intent("Backspace", on_chip()) == PickerKeyIntent("remove", index=1, then=1)
        assert picker_key_intent("Delete", on_chip()) == PickerKeyIntent("remove", index=1, then=1)
        assert picker_key_intent("Backspace", on_chip(focused=2)) == PickerKeyIntent("remove", index=2, then=1)
        assert picker_key_intent("Backspace", on_chip(focused=0, count=1)) == PickerKeyIntent(
            "remove", index=0, then=None
        )

    def test_gives_the_caret_back_on_enter_and_space_and_writes_a_character_through(self) -> None:
        assert picker_key_intent("Enter", on_chip()) == PickerKeyIntent("focus", index=None)
        assert picker_key_intent(" ", on_chip()) == PickerKeyIntent("focus", index=None)
        assert picker_key_intent("a", on_chip()) == PickerKeyIntent("type", key="a")
        assert picker_key_intent("7", on_chip()) == PickerKeyIntent("type", key="7")

    def test_shows_the_list_on_arrow_down(self) -> None:
        assert picker_key_intent("ArrowDown", on_chip()) == PickerKeyIntent("open")
        assert picker_key_intent("ArrowDown", on_chip(open=False)) == PickerKeyIntent("open")

    def test_ignores_a_chip_index_past_the_end_and_reads_as_the_input(self) -> None:
        assert picker_key_intent("Backspace", state(focused=5)) == PickerKeyIntent("focus", index=2)

    def test_leaves_every_key_alone_on_a_control_that_takes_no_edits(self) -> None:
        for key in ["Backspace", "Delete", "ArrowLeft", "a"]:
            assert picker_key_intent(key, on_chip(editable=False)) == PickerKeyIntent("nothing")

    def test_has_nothing_to_say_about_arrow_up_or_tab(self) -> None:
        assert picker_key_intent("ArrowUp", on_chip()) == PickerKeyIntent("nothing")
        assert picker_key_intent("Tab", on_chip()) == PickerKeyIntent("nothing")


class TestPickerKeyIntentThePopup:
    def test_dismisses_on_escape_only_while_the_popup_shows(self) -> None:
        assert picker_key_intent("Escape", state()) == PickerKeyIntent("dismiss")
        assert picker_key_intent("Escape", state(open=False)) == PickerKeyIntent("nothing")
        assert picker_key_intent("Escape", state(focused=1)) == PickerKeyIntent("dismiss")

    def test_follows_the_highlight_on_the_arrows_only_while_the_popup_shows(self) -> None:
        assert picker_key_intent("ArrowDown", state()) == PickerKeyIntent("follow")
        assert picker_key_intent("ArrowUp", state()) == PickerKeyIntent("follow")
        assert picker_key_intent("ArrowUp", state(open=False)) == PickerKeyIntent("nothing")


class TestSearchKeyIntent:
    def test_clears_a_query_on_escape(self) -> None:
        assert search_key_intent("Escape", SearchKeyState(query="sh010")) == SearchKeyIntent("clear")
        assert search_key_intent("Escape", SearchKeyState(query=" ")) == SearchKeyIntent("clear")

    def test_leaves_an_escape_with_no_query_to_the_shell(self) -> None:
        assert search_key_intent("Escape", SearchKeyState(query="")) == SearchKeyIntent("nothing")

    def test_leaves_every_other_key_alone(self) -> None:
        for key in ["Enter", "Backspace", "ArrowDown", "ArrowUp", "Tab", "a"]:
            assert search_key_intent(key, SearchKeyState(query="sh010")) == SearchKeyIntent("nothing")
