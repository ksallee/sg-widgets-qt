"""Port of `packages/core/test/entity-card.test.ts`."""
from __future__ import annotations

import pytest

from sg_widgets_core.client import EntityRow, SearchOptions
from sg_widgets_core.context import SgContext, SgContextOptions, create_sg_context
from sg_widgets_core.entity_card import (
    EntityCardOptions,
    describe_entity_card,
    entity_card_fields,
    load_entity_card,
)
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.mock import MOCK_NOW, MockClient


def context() -> SgContext:
    return create_sg_context(
        MockClient(seed=1, now=MOCK_NOW),
        SgContextOptions(site_url="https://example.shotgunstudio.com"),
    )


def first_row(sg: SgContext, entity_type: str, field: str) -> EntityRow:
    return sg.client.search(entity_type, SearchOptions(fields=[field], page={"size": 1})).data[0]


class TestEntityCardFields:
    def test_asks_for_the_identity_chain_the_thumbnail_the_status_field_and_the_caller_paths(self) -> None:
        fields = entity_card_fields(
            context(), "Shot", EntityCardOptions(fields=["sg_sequence", "description"])
        )
        assert "cached_display_name" in fields
        assert "code" in fields
        assert "image" in fields
        assert "sg_status_list" in fields
        assert "sg_sequence" in fields
        assert "description" in fields

    def test_leaves_out_an_identity_field_the_type_does_not_have(self) -> None:
        fields = entity_card_fields(context(), "Task")
        assert "code" not in fields
        assert "name" not in fields
        assert "content" in fields

    def test_names_each_field_once(self) -> None:
        fields = entity_card_fields(context(), "Shot", EntityCardOptions(fields=["code", "code"]))
        assert len([f for f in fields if f == "code"]) == 1


class TestLoadEntityCard:
    def test_reads_one_row_and_describes_it(self) -> None:
        sg = context()
        first = first_row(sg, "Shot", "code")
        card = load_entity_card(
            sg, EntityRef(type="Shot", id=first.id), EntityCardOptions(fields=["sg_status_list"])
        )
        assert card.entity.id == first.id
        assert len(card.name) > 0
        assert card.type_label == "Shot"
        assert card.status is not None
        assert card.status.code
        # The header already carries this status, so the column naming the same field is gone.
        assert card.columns == []

    def test_keeps_a_linked_row_status_which_is_a_different_row_from_the_one_the_card_is_of(self) -> None:
        sg = context()
        first = first_row(sg, "Version", "code")
        card = load_entity_card(
            sg,
            EntityRef(type="Version", id=first.id),
            EntityCardOptions(fields=["sg_status_list", "sg_task.Task.sg_status_list"]),
        )
        assert [c.path for c in card.columns] == ["sg_task.Task.sg_status_list"]
        assert card.status is not None
        assert card.status.field.name == "sg_status_list"

    def test_labels_a_dotted_path_through_a_field_with_several_valid_types(self) -> None:
        sg = context()
        first = first_row(sg, "Version", "code")
        card = load_entity_card(
            sg,
            EntityRef(type="Version", id=first.id),
            EntityCardOptions(fields=["entity.Shot.sg_sequence", "sg_task.Task.sg_status_list"]),
        )
        assert [c.label for c in card.columns] == ["Link › Shot › Sequence", "Task › Status"]
        assert card.columns[0].data_type == "entity"
        assert card.columns[1].data_type == "status_list"

    def test_carries_the_row_it_described_for_a_label_the_caller_derives(self) -> None:
        sg = context()
        first = first_row(sg, "Shot", "code")
        card = load_entity_card(sg, EntityRef(type="Shot", id=first.id))
        assert card.row.id == first.id
        assert card.row.type == "Shot"

    def test_names_the_type_by_its_display_name(self) -> None:
        sg = context()
        first = first_row(sg, "HumanUser", "name")
        card = load_entity_card(sg, EntityRef(type="HumanUser", id=first.id))
        assert card.type_label == "Person"

    def test_throws_for_a_row_that_is_not_readable(self) -> None:
        with pytest.raises(ValueError, match="not readable"):
            load_entity_card(context(), EntityRef(type="Shot", id=99_999_999))


class TestDescribeEntityCard:
    def test_shows_an_unresolvable_path_under_its_own_text_and_an_empty_value(self) -> None:
        sg = context()
        row = first_row(sg, "Shot", "code")
        card = describe_entity_card(sg, row, EntityCardOptions(fields=["sg_nonesuch"]))
        assert card.columns[0].path == "sg_nonesuch"
        assert card.columns[0].label == "sg_nonesuch"
        assert card.columns[0].data_type == "text"
        assert card.columns[0].value is None

    def test_has_no_status_for_a_type_without_a_status_field(self) -> None:
        sg = context()
        row = first_row(sg, "HumanUser", "name")
        assert describe_entity_card(sg, row).status is None

    def test_drops_a_project_column_naming_sg_status_the_status_field_of_that_type(self) -> None:
        sg = context()
        first = first_row(sg, "Project", "name")
        card = load_entity_card(
            sg, EntityRef(type="Project", id=first.id), EntityCardOptions(fields=["sg_status", "sg_type"])
        )
        assert card.status is not None
        assert card.status.field.name == "sg_status"
        assert [c.path for c in card.columns] == ["sg_type"]

    def test_keeps_the_status_column_when_the_row_has_no_status_to_draw(self) -> None:
        sg = context()
        row = EntityRow(type="Shot", id=4243, values={"code": "sh_4243", "sg_status_list": None})
        card = describe_entity_card(sg, row, EntityCardOptions(fields=["sg_status_list", "description"]))
        assert card.status is None
        assert [c.path for c in card.columns] == ["sg_status_list", "description"]

    def test_falls_back_to_type_and_id_when_the_row_has_no_name(self) -> None:
        sg = context()
        card = describe_entity_card(sg, EntityRow(type="Shot", id=4242, values={}))
        assert card.name == "Shot #4242"
