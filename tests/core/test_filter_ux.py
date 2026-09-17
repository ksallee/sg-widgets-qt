"""Port of `packages/core/test/filter-ux.test.ts`."""
from __future__ import annotations

from typing import Any

import pytest

from sg_widgets_core.client import EntityRow, SgApiError, SummarizeOptions, SummaryGroup, SummaryGrouping
from sg_widgets_core.filter import EntityRef, FilterGroup, condition, group, to_api3_hash
from sg_widgets_core.filter_ux import (
    ConditionParts,
    ConditionValues,
    FacetList,
    FacetReads,
    FacetShape,
    FacetValue,
    OperatorPreset,
    RelativeDate,
    RelativeWindow,
    SortKey,
    append_at,
    apply_preset,
    condition_arity,
    condition_list,
    condition_parts,
    condition_values,
    count_active_conditions,
    count_conditions,
    default_condition,
    default_value_for,
    describe_condition,
    empty_value_for,
    facet_counts,
    facet_lists,
    facet_presets,
    facet_scopes,
    facet_shape,
    facet_values,
    facet_values_from_groups,
    field_operators,
    filterable_fields,
    find_condition,
    find_facet,
    from_sort_string,
    is_grouping_refusal,
    is_hidden_path,
    is_sortable,
    move_at,
    node_at,
    operator_label,
    operator_menu,
    preset_by_id,
    preset_id_of,
    presets_for,
    relative_from,
    relative_operator,
    relative_window,
    remove_at,
    replace_at,
    set_facet,
    set_facet_preset,
    sortable_fields,
    supports_empty,
    time_unit_field,
    time_unit_label,
    to_sort_string,
    validate_condition,
    value_arity,
    value_editor_for,
    with_added_list_value,
    with_list_value,
    with_relative_window,
    without_list_value,
    without_paths,
)
from sg_widgets_core.schema import FieldSchema, normalize_fields


def field(name: str, data_type: str, display_name: str | None = None, **rest: Any) -> FieldSchema:
    return FieldSchema(
        name=name,
        display_name=display_name if display_name is not None else name,
        entity_type=rest.pop("entity_type", "Shot"),
        data_type=data_type,
        editable=True,
        mandatory=False,
        unique=False,
        **rest,
    )


status = field(
    "sg_status_list",
    "status_list",
    "Status",
    valid_values=["wtg", "ip", "fin", "apr"],
    display_values={"wtg": "Waiting to Start", "ip": "In Progress", "fin": "Final", "apr": "Approved"},
)
turnover = field("sg_turnover_date", "date", "Turnover Date")
cut_in = field("sg_cut_in", "number", "Cut In")
omit = field("sg_omit", "checkbox", "Omitted")
sequence = field("sg_sequence", "entity", "Sequence", valid_types=["Sequence"])


def type_field(data_type: str) -> FieldSchema:
    """A schema carrying nothing but a data type, as upstream's `{ dataType }` does."""
    return field("", data_type)


class TestOperatorLabel:
    def test_reads_comparison_as_time_on_a_date_and_as_size_on_a_number(self) -> None:
        assert operator_label("greater_than", "date") == "after"
        assert operator_label("less_than", "date_time") == "before"
        assert operator_label("greater_than", "number") == "greater than"
        assert operator_label("in") == "is any of"
        assert operator_label("not_in") == "is none of"


class TestPresetsFor:
    def test_offers_every_legal_operator_plus_the_empty_pair_and_no_raw_calendar_operator(self) -> None:
        ids = [p.id for p in presets_for("status_list")]
        assert ids == ["is", "is_not", "in", "not_in", "is_empty", "is_not_empty"]

    def test_replaces_the_calendar_operators_with_named_offsets_on_a_date(self) -> None:
        ids = [p.id for p in presets_for("date")]
        assert "in_calendar_week" not in ids
        assert "this_week" in ids
        assert "today" in ids
        assert "this_month" in ids
        assert "this_year" in ids
        this_week = preset_by_id("date", "this_week")
        assert this_week is not None
        assert (this_week.operator, this_week.value, this_week.input) == ("in_calendar_week", 0, "none")

    def test_names_every_bucket_around_today_on_a_date_and_on_a_date_time(self) -> None:
        expected = [
            ("today", "in_calendar_day", 0),
            ("yesterday", "in_calendar_day", -1),
            ("tomorrow", "in_calendar_day", 1),
            ("this_week", "in_calendar_week", 0),
            ("last_week", "in_calendar_week", -1),
            ("next_week", "in_calendar_week", 1),
            ("this_month", "in_calendar_month", 0),
            ("last_month", "in_calendar_month", -1),
            ("next_month", "in_calendar_month", 1),
            ("this_year", "in_calendar_year", 0),
            ("last_year", "in_calendar_year", -1),
            ("next_year", "in_calendar_year", 1),
        ]
        for data_type in ["date", "date_time"]:
            calendar = next((run for run in operator_menu(data_type) if run.label == "Calendar"), None)
            assert calendar is not None
            assert [(p.id, p.operator, p.value) for p in calendar.presets] == expected
            for id, _operator, _offset in expected:
                found = preset_by_id(data_type, id)
                assert found is not None and found.input == "none"

    def test_keeps_the_forward_buckets_off_a_type_that_has_no_calendar_operator(self) -> None:
        for id in ["next_week", "next_month", "next_year"]:
            assert preset_by_id("number", id) is None
            assert preset_by_id("status_list", id) is None

    def test_reads_a_forward_bucket_back_as_its_name_and_serialises_the_signed_offset(self) -> None:
        assert preset_id_of(condition("sg_turnover_date", "in_calendar_week", 1), "date") == "next_week"
        assert preset_id_of(condition("sg_turnover_date", "in_calendar_month", 1), "date") == "next_month"
        assert preset_id_of(condition("sg_turnover_date", "in_calendar_year", 1), "date") == "next_year"
        preset = preset_by_id("date", "next_week")
        assert preset is not None
        moved = apply_preset(condition("sg_turnover_date", "is", "2026-01-01"), preset, "date")
        assert (moved.operator, moved.value) == ("in_calendar_week", 1)

    def test_reads_a_forward_bucket_as_a_sentence(self) -> None:
        assert (
            describe_condition(condition("sg_turnover_date", "in_calendar_week", 1), turnover)
            == "Turnover Date next week"
        )
        assert (
            describe_condition(condition("sg_turnover_date", "in_calendar_month", 1), turnover)
            == "Turnover Date next month"
        )

    def test_gives_a_checkbox_no_empty_pair_and_an_image_nothing_but_one(self) -> None:
        assert supports_empty("checkbox") is False
        assert [p.id for p in presets_for("checkbox")] == ["is", "is_not"]
        assert [p.id for p in presets_for("image")] == ["is_empty", "is_not_empty"]

    def test_gives_an_unfilterable_type_no_menu_at_all(self) -> None:
        for data_type in ["url", "serializable", "calculated", "summary", "password", "pivot_column"]:
            assert presets_for(data_type) == []
            assert operator_menu(data_type) == []

    def test_leaves_uuid_without_an_empty_entry_because_its_spelling_is_a_blank_row(self) -> None:
        assert empty_value_for("uuid") == ""
        assert [p.id for p in presets_for("uuid")] == ["is", "is_not", "in", "not_in"]


class TestOperatorMenu:
    def test_groups_a_date_menu_in_reading_order(self) -> None:
        assert [g.label for g in operator_menu("date")] == ["Is", "Compare", "Relative", "Calendar", "Empty"]

    def test_groups_a_text_menu_with_its_text_run(self) -> None:
        assert [g.label for g in operator_menu("text")] == ["Is", "Text", "Empty"]

    def test_groups_an_entity_menu_with_its_link_run(self) -> None:
        assert [g.label for g in operator_menu("entity")] == ["Is", "Link", "Empty"]


class TestPresetIdOf:
    def test_reads_a_null_equality_back_as_the_empty_pair(self) -> None:
        assert preset_id_of(condition("sg_sequence", "is", None), "entity") == "is_empty"
        assert preset_id_of(condition("sg_sequence", "is_not", None), "entity") == "is_not_empty"
        assert preset_id_of(condition("code", "is", "x"), "text") == "is"

    def test_reads_a_calendar_offset_back_as_its_name(self) -> None:
        assert preset_id_of(condition("created_at", "in_calendar_week", 0), "date") == "this_week"
        assert preset_id_of(condition("created_at", "in_calendar_day", -1), "date") == "yesterday"
        # An offset with no name of its own still lands on its calendar operator.
        assert preset_id_of(condition("created_at", "in_calendar_year", -9), "date") == "this_year"


class TestApplyPreset:
    def test_keeps_a_value_across_entries_that_edit_the_same_shape(self) -> None:
        before = condition("code", "contains", "sh010")
        after = apply_preset(before, _preset("text", "starts_with"), "text")
        assert (after.operator, after.value) == ("starts_with", "sh010")

    def test_resets_a_value_when_the_shape_changes(self) -> None:
        before = condition("sg_status_list", "is", "fin")
        after = apply_preset(before, _preset("status_list", "in"), "status_list")
        assert (after.operator, after.value) == ("in", [])

    def test_pins_the_value_of_a_preset_that_carries_one_and_does_not_carry_it_back_out(self) -> None:
        empty = apply_preset(condition("code", "is", "x"), _preset("text", "is_empty"), "text")
        assert (empty.operator, empty.value) == ("is", None)
        back = apply_preset(empty, _preset("text", "is"), "text")
        assert back.value == ""


def _preset(data_type: str, id: str) -> OperatorPreset:
    found = preset_by_id(data_type, id)
    assert found is not None
    return found


class TestDefaultValueFor:
    def test_starts_blank_wherever_a_person_supplies_the_value(self) -> None:
        assert default_value_for("text", "is") == ""
        assert default_value_for("status_list", "in") == []
        assert default_value_for("date", "between") == [None, None]
        assert default_value_for("entity", "name_contains") == ""

    def test_starts_filled_where_the_type_has_one_sensible_value(self) -> None:
        assert default_value_for("checkbox", "is") is True
        assert default_value_for("date", "in_last") == [7, "DAY"]
        assert default_value_for("date", "in_calendar_week") == 0

    def test_makes_a_fresh_row_on_a_text_field_serialise_to_nothing(self) -> None:
        assert to_api3_hash(default_condition("code", "text")) is None
        assert to_api3_hash(default_condition("sg_status_list", "status_list")) is None

    def test_makes_a_fresh_row_on_a_checkbox_a_complete_filter(self) -> None:
        wire = to_api3_hash(default_condition("sg_omit", "checkbox"))
        assert wire is not None and wire["conditions"] == [["sg_omit", "is", True]]


class TestDescribeCondition:
    def test_names_the_field_the_wording_and_the_values(self) -> None:
        assert (
            describe_condition(condition("sg_status_list", "in", ["apr", "fin"]), status)
            == "Status is any of Approved, Final"
        )
        assert describe_condition(condition("sg_status_list", "is", "ip"), status) == "Status is In Progress"

    def test_says_what_a_pinned_preset_means(self) -> None:
        assert (
            describe_condition(condition("sg_turnover_date", "in_calendar_week", 0), turnover)
            == "Turnover Date this week"
        )
        assert describe_condition(condition("sg_turnover_date", "is", None), turnover) == "Turnover Date is empty"

    def test_spells_a_relative_window_and_a_range(self) -> None:
        assert (
            describe_condition(condition("sg_turnover_date", "in_last", [1, "WEEK"]), turnover)
            == "Turnover Date in the last 1 week"
        )
        assert (
            describe_condition(condition("sg_turnover_date", "in_next", [3, "DAY"]), turnover)
            == "Turnover Date in the next 3 days"
        )
        assert (
            describe_condition(condition("sg_cut_in", "between", [1001, 1100]), cut_in)
            == "Cut In between 1001 and 1100"
        )

    def test_spells_a_checkbox_and_an_entity(self) -> None:
        assert describe_condition(condition("sg_omit", "is", False), omit) == "Omitted is No"
        assert (
            describe_condition(
                condition("sg_sequence", "is", EntityRef(type="Sequence", id=5, name="sh010")), sequence
            )
            == "Sequence is sh010"
        )
        assert (
            describe_condition(condition("sg_sequence", "is", EntityRef(type="Sequence", id=5)), sequence)
            == "Sequence is Sequence #5"
        )

    def test_falls_back_to_the_path_with_no_schema(self) -> None:
        assert describe_condition(condition("entity.Shot.code", "contains", "010")) == "entity.Shot.code contains 010"


class TestValidateCondition:
    def test_passes_a_filled_row(self) -> None:
        assert validate_condition(condition("sg_status_list", "in", ["fin"]), status) == []

    def test_flags_a_row_with_no_field_and_a_path_that_resolves_to_nothing(self) -> None:
        assert [i.code for i in validate_condition(condition("", "is", "x"))] == ["no-field"]
        assert [i.code for i in validate_condition(condition("nope", "is", "x"), None)] == ["unknown-field"]

    def test_flags_an_unfilterable_type(self) -> None:
        movie = field("sg_uploaded_movie", "url", "Uploaded Movie")
        assert [i.code for i in validate_condition(condition("sg_uploaded_movie", "is", "x"), movie)] == [
            "unfilterable"
        ]

    def test_flags_an_operator_the_type_does_not_take(self) -> None:
        codes = [i.code for i in validate_condition(condition("sg_status_list", "contains", "fi"), status)]
        assert "unknown-operator" in codes

    def test_flags_a_value_of_the_wrong_shape_and_a_blank_one(self) -> None:
        assert [i.code for i in validate_condition(condition("sg_status_list", "in", "fin"), status)] == [
            "wrong-shape"
        ]
        assert [i.code for i in validate_condition(condition("sg_status_list", "in", []), status)] == ["blank-value"]
        assert [
            i.code for i in validate_condition(condition("sg_turnover_date", "in_last", [0, "DAY"]), turnover)
        ] == ["blank-value"]


class TestValueEditors:
    def test_picks_an_editor_from_the_type_and_an_arity_from_the_operator(self) -> None:
        assert value_editor_for("status_list", "in") == "options"
        assert value_editor_for("entity", "is") == "entity"
        assert value_editor_for("entity", "name_contains") == "text"
        assert value_editor_for("date_time", "between") == "date_time"
        assert value_editor_for("percent", "greater_than") == "number"
        assert value_editor_for("checkbox", "is") == "checkbox"
        assert value_editor_for("date", "in_calendar_week") == "none"

        assert value_arity("in") == "many"
        assert value_arity("between") == "two"
        assert value_arity("in_last") == "relative"
        assert value_arity("in_calendar_day") == "none"
        assert value_arity("is") == "one"

    def test_gives_colour_and_web_link_conditions_their_own_editors(self) -> None:
        assert value_editor_for("color", "is") == "color"
        assert value_editor_for("color", "in") == "color"
        assert value_editor_for("url", "is") == "url"
        # A name comparison is a plain string whatever the field holds.
        assert value_editor_for("color", "name_contains") == "text"


class TestListValues:
    def test_reads_a_list_condition_and_leaves_anything_else_empty(self) -> None:
        assert condition_list(["a", "b"]) == ["a", "b"]
        assert condition_list("a") == []
        assert condition_list(None) == []

    def test_replaces_drops_and_adds_one_value_at_a_time(self) -> None:
        assert with_list_value(["a", "b"], 1, "c") == ["a", "c"]
        assert with_list_value(["a", "b"], 5, "c") == ["a", "b"]
        assert without_list_value(["a", "b", "c"], 1) == ["a", "c"]
        assert with_added_list_value(["a"]) == ["a", ""]
        assert with_added_list_value(None) == [""]

    def test_never_edits_the_list_in_place(self) -> None:
        values = ["a", "b"]
        assert with_list_value(values, 0, "z") is not values
        assert values == ["a", "b"]


class TestRelativeWindows:
    def test_reads_the_pair_back_with_a_day_as_the_unit_it_cannot_read(self) -> None:
        assert relative_window([3, "MONTH"]) == RelativeWindow(count=3, unit="MONTH")
        assert relative_window([2, "FORTNIGHT"]) == RelativeWindow(count=2, unit="DAY")
        assert relative_window(None) == RelativeWindow(count=None, unit="DAY")
        assert relative_window(["", "WEEK"]) == RelativeWindow(count=None, unit="WEEK")

    def test_replaces_one_half_and_sends_a_count_of_one_for_an_unfilled_window(self) -> None:
        assert with_relative_window([3, "MONTH"], unit="WEEK") == [3, "WEEK"]
        assert with_relative_window([3, "MONTH"], count=7) == [7, "MONTH"]
        assert with_relative_window(None, unit="YEAR") == [1, "YEAR"]

    def test_offers_the_units_as_a_list_field(self) -> None:
        unit = time_unit_field()
        assert unit.valid_values == ["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
        assert unit.display_values is not None and unit.display_values["WEEK"] == "weeks"
        assert unit.mandatory is True


class TestRelativeDates:
    def test_maps_a_window_onto_its_operator_and_back(self) -> None:
        assert relative_operator("last") == "in_last"
        assert relative_operator("next", negated=True) == "not_in_next"
        assert relative_from("not_in_last", [4, "MONTH"]) == RelativeDate(
            count=4, unit="MONTH", direction="last", negated=True
        )
        assert relative_from("is", "x") is None

    def test_pluralises_a_unit(self) -> None:
        assert time_unit_label("DAY", 1) == "day"
        assert time_unit_label("DAY", 3) == "days"


class TestFieldLists:
    def test_hides_a_pattern_and_everything_under_it(self) -> None:
        assert is_hidden_path("sg_task", ["sg_task"]) is True
        assert is_hidden_path("sg_task.Task.content", ["sg_task"]) is True
        assert is_hidden_path("sg_tasks", ["sg_task"]) is False

    def test_drops_unfilterable_fields_and_sorts_by_display_name(self) -> None:
        fields = {
            "sg_status_list": status,
            "sg_uploaded_movie": field("sg_uploaded_movie", "url", "Uploaded Movie"),
            "sg_cut_in": cut_in,
            "sg_omit": omit,
        }
        assert [f.name for f in filterable_fields(fields)] == ["sg_cut_in", "sg_omit", "sg_status_list"]
        assert [f.name for f in filterable_fields(fields, hide_paths=["sg_omit"])] == [
            "sg_cut_in",
            "sg_status_list",
        ]
        assert [f.name for f in filterable_fields(fields, data_types=["status_list"])] == ["sg_status_list"]


class TestTreeEditing:
    tree = group(
        "and",
        [
            condition("code", "contains", "sh"),
            group("or", [condition("sg_status_list", "is", "fin"), condition("sg_status_list", "is", "apr")]),
        ],
    )

    def test_reads_a_node_by_its_index_path(self) -> None:
        assert node_at(self.tree, []) is self.tree
        found = node_at(self.tree, [1, 0])
        assert found is not None and (found.path, found.value) == ("sg_status_list", "fin")
        assert node_at(self.tree, [9]) is None
        assert node_at(self.tree, [0, 0]) is None

    def test_replaces_removes_and_appends_without_touching_the_original(self) -> None:
        replaced = replace_at(self.tree, [1, 0], condition("sg_status_list", "is", "ip"))
        assert node_at(replaced, [1, 0]).value == "ip"
        assert node_at(self.tree, [1, 0]).value == "fin"

        assert count_conditions(remove_at(self.tree, [1, 1])) == 2
        assert count_conditions(remove_at(self.tree, [1])) == 1

        appended = append_at(self.tree, [1], condition("code", "is", "x"))
        assert count_conditions(appended) == 4
        assert count_conditions(self.tree) == 3
        # Appending to a condition is a no-op, not a crash.
        assert append_at(self.tree, [0], condition("code", "is", "x")) is self.tree

    def test_moves_a_node_among_its_siblings_and_stops_at_the_ends(self) -> None:
        moved = move_at(self.tree, [1, 0], 1)
        assert node_at(moved, [1, 0]).value == "apr"
        assert move_at(self.tree, [0], -1) == self.tree
        assert move_at(self.tree, [1], 1) == self.tree

    def test_counts_every_condition_and_only_the_ones_that_survive_serialisation(self) -> None:
        with_blank = append_at(self.tree, [], condition("", "is", ""))
        assert count_conditions(with_blank) == 4
        assert count_active_conditions(with_blank) == 3


class TestFacets:
    tree = group(
        "and",
        [
            condition("code", "contains", "sh"),
            condition("sg_status_list", "in", ["fin"]),
            group("or", [condition("sg_shot_type", "in", ["Insert"])]),
        ],
    )

    def test_finds_a_condition_by_field_path_wherever_it_sits(self) -> None:
        found = find_condition(self.tree, "sg_status_list")
        assert found is not None and found.at == [1]
        nested = find_condition(self.tree, "sg_shot_type")
        assert nested is not None and nested.at == [2, 0]
        assert find_condition(self.tree, "nope") is None

    def test_strips_every_condition_on_the_named_paths_nested_groups_included(self) -> None:
        stripped = without_paths(self.tree, ["sg_status_list", "sg_shot_type"])
        assert count_conditions(stripped) == 1
        assert node_at(stripped, [0]).path == "code"

    def test_sets_replaces_and_removes_a_facet_condition(self) -> None:
        added = set_facet(self.tree, "sg_omit", ["x"])
        node = node_at(added, [3])
        assert (node.path, node.operator, node.value) == ("sg_omit", "in", ["x"])

        replaced = set_facet(self.tree, "sg_status_list", ["fin", "apr"])
        assert node_at(replaced, [1]).value == ["fin", "apr"]
        assert count_conditions(replaced) == 3

        removed = set_facet(self.tree, "sg_shot_type", [])
        assert count_conditions(removed) == 2
        assert set_facet(self.tree, "sg_omit", []) is self.tree

    def test_writes_the_facet_on_the_operator_it_is_given(self) -> None:
        negated = set_facet(self.tree, "sg_status_list", ["fin"], "not_in")
        node = node_at(negated, [1])
        assert (node.operator, node.value) == ("not_in", ["fin"])

    def test_offers_a_facet_the_list_operators_and_the_empty_tests_and_nothing_that_takes_one_value(self) -> None:
        assert [p.id for p in facet_presets("status_list")] == ["in", "not_in", "is_empty", "is_not_empty"]
        assert facet_presets("checkbox") == []

    def test_moves_a_facet_onto_another_of_its_entries_keeping_the_ticked_values_where_the_shape_holds(
        self,
    ) -> None:
        negated = set_facet_preset(self.tree, "sg_status_list", _preset("status_list", "not_in"), "status_list")
        node = node_at(negated, [1])
        assert (node.operator, node.value) == ("not_in", ["fin"])

        emptied = set_facet_preset(self.tree, "sg_status_list", _preset("status_list", "is_empty"), "status_list")
        node = node_at(emptied, [1])
        assert (node.operator, node.value) == ("is", None)

        fresh = set_facet_preset(self.tree, "sg_omit", _preset("checkbox", "is"), "checkbox")
        node = node_at(fresh, [3])
        assert (node.path, node.operator) == ("sg_omit", "is")


class TestAFacetOnAFieldTheApiEvaluatesNoInOn:
    read_state = normalize_fields({"data": {}}, "Note")["read_by_current_user"]
    empty: FilterGroup = group("and", [])

    def test_narrows_the_data_type_vocabulary_to_what_the_field_declares(self) -> None:
        assert field_operators(self.read_state) == ["is", "is_not"]
        assert field_operators(type_field("list")) == ["is", "is_not", "in", "not_in"]
        assert facet_shape(self.read_state) == FacetShape(any="is", none="is_not", spread=True)
        assert facet_shape(status) == FacetShape(any="in", none="not_in", spread=False)

    def test_serialises_one_ticked_value_to_is_and_several_to_an_or_of_is(self) -> None:
        one = set_facet(self.empty, "read_by_current_user", ["read"], "in", self.read_state)
        assert to_api3_hash(one) == {
            "logical_operator": "and",
            "conditions": [["read_by_current_user", "is", "read"]],
        }

        both = set_facet(self.empty, "read_by_current_user", ["read", "unread"], "in", self.read_state)
        assert to_api3_hash(both) == {
            "logical_operator": "and",
            "conditions": [
                {
                    "logical_operator": "or",
                    "conditions": [
                        ["read_by_current_user", "is", "read"],
                        ["read_by_current_user", "is", "unread"],
                    ],
                }
            ],
        }

    def test_negates_as_is_not_which_is_and_over_several_values(self) -> None:
        negated = set_facet(self.empty, "read_by_current_user", ["read", "unread"], "not_in", self.read_state)
        assert to_api3_hash(negated) == {
            "logical_operator": "and",
            "conditions": [
                {
                    "logical_operator": "and",
                    "conditions": [
                        ["read_by_current_user", "is_not", "read"],
                        ["read_by_current_user", "is_not", "unread"],
                    ],
                }
            ],
        }

    def test_reads_the_spread_conditions_back_as_one_checklist_and_replaces_them_in_place(self) -> None:
        both = set_facet(self.empty, "read_by_current_user", ["read", "unread"], "in", self.read_state)
        found = find_facet(both, "read_by_current_user", self.read_state)
        assert found is not None
        assert found.checklist is True
        assert found.operator == "is"
        assert found.values == ["read", "unread"]
        # The pill reads every facet the same way, so the group stands in as one list condition.
        assert (found.summary.operator, found.summary.value) == ("in", ["read", "unread"])

        one = set_facet(both, "read_by_current_user", ["read"], "is", self.read_state)
        assert count_conditions(one) == 1
        node = node_at(one, [0])
        assert (node.operator, node.value) == ("is", "read")
        assert set_facet(both, "read_by_current_user", [], "in", self.read_state).conditions == []

    def test_strips_the_whole_group_when_the_pill_is_removed(self) -> None:
        tree = group(
            "and",
            [
                condition("project", "is", EntityRef(type="Project", id=1180)),
                group(
                    "or",
                    [
                        condition("read_by_current_user", "is", "read"),
                        condition("read_by_current_user", "is", "unread"),
                    ],
                ),
            ],
        )
        stripped = without_paths(tree, ["read_by_current_user"])
        assert len(stripped.conditions) == 1
        assert node_at(stripped, [0]).path == "project"

    def test_offers_the_editor_menu_only_the_operators_the_field_evaluates_the_empty_tests_included(self) -> None:
        only = field_operators(self.read_state)
        ids = [p.id for run in operator_menu("list", only) for p in run.presets]
        assert ids == ["is", "is_not"]
        assert preset_by_id("list", "in", only) is None
        assert preset_by_id("list", "is_empty", only) is None
        assert default_condition("read_by_current_user", "list", only).operator == "is"
        # A field with no narrowing keeps the type's whole menu, the empty tests included.
        assert [p.id for p in presets_for("list", field_operators(type_field("list")))] == [
            p.id for p in presets_for("list")
        ]
        assert [p.id for p in facet_presets("list", self.read_state)] == ["in", "not_in"]

    def test_finds_a_negated_single_value_at_the_root_at_its_own_path_so_it_unticks_and_clears(self) -> None:
        tree = group("and", [condition("read_by_current_user", "is_not", "read")])
        found = find_facet(tree, "read_by_current_user", self.read_state)
        assert found is not None
        assert (found.at, found.operator, found.values, found.checklist) == ([0], "is_not", ["read"], True)
        assert (found.summary.operator, found.summary.value) == ("not_in", ["read"])
        assert set_facet(tree, "read_by_current_user", [], "is_not", self.read_state).conditions == []
        both = set_facet(tree, "read_by_current_user", ["read", "unread"], "is_not", self.read_state)
        node = node_at(both, [0])
        assert (node.kind, node.logical_operator) == ("group", "and")
        assert find_facet(both, "read_by_current_user", self.read_state).at == [0]
        # A group at the root holding one such condition is never the facet itself.
        alone = group("or", [condition("read_by_current_user", "is", "read")])
        assert find_facet(alone, "read_by_current_user", self.read_state).at == [0]

    def test_spells_a_facet_by_what_the_field_evaluates_per_data_type(self) -> None:
        both = FacetShape(any="in", none="not_in", spread=False)
        assert facet_shape(type_field("list")) == both
        assert facet_shape(type_field("status_list")) == both
        assert facet_shape(type_field("entity")) == both
        assert facet_shape(type_field("multi_entity")) == both
        assert facet_shape(type_field("text")) == both
        assert facet_shape(type_field("checkbox")) == FacetShape(any="is", none="is_not", spread=True)
        assert facet_shape(self.read_state) == FacetShape(any="is", none="is_not", spread=True)

    def test_leaves_an_emptied_root_as_an_empty_group(self) -> None:
        tree = group("and", [condition("read_by_current_user", "is_not", "read")])
        assert without_paths(tree, ["read_by_current_user"]) == FilterGroup(logical_operator="and", conditions=[])

    def test_names_the_ticked_values_as_one_comma_joined_line(self) -> None:
        found = find_facet(
            set_facet(self.empty, "read_by_current_user", ["read", "unread"], "in", self.read_state),
            "read_by_current_user",
            self.read_state,
        )
        assert found is not None
        assert condition_values(found.summary, self.read_state, 2).text == "read, unread"
        narrowed = condition_values(found.summary, self.read_state, 1)
        assert (narrowed.text, narrowed.overflow) == ("read", 1)


class TestConditionParts:
    def test_splits_the_sentence_describe_condition_joins(self) -> None:
        ticked = condition("sg_status_list", "in", ["apr", "fin"])
        assert condition_parts(ticked, status) == ConditionParts(
            field="Status", operator="is any of", value="Approved, Final"
        )
        assert describe_condition(ticked, status) == "Status is any of Approved, Final"

    def test_leaves_the_value_empty_where_the_operator_pins_it(self) -> None:
        assert condition_parts(
            condition("sg_turnover_date", "in_calendar_week", 1), turnover
        ) == ConditionParts(field="Turnover Date", operator="next week", value="")
        assert condition_parts(condition("sg_turnover_date", "is", None), turnover).value == ""

    def test_falls_back_to_the_dotted_path_with_no_schema(self) -> None:
        assert condition_parts(condition("entity.Shot.code", "contains", "010")).field == "entity.Shot.code"


class TestConditionValues:
    def test_names_the_first_values_and_counts_the_rest_with_the_whole_list_in_the_title(self) -> None:
        ticked = condition("sg_status_list", "in", ["apr", "fin", "ip", "rev"])
        assert condition_values(ticked, status, 2) == ConditionValues(
            shown=["Approved", "Final"],
            overflow=2,
            title="Approved, Final, In Progress, rev",
            text="Approved, Final",
            values=["apr", "fin"],
        )
        # `max` of 0 is every value, and a list shorter than `max` never overflows.
        assert condition_values(ticked, status, 0).overflow == 0
        assert condition_values(condition("sg_status_list", "in", ["apr"]), status, 2).overflow == 0

    def test_gives_a_condition_on_any_other_shape_its_one_value_and_no_overflow(self) -> None:
        one = condition_values(condition("code", "contains", "010"))
        assert one.shown == ["010"]
        assert one.overflow == 0
        assert one.values == []
        # An operator that pins its own value has nothing to name.
        assert condition_values(condition("sg_status_list", "is", None), status).shown == []


def row(values: dict[str, Any]) -> EntityRow:
    return EntityRow(type="Shot", id=1, values=values)


class TestFacetValues:
    def test_keeps_the_site_vocabulary_at_zero_and_counts_what_the_rows_hold(self) -> None:
        values = facet_values([row({"sg_status_list": "fin"}), row({"sg_status_list": "fin"})], status)
        assert [(v.key, v.label, v.count) for v in values] == [
            ("fin", "Final", 2),
            ("apr", "Approved", 0),
            ("ip", "In Progress", 0),
            ("wtg", "Waiting to Start", 0),
        ]

    def test_reads_a_link_value_out_of_the_row_and_keys_it_by_type_and_id(self) -> None:
        values = facet_values(
            [
                row({"sg_sequence": {"type": "Sequence", "id": 5, "name": "sh010"}}),
                row({"sg_sequence": None}),
            ],
            sequence,
        )
        assert values == [
            FacetValue(
                key="Sequence:5", label="sh010", value=EntityRef(type="Sequence", id=5, name="sh010"), count=1
            )
        ]

    def test_offers_both_states_of_a_checkbox_even_when_the_rows_show_one(self) -> None:
        assert [(v.key, v.label, v.count) for v in facet_values([row({"sg_omit": False})], omit)] == [
            ("false", "No", 1),
            ("true", "Yes", 0),
        ]


class TestFacetValuesFromGroups:
    author = field("user", "entity", "Author", entity_type="Note", valid_types=["HumanUser"])
    ada = {"type": "HumanUser", "id": 385, "name": "Ada Lovelace", "valid": "valid"}
    other = {"type": "HumanUser", "id": 412, "name": "Ada Lovelace", "valid": "valid"}

    @staticmethod
    def groups_of(*rows: tuple[str, Any, float]) -> list[SummaryGroup]:
        return [
            SummaryGroup(group_name=name, group_value=value, summaries={"id": count})
            for name, value, count in rows
        ]

    def test_lists_the_entities_the_groups_carry_keyed_on_id_with_the_name_and_the_count(self) -> None:
        # Two people sharing a display name are two groups, and the `''` group is the rows with nobody (020_summarize).
        values = facet_values_from_groups(
            self.groups_of(
                ("Ada Lovelace", self.ada, 3), ("Ada Lovelace", self.other, 5), ("", None, 2)
            ),
            self.author,
        )
        assert values == [
            FacetValue(
                key="HumanUser:412",
                label="Ada Lovelace",
                value=EntityRef(type="HumanUser", id=412, name="Ada Lovelace"),
                count=5,
            ),
            FacetValue(
                key="HumanUser:385",
                label="Ada Lovelace",
                value=EntityRef(type="HumanUser", id=385, name="Ada Lovelace"),
                count=3,
            ),
        ]

    def test_counts_a_multi_entity_group_towards_each_link_it_holds(self) -> None:
        to = field("addressings_to", "multi_entity", "To", entity_type="Note", valid_types=["HumanUser"])
        values = facet_values_from_groups(
            self.groups_of(
                ("Ada Lovelace", [self.ada], 3), ("Ada Lovelace, Anna van der Meer", [self.ada, self.other], 2)
            ),
            to,
        )
        assert [(v.key, v.label, v.count) for v in values] == [
            ("HumanUser:385", "Ada Lovelace", 5),
            ("HumanUser:412", "Ada Lovelace", 2),
        ]

    def test_keeps_a_list_vocabulary_at_zero_and_labels_a_code_by_its_display_value(self) -> None:
        values = facet_values_from_groups(self.groups_of(("fin", "fin", 2), ("ip", "ip", 1)), status)
        assert [(v.key, v.label, v.count) for v in values] == [
            ("fin", "Final", 2),
            ("ip", "In Progress", 1),
            ("apr", "Approved", 0),
            ("wtg", "Waiting to Start", 0),
        ]

    def test_answers_an_empty_result_as_the_vocabulary_alone(self) -> None:
        assert [v.count for v in facet_values_from_groups([], status)] == [0, 0, 0, 0]
        assert facet_values_from_groups([], self.author) == []


class TestFacetScopes:
    facets = ["sg_status_list", "sg_shot_type"]
    base = group("and", [condition("project", "is", EntityRef(type="Project", id=70))])

    def test_counts_every_facet_against_the_whole_tree_when_none_is_ticked(self) -> None:
        scopes = facet_scopes(group("and", []), None, self.facets)
        assert scopes == {"sg_status_list": None, "sg_shot_type": None}
        scoped = facet_scopes(group("and", []), self.base, self.facets)
        assert scoped["sg_status_list"] == to_api3_hash(self.base)
        assert scoped["sg_shot_type"] == scoped["sg_status_list"]

    def test_drops_a_ticked_facet_from_its_own_scope_and_keeps_it_in_the_others(self) -> None:
        tree = group("and", [condition("sg_status_list", "in", ["ip", "fin"])])
        scopes = facet_scopes(tree, None, self.facets)
        assert scopes["sg_status_list"] is None
        assert scopes["sg_shot_type"] == to_api3_hash(tree)

    def test_gives_two_ticked_facets_each_other_and_nothing_of_themselves(self) -> None:
        statuses = condition("sg_status_list", "in", ["ip"])
        kinds = condition("sg_shot_type", "in", ["VFX"])
        scopes = facet_scopes(group("and", [statuses, kinds]), self.base, self.facets)
        assert scopes["sg_status_list"] == to_api3_hash(group("and", [self.base, group("and", [kinds])]))
        assert scopes["sg_shot_type"] == to_api3_hash(group("and", [self.base, group("and", [statuses])]))

    def test_drops_an_editor_condition_on_the_facet_field_from_that_facet_alone(self) -> None:
        written = condition("sg_status_list", "is_not", "omt")
        scopes = facet_scopes(group("and", [written]), None, self.facets)
        assert scopes["sg_status_list"] is None
        assert scopes["sg_shot_type"] == to_api3_hash(group("and", [written]))


class TestFacetLists:
    author = field("user", "entity", "Author", entity_type="Note", valid_types=["HumanUser"])
    read_state = field(
        "read_by_current_user",
        "list",
        "Read by Current User",
        entity_type="Note",
        valid_values=["unread", "read"],
        operators=["is", "is_not"],
    )
    ada = {"type": "HumanUser", "id": 385, "name": "Ada Lovelace"}

    @classmethod
    def note(cls, values: dict[str, Any]) -> EntityRow:
        return EntityRow(type="Note", id=1, values={**values, "user": cls.ada})

    @staticmethod
    def refusal() -> SgApiError:
        return SgApiError(400, None, "Grouping is not allowed for field Note.read_by_current_user.")

    def test_lists_an_entity_facet_from_the_groups_and_a_refused_field_from_a_page_of_rows(self) -> None:
        asked: list[tuple[str, Any]] = []
        sampled: list[tuple[list[str], Any]] = []

        def counts(name: str, filters: Any) -> list[SummaryGroup]:
            asked.append((name, filters))
            if name == "read_by_current_user":
                raise self.refusal()
            return [SummaryGroup(group_name="Ada Lovelace", group_value=self.ada, summaries={"id": 4})]

        def sample(names: list[str], filters: Any) -> list[EntityRow]:
            sampled.append((names, filters))
            return [
                self.note({"read_by_current_user": "read"}),
                self.note({"read_by_current_user": "unread"}),
                self.note({"read_by_current_user": "unread"}),
            ]

        lists = facet_lists(
            [self.author, self.read_state],
            {"user": None, "read_by_current_user": None},
            FacetReads(sample=sample, counts=counts),
        )
        assert [name for name, _filters in asked] == ["user", "read_by_current_user"]
        assert sampled == [(["read_by_current_user"], None)]
        assert lists["user"] == FacetList(
            values=[
                FacetValue(
                    key="HumanUser:385",
                    label="Ada Lovelace",
                    value=EntityRef(type="HumanUser", id=385, name="Ada Lovelace"),
                    count=4,
                )
            ]
        )
        assert lists["read_by_current_user"] == FacetList(
            values=[
                FacetValue(key="unread", label="unread", value="unread", count=2),
                FacetValue(key="read", label="read", value="read", count=1),
            ],
            sampled=3,
        )

    def test_asks_the_site_once_about_a_field_it_refused(self) -> None:
        asked: list[str] = []
        refused: set[str] = set()

        def counts(name: str, filters: Any) -> list[SummaryGroup]:
            asked.append(name)
            raise self.refusal()

        def sample(names: list[str], filters: Any) -> list[EntityRow]:
            return [self.note({"read_by_current_user": "read"})]

        reads = FacetReads(sample=sample, counts=counts, refused=refused)
        first = facet_lists([self.read_state], {"read_by_current_user": None}, reads)
        second = facet_lists([self.read_state], {"read_by_current_user": None}, reads)
        assert asked == ["read_by_current_user"]
        assert refused == {"Note.read_by_current_user"}
        assert second == first
        assert second["read_by_current_user"].sampled == 1

    def test_fails_the_read_on_anything_but_a_refusal(self) -> None:
        def sample(names: list[str], filters: Any) -> list[EntityRow]:
            return []

        def server_error(name: str, filters: Any) -> list[SummaryGroup]:
            raise SgApiError(500, None, "Shotgun Server Error")

        def broken(name: str, filters: Any) -> list[SummaryGroup]:
            raise TypeError("Failed to fetch")

        with pytest.raises(SgApiError, match="Shotgun Server Error"):
            facet_lists([self.author], {"user": None}, FacetReads(sample=sample, counts=server_error))
        with pytest.raises(TypeError, match="Failed to fetch"):
            facet_lists([self.author], {"user": None}, FacetReads(sample=sample, counts=broken))
        assert is_grouping_refusal(self.refusal()) is True
        assert is_grouping_refusal(SgApiError(500, None)) is False

    def test_reads_a_refusal_with_no_status_off_its_wording(self) -> None:
        """`shotgun_api3` raises a Fault with no HTTP status behind it (probe 020)."""
        # The site's own words, as the adapter hands them on.
        faulted = SgApiError(
            None,
            None,
            "API summarize() grouping is not allowed for Note.read_by_current_user",
        )
        assert is_grouping_refusal(faulted) is True
        assert is_grouping_refusal(SgApiError(None, None, "Shotgun Server Error")) is False

        def sample(names: list[str], filters: Any) -> list[EntityRow]:
            return []

        def faults(name: str, filters: Any) -> list[SummaryGroup]:
            raise faulted

        refused: set[str] = set()
        lists = facet_lists(
            [self.author],
            {"user": None},
            FacetReads(sample=sample, counts=faults, refused=refused),
        )
        # The facet falls back to a tally of one page and says how many rows it read.
        assert lists["user"].sampled == 0
        assert refused == {f"{self.author.entity_type}.{self.author.name}"}

    def test_tallies_every_facet_from_rows_without_counts_one_page_per_scope(self) -> None:
        sampled: list[tuple[list[str], Any]] = []
        kinds = to_api3_hash(group("and", [condition("sg_shot_type", "in", ["VFX"])]))

        def sample(names: list[str], filters: Any) -> list[EntityRow]:
            sampled.append((names, filters))
            return []

        lists = facet_lists(
            [status, sequence],
            {"sg_status_list": kinds, "sg_sequence": kinds},
            FacetReads(sample=sample),
        )
        assert sampled == [(["sg_status_list", "sg_sequence"], kinds)]
        assert lists["sg_status_list"].sampled == 0
        assert [v.count for v in lists["sg_status_list"].values] == [0, 0, 0, 0]
        assert lists["sg_sequence"] == FacetList(values=[], sampled=0)

        sampled.clear()
        facet_lists(
            [status, sequence],
            {"sg_status_list": None, "sg_sequence": kinds},
            FacetReads(sample=sample),
        )
        assert sampled == [(["sg_status_list"], None), (["sg_sequence"], kinds)]

    def test_reads_counts_as_one_grouped_summarize_call(self) -> None:
        calls: list[Any] = []

        class Client:
            def summarize(self, entity_type: str, options: SummarizeOptions) -> Any:
                calls.append((entity_type, options))
                from sg_widgets_core.client import SummarizeResult

                return SummarizeResult(
                    summaries={"id": 1},
                    groups=[SummaryGroup(group_name="ip", group_value="ip", summaries={"id": 1})],
                )

        groups = facet_counts(Client(), "Note")("sg_status_list", None)
        assert calls == [
            ("Note", SummarizeOptions(filters=None, grouping=[SummaryGrouping(field="sg_status_list")]))
        ]
        assert len(groups) == 1


class TestSortableFields:
    def test_keeps_out_the_types_a_sort_cannot_name(self) -> None:
        for data_type in ["summary", "url", "password", "serializable", "uuid", "pivot_column"]:
            assert is_sortable(data_type) is False
        # `calculated` sorts even though it cannot be filtered.
        assert is_sortable("calculated") is True
        assert is_sortable("text") is True

    def test_sorts_what_it_offers_by_display_name(self) -> None:
        fields = {
            "code": field("code", "text", "Shot Code"),
            "uuid": field("uuid", "uuid", "UUID"),
            "sg_cut_in": cut_in,
        }
        assert [f.name for f in sortable_fields(fields)] == ["sg_cut_in", "code"]


class TestSortStrings:
    def test_joins_keys_with_a_minus_for_descending(self) -> None:
        assert (
            to_sort_string([SortKey(field="sg_status_list", direction="asc"), SortKey(field="id", direction="desc")])
            == "sg_status_list,-id"
        )
        assert to_sort_string([]) == ""
        assert to_sort_string([SortKey(field="", direction="asc")]) == ""

    def test_reads_one_back_dotted_paths_included(self) -> None:
        assert from_sort_string("-created_at,entity.Shot.code") == [
            SortKey(field="created_at", direction="desc"),
            SortKey(field="entity.Shot.code", direction="asc"),
        ]
        assert from_sort_string("") == []
        assert from_sort_string(None) == []


class TestConditionArity:
    def test_draws_no_editor_for_a_pinned_preset(self) -> None:
        assert condition_arity(condition("image", "is", None), "image") == "none"
        assert condition_arity(condition("created_at", "in_calendar_week", 0), "date_time") == "none"
        assert condition_arity(condition("code", "is", "x"), "text") == "one"
