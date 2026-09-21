"""Port of `packages/core/test/hierarchy.test.ts`."""
from __future__ import annotations

import re
from typing import Any

import pytest

from sg_widgets_core.client import HierarchyRef, SgApiError
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.mock import MockClient
from sg_widgets_core.query import QueryCacheOptions, create_query_cache
from sg_widgets_core.search import breadcrumb, hydrate, path_refs, scope_to_project

from .fake_client import CountingClient


def client() -> MockClient:
    return MockClient()


def sample(c: MockClient) -> tuple[EntityRef, EntityRef]:
    """The first Shot of the first Sequence, and the Task on it."""
    shot = c.rows_of("Shot")[0]
    task = next(t for t in c.rows_of("Task") if t["entity"]["id"] == int(shot["id"]))
    return EntityRef(type="Shot", id=int(shot["id"])), EntityRef(type="Task", id=int(task["id"]))


class Schema:
    """Enough of a schema service for `scope_to_project`."""

    def __init__(self, c: MockClient) -> None:
        self._client = c

    def field(self, entity_type: str, name: str) -> Any | None:
        return self._client.fields(entity_type).get(name)


class TestExpandingTheTree:
    def test_answers_one_level_at_a_time_entity_types_under_a_project(self) -> None:
        c = client()
        root = c.hierarchy_expand("/Project/70")
        assert root.ref == HierarchyRef(kind="entity", value=EntityRef(type="Project", id=70))
        assert root.parent_path == "/"
        assert root.path == "/Project/70"
        assert root.has_children is True
        assert [child.label for child in root.children] == ["Assets", "Shots"]
        # `value` is a bare schema name on an entity_type ref, not an object.
        assert root.children[1].ref == HierarchyRef(kind="entity_type", value="Shot")

    def test_walks_project_sequence_shot_task_one_call_per_node(self) -> None:
        c = client()
        shots = c.hierarchy_expand("/Project/70/Shot")
        sequence = shots.children[0]
        assert sequence.ref.kind == "entity"
        level = c.hierarchy_expand(sequence.path)
        shot = level.children[0]
        assert shot.ref.kind == "entity"
        assert shot.ref.value.type == "Shot"
        shot_node = c.hierarchy_expand(shot.path)
        assert [n.label for n in shot_node.children] == ["Tasks"]
        tasks = c.hierarchy_expand(shot_node.children[0].path)
        assert len(tasks.children) > 0
        assert tasks.children[0].ref.kind == "entity"
        assert tasks.children[0].ref.value.type == "Task"

    def test_walks_project_asset_task_too(self) -> None:
        c = client()
        assets = c.hierarchy_expand("/Project/70/Asset")
        asset = assets.children[0]
        assert asset.ref.kind == "entity"
        assert asset.ref.value.type == "Asset"
        node = c.hierarchy_expand(asset.path)
        tasks = c.hierarchy_expand(node.children[0].path)
        assert tasks.children[0].ref.kind == "entity"
        assert tasks.children[0].ref.value.type == "Task"

    def test_refuses_a_project_that_is_not_there_the_way_code_107_does(self) -> None:
        with pytest.raises(SgApiError):
            client().hierarchy_expand("/Project/999999999")


class TestFindingARowInTheTree:
    def test_answers_the_breadcrumb_to_a_shot_project_first_and_the_row_last(self) -> None:
        c = client()
        shot, _task = sample(c)
        path = c.hierarchy_search("/Project/70", shot)[0]
        assert path.ref == shot
        assert path.project_id == 70
        assert path.incremental_path[0] == "/Project/70"
        assert path.incremental_path[1] == "/Project/70/Shot"
        assert re.match(r"^/Project/70/Shot/sg_sequence/Sequence/\d+$", path.incremental_path[2])
        assert path.incremental_path[-1] == f"/Project/70/Shot/sg_sequence/Sequence/100/id/{shot.id}"
        # `path_label` holds neither the project nor the row itself.
        assert path.path_label == "Shots > sh010"
        assert breadcrumb(path) == ["Shots", "sh010", path.label]

    def test_reaches_a_task_through_its_shot(self) -> None:
        c = client()
        _shot, task = sample(c)
        path = c.hierarchy_search("/Project/70", task)[0]
        assert path.path_label == "Shots > sh010 > sh010_0010 > Tasks"
        assert path_refs(path.incremental_path) == [
            EntityRef(type="Project", id=70),
            EntityRef(type="Sequence", id=100),
            EntityRef(type="Shot", id=862),
            EntityRef(type="Task", id=task.id),
        ]

    def test_answers_nothing_outside_the_root_or_for_a_type_the_tree_has_no_place_for(self) -> None:
        c = client()
        shot, _task = sample(c)
        assert c.hierarchy_search("/Project/71", shot) == []
        assert c.hierarchy_search("/Project/70", EntityRef(type="HumanUser", id=20)) == []


class TestPathRefs:
    def test_reads_a_leaf_under_a_grouping_as_the_type_the_folder_named(self) -> None:
        assert path_refs("/Project/70/Shot/sg_sequence/Sequence/23/id/862") == [
            EntityRef(type="Project", id=70),
            EntityRef(type="Sequence", id=23),
            EntityRef(type="Shot", id=862),
        ]
        assert path_refs("/Project/70/Asset/id/1226") == [
            EntityRef(type="Project", id=70),
            EntityRef(type="Asset", id=1226),
        ]
        assert path_refs("/Project/70") == [EntityRef(type="Project", id=70)]
        assert path_refs("/") == []


class TestHydratingATextSearch:
    def test_fills_the_thumbnail_and_the_project_a_text_search_does_not_answer(self) -> None:
        c = client()
        rows = c.text_search("sh010_0010", {"Shot": None})
        hits = hydrate(c, rows)
        assert hits[0].ref.type == "Shot"
        assert hits[0].ref.name == "sh010_0010"
        assert hits[0].image.startswith("https:")
        assert hits[0].project == EntityRef(type="Project", id=70, name="Blue Moon Rising")
        # The linked row `_text_search` matched the words against survives on the hit.
        assert isinstance(hits[0].status, str)

    def test_leaves_a_type_with_no_image_and_no_project_alone(self) -> None:
        c = client()
        rows = c.text_search("ada", {"HumanUser": None})
        hits = hydrate(c, rows)
        assert hits[0].project is None
        assert hits[0].image.startswith("https:")

    def test_carries_every_value_a_row_anatomy_asked_for(self) -> None:
        c = client()
        rows = c.text_search("sh010_0010", {"Shot": None})
        hits = hydrate(c, rows, fields=["sg_cut_in", "sg_sequence"])
        assert hits[0].values["sg_cut_in"] == 1001
        # A relationship is unwrapped to its data, so a caller reads `{type, id, name}`.
        assert hits[0].values["sg_sequence"]["type"] == "Sequence"

    def test_labels_a_row_with_the_named_field_rather_than_the_display_name_chain(self) -> None:
        c = client()
        rows = c.text_search("sh010_0010", {"Shot": None})
        hits = hydrate(c, rows, fields=["description"], label_field="description")
        assert hits[0].ref.name == "Shot sh010_0010"

    def test_reads_once_per_type_not_once_per_row(self) -> None:
        c = create_query_cache(MockClient(), QueryCacheOptions(ttl_ms=0))
        counted = CountingClient(c)
        rows = c.text_search("sh010", {"Shot": None, "Task": None})
        hydrate(counted, rows)
        assert len(rows) > 2
        assert len([call for call in counted.calls if call.startswith("search ")]) == 2


class TestScopingToAProject:
    def test_adds_the_condition_only_to_types_that_have_a_project_field(self) -> None:
        c = client()
        scoped = scope_to_project(Schema(c), {"Shot": None, "Project": None, "Step": None}, 70)
        assert scoped["Shot"] == [["project", "is", {"type": "Project", "id": 70}]]
        # Project has no `project` field and Step has none either; the path would 400.
        assert scoped["Project"] == []
        assert scoped["Step"] == []

    def test_keeps_the_conditions_the_caller_gave(self) -> None:
        c = client()
        scoped = scope_to_project(Schema(c), {"Task": [["sg_status_list", "is", "ip"]]}, 71)
        assert scoped["Task"] == [
            ["sg_status_list", "is", "ip"],
            ["project", "is", {"type": "Project", "id": 71}],
        ]
