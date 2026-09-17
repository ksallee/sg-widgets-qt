"""Port of the schema blocks of `packages/core/test/status.test.ts`; upstream has no schema.test.ts."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.schema import (
    FieldSchema,
    display_name_of,
    field_schema_override,
    normalize_field,
    normalize_fields,
    status_field_for,
    status_field_name_for,
)


class TestSchema:
    def test_normalises_the_value_editable_wrapper(self) -> None:
        f = normalize_field("sg_status_list", {
            "name": {"value": "Status", "editable": True},
            "entity_type": {"value": "Version", "editable": False},
            "data_type": {"value": "status_list", "editable": False},
            "editable": {"value": True, "editable": False},
            "mandatory": {"value": False, "editable": False},
            "unique": {"value": False, "editable": False},
            "properties": {
                "valid_values": {"value": ["rev", "fin"], "editable": True},
                "hidden_values": {"value": ["fin"], "editable": True},
                "display_values": {"value": {"rev": "Pending Review", "fin": "Final"}, "editable": True},
                "default_value": {"value": "rev", "editable": True},
            },
        })
        assert f.display_name == "Status"
        assert f.data_type == "status_list"
        assert f.hidden_values == ["fin"]
        assert status_field_for("Version", {"sg_status_list": f}) is f
        assert status_field_for("Project") == "sg_status"

    def test_the_conventional_status_field_wins_over_another_status_list_the_site_added(self) -> None:
        def shape(name: str, display_name: str) -> FieldSchema:
            return FieldSchema(
                name=name,
                display_name=display_name,
                entity_type="Shot",
                data_type="status_list",
                editable=True,
                mandatory=False,
                unique=False,
            )

        # A schema read answers in no order the caller controls, so the first status_list
        # found is not the type's status.
        fields = {
            "sg_client_status": shape("sg_client_status", "Client Status"),
            "sg_status_list": shape("sg_status_list", "Status"),
        }
        assert status_field_for("Shot", fields) is fields["sg_status_list"]
        # With no conventional field the first status_list is still better than a guess.
        assert status_field_for("Shot", {"sg_client_status": fields["sg_client_status"]}) is fields["sg_client_status"]
        assert status_field_for("Shot", {}) == "sg_status_list"
        assert status_field_name_for("Project") == "sg_status"

    def test_display_name_falls_back_through_the_conventional_fields(self) -> None:
        assert display_name_of({"code": "sh010", "name": "x"}) == "sh010"
        assert display_name_of({"content": "Comp"}) == "Comp"
        assert display_name_of({}, "#12") == "#12"


class TestTheFieldsTheSchemaTypesWrongly:
    def test_reads_note_read_by_current_user_as_a_list_of_unread_and_read(self) -> None:
        field = normalize_field("read_by_current_user", {
            "name": {"value": "Read by Current User", "editable": True},
            "entity_type": {"value": "Note", "editable": False},
            "data_type": {"value": "checkbox", "editable": False},
            "editable": {"value": True, "editable": False},
            "mandatory": {"value": False, "editable": False},
            "unique": {"value": False, "editable": False},
            "properties": {},
        })
        assert field.data_type == "list"
        assert field.valid_values == ["unread", "read"]
        assert field_schema_override("Shot", "sg_status_list") is None

    def test_answers_note_read_by_current_user_from_a_schema_that_does_not_declare_it(self) -> None:
        fields = normalize_fields({
            "data": {
                "subject": {
                    "name": {"value": "Subject", "editable": True},
                    "entity_type": {"value": "Note", "editable": False},
                    "data_type": {"value": "text", "editable": False},
                    "editable": {"value": True, "editable": False},
                    "mandatory": {"value": True, "editable": False},
                    "unique": {"value": False, "editable": False},
                    "properties": {},
                },
            },
        })
        read = fields["read_by_current_user"]
        assert read == FieldSchema(
            name="read_by_current_user",
            display_name="Read by Current User",
            entity_type="Note",
            data_type="list",
            valid_values=["unread", "read"],
            operators=["is", "is_not"],
            # A person's write is stored (068_note_read_state).
            editable=True,
            mandatory=False,
            unique=False,
        )

    def test_patches_only_the_type_the_values_and_the_operators_on_a_site_that_declares_the_field(self) -> None:
        declared = normalize_field("read_by_current_user", {
            "name": {"value": "Read State", "editable": True},
            "entity_type": {"value": "Note", "editable": False},
            "data_type": {"value": "checkbox", "editable": False},
            "editable": {"value": False, "editable": False},
            "mandatory": {"value": False, "editable": False},
            "unique": {"value": False, "editable": False},
            "properties": {"description": {"value": "Per person.", "editable": True}},
        })
        assert declared == FieldSchema(
            name="read_by_current_user",
            display_name="Read State",
            entity_type="Note",
            data_type="list",
            valid_values=["unread", "read"],
            operators=["is", "is_not"],
            editable=False,
            mandatory=False,
            unique=False,
            description="Per person.",
        )
        assert field_schema_override("Note", "read_by_current_user") == {
            "data_type": "list",
            "valid_values": ["unread", "read"],
            "operators": ["is", "is_not"],
        }

    def test_leaves_the_field_the_schema_did_declare_alone_and_adds_nothing_to_another_type(self) -> None:
        def raw(entity_type: str, data_type: str) -> dict[str, Any]:
            return {
                "name": {"value": "Read by Current User", "editable": True},
                "entity_type": {"value": entity_type, "editable": False},
                "data_type": {"value": data_type, "editable": False},
                "editable": {"value": True, "editable": False},
                "mandatory": {"value": False, "editable": False},
                "unique": {"value": False, "editable": False},
                "properties": {},
            }

        notes = normalize_fields({"data": {"read_by_current_user": raw("Note", "checkbox")}})
        assert list(notes.keys()) == ["read_by_current_user"]
        assert notes["read_by_current_user"].data_type == "list"
        shots = normalize_fields({"data": {"read_by_current_user": raw("Shot", "checkbox")}})
        assert shots["read_by_current_user"].data_type == "checkbox"
        assert list(normalize_fields({"data": {}}, "Note").keys()) == ["read_by_current_user"]
        assert list(normalize_fields({"data": {}}).keys()) == []
