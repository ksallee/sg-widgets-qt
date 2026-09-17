"""Port of `packages/core/test/filter.test.ts`."""
from __future__ import annotations

from sg_widgets_core.filter import (
    EntityRef,
    condition,
    empty_filter,
    from_wire,
    group,
    is_empty_filter,
    referenced_paths,
    to_api3_hash,
)


class TestToApi3Hash:
    def test_serialises_a_nested_and_or_tree_in_the_shape_search_accepts(self) -> None:
        tree = group("and", [
            condition("project", "is", EntityRef(type="Project", id=70, name="Demo")),
            group("or", [condition("sg_status_list", "is", "fin"), condition("sg_status_list", "is", "rev")]),
        ])
        assert to_api3_hash(tree) == {
            "logical_operator": "and",
            "conditions": [
                ["project", "is", {"type": "Project", "id": 70}],
                {
                    "logical_operator": "or",
                    "conditions": [["sg_status_list", "is", "fin"], ["sg_status_list", "is", "rev"]],
                },
            ],
        }

    def test_drops_blank_conditions_and_empty_groups_and_returns_none_when_nothing_remains(self) -> None:
        assert to_api3_hash(empty_filter()) is None
        tree = group("and", [condition("", "is", "x"), group("or", [condition("code", "in", [])])])
        assert to_api3_hash(tree) is None
        assert is_empty_filter(tree) is True

    def test_keeps_is_null_as_a_real_condition(self) -> None:
        assert to_api3_hash(condition("entity", "is", None)) == {
            "logical_operator": "and",
            "conditions": [["entity", "is", None]],
        }

    def test_keeps_relative_and_range_values_verbatim(self) -> None:
        tree = group("and", [
            condition("created_at", "in_last", [3, "DAY"]),
            condition("sg_turnover_date", "between", ["2026-09-01", "2026-09-03"]),
            condition("created_at", "in_calendar_week", 0),
        ])
        result = to_api3_hash(tree)
        assert result is not None
        assert result["conditions"] == [
            ["created_at", "in_last", [3, "DAY"]],
            ["sg_turnover_date", "between", ["2026-09-01", "2026-09-03"]],
            ["created_at", "in_calendar_week", 0],
        ]

    def test_treats_a_non_positive_relative_count_as_blank(self) -> None:
        assert to_api3_hash(condition("created_at", "in_last", [0, "DAY"])) is None


class TestFromWire:
    def test_round_trips_a_hash_group_and_accepts_a_flat_api3_array_list(self) -> None:
        wire = {"logical_operator": "or", "conditions": [["id", "is", 862], ["id", "is", 863]]}
        tree = from_wire(wire)
        assert to_api3_hash(tree) == wire
        assert from_wire([["id", "is", 1]]).logical_operator == "and"


class TestReferencedPaths:
    def test_collects_unique_paths_depth_first(self) -> None:
        tree = group("and", [
            condition("code", "is", "a"),
            group("or", [condition("entity.Shot.code", "is", "b"), condition("code", "is", "c")]),
        ])
        assert referenced_paths(tree) == ["code", "entity.Shot.code"]
