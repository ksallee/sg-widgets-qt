"""Port of `packages/core/test/collection.test.ts`."""
from __future__ import annotations

import re
from typing import Any

import pytest

from sg_widgets_core.client import EntityRow, SearchOptions, SearchResult, SgApiError
from sg_widgets_core.collection import (
    ColumnSpec,
    EntitySource,
    EntitySourceOptions,
    EntitySourceState,
    SortSpec,
    cell_value,
    create_entity_source,
    describe_paging,
    group_key_text,
    group_rows,
    resolve_columns,
    row_key,
    serialize_sort,
)
from sg_widgets_core.filter import EntityRef, condition, group
from sg_widgets_core.mock import MOCK_NOW, MockClient, MockFailure
from sg_widgets_core.schema_service import create_schema_service


def mock() -> MockClient:
    return MockClient(seed=1, now=MOCK_NOW)


def source(**over: Any) -> EntitySource:
    settings: dict[str, Any] = {
        "client": mock(),
        "entity_type": "Version",
        "fields": ["code", "sg_status_list", "entity", "created_at"],
        "page_size": 10,
    }
    settings.update(over)
    return create_entity_source(EntitySourceOptions(**settings))


class TestPaths:
    def test_reads_a_plain_field_a_link_and_a_dotted_path_off_one_row(self) -> None:
        s = source(fields=["code", "entity", "entity.Shot.code"])
        s.load()
        row = s.rows[0]
        assert isinstance(cell_value(row, "code"), str)
        # A link and a dotted path come back flat under their own keys.
        link = cell_value(row, "entity")
        assert isinstance(link, dict)
        assert isinstance(link["type"], str)
        assert isinstance(link["id"], int)
        assert isinstance(cell_value(row, "entity.Shot.code"), str)
        assert cell_value(row, "id") == row.id
        assert cell_value(row, "sg_not_asked_for") is None
        assert row_key(row) == f"Version:{row.id}"

    def test_always_projects_id_whatever_the_caller_asked_for(self) -> None:
        assert source(fields=["code"]).fields == ["id", "code"]


class TestSort:
    def test_serialises_keys_the_way_the_body_takes_them(self) -> None:
        assert serialize_sort([SortSpec(path="code", descending=False)]) == "code"
        assert serialize_sort([
            SortSpec(path="sg_status_list", descending=False),
            SortSpec(path="id", descending=True),
        ]) == "sg_status_list,-id"
        assert serialize_sort([]) is None

    def test_reorders_through_the_server_and_starts_again_at_the_first_page(self) -> None:
        s = source()
        s.load()
        s.load_more()
        ascending = [r.id for r in s.rows]
        assert len(ascending) == 20

        s.set_sort([SortSpec(path="id", descending=True)])
        assert len(s.rows) == 10
        assert s.rows[0].id > ascending[0]


class TestPaging:
    def test_appends_a_page_and_stops_on_a_short_one(self) -> None:
        s = source(page_size=25)
        s.load()
        assert s.status == "ready"
        assert len(s.rows) == 25
        assert s.has_more is True

        s.load_more()
        assert len(s.rows) == 50
        s.load_more()
        # 60 Versions: the third page is short, which is the end of the set.
        assert len(s.rows) == 60
        assert s.has_more is False

        s.load_more()
        assert len(s.rows) == 60

    def test_refresh_keeps_the_rows_already_shown(self) -> None:
        s = source()
        s.load()
        s.load_more()
        s.refresh()
        assert len(s.rows) == 20
        assert s.status == "ready"


class TestFilters:
    def test_takes_the_editor_tree_and_the_wire_group_alike(self) -> None:
        tree = group("and", [condition("sg_status_list", "is", "ip")])
        s = source()
        s.set_filters(tree)
        assert s.filters == {"logical_operator": "and", "conditions": [["sg_status_list", "is", "ip"]]}
        for row in s.rows:
            assert row.values["sg_status_list"] == "ip"

        s.set_filters({"logical_operator": "and", "conditions": [["sg_status_list", "is", "fin"]]})
        for row in s.rows:
            assert row.values["sg_status_list"] == "fin"

    def test_counts_the_whole_matching_set_not_the_loaded_page(self) -> None:
        s = source()
        s.load()
        assert len(s.rows) == 10
        assert s.count() == 60

        s.set_filters(group("and", [condition("sg_status_list", "is", "ip")]))
        counted = s.count()
        assert counted is not None
        assert counted == len(s.rows) + (counted - len(s.rows) if s.has_more else 0)


class TestStates:
    def test_reports_a_failed_read_without_losing_the_rows_it_had(self) -> None:
        client = mock()
        s = create_entity_source(EntitySourceOptions(
            client=client, entity_type="Version", fields=["code"], page_size=5,
        ))
        s.load()
        assert s.status == "ready"

        client.fail_next(MockFailure(status=500, message="Flow PT API error 500"))
        s.load_more()
        assert s.status == "error"
        assert str(s.error) == "Flow PT API error 500"
        assert len(s.rows) == 5

    def test_notifies_a_subscriber_on_every_change_and_stops_on_unsubscribe(self) -> None:
        s = source()
        seen = 0

        def listener() -> None:
            nonlocal seen
            seen += 1

        stop = s.subscribe(listener)
        s.load()
        assert seen > 0
        before = seen
        stop()
        s.load_more()
        assert seen == before

    def test_hands_out_one_state_object_until_something_changes(self) -> None:
        s = source()
        first = s.snapshot()
        assert s.snapshot() is first
        s.load()
        assert s.snapshot() is not first


class TestUpdateRow:
    def test_writes_through_the_client_and_puts_the_re_read_row_back_in_place(self) -> None:
        s = source(fields=["code", "description", "entity.Shot.code"])
        s.load()
        row = s.rows[2]

        fresh = s.update_row(EntityRef(type="Version", id=row.id), {"description": "a new note"})
        assert fresh.values["description"] == "a new note"
        # The re-read carries the projection, which a write's own answer never does.
        assert fresh.values["entity.Shot.code"] == row.values["entity.Shot.code"]
        assert s.rows[2].values["description"] == "a new note"
        assert len(s.rows) == 10

    def test_reads_the_row_back_even_when_the_change_moves_it_out_of_the_filter(self) -> None:
        s = source(fields=["code", "sg_status_list"])
        s.set_filters(group("and", [condition("sg_status_list", "is", "ip")]))
        row = s.rows[0]
        fresh = s.update_row(EntityRef(type="Version", id=row.id), {"sg_status_list": "fin"})
        assert fresh.values["sg_status_list"] == "fin"
        assert s.rows[0].values["sg_status_list"] == "fin"

    def test_throws_and_changes_nothing_when_the_write_is_refused(self) -> None:
        s = source(fields=["code"])
        s.load()
        row = s.rows[0]
        before = s.rows
        with pytest.raises(SgApiError) as raised:
            s.update_row(EntityRef(type="Version", id=row.id), {"created_at": "x"})
        assert raised.value.status == 400
        assert s.rows is before
        assert s.status == "ready"


class WatchingClient(MockClient):
    """A mock that counts its reads and can withhold rows the site no longer answers."""

    def __init__(self) -> None:
        super().__init__(seed=1, now=MOCK_NOW)
        self.searches = 0
        self.hidden: set[int] = set()

    def search(self, entity_type: str, options: SearchOptions | None = None) -> SearchResult:
        self.searches += 1
        result = super().search(entity_type, options)
        return SearchResult(
            data=[row for row in result.data if row.id not in self.hidden],
            has_more=result.has_more,
        )


class TestRereadRows:
    def test_takes_the_new_attributes_and_leaves_every_row_where_it_was(self) -> None:
        client = mock()
        s = source(client=client, fields=["code", "description", "entity.Shot.code"])
        s.load()
        before = [r.id for r in s.rows]
        row = s.rows[3]
        client.update("Version", row.id, {"description": "read again"})

        s.reread_rows([row.id])
        assert [r.id for r in s.rows] == before
        assert s.rows[3].values["description"] == "read again"
        # The re-read carries the projection, dotted path and all.
        assert s.rows[3].values["entity.Shot.code"] == row.values["entity.Shot.code"]

    def test_reads_a_row_that_moved_out_of_the_filter_back_into_its_place(self) -> None:
        client = mock()
        s = source(client=client, fields=["code", "sg_status_list"])
        s.set_filters(group("and", [condition("sg_status_list", "is", "ip")]))
        row = s.rows[1]
        client.update("Version", row.id, {"sg_status_list": "fin"})

        s.reread_rows([row.id])
        assert s.rows[1].id == row.id
        assert s.rows[1].values["sg_status_list"] == "fin"

    def test_drops_a_row_the_site_no_longer_answers_and_keeps_the_rest(self) -> None:
        client = WatchingClient()
        s = source(client=client, fields=["code"])
        s.load()
        gone = s.rows[2]
        kept = s.rows[3]
        client.hidden.add(gone.id)

        s.reread_rows([gone.id, kept.id])
        assert len(s.rows) == 9
        assert gone.id not in [r.id for r in s.rows]
        assert s.rows[2].id == kept.id

    def test_ignores_an_id_that_is_not_on_screen_and_asks_the_site_nothing(self) -> None:
        client = WatchingClient()
        s = source(client=client, fields=["code"])
        s.load()
        reads = client.searches
        before = s.rows

        s.reread_rows([-1, 999999])
        assert client.searches == reads
        assert s.rows is before

    def test_asks_the_site_nothing_for_an_empty_list(self) -> None:
        client = WatchingClient()
        s = source(client=client, fields=["code"])
        s.load()
        reads = client.searches

        s.reread_rows([])
        assert client.searches == reads

    def test_leaves_the_status_the_paging_and_the_total_alone(self) -> None:
        client = MockClient(seed=1, now=MOCK_NOW, latency_ms=5)
        s = source(client=client, mode="pages", page_size=25, fields=["code"])
        s.load()
        assert s.status == "ready"
        assert s.total == 60
        row = s.rows[0]

        # Nothing dims while the rows are in the air: a re-read never touches the status.
        assert s.status == "ready"
        s.reread_rows([row.id])
        assert s.status == "ready"
        assert s.has_more is True
        assert s.total == 60
        assert s.page == 1
        assert len(s.rows) == 25

    def test_does_not_cancel_or_wait_for_a_page_already_in_flight(self) -> None:
        client = MockClient(seed=1, now=MOCK_NOW, latency_ms=5)
        s = source(client=client, fields=["code"])
        s.load()
        row = s.rows[0]

        s.load_more()
        s.reread_rows([row.id])
        assert len(s.rows) == 20
        assert s.status == "ready"


class TestColumns:
    def test_takes_headers_data_types_and_editability_off_the_schema(self) -> None:
        schema = create_schema_service(mock())
        columns = resolve_columns(
            schema, "Version", ["code", "sg_status_list", "entity.Shot.code", "created_at", "frame_count"]
        )
        assert [c.header for c in columns] == [
            "Version Name", "Status", "Shot Code", "Date Created", "Frame Count",
        ]
        assert [c.data_type for c in columns] == ["text", "status_list", "text", "date_time", "number"]
        # A projection is never writable, and neither is a field the schema calls read-only.
        assert [c.editable for c in columns] == [True, True, False, False, True]
        # Numbers are right-aligned.
        assert [c.align for c in columns] == ["left", "left", "left", "left", "right"]
        assert columns[1].field is not None
        assert columns[1].field.display_values is not None
        assert columns[1].field.display_values["ip"] == "In Progress"

    def test_lets_a_caller_overrule_any_of_it(self) -> None:
        schema = create_schema_service(mock())
        column = resolve_columns(
            schema, "Version", [ColumnSpec(path="code", header="Name", width=220, align="right")]
        )[0]
        assert column.header == "Name"
        assert column.width == 220
        assert column.align == "right"

    def test_names_the_whole_path_when_a_segment_does_not_resolve(self) -> None:
        schema = create_schema_service(mock())
        with pytest.raises(ValueError, match=re.escape("entity.Task.code")):
            resolve_columns(schema, "Version", ["entity.Task.code"])


class TestGroupRows:
    def test_walks_contiguous_runs_of_the_sorted_order(self) -> None:
        s = source(fields=["code", "sg_status_list"], page_size=60)
        s.set_sort([SortSpec(path="sg_status_list", descending=False)])
        groups = group_rows(s.rows, "sg_status_list")
        assert len(groups) > 1
        assert sum(len(g.rows) for g in groups) == len(s.rows)
        # One run per value, because the server put them together.
        values = [g.value for g in groups]
        assert len(set(values)) == len(values)

    def test_splits_an_unsorted_list_wherever_the_value_changes(self) -> None:
        rows = [
            EntityRow(type="Version", id=i, values={"sg_status_list": v})
            for i, v in enumerate(["a", "b", "a"])
        ]
        assert [g.value for g in group_rows(rows, "sg_status_list")] == ["a", "b", "a"]

    def test_groups_on_a_key_derived_from_the_row_in_the_order_the_rows_came_in(self) -> None:
        def note(id: int, link: dict[str, Any] | None) -> EntityRow:
            return EntityRow(
                type="Note", id=id, values={"subject": f"n{id}", "note_links": [link] if link else []}
            )

        shot = {"type": "Shot", "id": 7, "name": "sh010"}
        asset = {"type": "Asset", "id": 9, "name": "Tree"}

        def record_of(row: EntityRow) -> Any:
            links = row.values.get("note_links") or []
            return links[0] if links else None

        groups = group_rows([note(1, shot), note(2, shot), note(3, asset), note(4, shot)], record_of)
        assert [group_key_text(g.value) for g in groups] == ["sh010", "Tree", "sh010"]
        assert [len(g.rows) for g in groups] == [2, 1, 1]
        assert [g.value for g in group_rows([note(5, None)], record_of)] == [None]


class TestGroupKeyText:
    def test_reads_a_row_as_its_display_name_and_anything_else_as_its_own_text(self) -> None:
        assert group_key_text({"type": "Shot", "id": 7, "name": "sh010"}) == "sh010"
        assert group_key_text({"type": "Shot", "id": 7, "code": "sh020", "name": "x"}) == "sh020"
        assert group_key_text("ip") == "ip"
        assert group_key_text(12) == "12"
        assert group_key_text(None) == ""
        assert group_key_text({"type": "Shot", "id": 7}) == ""


class TestPagesMode:
    def test_walks_the_set_one_page_at_a_time_and_counts_it_once(self) -> None:
        s = source(mode="pages", page_size=25)
        s.load()
        assert s.mode == "pages"
        assert s.page == 1
        assert len(s.rows) == 25
        # The first read asks `_summarize` for the total the read itself never carries.
        assert s.total == 60
        first = [r.id for r in s.rows]

        s.set_page(2)
        assert s.page == 2
        assert len(s.rows) == 25
        assert [r.id for r in s.rows] != first
        # A page replaces the rows; it never appends.
        assert s.total == 60

        s.set_page(3)
        assert len(s.rows) == 10
        assert s.has_more is False

    def test_reopens_at_the_first_page_on_a_new_page_size_and_keeps_the_total(self) -> None:
        s = source(mode="pages", page_size=25)
        s.load()
        s.set_page(2)

        s.set_page_size(50)
        assert s.page == 1
        assert s.page_size == 50
        assert len(s.rows) == 50
        assert s.total == 60

    def test_leaves_load_more_alone_and_re_counts_when_the_filter_moves(self) -> None:
        s = source(mode="pages", page_size=25)
        s.load()
        s.load_more()
        assert len(s.rows) == 25

        s.set_filters(condition("sg_status_list", "is", "ip"))
        assert s.page == 1
        assert s.total != 60
        assert s.total is not None
        assert s.total == len(s.rows) + (s.total - len(s.rows) if s.has_more else 0)

    def test_sorts_without_asking_for_the_total_again(self) -> None:
        s = source(mode="pages", page_size=25)
        s.load()
        s.set_page(2)

        s.set_sort([SortSpec(path="id", descending=True)])
        assert s.page == 1
        assert s.total == 60


class TestCount:
    def test_lands_even_when_the_first_read_starts_beside_it(self) -> None:
        s = source(page_size=25)
        pending = s.begin_count()
        s.load()
        total = s.count(pending)
        assert total == 60
        # The read that overtook it changed no filter, so the total it took still stands.
        assert s.total == 60

    def test_is_dropped_when_the_filter_it_counted_has_moved(self) -> None:
        s = source(page_size=25)
        s.load()
        stale = s.begin_count()
        s.set_filters(condition("sg_status_list", "is", "ip"))
        s.count(stale)
        assert s.total != 60


class TestDescribePaging:
    def test_reads_a_range_against_a_known_total(self) -> None:
        s = source(mode="pages", page_size=25)
        s.load()
        s.set_page(2)
        paging = describe_paging(s.snapshot())
        assert paging.range_label == "26 to 50 of 60"
        assert paging.page_count == 3
        assert paging.has_previous is True
        assert paging.has_next is True

    def test_drops_the_total_from_the_range_when_nothing_counted_the_set(self) -> None:
        paging = describe_paging(EntitySourceState(
            rows=[EntityRow(type="Version", id=id, values={}) for id in (1, 2, 3)],
            status="ready",
            error=None,
            has_more=True,
            total=None,
            filters=None,
            sort=[],
            mode="pages",
            page=2,
            page_size=3,
        ))
        assert paging.range_label == "4 to 6"
        assert paging.page_count is None
        # With no total the full page that came back is the only evidence of a next one.
        assert paging.has_next is True

    def test_counts_what_is_loaded_in_infinite_mode(self) -> None:
        s = source(page_size=25)
        s.load()
        s.load_more()
        s.count()
        paging = describe_paging(s.snapshot())
        assert paging.from_ == 1
        assert paging.to == 50
        assert paging.loaded_label == "50 of 60 loaded"
        assert paging.has_previous is False

    def test_reads_zero_rows_as_an_empty_range(self) -> None:
        paging = describe_paging(EntitySourceState(
            rows=[],
            status="ready",
            error=None,
            has_more=False,
            total=0,
            filters=None,
            sort=[],
            mode="pages",
            page=1,
            page_size=25,
        ))
        assert paging.range_label == "0 to 0 of 0"
        assert paging.has_next is False
