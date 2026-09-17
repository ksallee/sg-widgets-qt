"""Port of `packages/core/test/pickers.test.ts`."""
from __future__ import annotations

from collections.abc import Sequence

from sg_widgets_core.client import EntityTypeInfo
from sg_widgets_core.pickers import (
    UNRESOLVED_PATH_LABEL,
    EntityTypeOptionsInput,
    EntityTypeRestrictions,
    ExtraField,
    FieldHop,
    FieldOption,
    FieldOptionsInput,
    FieldPathOption,
    current_type,
    derive_field_options,
    entity_type_options,
    field_path_of,
    filter_entity_types,
    friendly_field_path,
    matches_tokens,
    move_field_path,
    path_types,
    resolve_field_path_options,
    search_field_options,
    search_field_path_options,
    toggle_field_path,
    traversal_targets,
)
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.schema_service import create_schema_service

from .fake_client import FakeClient

schema = create_schema_service(FakeClient())


def fields_of(entity_type: str) -> dict[str, FieldSchema]:
    return schema.fields(entity_type)


def paths_of(options: Sequence[FieldOption | FieldPathOption]) -> list[str]:
    return [o.path for o in options]


def a_field(data_type: str, valid_types: list[str] | None = None) -> FieldSchema:
    return FieldSchema(
        name="entity",
        display_name="Link",
        entity_type="Version",
        data_type=data_type,
        editable=True,
        mandatory=False,
        unique=False,
        valid_types=valid_types,
    )


TYPES = [
    EntityTypeInfo(name="Shot", display_name="Shot"),
    EntityTypeInfo(name="Asset", display_name="Asset"),
    EntityTypeInfo(name="HumanUser", display_name="Person"),
]


class TestMatchesTokens:
    def test_needs_every_token_in_any_order_and_any_field(self) -> None:
        assert matches_tokens("due date", "Due Date", "due_date") is True
        assert matches_tokens("date due", "Due Date", "due_date") is True
        assert matches_tokens("due code", "Due Date", "due_date") is False
        assert matches_tokens("", "anything") is True
        assert matches_tokens("STATUS", "Status", "sg_status_list") is True


class TestFilterEntityTypes:
    def test_passes_everything_through_with_no_restriction(self) -> None:
        assert len(filter_entity_types(TYPES)) == 3
        assert len(filter_entity_types(TYPES, EntityTypeRestrictions(allow=[], deny=[]))) == 3

    def test_applies_allow_then_deny(self) -> None:
        allowed = filter_entity_types(TYPES, EntityTypeRestrictions(allow=["Shot", "Asset"]))
        assert [t.name for t in allowed] == ["Shot", "Asset"]
        denied = filter_entity_types(TYPES, EntityTypeRestrictions(deny=["HumanUser"]))
        assert [t.name for t in denied] == ["Shot", "Asset"]
        both = filter_entity_types(TYPES, EntityTypeRestrictions(allow=["Shot", "Asset"], deny=["Asset"]))
        assert [t.name for t in both] == ["Shot"]


class TestEntityTypeOptions:
    def test_offers_nothing_while_the_read_is_in_flight(self) -> None:
        options = entity_type_options(None)
        assert options.types == []
        assert options.shown == []
        assert options.label_of("Shot") == "Shot"

    def test_narrows_the_derived_list_by_the_query_on_display_name_or_code(self) -> None:
        shown = entity_type_options(TYPES, EntityTypeOptionsInput(query="person")).shown
        assert [t.name for t in shown] == ["HumanUser"]
        shown = entity_type_options(TYPES, EntityTypeOptionsInput(query="humanuser")).shown
        assert [t.name for t in shown] == ["HumanUser"]
        assert len(entity_type_options(TYPES, EntityTypeOptionsInput(query="")).shown) == 3

    def test_searches_what_allow_and_deny_left(self) -> None:
        options = entity_type_options(TYPES, EntityTypeOptionsInput(deny=["HumanUser"]))
        assert [t.name for t in options.types] == ["Shot", "Asset"]
        assert [t.name for t in options.shown] == ["Shot", "Asset"]

    def test_labels_a_code_by_its_display_name_and_an_absent_one_by_itself(self) -> None:
        options = entity_type_options(TYPES)
        assert options.label_of("HumanUser") == "Person"
        assert options.label_of("CustomEntity07") == "CustomEntity07"
        denied = entity_type_options(TYPES, EntityTypeOptionsInput(deny=["HumanUser"]))
        assert denied.label_of("HumanUser") == "HumanUser"


class TestDottedPaths:
    hops = [
        FieldHop(name="entity", display_name="Link", through="Shot"),
        FieldHop(name="project", display_name="Project", through="Project"),
    ]

    def test_names_the_type_it_travels_through_at_every_hop(self) -> None:
        assert field_path_of([], "code") == "code"
        assert field_path_of(self.hops, "name") == "entity.Shot.project.Project.name"

    def test_a_path_built_here_resolves_against_the_schema(self) -> None:
        hop = FieldHop(name="entity", display_name="Link", through="Shot")
        segments = schema.resolve_path("Version", field_path_of([hop], "code"))
        assert [s.name for s in segments] == ["entity", "code"]
        assert friendly_field_path(segments) == "Link › Shot Code"

    def test_tracks_the_types_already_visited(self) -> None:
        assert path_types("Version", self.hops) == ["Version", "Shot", "Project"]
        assert current_type("Version", []) == "Version"
        assert current_type("Version", self.hops) == "Project"


class TestTraversalTargets:
    link = a_field("entity", ["Shot", "Asset", "Sequence"])

    def test_is_empty_until_deep_links_are_on(self) -> None:
        assert traversal_targets(self.link, FieldOptionsInput(root_type="Version")) == []
        assert traversal_targets(self.link, FieldOptionsInput(root_type="Version", deep_links=True)) == [
            "Shot", "Asset", "Sequence",
        ]

    def test_refuses_a_multi_entity_field_whose_dotted_path_reads_back_nothing(self) -> None:
        # probe 016
        multi = a_field("multi_entity", ["Task"])
        assert traversal_targets(multi, FieldOptionsInput(root_type="Shot", deep_links=True)) == []

    def test_refuses_a_link_declaring_no_target_type(self) -> None:
        assert traversal_targets(a_field("entity"), FieldOptionsInput(root_type="Version", deep_links=True)) == []
        assert traversal_targets(a_field("entity", []), FieldOptionsInput(root_type="Version", deep_links=True)) == []

    def test_drops_a_type_already_on_the_path(self) -> None:
        hops = [FieldHop(name="entity", display_name="Link", through="Shot")]
        assert traversal_targets(
            self.link, FieldOptionsInput(root_type="Version", hops=hops, deep_links=True)
        ) == ["Asset", "Sequence"]
        assert traversal_targets(
            a_field("entity", ["Version"]), FieldOptionsInput(root_type="Version", hops=hops, deep_links=True)
        ) == []

    def test_stops_at_the_depth_limit(self) -> None:
        two = [
            FieldHop(name="entity", display_name="Link", through="Shot"),
            FieldHop(name="sg_sequence", display_name="Sequence", through="Sequence"),
        ]
        assert traversal_targets(self.link, FieldOptionsInput(root_type="Version", hops=two, deep_links=True)) == []
        assert traversal_targets(
            self.link, FieldOptionsInput(root_type="Version", hops=two, deep_links=True, max_depth=3)
        ) == ["Asset"]
        assert traversal_targets(
            self.link, FieldOptionsInput(root_type="Version", hops=two[:1], deep_links=True, max_depth=1)
        ) == []


class TestDeriveFieldOptions:
    def test_sorts_by_display_name_and_marks_every_row_selectable_with_no_restriction(self) -> None:
        options = derive_field_options(fields_of("Version"), FieldOptionsInput(root_type="Version"))
        assert all(o.selectable for o in options)
        assert all(not o.traversable for o in options)
        names = [o.display_name for o in options]
        assert sorted(names, key=str.casefold) == names

    def test_keeps_a_link_on_the_list_when_the_selection_is_restricted_to_another_type(self) -> None:
        options = derive_field_options(fields_of("Version"), FieldOptionsInput(
            root_type="Version", deep_links=True, data_types=["date", "date_time"],
        ))
        link = next(o for o in options if o.path == "entity")
        assert (link.selectable, link.traversable, link.targets) == (False, True, ["Shot", "Asset", "Sequence"])
        date = next(o for o in options if o.path == "client_approved_at")
        assert (date.selectable, date.traversable) == (True, False)
        assert "code" not in paths_of(options)

    def test_drops_a_link_too_when_deep_links_are_off_and_the_type_is_not_wanted(self) -> None:
        options = derive_field_options(
            fields_of("Version"), FieldOptionsInput(root_type="Version", data_types="date")
        )
        assert "entity" not in paths_of(options)
        assert all(o.data_type == "date" for o in options)

    def test_takes_a_single_data_type_as_a_string(self) -> None:
        one = derive_field_options(fields_of("Shot"), FieldOptionsInput(root_type="Shot", data_types="checkbox"))
        many = derive_field_options(fields_of("Shot"), FieldOptionsInput(root_type="Shot", data_types=["checkbox"]))
        assert paths_of(one) == paths_of(many)

    def test_restricts_selection_to_fields_linking_one_of_the_wanted_types(self) -> None:
        options = derive_field_options(
            fields_of("Task"), FieldOptionsInput(root_type="Task", valid_types=["HumanUser"])
        )
        assert "task_assignees" in paths_of(options)
        assert "content" not in paths_of(options)
        assert "step" not in paths_of(options)

    def test_excludes_by_full_path_so_a_hop_keeps_its_own_name(self) -> None:
        hops = [FieldHop(name="entity", display_name="Link", through="Shot")]
        root = derive_field_options(fields_of("Shot"), FieldOptionsInput(root_type="Shot", exclude=["code"]))
        assert "code" not in paths_of(root)
        nested = derive_field_options(
            fields_of("Shot"), FieldOptionsInput(root_type="Version", hops=hops, exclude=["code"])
        )
        assert "entity.Shot.code" in paths_of(nested)

    def test_hides_a_prefix_and_everything_beneath_it(self) -> None:
        hops = [FieldHop(name="entity", display_name="Link", through="Shot")]
        root = derive_field_options(fields_of("Version"), FieldOptionsInput(
            root_type="Version", deep_links=True, hide_paths=["entity"],
        ))
        assert "entity" not in paths_of(root)
        nested = derive_field_options(fields_of("Shot"), FieldOptionsInput(
            root_type="Version", hops=hops, hide_paths=["entity"],
        ))
        assert len(nested) == 0

    def test_drops_the_types_the_api_refuses_in_a_filter(self) -> None:
        # 017_filter_operators
        options = derive_field_options(
            fields_of("Version"), FieldOptionsInput(root_type="Version", filterable_only=True)
        )
        assert "sg_uploaded_movie" not in paths_of(options)
        assert "code" in paths_of(options)

    def test_takes_a_caller_predicate_over_the_schema_and_the_full_path(self) -> None:
        seen: list[str] = []

        def keep(field: FieldSchema, path: str) -> bool:
            seen.append(path)
            return field.editable

        options = derive_field_options(fields_of("Shot"), FieldOptionsInput(root_type="Shot", filter=keep))
        assert "id" in seen
        assert "id" not in paths_of(options)
        assert "code" in paths_of(options)

    def test_puts_computed_entries_first_at_the_root_only_past_every_restriction(self) -> None:
        extra_fields = [ExtraField(name="row_number", display_name="Row Number")]
        root = derive_field_options(fields_of("Version"), FieldOptionsInput(
            root_type="Version", data_types="date", extra_fields=extra_fields,
        ))
        assert (root[0].path, root[0].computed, root[0].selectable, root[0].traversable) == (
            "row_number", True, True, False,
        )
        nested = derive_field_options(fields_of("Shot"), FieldOptionsInput(
            root_type="Version",
            hops=[FieldHop(name="entity", display_name="Link", through="Shot")],
            extra_fields=extra_fields,
        ))
        assert "row_number" not in paths_of(nested)

    def test_builds_nested_paths_that_resolve_back_through_the_schema(self) -> None:
        hops = [FieldHop(name="entity", display_name="Link", through="Shot")]
        options = derive_field_options(fields_of("Shot"), FieldOptionsInput(
            root_type="Version", hops=hops, data_types="date",
        ))
        turnover = next(o for o in options if o.path == "entity.Shot.sg_turnover_date")
        assert turnover.selectable is True
        segments = schema.resolve_path("Version", turnover.path)
        assert friendly_field_path(segments) == "Link › Turnover Date"


class TestSearchFieldOptions:
    def test_matches_display_name_code_and_data_type(self) -> None:
        options = derive_field_options(fields_of("Shot"), FieldOptionsInput(root_type="Shot"))
        assert paths_of(search_field_options(options, "turnover")) == ["sg_turnover_date"]
        assert paths_of(search_field_options(options, "sg_cut_in")) == ["sg_cut_in"]
        assert len(search_field_options(options, "   ")) == len(options)
        assert len(search_field_options(options, "zzznope")) == 0


class TestToggleFieldPath:
    def test_appends_a_path_that_is_absent_and_drops_one_that_is_there(self) -> None:
        assert toggle_field_path(["code"], "sg_status_list") == ["code", "sg_status_list"]
        assert toggle_field_path(["code", "sg_status_list"], "code") == ["sg_status_list"]
        assert toggle_field_path([], "code") == ["code"]

    def test_leaves_the_source_alone(self) -> None:
        paths = ["code"]
        assert toggle_field_path(paths, "description") is not paths
        assert paths == ["code"]


class TestMoveFieldPath:
    paths = ["code", "sg_status_list", "entity.Shot.sg_turnover_date"]

    def test_moves_an_entry_and_keeps_the_rest_in_order(self) -> None:
        assert move_field_path(self.paths, 2, 1) == ["code", "entity.Shot.sg_turnover_date", "sg_status_list"]
        assert move_field_path(self.paths, 0, 2) == ["sg_status_list", "entity.Shot.sg_turnover_date", "code"]

    def test_leaves_the_order_alone_off_either_end(self) -> None:
        assert move_field_path(self.paths, 0, -1) == self.paths
        assert move_field_path(self.paths, 2, 3) == self.paths
        assert move_field_path(self.paths, 1, 1) == self.paths
        assert move_field_path([], 0, 0) == []


class TestResolveFieldPathOptions:
    paths = ["code", "entity.Shot.sg_turnover_date", "sg_nope.Thing.code"]

    def test_keeps_the_order_it_was_given_and_labels_a_plain_path_by_its_field(self) -> None:
        options = resolve_field_path_options(schema, "Version", self.paths)
        assert paths_of(options) == self.paths
        assert options[0].label == "Version Name"
        assert options[0].name == "code"
        assert options[0].data_type == "text"
        assert options[0].resolved is True

    def test_labels_a_dotted_path_by_every_display_name_it_travels(self) -> None:
        dotted = resolve_field_path_options(schema, "Version", ["entity.Shot.sg_turnover_date"])[0]
        assert dotted.label == "Link › Shot › Turnover Date"
        assert dotted.name == "sg_turnover_date"
        assert dotted.data_type == "date"
        assert dotted.sub_label == "date"
        assert dotted.resolved is True

    def test_keeps_a_path_the_schema_does_not_hold_marked_in_its_sub_label(self) -> None:
        options = resolve_field_path_options(schema, "Version", self.paths)
        assert options[2] == FieldPathOption(
            path="sg_nope.Thing.code",
            label="sg_nope.Thing.code",
            name="",
            data_type="",
            sub_label=UNRESOLVED_PATH_LABEL,
            resolved=False,
        )

    def test_carries_the_leaf_code_a_row_shows_under_show_code(self) -> None:
        options = resolve_field_path_options(
            schema, "Version", ["sg_status_list", "entity.Shot.sg_turnover_date"]
        )
        assert [o.name for o in options] == ["sg_status_list", "sg_turnover_date"]


class TestSearchFieldPathOptions:
    def test_matches_the_label_and_the_path_and_leaves_an_empty_query_alone(self) -> None:
        options = resolve_field_path_options(
            schema, "Version", ["code", "entity.Shot.sg_turnover_date", "sg_nope"]
        )
        assert paths_of(search_field_path_options(options, "turnover")) == ["entity.Shot.sg_turnover_date"]
        assert paths_of(search_field_path_options(options, "entity.Shot")) == ["entity.Shot.sg_turnover_date"]
        assert paths_of(search_field_path_options(options, "sg_nope")) == ["sg_nope"]
        assert len(search_field_path_options(options, "   ")) == 3
        assert len(search_field_path_options(options, "zzznope")) == 0
