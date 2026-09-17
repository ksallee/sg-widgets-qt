"""Port of the `RestClient` half of `packages/core/test/client.test.ts`.

The behaviours upstream measures on the wire are measured here on the calls the
adapter makes to `shotgun_api3`, through a fake connection injected with
`factory`. Nothing here reaches the network.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
import shotgun_api3

from sg_widgets_core.client import (
    EventLogOptions,
    FollowingOptions,
    Page,
    SearchOptions,
    SgApiError,
    SummarizeOptions,
    SummaryField,
    SummaryGrouping,
    UploadFile,
)
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.shotgun_client import (
    ShotgunClient,
    from_api3_value,
    to_api3_value,
    wire_to_api3,
)
from sg_widgets_core.status import HtmlIcon, ImageIcon, ImageMapIcon


@dataclass
class Call:
    name: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


class FakeShotgun:
    """A `shotgun_api3.Shotgun` stand-in that records calls and answers canned rows.

    An answer is a value, or a callable taking the call's arguments.
    """

    def __init__(self, answers: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.calls: list[Call] = []
        self.answers = dict(answers or {})
        self.error = error

    def call(self, name: str) -> Call:
        """The one call of that name, so a test names what it asserts on."""
        matching = [c for c in self.calls if c.name == name]
        assert len(matching) == 1, f"expected one {name} call, got {len(matching)}"
        return matching[0]

    def _record(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        self.calls.append(Call(name=name, args=args, kwargs=kwargs))
        if self.error is not None:
            raise self.error
        answer = self.answers.get(name)
        return answer(*args, **kwargs) if callable(answer) else answer

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Any:
            return self._record(name, args, kwargs)

        return method


def client_on(fake: FakeShotgun) -> ShotgunClient:
    return ShotgunClient("https://studio.example.com", script_name="s", api_key="k", factory=lambda: fake)


def client_with(answers: dict[str, Any]) -> tuple[ShotgunClient, FakeShotgun]:
    fake = FakeShotgun(answers)
    return client_on(fake), fake


class TestTextSearchOnTheWire:
    def test_sends_the_hash_content_type_with_a_hash_group_per_type_and_flattens_the_row(self) -> None:
        client, fake = client_with(
            {
                "text_search": {
                    "matches": [
                        {
                            "id": 17055,
                            "type": "Version",
                            "name": "zzprobe_053_zzz_v001",
                            "project_id": 70,
                            "image": "https://media.example.com/thumb.jpg",
                            "links": ["Shot", "zzprobe_053_qat_0020"],
                            "status": "rev",
                        }
                    ],
                    "terms": ["qat", "0020"],
                }
            }
        )
        rows = client.text_search(
            "qat 0020", {"Version": {"logical_operator": "and", "conditions": [["id", "is", 1]]}}
        )
        call = fake.call("text_search")
        assert call.args[0] == "qat 0020"
        # One filter list per type, which is the shape `text_search` takes (post_entity_text_search).
        assert call.args[1] == {"Version": [["id", "is", 1]]}
        assert call.kwargs["limit"] == 25
        # Name, links and status are the row, and there is nothing else on it.
        assert rows[0].type == "Version"
        assert rows[0].id == 17055
        assert rows[0].name == "zzprobe_053_zzz_v001"
        assert rows[0].links == ("Shot", "zzprobe_053_qat_0020")
        assert rows[0].status == "rev"

    def test_caps_the_page_size_at_25_which_is_the_cap_and_the_default(self) -> None:
        # 25 is the cap and the default, and the call takes a row cap and no offset,
        # so page three of 25 is cut from a read of 75 (probe 053).
        client, fake = client_with({"text_search": {"matches": []}})
        client.text_search("x", {"Shot": None}, Page(size=100, number=3))
        assert fake.call("text_search").kwargs["limit"] == 75
        assert fake.call("text_search").args[1] == {"Shot": []}

    def test_reads_a_row_that_links_to_nothing_as_two_empty_strings(self) -> None:
        client, _ = client_with(
            {"text_search": {"matches": [{"id": 70, "type": "Project", "name": "Blue Moon Rising", "links": ["", ""]}]}}
        )
        rows = client.text_search("blue", {"Project": None})
        assert rows[0].type == "Project"
        assert rows[0].id == 70
        assert rows[0].name == "Blue Moon Rising"
        assert rows[0].links == ("", "")
        assert rows[0].status is None


class TestTheHierarchyEndpointsOnTheWire:
    def test_sends_plain_json_which_is_the_only_content_type_they_take(self) -> None:
        client, fake = client_with(
            {
                "nav_search_entity": [
                    {
                        "label": "sh010_0010",
                        "incremental_path": ["/Project/70", "/Project/70/Shot"],
                        "path_label": "Shots",
                        "ref": {"id": 862, "type": "Shot"},
                        "project_id": 70,
                    }
                ]
            }
        )
        paths = client.hierarchy_search("/Project/70", EntityRef(type="Shot", id=862, name="sh010_0010"))
        call = fake.call("nav_search_entity")
        # The criteria takes the literal key `entity`, and the name a caller carries is not sent.
        assert call.args == ("/Project/70", {"type": "Shot", "id": 862})
        assert paths[0].ref == EntityRef(type="Shot", id=862)
        assert paths[0].path_label == "Shots"
        assert paths[0].project_id == 70
        assert paths[0].incremental_path == ["/Project/70", "/Project/70/Shot"]

    def test_reads_both_ref_shapes_out_of_an_expand(self) -> None:
        client, fake = client_with(
            {
                "nav_expand": {
                    "label": "Blue Moon Rising",
                    "ref": {"kind": "entity", "value": {"type": "Project", "id": 70}},
                    "parent_path": "/",
                    "path": "/Project/70",
                    "has_children": True,
                    "children": [{"label": "Shots", "ref": {"kind": "entity_type", "value": "Shot"}, "has_children": True}],
                }
            }
        )
        node = client.hierarchy_expand("/Project/70")
        call = fake.call("nav_expand")
        assert call.args == ("/Project/70",)
        # `seed_entity_field` is documented and ignored (post_hierarchy_expand).
        assert call.kwargs == {"seed_entity_field": None, "entity_fields": None}
        assert node.ref.kind == "entity"
        assert node.ref.value == EntityRef(type="Project", id=70)
        # `value` is a bare schema name on an entity_type ref, not an object.
        assert node.children[0].ref.kind == "entity_type"
        assert node.children[0].ref.value == "Shot"
        assert node.children[0].has_children is True
        assert node.children[0].path == "/Project/70/Shot"


def status_row(id: int, code: str, icon_id: int) -> dict[str, Any]:
    return {
        "type": "Status",
        "id": id,
        "code": code,
        "name": code.upper(),
        "bg_color": "25,118,27",
        "icon": {"type": "Icon", "id": icon_id, "name": code},
    }


def client_with_icons(icons: list[dict[str, Any]], rows: list[dict[str, Any]] | None = None) -> ShotgunClient:
    """A client whose statuses carry the given icon rows, in order from id 3."""
    rows = rows if rows is not None else [status_row(1, "custom", 3)]
    icon_rows = [dict(attributes, type="Icon", id=3 + i) for i, attributes in enumerate(icons)]

    def find(entity_type: str, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return rows if entity_type == "Status" else icon_rows

    client, _ = client_with({"find": find})
    return client


class TestStatusIconsOnTheWire:
    def test_drops_an_image_icon_the_site_holds_with_an_empty_url(self) -> None:
        client = client_with_icons(
            [{"display_type": "image", "url": ""}, {"display_type": "image_map", "image_map_key": "icon_apr"}],
            [status_row(1, "custom", 3), status_row(2, "apr", 4)],
        )
        custom, approved = client.statuses()
        assert custom.icon is None
        assert approved.icon == ImageMapIcon(image_map_key="icon_apr")

    def test_strips_the_newlines_an_image_icon_carries_in_its_data_url(self) -> None:
        client = client_with_icons([{"display_type": "image", "url": "data:image/png;base64,AA\nBB"}])
        assert client.statuses()[0].icon == ImageIcon(data_url="data:image/png;base64,AABB")

    def test_reads_the_code_name_and_colour_of_every_status(self) -> None:
        client = client_with_icons([{"display_type": "html", "html": "<b>act</b>"}])
        record = client.statuses()[0]
        assert (record.id, record.code, record.name, record.bg_color) == (1, "custom", "CUSTOM", "25,118,27")
        assert record.icon == HtmlIcon(html="<b>act</b>")


class TestANoteThreadOnTheWire:
    def test_asks_for_one_path_widens_a_type_through_entity_fields_and_reads_the_author_from_two_keys(self) -> None:
        client, fake = client_with(
            {
                "note_thread_read": [
                    {
                        "type": "Note",
                        "id": 6376,
                        "content": "the note body",
                        "created_at": datetime(2025, 5, 30, 20, 39, 17, tzinfo=timezone.utc),
                        "created_by": {"id": 88, "name": "Anna van der Meer", "type": "HumanUser"},
                    },
                    {
                        "type": "Attachment",
                        "id": 650,
                        "created_at": datetime(2025, 5, 30, 20, 39, 19, tzinfo=timezone.utc),
                        "created_by": {"id": 88, "name": "Anna van der Meer", "type": "HumanUser"},
                    },
                    {
                        "type": "Reply",
                        "id": 477,
                        "content": "the reply body",
                        "created_at": datetime(2025, 5, 30, 21, 21, 50, tzinfo=timezone.utc),
                        "user": {
                            "id": 88,
                            "name": "Anna van der Meer",
                            "type": "HumanUser",
                            "image": "https://media.example.com/avatar.png",
                        },
                    },
                ]
            }
        )
        thread = client.thread_contents(6376, {"Note": ["subject", "sg_status_list"]})
        assert fake.call("note_thread_read").args == (6376, {"Note": ["subject", "sg_status_list"]})
        assert [(row.type, row.id) for row in thread] == [("Note", 6376), ("Attachment", 650), ("Reply", 477)]
        assert thread[0].author is not None
        assert (thread[0].author.type, thread[0].author.id, thread[0].author.name) == (
            "HumanUser",
            88,
            "Anna van der Meer",
        )
        assert thread[0].author.image is None
        # A Reply's author comes from `user` and carries the avatar the other two lack.
        assert thread[2].author is not None
        assert thread[2].author.image == "https://media.example.com/avatar.png"
        assert thread[1].content is None
        assert thread[0].created_at == "2025-05-30T20:39:17Z"

    def test_keeps_the_author_under_created_by_on_a_note_widened_with_user(self) -> None:
        client, _ = client_with(
            {
                "note_thread_read": [
                    {
                        "type": "Note",
                        "id": 6376,
                        "content": "the note body",
                        "created_by": {"id": 88, "name": "Anna van der Meer", "type": "HumanUser"},
                        "user": {"id": 91, "name": "j.doe", "type": "HumanUser"},
                    },
                    {
                        "type": "Reply",
                        "id": 477,
                        "content": "the reply body",
                        "user": {"id": 91, "name": "j.doe", "type": "HumanUser", "image": None},
                    },
                ]
            }
        )
        thread = client.thread_contents(6376, {"Note": ["user"]})
        assert thread[0].author is not None and thread[0].author.id == 88
        assert thread[0].fields["user"] == {"id": 91, "name": "j.doe", "type": "HumanUser"}
        assert thread[1].author is not None and thread[1].author.id == 91
        assert thread[1].author.image is None


def field_schema(name: str, entity_type: str, data_type: str) -> dict[str, Any]:
    return {
        "name": {"value": name.replace("_", " ").title(), "editable": True},
        "entity_type": {"value": entity_type, "editable": False},
        "data_type": {"value": data_type, "editable": False},
        "editable": {"value": True, "editable": False},
        "mandatory": {"value": False, "editable": False},
        "unique": {"value": False, "editable": False},
        "properties": {"valid_values": {"value": ["ip", "fin"], "editable": True}},
    }


class TestOneFieldOfTheSchemaOnTheWire:
    def test_answers_the_override_when_the_site_reads_the_field_as_data_null(self) -> None:
        # An undeclared field the site still answers on the row (068_note_read_state).
        client, fake = client_with({"schema_field_read": {}})
        schema = client.field_with_project("Note", "read_by_current_user", 70)
        call = fake.call("schema_field_read")
        assert call.args == ("Note",)
        assert call.kwargs == {
            "field_name": "read_by_current_user",
            "project_entity": {"type": "Project", "id": 70},
        }
        assert (schema.name, schema.entity_type, schema.data_type, schema.editable) == (
            "read_by_current_user",
            "Note",
            "list",
            True,
        )

    def test_refuses_a_data_null_answer_for_a_field_it_has_no_override_for(self) -> None:
        client, _ = client_with({"schema_field_read": {}})
        with pytest.raises(SgApiError, match="Field 'Shot.sg_mystery' is not in the schema."):
            client.field_with_project("Shot", "sg_mystery", 70)

    def test_reads_one_field_the_schema_declares(self) -> None:
        client, _ = client_with({"schema_field_read": {"sg_status_list": field_schema("sg_status_list", "Shot", "status_list")}})
        schema = client.field_with_project("Shot", "sg_status_list", 70)
        assert (schema.data_type, schema.valid_values) == ("status_list", ["ip", "fin"])

    def test_reads_every_field_of_a_type_at_project_scope(self) -> None:
        client, fake = client_with({"schema_field_read": {"code": field_schema("code", "Shot", "text")}})
        fields = client.fields("Shot", 70)
        assert fake.call("schema_field_read").kwargs == {"project_entity": {"type": "Project", "id": 70}}
        assert fields["code"].data_type == "text"

    def test_reads_the_enabled_entity_types_with_their_display_names(self) -> None:
        client, fake = client_with(
            {
                "schema_entity_read": {
                    "Shot": {"name": {"value": "Shot"}, "visible": {"value": True}},
                    "Asset": {"name": {"value": "Asset"}, "visible": {"value": True}},
                    "Cut": {"name": {"value": "Cut"}, "visible": {"value": False}},
                }
            }
        )
        types = client.entity_types()
        assert fake.call("schema_entity_read").args == ()
        assert [(t.name, t.display_name) for t in types] == [("Shot", "Shot"), ("Asset", "Asset")]


class TestTheEventLogOnTheWire:
    def test_narrows_on_the_filterable_fields_sorts_id_and_lifts_the_two_values_out_of_meta(self) -> None:
        client, fake = client_with(
            {
                "find": [
                    {
                        "type": "EventLogEntry",
                        "id": 247337,
                        "event_type": "Shotgun_Shot_Change",
                        "attribute_name": "sg_status_list",
                        "description": 'Anna van der Meer changed "Status"',
                        "created_at": datetime(2026, 1, 21, 19, 47, 33, tzinfo=timezone.utc),
                        "meta": {
                            "type": "attribute_change",
                            "attribute_name": "sg_status_list",
                            "entity_type": "Shot",
                            "entity_id": 862,
                            "old_value": "wtg",
                            "new_value": "ip",
                        },
                        "entity": {"id": 862, "name": "sh010", "type": "Shot"},
                        "project": {"id": 70, "type": "Project"},
                        "user": None,
                    }
                ]
            }
        )
        log = client.event_log(
            EventLogOptions(
                project_id=70,
                entity=EntityRef(type="Shot", id=862),
                event_type=["Shotgun_Shot_Change", "Shotgun_Shot_New"],
                attribute_name="sg_status_list",
                since="2026-01-01T00:00:00Z",
                page=Page(size=1),
            )
        )
        call = fake.call("find")
        assert call.args[0] == "EventLogEntry"
        assert call.args[1] == [
            ["project", "is", {"type": "Project", "id": 70}],
            ["entity", "is", {"type": "Shot", "id": 862}],
            ["event_type", "in", ["Shotgun_Shot_Change", "Shotgun_Shot_New"]],
            ["attribute_name", "is", "sg_status_list"],
            ["created_at", "greater_than", "2026-01-01T00:00:00Z"],
        ]
        assert call.args[2] == [
            "event_type",
            "attribute_name",
            "description",
            "created_at",
            "meta",
            "entity",
            "project",
            "user",
        ]
        assert call.kwargs["order"] == [{"field_name": "id", "direction": "desc"}]
        assert call.kwargs["limit"] == 1
        assert call.kwargs["page"] == 1
        assert log.data[0].old_value == "wtg"
        assert log.data[0].new_value == "ip"
        assert log.data[0].entity == EntityRef(type="Shot", id=862, name="sh010")
        assert log.data[0].user is None
        assert log.data[0].created_at == "2026-01-21T19:47:33Z"
        # A full page means another may exist, the same rule `search` follows (probe 006).
        assert log.has_more is True

    def test_sends_an_empty_group_when_nothing_narrows_it(self) -> None:
        client, fake = client_with({"find": []})
        log = client.event_log()
        call = fake.call("find")
        assert call.args[1] == []
        assert call.kwargs["limit"] == 50
        assert call.kwargs["page"] == 1
        assert log.has_more is False


class TestFollowingOnTheWire:
    def test_sends_the_two_filters_it_takes_and_reads_a_type_and_an_id_per_row(self) -> None:
        client, fake = client_with(
            {"following": [{"id": 346, "type": "Note"}, {"id": 360, "type": "Note"}]}
        )
        rows = client.following(3, FollowingOptions(entity="Note", project_id=70))
        call = fake.call("following")
        assert call.args == ({"type": "HumanUser", "id": 3},)
        assert call.kwargs == {"project": {"type": "Project", "id": 70}, "entity_type": "Note"}
        assert rows == [EntityRef(type="Note", id=346), EntityRef(type="Note", id=360)]


class TestACreateOnTheWire:
    def test_posts_plain_json_to_the_type_and_answers_the_row(self) -> None:
        client, fake = client_with(
            {"create": {"type": "Reply", "id": 610, "content": "on it", "entity": {"type": "Note", "id": 11030}}}
        )
        row = client.create("Reply", {"entity": {"type": "Note", "id": 11030}, "content": "on it"})
        call = fake.call("create")
        assert call.args == ("Reply", {"entity": {"type": "Note", "id": 11030}, "content": "on it"})
        assert call.kwargs == {"return_fields": ["entity", "content"]}
        assert (row.type, row.id) == ("Reply", 610)
        assert row.values["content"] == "on it"


class TestAnUploadOnTheWire:
    def test_takes_a_ticket_puts_the_bytes_with_no_auth_header_and_completes_without_parsing_the_reply(self) -> None:
        seen: dict[str, Any] = {}

        def upload_thumbnail(entity_type: str, entity_id: int, path: str, **kwargs: Any) -> int:
            seen["path"] = path
            with open(path, "rb") as handle:
                seen["data"] = handle.read()
            return 651

        client, fake = client_with({"upload_thumbnail": upload_thumbnail})
        result = client.upload("Shot", 862, UploadFile(filename="frame.png", data=b"\x89PNG", field="image"))
        call = fake.call("upload_thumbnail")
        assert call.args[:2] == ("Shot", 862)
        # The bytes reach the call as a file with the filename's suffix, removed after.
        assert seen["data"] == b"\x89PNG"
        assert seen["path"].endswith(".png")
        import os

        assert not os.path.exists(seen["path"])
        assert result.upload_type == "Thumbnail"
        assert result.upload_info["id"] == 651
        assert result.upload_info["original_filename"] == "frame.png"
        assert result.etag is None

    def test_leaves_the_field_out_of_the_path_for_a_generic_attachment(self) -> None:
        client, fake = client_with({"upload": 652})
        result = client.upload("Version", 17055, UploadFile(filename="workflow.json", data=b"{}"))
        call = fake.call("upload")
        assert call.args[:2] == ("Version", 17055)
        assert call.kwargs == {"field_name": None, "display_name": "workflow.json"}
        assert result.upload_type == "Attachment"

    def test_calls_an_absolute_complete_upload_link_as_it_is(self) -> None:
        # A field that is not `image` is an Attachment on that field (recipes/001).
        client, fake = client_with({"upload": 653})
        result = client.upload(
            "Version", 17055, UploadFile(filename="notes.txt", data=b"hi", field="sg_uploaded_movie")
        )
        assert fake.call("upload").kwargs["field_name"] == "sg_uploaded_movie"
        assert result.upload_type == "Attachment"


class TestASearchOnTheWire:
    def test_pages_sorts_and_passes_a_dotted_field_through(self) -> None:
        client, fake = client_with(
            {"find": [{"type": "Version", "id": 1, "code": "v001", "entity.Shot.code": "sh010"}]}
        )
        result = client.search(
            "Version",
            SearchOptions(
                filters={"logical_operator": "and", "conditions": [["project", "is", {"type": "Project", "id": 70}]]},
                fields=["code", "entity.Shot.code"],
                sort="-created_at",
                page=Page(size=1, number=2),
            ),
        )
        call = fake.call("find")
        assert call.args[0] == "Version"
        assert call.args[1] == [["project", "is", {"type": "Project", "id": 70}]]
        assert call.args[2] == ["code", "entity.Shot.code"]
        assert call.kwargs["order"] == [{"field_name": "created_at", "direction": "desc"}]
        assert call.kwargs["limit"] == 1
        assert call.kwargs["page"] == 2
        assert result.data[0].values["entity.Shot.code"] == "sh010"
        # A full page means another may exist (probe 006).
        assert result.has_more is True

    def test_answers_a_short_page_as_the_last_one(self) -> None:
        client, _ = client_with({"find": [{"type": "Version", "id": 1}]})
        assert client.search("Version", SearchOptions(page=Page(size=5))).has_more is False


class TestAnUpdateOnTheWire:
    def test_writes_the_patch_then_reads_the_row_back_on_the_same_fields(self) -> None:
        client, fake = client_with(
            {
                "update": {"type": "Shot", "id": 862, "sg_status_list": "ip"},
                "find_one": {"type": "Shot", "id": 862, "sg_status_list": "ip"},
            }
        )
        row = client.update("Shot", 862, {"sg_status_list": "ip"})
        assert fake.call("update").args == ("Shot", 862, {"sg_status_list": "ip"})
        # The answer never resolves a dotted path, so the row is read back (024_read_after_write).
        assert fake.call("find_one").args == ("Shot", [["id", "is", 862]], ["sg_status_list", "id"])
        assert (row.type, row.id) == ("Shot", 862)
        assert row.values["sg_status_list"] == "ip"


class TestASummarizeOnTheWire:
    def test_sends_the_grouping_list_shape_and_reads_the_groups_back(self) -> None:
        client, fake = client_with(
            {
                "summarize": {
                    "summaries": {"id": 15},
                    "groups": [
                        {"group_name": "In Progress", "group_value": "ip", "summaries": {"id": 9}},
                        {"group_name": "Final", "group_value": "fin", "summaries": {"id": 6}},
                    ],
                }
            }
        )
        result = client.summarize(
            "Version", SummarizeOptions(grouping=[SummaryGrouping(field="sg_status_list")])
        )
        call = fake.call("summarize")
        assert call.args[0] == "Version"
        assert call.args[1] == []
        # The default is one count of `id` (020_summarize).
        assert call.args[2] == [{"field": "id", "type": "count"}]
        assert call.kwargs["grouping"] == [{"field": "sg_status_list", "type": "exact", "direction": "asc"}]
        assert result.summaries == {"id": 15}
        assert [(g.group_name, g.group_value, g.summaries) for g in result.groups] == [
            ("In Progress", "ip", {"id": 9}),
            ("Final", "fin", {"id": 6}),
        ]

    def test_the_ungrouped_count_is_the_python_api_shape_and_reads_the_total_back(self) -> None:
        # `shotgun_api3.summarize` takes the same `{'field': ..., 'type': ...}` records the
        # REST endpoint does and answers `{'summaries': ..., 'groups': ...}`, so the count a
        # range is built from is `summaries['id']` (020_summarize).
        client, fake = client_with({"summarize": {"summaries": {"id": 320}, "groups": []}})
        wire = {"logical_operator": "and", "conditions": [["project", "is", {"type": "Project", "id": 70}]]}
        result = client.summarize("Version", SummarizeOptions(filters=wire))
        call = fake.call("summarize")
        assert call.args[0] == "Version"
        assert call.args[1] == [["project", "is", {"type": "Project", "id": 70}]]
        assert call.args[2] == [{"field": "id", "type": "count"}]
        assert call.kwargs["grouping"] is None
        assert result.summaries["id"] == 320
        assert result.groups == []

    def test_a_summary_type_of_the_callers_own_reaches_the_api_unchanged(self) -> None:
        # `record_count` counts rows where `count` counts values, and the Python API takes it
        # under the same key, so nothing here rewrites what the caller asked for.
        client, fake = client_with({"summarize": {"summaries": {"id": 12}, "groups": []}})
        client.summarize(
            "Shot",
            SummarizeOptions(summary_fields=[SummaryField(field="id", type="record_count")]),
        )
        assert fake.call("summarize").args[2] == [{"field": "id", "type": "record_count"}]

    def test_a_field_that_cannot_be_summarized_leaves_the_key_out(self) -> None:
        # The site answers 200 with a near-empty body rather than 400, so the key is tested
        # rather than assumed (020_summarize).
        client, fake = client_with({"summarize": {"summaries": {}, "groups": []}})
        result = client.summarize(
            "Version", SummarizeOptions(summary_fields=[SummaryField(field="image", type="count")])
        )
        assert fake.call("summarize").args[2] == [{"field": "image", "type": "count"}]
        assert result.summaries.get("image") is None


class TestTheFilterTranslation:
    def test_an_empty_filter_is_an_empty_list(self) -> None:
        assert wire_to_api3(None) == []
        assert wire_to_api3({"logical_operator": "and", "conditions": []}) == []

    def test_an_and_group_is_its_conditions(self) -> None:
        wire = {"logical_operator": "and", "conditions": [["code", "is", "x"], ["id", "in", [1, 2]]]}
        assert wire_to_api3(wire) == [["code", "is", "x"], ["id", "in", [1, 2]]]

    def test_an_or_group_at_the_top_is_one_nested_group(self) -> None:
        wire = {"logical_operator": "or", "conditions": [["code", "is", "x"], ["code", "is", "y"]]}
        assert wire_to_api3(wire) == [
            {"filter_operator": "any", "filters": [["code", "is", "x"], ["code", "is", "y"]]}
        ]

    def test_a_nested_group_becomes_the_dict_form_find_translates(self) -> None:
        wire = {
            "logical_operator": "and",
            "conditions": [
                ["project", "is", {"type": "Project", "id": 70}],
                {
                    "logical_operator": "or",
                    "conditions": [
                        ["sg_status_list", "is", "ip"],
                        {"logical_operator": "and", "conditions": [["code", "starts_with", "sh"]]},
                    ],
                },
            ],
        }
        assert wire_to_api3(wire) == [
            ["project", "is", {"type": "Project", "id": 70}],
            {
                "filter_operator": "any",
                "filters": [
                    ["sg_status_list", "is", "ip"],
                    {"filter_operator": "all", "filters": [["code", "starts_with", "sh"]]},
                ],
            },
        ]

    def test_shotgun_api3_translates_what_it_is_handed(self) -> None:
        # The proof the list form is the one `find` takes without loss.
        from shotgun_api3.shotgun import _translate_filters

        translated = _translate_filters(
            wire_to_api3({"logical_operator": "or", "conditions": [["code", "is", "x"]]}), None
        )
        assert translated == {
            "logical_operator": "and",
            "conditions": [
                {"logical_operator": "or", "conditions": [{"path": "code", "relation": "is", "values": ["x"]}]}
            ],
        }


class TestTheDateConversion:
    def test_a_datetime_answered_becomes_the_iso_string_the_rest_api_sends(self) -> None:
        local = timezone(timedelta(hours=2))
        assert from_api3_value(datetime(2026, 3, 4, 14, 0, 0, tzinfo=local)) == "2026-03-04T12:00:00Z"
        assert from_api3_value(datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)) == "2026-03-04T12:00:00Z"

    def test_a_date_answered_stays_a_day(self) -> None:
        assert from_api3_value(date(2026, 3, 4)) == "2026-03-04"

    def test_it_converts_inside_a_row_and_leaves_an_entity_link_alone(self) -> None:
        row = {
            "created_at": datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc),
            "due_date": date(2026, 3, 5),
            "project": {"type": "Project", "id": 70, "name": "Blue Moon Rising"},
            "shots": [{"type": "Shot", "id": 1, "name": "sh010"}],
        }
        assert from_api3_value(row) == {
            "created_at": "2026-03-04T12:00:00Z",
            "due_date": "2026-03-05",
            "project": {"type": "Project", "id": 70, "name": "Blue Moon Rising"},
            "shots": [{"type": "Shot", "id": 1, "name": "sh010"}],
        }

    def test_an_iso_string_written_becomes_an_aware_datetime(self) -> None:
        written = to_api3_value({"created_at": "2026-03-04T12:00:00Z", "due_date": "2026-03-05", "code": "v001"})
        assert written["created_at"] == datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        # A `date` is sent as it is: only a datetime is transformed on the way out.
        assert written["due_date"] == "2026-03-05"
        assert written["code"] == "v001"

    def test_a_write_carries_the_datetime_and_the_read_carries_the_string(self) -> None:
        client, fake = client_with(
            {
                "update": {"type": "Version", "id": 1},
                "find_one": {
                    "type": "Version",
                    "id": 1,
                    "sg_first_frame_date": datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc),
                },
            }
        )
        row = client.update("Version", 1, {"sg_first_frame_date": "2026-03-04T12:00:00Z"})
        assert fake.call("update").args[2] == {
            "sg_first_frame_date": datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)
        }
        assert row.values["sg_first_frame_date"] == "2026-03-04T12:00:00Z"


class TestTheConnection:
    def test_one_connection_per_thread(self) -> None:
        made: list[FakeShotgun] = []

        def factory() -> FakeShotgun:
            fake = FakeShotgun({"schema_entity_read": {}})
            made.append(fake)
            return fake

        client = ShotgunClient("https://studio.example.com", script_name="s", api_key="k", factory=factory)
        seen: list[Any] = []

        def read() -> None:
            client.entity_types()
            client.entity_types()
            seen.append(client.connection)

        first = threading.Thread(target=read)
        second = threading.Thread(target=read)
        first.start()
        first.join()
        second.start()
        second.join()
        assert len(made) == 2
        assert seen[0] is not seen[1]

    def test_the_same_thread_keeps_one_connection(self) -> None:
        client, fake = client_with({"schema_entity_read": {}})
        client.entity_types()
        assert client.connection is fake

    def test_from_env_reads_the_three_keys(self) -> None:
        client = ShotgunClient.from_env(
            {
                "FPT_API_SITE_URL": "https://studio.example.com/",
                "FPT_API_SCRIPT_NAME": "widgets",
                "FPT_API_API_KEY": "secret",
            }
        )
        assert client.site_url == "https://studio.example.com"
        assert client.script_name == "widgets"

    def test_from_env_names_the_missing_key_and_never_a_value(self) -> None:
        with pytest.raises(SgApiError) as caught:
            ShotgunClient.from_env({"FPT_API_SITE_URL": "https://studio.example.com", "FPT_API_API_KEY": "secret"})
        assert str(caught.value) == "FPT_API_SCRIPT_NAME is not set."
        assert "secret" not in str(caught.value)


class TestTheErrorMapping:
    def test_a_fault_becomes_an_api_error_carrying_its_message(self) -> None:
        fault = shotgun_api3.Fault("API read() invalid/missing string entity 'type'")
        client = client_on(FakeShotgun(error=fault))
        with pytest.raises(SgApiError) as caught:
            client.search("Nope", SearchOptions())
        assert str(caught.value) == "API read() invalid/missing string entity 'type'"
        assert caught.value.status is None
        assert caught.value.body is fault

    def test_a_protocol_error_carries_the_status_it_names(self) -> None:
        error = shotgun_api3.ProtocolError("studio.example.com", 503, "down for maintenance", {})
        client = client_on(FakeShotgun(error=error))
        with pytest.raises(SgApiError) as caught:
            client.entity_types()
        assert caught.value.status == 503
        assert str(caught.value) == "down for maintenance"

    def test_a_status_is_lifted_out_of_the_message_when_that_is_where_it_is(self) -> None:
        client = client_on(
            FakeShotgun(error=shotgun_api3.ShotgunError("Unanticipated error occurred HTTP Error 413: Payload Too Large"))
        )
        with pytest.raises(SgApiError) as caught:
            client.upload("Shot", 1, UploadFile(filename="a.png", data=b"x", field="image"))
        assert caught.value.status == 413
