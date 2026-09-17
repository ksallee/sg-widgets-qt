"""Port of `packages/core/test/paging.test.ts`."""
from __future__ import annotations

import dataclasses
from typing import Any

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import (
    EntitySource,
    EntitySourceOptions,
    EntitySourceState,
    create_entity_source,
)
from sg_widgets_core.mock import MOCK_NOW, MockClient, MockFailure
from sg_widgets_core.paging import (
    LoadNextOptions,
    can_load_next,
    collection_bottom,
    collection_view,
    group_rows_keyed,
    has_failed_page,
    loads_on_arrow_down,
    reached_end,
    should_load_next,
    source_mode_for,
)


def mock() -> MockClient:
    return MockClient(seed=1, now=MOCK_NOW)


def source(**over: Any) -> EntitySource:
    settings: dict[str, Any] = {
        "client": mock(),
        "entity_type": "Version",
        "fields": ["code", "sg_status_list"],
        "page_size": 10,
    }
    settings.update(over)
    return create_entity_source(EntitySourceOptions(**settings))


def state(**over: Any) -> EntitySourceState:
    settings: dict[str, Any] = {
        "rows": [],
        "status": "ready",
        "error": None,
        "has_more": True,
        "total": None,
        "filters": None,
        "sort": [],
        "mode": "infinite",
        "page": 1,
        "page_size": 10,
    }
    settings.update(over)
    return EntitySourceState(**settings)


def rows(count: int, value: str) -> list[EntityRow]:
    return [
        EntityRow(type="Version", id=at + 1, values={"sg_status_list": value}) for at in range(count)
    ]


class TestModes:
    def test_maps_a_paging_mode_onto_the_source_mode_it_needs(self) -> None:
        assert source_mode_for("pages") == "pages"
        assert source_mode_for("more") == "infinite"
        assert source_mode_for("scroll") == "infinite"

    def test_switches_a_source_between_walking_and_appending(self) -> None:
        s = source(mode="pages", page_size=25)
        s.load()
        s.set_page(2)
        assert len(s.rows) == 25

        s.set_mode("infinite")
        assert s.mode == "infinite"
        # Appending opens at the first page again, whatever page was on screen.
        assert s.page == 1
        s.load_more()
        assert len(s.rows) == 50

        same = s.snapshot()
        s.set_mode("infinite")
        assert s.snapshot() is same


class TestReachingTheEnd:
    def test_is_a_short_page_and_never_an_unread_set(self) -> None:
        assert reached_end(state(status="idle", has_more=False)) is False
        assert reached_end(state(status="loading", has_more=False)) is False

        s = source(page_size=25)
        s.load()
        assert reached_end(s.snapshot()) is False
        s.load_more()
        s.load_more()
        # 60 rows in three pages of 25: the third is short.
        assert len(s.rows) == 60
        assert reached_end(s.snapshot()) is True


class TestLoadingTheNextPage:
    def test_refuses_in_pages_mode_at_the_end_and_while_a_read_is_in_flight(self) -> None:
        assert can_load_next(state(), "pages") is False
        assert can_load_next(state(has_more=False), "scroll") is False
        assert can_load_next(state(status="loadingMore"), "more") is False
        assert can_load_next(state(status="loading"), "more") is False
        assert can_load_next(state(status="idle"), "more") is False
        assert can_load_next(state(), "more") is True
        # A failed page is asked for again, which is the retry.
        assert can_load_next(state(status="error"), "more") is True

    def test_asks_on_a_scroll_within_the_threshold_of_the_last_loaded_row(self) -> None:
        loaded = state(rows=rows(50, "ip"))
        assert should_load_next(loaded, LoadNextOptions(paging="scroll", last_visible=20)) is False
        assert should_load_next(loaded, LoadNextOptions(paging="scroll", last_visible=44)) is True
        assert should_load_next(loaded, LoadNextOptions(paging="scroll", last_visible=49)) is True
        assert should_load_next(
            loaded, LoadNextOptions(paging="scroll", last_visible=44, threshold=0)
        ) is False
        # Only `scroll` follows the scroller, and a failed page waits for its retry.
        assert should_load_next(loaded, LoadNextOptions(paging="more", last_visible=49)) is False
        assert should_load_next(loaded, LoadNextOptions(paging="pages", last_visible=49)) is False
        assert should_load_next(
            dataclasses.replace(loaded, status="error"), LoadNextOptions(paging="scroll", last_visible=49)
        ) is False

    def test_asks_when_a_cursor_steps_past_the_last_loaded_row(self) -> None:
        loaded = state(rows=rows(50, "ip"))
        assert loads_on_arrow_down(loaded, "more", 49) is False
        assert loads_on_arrow_down(loaded, "more", 50) is True
        assert loads_on_arrow_down(loaded, "scroll", 52) is True
        assert loads_on_arrow_down(loaded, "pages", 50) is False
        assert loads_on_arrow_down(dataclasses.replace(loaded, has_more=False), "more", 50) is False
        assert loads_on_arrow_down(dataclasses.replace(loaded, status="loadingMore"), "more", 50) is False

    def test_retries_a_failed_page_and_keeps_the_rows_that_landed_before_it(self) -> None:
        client = mock()
        s = create_entity_source(EntitySourceOptions(
            client=client, entity_type="Version", fields=["code"], page_size=10,
        ))
        s.load()

        client.fail_next(MockFailure(status=500, message="Flow PT API error 500"))
        s.load_more()
        assert has_failed_page(s.snapshot()) is True
        assert len(s.rows) == 10

        s.load_more()
        assert s.status == "ready"
        assert len(s.rows) == 20
        assert has_failed_page(s.snapshot()) is False

    def test_reads_a_failed_first_read_as_a_state_of_its_own_with_no_rows_under_it(self) -> None:
        client = mock()
        s = create_entity_source(EntitySourceOptions(
            client=client, entity_type="Version", fields=["code"], page_size=10,
        ))
        client.fail_next(MockFailure(status=500, message="Flow PT API error 500"))
        s.load()
        assert s.status == "error"
        assert has_failed_page(s.snapshot()) is False


class TestGroupsAcrossAPageBoundary:
    def test_grows_the_last_group_when_the_next_page_continues_it(self) -> None:
        first = group_rows_keyed([*rows(3, "ip"), *rows(2, "fin")], "sg_status_list")
        assert [g.key for g in first] == ['group:0:"ip"', 'group:1:"fin"']

        # The page that follows opens on the value the last group carries.
        second = group_rows_keyed(
            [*rows(3, "ip"), *rows(2, "fin"), *rows(4, "fin")], "sg_status_list"
        )
        assert len(second) == 2
        assert second[1].key == 'group:1:"fin"'
        assert len(second[1].rows) == 6

    def test_opens_a_group_when_the_next_page_starts_a_new_value(self) -> None:
        grown = group_rows_keyed(
            [*rows(3, "ip"), *rows(2, "fin"), *rows(4, "rev")], "sg_status_list"
        )
        assert [g.key for g in grown] == ['group:0:"ip"', 'group:1:"fin"', 'group:2:"rev"']
        assert len(grown[2].rows) == 4

    def test_keys_a_derived_group_the_same_way_so_a_shut_group_survives_the_next_page(self) -> None:
        def note(id: int, record: str) -> EntityRow:
            return EntityRow(
                type="Note",
                id=id,
                values={
                    "subject": f"n{id}",
                    "note_links": [{"type": "Shot", "id": len(record), "name": record}],
                },
            )

        def record_of(row: EntityRow) -> Any:
            links = row.values.get("note_links") or []
            return links[0].get("name") if links else None

        first = group_rows_keyed([note(1, "sh010"), note(2, "sh010"), note(3, "tree")], record_of)
        assert [g.key for g in first] == ['group:0:"sh010"', 'group:1:"tree"']
        second = group_rows_keyed(
            [note(1, "sh010"), note(2, "sh010"), note(3, "tree"), note(4, "tree")], record_of
        )
        assert second[1].key == 'group:1:"tree"'
        assert len(second[1].rows) == 2

    def test_keys_an_empty_value_and_reads_no_rows_as_no_groups(self) -> None:
        assert group_rows_keyed([], "sg_status_list") == []
        none = group_rows_keyed(
            [EntityRow(type="Version", id=1, values={})], "sg_status_list"
        )
        assert none[0].key == "group:0:null"


class TestWhatACollectionDraws:
    def test_reads_the_body_as_error_loading_empty_or_rows(self) -> None:
        assert collection_view(state(status="error", error=Exception("no")), 0) == "error"
        assert collection_view(state(status="loading"), 0) == "loading"
        assert collection_view(state(), 0) == "empty"
        assert collection_view(state(rows=rows(2, "ip")), 2) == "rows"

    def test_leaves_the_rows_up_when_a_later_page_fails(self) -> None:
        failed = state(status="error", error=Exception("no"), rows=rows(3, "ip"))
        assert collection_view(failed, 3) == "rows"

    def test_counts_the_lines_the_layout_drew_not_the_rows(self) -> None:
        # A grouped table draws headers as well, so a set with rows is never empty.
        assert collection_view(state(rows=rows(2, "ip")), 0) == "empty"

    def test_puts_one_block_under_the_last_row(self) -> None:
        assert collection_bottom(
            state(status="error", error=Exception("no"), rows=rows(3, "ip")), "scroll"
        ) == "error"
        assert collection_bottom(state(status="loadingMore"), "scroll") == "loading"
        assert collection_bottom(state(), "more") == "more"
        assert collection_bottom(state(), "scroll") == "sentinel"
        assert collection_bottom(state(), "pages") is None
        assert collection_bottom(state(has_more=False), "scroll") is None
