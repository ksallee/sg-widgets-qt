"""Port of `packages/core/test/schema-service.test.ts`."""
from __future__ import annotations

import pytest

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.query import create_query_cache
from sg_widgets_core.schema_service import create_schema_service

from .fake_client import CountingClient, FakeClient, concurrently


class TestCaching:
    def test_fetches_a_type_once_however_many_widgets_ask(self) -> None:
        inner = FakeClient()
        client = CountingClient(inner)
        schema = create_schema_service(client)
        values, errors = concurrently(inner, lambda: schema.fields("Shot"))
        assert errors == [None, None]
        schema.field("Shot", "code")
        schema.status_field("Shot")
        assert client.calls == ["fields Shot -"]
        assert values[1] is values[0]

    def test_reads_fields_at_site_scope_never_with_a_project(self) -> None:
        client = CountingClient(FakeClient())
        schema = create_schema_service(client)
        schema.fields("Shot")
        schema.status_options("Shot", 70)
        assert client.calls == ["fields Shot -", "field_with_project Shot.sg_status_list 70"]

    def test_keys_hidden_values_on_type_field_and_project(self) -> None:
        client = CountingClient(FakeClient())
        schema = create_schema_service(client)
        schema.hidden_values("Shot", "sg_status_list", 70)
        schema.hidden_values("Shot", "sg_status_list", 70)
        schema.hidden_values("Shot", "sg_status_list", 71)
        schema.hidden_values("Task", "sg_status_list", 70)
        assert client.calls == [
            "field_with_project Shot.sg_status_list 70",
            "field_with_project Shot.sg_status_list 71",
            "field_with_project Task.sg_status_list 70",
        ]

    def test_drops_only_the_schema_keys_out_of_a_cache_it_was_handed(self) -> None:
        client = CountingClient(FakeClient())
        cache = create_query_cache(client)
        schema = create_schema_service(cache)
        schema.fields("Shot")
        cache.search("Shot", SearchOptions(fields=["code"]))
        schema.invalidate()
        schema.fields("Shot")
        cache.search("Shot", SearchOptions(fields=["code"]))
        assert client.calls == ["fields Shot -", "search Shot", "fields Shot -"]

    def test_drops_everything_out_of_a_cache_it_owns(self) -> None:
        client = CountingClient(FakeClient())
        schema = create_schema_service(client)
        schema.entity_types()
        schema.invalidate()
        schema.entity_types()
        assert client.calls == ["entity_types", "entity_types"]


class TestStatusOptions:
    def test_subtracts_the_project_hidden_values_which_the_api_does_not_enforce(self) -> None:
        schema = create_schema_service(FakeClient())
        site = schema.status_options("Shot")
        scoped = schema.status_options("Shot", 70)
        assert [s.code for s in site] == ["wtg", "ip", "rev", "apr", "fin", "hld", "omt"]
        assert schema.hidden_values("Shot", "sg_status_list", 70) == ["omt"]
        assert [s.code for s in scoped] == ["wtg", "ip", "rev", "apr", "fin", "hld"]

    def test_labels_from_display_values_and_falls_back_to_the_raw_code(self) -> None:
        schema = create_schema_service(FakeClient())
        options = schema.status_options("Shot", 70)
        assert next(s for s in options if s.code == "ip").label == "In Progress"

    def test_intersects_across_projects_in_the_first_project_order(self) -> None:
        schema = create_schema_service(FakeClient())
        # Project 70 hides `omt`, project 71 hides `hld` and `omt`.
        both = schema.status_options_for_projects("Shot", [70, 71])
        assert [s.code for s in both] == ["wtg", "ip", "rev", "apr", "fin"]
        assert schema.status_options_for_projects("Shot", []) == []

    def test_finds_project_own_status_field_a_plain_list_under_another_name(self) -> None:
        schema = create_schema_service(FakeClient())
        field = schema.status_field("Project")
        assert (field if isinstance(field, str) else field.name) == "sg_status"
        assert ("" if isinstance(field, str) else field.data_type) == "list"
        # Project 71 hides `On Hold` on it.
        assert [s.code for s in schema.status_options("Project", 71)] == ["Active", "Bidding", "Complete"]

    def test_offers_a_named_field_instead_of_the_type_status_field(self) -> None:
        schema = create_schema_service(FakeClient())
        types = schema.status_options("Version", None, "sg_version_type")
        assert [s.code for s in types] == ["Type A", "Type B", "Type C"]
        assert schema.status_options("Version", 70, "nosuchfield") == []
        intersected = schema.status_options_for_projects("Version", [70, 71], "sg_version_type")
        assert [s.code for s in intersected] == ["Type A", "Type B", "Type C"]

    def test_falls_back_to_the_conventional_name_on_a_type_with_no_status_field(self) -> None:
        schema = create_schema_service(FakeClient())
        assert schema.status_field("Icon") == "sg_status_list"
        assert schema.status_options("Icon") == []


class TestPathResolution:
    def test_resolves_a_plain_field(self) -> None:
        schema = create_schema_service(FakeClient())
        segments = schema.resolve_path("Shot", "code")
        assert len(segments) == 1
        assert (segments[0].entity_type, segments[0].name, segments[0].display_name, segments[0].data_type) == (
            "Shot", "code", "Shot Code", "text",
        )
        assert segments[0].through is None

    def test_walks_a_link_through_the_type_the_path_names(self) -> None:
        schema = create_schema_service(FakeClient())
        segments = schema.resolve_path("Shot", "sg_sequence.Sequence.code")
        assert [
            [s.entity_type, s.name, s.display_name, s.data_type, s.through] for s in segments
        ] == [
            ["Shot", "sg_sequence", "Sequence", "entity", "Sequence"],
            ["Sequence", "code", "Sequence Name", "text", None],
        ]

    def test_walks_more_than_one_hop(self) -> None:
        schema = create_schema_service(FakeClient())
        segments = schema.resolve_path("Version", "entity.Shot.project.Project.name")
        assert [s.name for s in segments] == ["entity", "project", "name"]
        assert segments[-1].data_type == "text"

    def test_refuses_a_leaf_the_type_does_not_have(self) -> None:
        schema = create_schema_service(FakeClient())
        with pytest.raises(ValueError, match=r"Shot\.bogusfield does not exist"):
            schema.resolve_path("Shot", "bogusfield")
        with pytest.raises(ValueError, match="does not exist"):
            schema.resolve_path("Shot", "sg_sequence.Sequence.bogusfield")

    def test_refuses_a_middle_segment_outside_the_field_valid_types(self) -> None:
        schema = create_schema_service(FakeClient())
        # The type is real and the leaf is real, but Shot.sg_sequence does not link Asset.
        with pytest.raises(ValueError, match="does not link Asset"):
            schema.resolve_path("Shot", "sg_sequence.Asset.code")
        with pytest.raises(ValueError, match="does not link Bogus"):
            schema.resolve_path("Shot", "sg_sequence.Bogus.code")

    def test_refuses_an_empty_path_and_one_that_ends_on_a_type(self) -> None:
        schema = create_schema_service(FakeClient())
        with pytest.raises(ValueError, match="Empty field path"):
            schema.resolve_path("Shot", "")
        with pytest.raises(ValueError, match="ends on a type"):
            schema.resolve_path("Shot", "sg_sequence.Sequence")

