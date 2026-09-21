"""Port of `packages/core/test/collection-state.test.ts`."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import SortSpec
from sg_widgets_core.collection_state import (
    CollapseState,
    SelectionState,
    _stable,
    as_collapse_state,
    collapse_all,
    collapse_state_from,
    collapsed_keys,
    expand_all,
    first_enabled_index,
    ids_for_refs,
    is_collapsed,
    next_enabled_index,
    refs_for_ids,
    row_id_of,
    row_is_disabled,
    same_collapse,
    same_filters,
    same_ids,
    same_refs,
    same_sort,
    selectable_refs,
    selection_state,
    to_sort_keys,
    to_sort_specs,
    toggle_collapsed,
    toggle_id,
    toggle_ref,
)
from sg_widgets_core.filter import EntityRef, condition, group
from sg_widgets_core.filter_ux import SortKey


def row(id: int, **over: Any) -> EntityRow:
    return EntityRow(type="Version", id=id, values={"code": f"v{id}", **over})


rows = [row(1), row(2, locked=True), row(3)]


class TestRowIds:
    def test_keys_a_row_type_id_or_by_the_caller(self) -> None:
        assert row_id_of(row(7)) == "Version:7"
        assert row_id_of(row(7), lambda r: str(r.values["code"])) == "v7"

    def test_answers_the_refs_an_id_list_stands_for_in_row_order(self) -> None:
        assert refs_for_ids(rows, ["Version:3", "Version:1"]) == [
            EntityRef(type="Version", id=1),
            EntityRef(type="Version", id=3),
        ]

    def test_answers_the_ids_a_ref_list_is_keyed_under_and_drops_a_ref_no_row_stands_for(self) -> None:
        def by_code(r: EntityRow) -> str:
            return str(r.values["code"])

        assert ids_for_refs(
            rows,
            [EntityRef(type="Version", id=2), EntityRef(type="Shot", id=2), EntityRef(type="Version", id=2)],
            by_code,
        ) == ["v2"]


class TestDisabledRows:
    def test_is_false_without_a_predicate(self) -> None:
        assert row_is_disabled(row(1)) is False
        assert row_is_disabled(row(2, locked=True), lambda r: r.values.get("locked") is True) is True

    def test_steps_over_a_disabled_row_and_stops_at_the_ends(self) -> None:
        def disabled(index: int) -> bool:
            return index in (1, 2)

        assert next_enabled_index(4, 0, 1, disabled) == 3
        assert next_enabled_index(4, 3, -1, disabled) == 0
        # Nothing enabled that way leaves the cursor where it stands.
        assert next_enabled_index(4, 3, 1, disabled) == 3
        assert next_enabled_index(0, 0, 1, disabled) == -1

    def test_finds_the_first_enabled_row_from_an_end(self) -> None:
        def disabled(index: int) -> bool:
            return index < 2

        assert first_enabled_index(4, 0, 1, disabled) == 2
        assert first_enabled_index(4, 3, -1, disabled) == 3
        assert first_enabled_index(2, 0, 1, disabled) == -1


class TestSelectionLists:
    def test_adds_removes_and_forces_a_direction(self) -> None:
        assert toggle_id(["a"], "b") == ["a", "b"]
        assert toggle_id(["a", "b"], "a") == ["b"]
        assert toggle_id(["a"], "a", True) == ["a"]
        assert toggle_id(["a"], "b", False) == ["a"]

    def test_compares_id_and_ref_lists_whatever_their_order(self) -> None:
        assert same_ids(["a", "b"], ["b", "a"]) is True
        assert same_ids(["a"], ["a", "b"]) is False
        assert same_refs([EntityRef(type="Version", id=1)], [EntityRef(type="Version", id=1)]) is True
        assert same_refs([EntityRef(type="Version", id=1)], [EntityRef(type="Shot", id=1)]) is False


class TestMirroringASource:
    def test_compares_sort_keys_in_order(self) -> None:
        assert same_sort([SortSpec(path="code", descending=False)], [SortSpec(path="code", descending=False)]) is True
        assert same_sort([SortSpec(path="code", descending=False)], [SortSpec(path="code", descending=True)]) is False
        assert same_sort(
            [SortSpec(path="code", descending=False), SortSpec(path="id", descending=False)],
            [SortSpec(path="id", descending=False), SortSpec(path="code", descending=False)],
        ) is False

    def test_reads_the_editor_tree_and_the_wire_hash_as_one_filter(self) -> None:
        tree = group("and", [condition("code", "is", "v1")])
        wire = {"logical_operator": "and", "conditions": [["code", "is", "v1"]]}
        assert same_filters(tree, wire) is True
        assert same_filters(None, None) is True
        assert same_filters(tree, None) is False

    def test_keys_a_dict_and_a_dataclass_through_the_query_caches_key(self) -> None:
        # One key function: sorted keys, no spaces, a dataclass spelled as its fields.
        wire = {"logical_operator": "and", "conditions": [["code", "is", "v1"]]}
        assert _stable(wire) == '{"conditions":[["code","is","v1"]],"logical_operator":"and"}'
        assert _stable(SortSpec(path="code", descending=False)) == '{"descending":false,"path":"code"}'

    def test_turns_a_sort_pickers_keys_into_the_sources_sort_and_back(self) -> None:
        keys = [SortKey(field="code", direction="asc"), SortKey(field="created_at", direction="desc")]
        specs = to_sort_specs(keys)
        assert specs == [
            SortSpec(path="code", descending=False),
            SortSpec(path="created_at", descending=True),
        ]
        assert to_sort_keys(specs) == keys
        assert to_sort_specs([SortKey(field="", direction="asc")]) == []


class TestASelectionOverLoadedRows:
    @staticmethod
    def locked(candidate: EntityRow) -> bool:
        return candidate.values.get("locked") is True

    def test_adds_a_row_it_does_not_hold_and_drops_one_it_does(self) -> None:
        one = toggle_ref([], EntityRef(type="Version", id=1))
        assert one == [EntityRef(type="Version", id=1)]
        assert toggle_ref(one, EntityRef(type="Version", id=1)) == []
        assert toggle_ref(one, EntityRef(type="Version", id=2)) == [
            EntityRef(type="Version", id=1),
            EntityRef(type="Version", id=2),
        ]

    def test_reads_a_header_checkbox_as_all_some_or_neither(self) -> None:
        assert selection_state(rows, []) == SelectionState(all=False, some=False)
        assert selection_state(rows, [EntityRef(type="Version", id=1)]) == SelectionState(all=False, some=True)
        assert selection_state(
            rows, [EntityRef(type=r.type, id=r.id) for r in rows]
        ) == SelectionState(all=True, some=True)
        assert selection_state([], []) == SelectionState(all=False, some=False)

    def test_leaves_a_disabled_row_out_of_both_readings(self) -> None:
        open_ = [EntityRef(type="Version", id=1), EntityRef(type="Version", id=3)]
        assert selection_state(rows, open_, self.locked) == SelectionState(all=True, some=True)
        assert selectable_refs(rows, self.locked) == open_
        assert selection_state([rows[1]], [], self.locked) == SelectionState(all=False, some=False)


class TestCollapseState:
    def test_holds_a_mode_so_a_group_that_arrives_later_follows_it(self) -> None:
        shut = collapse_all()
        assert is_collapsed(shut, 'group:0:"apr"') is True
        # The key the next page brings was never named, and is shut all the same.
        assert is_collapsed(shut, 'group:9:"new"') is True
        assert is_collapsed(expand_all(), 'group:9:"new"') is False

    def test_toggles_one_group_against_the_mode_and_back_out_of_the_exceptions(self) -> None:
        opened = toggle_collapsed(collapse_all(), "a")
        assert opened == CollapseState(all=True, except_=["a"])
        assert is_collapsed(opened, "a") is False
        assert is_collapsed(opened, "b") is True
        # Shutting it again leaves no exception behind.
        assert toggle_collapsed(opened, "a") == CollapseState(all=True, except_=[])
        # `on` is whether the group ends up shut, and asking for what already holds changes nothing.
        assert toggle_collapsed(opened, "a", True) == CollapseState(all=True, except_=[])
        assert toggle_collapsed(opened, "a", False) == CollapseState(all=True, except_=["a"])
        assert toggle_collapsed(opened, "b", True) == CollapseState(all=True, except_=["a"])

    def test_toggles_one_group_under_expand_all_and_back(self) -> None:
        shut = toggle_collapsed(expand_all(), "a")
        assert shut == CollapseState(all=False, except_=["a"])
        assert is_collapsed(shut, "a") is True
        assert is_collapsed(shut, "b") is False
        assert toggle_collapsed(shut, "a") == CollapseState(all=False, except_=[])

    def test_reads_a_bare_key_list_as_the_open_mode_with_those_keys_shut(self) -> None:
        assert as_collapse_state(["a", "b"]) == CollapseState(all=False, except_=["a", "b"])
        assert as_collapse_state(None) == CollapseState(all=False, except_=[])
        assert is_collapsed(as_collapse_state(["a"]), "a") is True
        assert is_collapsed(as_collapse_state(["a"]), "b") is False

    def test_reads_a_mode_written_without_exceptions(self) -> None:
        assert as_collapse_state(CollapseState(all=True)) == CollapseState(all=True, except_=[])
        assert as_collapse_state(CollapseState(all=False)) == CollapseState(all=False, except_=[])
        # The copy is the caller's own list no longer.
        except_ = ["a"]
        state = as_collapse_state(CollapseState(all=True, except_=except_))
        except_.append("b")
        assert state.except_ == ["a"]

    def test_answers_which_of_the_drawn_keys_are_shut(self) -> None:
        assert collapsed_keys(collapse_all(), ["a", "b"]) == ["a", "b"]
        assert collapsed_keys(toggle_collapsed(collapse_all(), "a"), ["a", "b"]) == ["b"]
        assert collapsed_keys(as_collapse_state(["b"]), ["a", "b", "c"]) == ["b"]

    def test_reads_a_set_of_shut_headers_back_under_the_mode_in_force(self) -> None:
        keys = ["a", "b", "c"]
        # Under collapse-all, an open header is the exception and the mode survives.
        assert collapse_state_from(collapse_all(), ["a", "c"], keys) == CollapseState(all=True, except_=["b"])
        # Under expand-all it is the other way.
        assert collapse_state_from(expand_all(), ["a", "c"], keys) == CollapseState(
            all=False, except_=["a", "c"]
        )
        # An exception for a key no longer drawn is dropped.
        assert collapse_state_from(CollapseState(all=True, except_=["gone"]), keys, keys) == CollapseState(
            all=True, except_=[]
        )

    def test_keeps_the_mode_and_no_exception_when_nothing_is_drawn(self) -> None:
        assert collapse_state_from(collapse_all(), [], []) == CollapseState(all=True, except_=[])
        assert collapse_state_from(CollapseState(all=False, except_=["a"]), [], []) == CollapseState(
            all=False, except_=[]
        )

    def test_compares_two_states_by_what_they_shut(self) -> None:
        assert same_collapse(collapse_all(), CollapseState(all=True, except_=[])) is True
        assert same_collapse(
            CollapseState(all=True, except_=["a", "b"]), CollapseState(all=True, except_=["b", "a"])
        ) is True
        assert same_collapse(collapse_all(), expand_all()) is False
