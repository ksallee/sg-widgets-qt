"""Port of `packages/core/test/picker.test.ts`."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.client import EntityRow
from sg_widgets_core.filter import EntityRef, FilterCondition, FilterGroup, condition, group, to_api3_hash
from sg_widgets_core.mock import MOCK_NOW, MockClient, MockFailure
from sg_widgets_core.picker import (
    PROJECT_PICKER_FIELDS,
    USER_PICKER_FIELDS,
    ChipFit,
    ChipRow,
    EntitySearch,
    EntitySearchOptions,
    PickerRow,
    SearchField,
    as_filter_group,
    clearable_for_field,
    create_entity_search,
    entity_key,
    fit_chips,
    flatten_row,
    highlight_runs,
    is_bare_ref,
    merge_filters,
    name_search_filter,
    placeholder_name,
    project_picker_filters,
    prune_filter_to_fields,
    query_tokens,
    summarise_selection,
    user_picker_filters,
    user_picker_search_fields,
    user_picker_sub_label,
    user_picker_types,
    user_search_fields,
    with_selected_pinned,
)
from sg_widgets_core.query import create_query_cache
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.search import match_runs, search_words


def a_field(mandatory: bool) -> FieldSchema:
    return FieldSchema(
        name="entity",
        display_name="Link",
        entity_type="Version",
        data_type="entity",
        editable=True,
        mandatory=mandatory,
        unique=False,
    )


class TestQueryTokens:
    def test_is_the_one_tokenizer_under_its_picker_name(self) -> None:
        assert query_tokens is search_words
        assert query_tokens("  pub   an \n x ") == ["pub", "an", "x"]
        assert query_tokens("   ") == []


class TestNameSearchFilter:
    def test_requires_every_word_on_one_field(self) -> None:
        assert name_search_filter("pub an", ["name"]) == FilterGroup(
            logical_operator="and",
            conditions=[
                FilterCondition(path="name", operator="contains", value="pub"),
                FilterCondition(path="name", operator="contains", value="an"),
            ],
        )

    def test_ors_the_per_field_groups_so_a_word_may_sit_in_any_of_them(self) -> None:
        filter = name_search_filter("ada", ["name", "login"])
        assert filter.logical_operator == "or"
        assert len(filter.conditions) == 2
        assert to_api3_hash(filter) == {
            "logical_operator": "or",
            "conditions": [
                {"logical_operator": "and", "conditions": [["name", "contains", "ada"]]},
                {"logical_operator": "and", "conditions": [["login", "contains", "ada"]]},
            ],
        }

    def test_is_an_empty_group_for_an_empty_query_or_no_fields_which_matches_every_row(self) -> None:
        assert name_search_filter("   ", ["name"]).conditions == []
        assert name_search_filter("ada", []).conditions == []
        assert to_api3_hash(name_search_filter("   ", ["name"])) is None

    def test_takes_the_operator_a_field_is_matched_with(self) -> None:
        filter = name_search_filter("le", [SearchField(path="email", operator="starts_with"), "login"])
        assert to_api3_hash(filter) == {
            "logical_operator": "or",
            "conditions": [
                {"logical_operator": "and", "conditions": [["email", "starts_with", "le"]]},
                {"logical_operator": "and", "conditions": [["login", "contains", "le"]]},
            ],
        }

    def test_keeps_every_word_against_every_field_not_one_word_per_field(self) -> None:
        filter = name_search_filter("ada love", ["name", "login"])
        assert to_api3_hash(filter) == {
            "logical_operator": "or",
            "conditions": [
                {
                    "logical_operator": "and",
                    "conditions": [["name", "contains", "ada"], ["name", "contains", "love"]],
                },
                {
                    "logical_operator": "and",
                    "conditions": [["login", "contains", "ada"], ["login", "contains", "love"]],
                },
            ],
        }


class TestUserSearchFields:
    def test_matches_the_email_on_its_local_part_until_the_query_holds_an_at(self) -> None:
        assert user_search_fields("le") == [SearchField(path="email", operator="starts_with"), "login"]
        assert user_search_fields("le@example.studio") == [
            SearchField(path="email", operator="contains"),
            "login",
        ]

    def test_drops_the_login_once_the_query_holds_whitespace_because_a_login_never_does(self) -> None:
        assert user_search_fields("anna van") == [SearchField(path="email", operator="starts_with")]

    def test_is_empty_for_an_empty_query(self) -> None:
        assert user_search_fields("   ") == []


class TestThePersonConfigurationBothUserPickersTake:
    def test_offers_script_accounts_after_people_and_people_alone_when_they_are_not_wanted(self) -> None:
        assert user_picker_types(True) == ["HumanUser", "ApiUser"]
        assert user_picker_types(False) == ["HumanUser"]

    def test_sends_the_active_condition_unless_inactive_people_are_asked_for(self) -> None:
        assert to_api3_hash(user_picker_filters(False, None)) == {
            "logical_operator": "and",
            "conditions": [["sg_status_list", "is", "act"]],
        }
        assert len(user_picker_filters(True, None).conditions) == 0

    def test_keeps_the_callers_own_filter_beside_it(self) -> None:
        merged = user_picker_filters(False, group("and", [condition("id", "is", 7)]))
        assert to_api3_hash(merged) == {
            "logical_operator": "and",
            "conditions": [
                {"logical_operator": "and", "conditions": [["id", "is", 7]]},
                ["sg_status_list", "is", "act"],
            ],
        }

    def test_names_a_script_account_and_a_person_by_their_address(self) -> None:
        script = PickerRow(type="ApiUser", id=3, name="sync", values={})
        person = PickerRow(
            type="HumanUser", id=20, name="Ada Lovelace", values={"email": "ada@example.studio"},
        )
        nameless = PickerRow(type="HumanUser", id=21, name="Bruno Kessel", values={})
        assert user_picker_sub_label(script) == "API user"
        assert user_picker_sub_label(person) == "ada@example.studio"
        assert user_picker_sub_label(nameless) == ""

    def test_puts_the_callers_search_fields_after_the_ones_a_person_is_searched_by(self) -> None:
        assert user_picker_search_fields(["sg_department"])("ada") == [
            SearchField(path="email", operator="starts_with"),
            "login",
            "sg_department",
        ]
        assert user_picker_search_fields(lambda query: ["sg_department"] if len(query) > 2 else [])("ad") == [
            SearchField(path="email", operator="starts_with"),
            "login",
        ]


class TestTheProjectConfigurationBothProjectPickersTake:
    def test_hides_archived_projects_unless_they_are_asked_for(self) -> None:
        assert to_api3_hash(project_picker_filters(False, None)) == {
            "logical_operator": "and",
            "conditions": [["archived", "is", False]],
        }
        assert len(project_picker_filters(True, None).conditions) == 0

    def test_reads_the_status_field_project_alone_uses(self) -> None:
        assert "sg_status" in PROJECT_PICKER_FIELDS
        assert "sg_status_list" in USER_PICKER_FIELDS


class TestMergeFiltersAndAsFilterGroup:
    def test_drops_the_parts_that_would_serialise_to_nothing(self) -> None:
        merged = merge_filters(name_search_filter("", ["name"]), name_search_filter("ada", ["name"]), None)
        assert len(merged.conditions) == 1

    def test_takes_the_wire_shape_as_well_as_the_tree(self) -> None:
        wire = {"logical_operator": "and", "conditions": [["id", "is", 7]]}
        assert as_filter_group(wire) == FilterGroup(
            logical_operator="and",
            conditions=[FilterCondition(path="id", operator="is", value=7)],
        )
        assert as_filter_group(None) is None


class TestPruneFilterToFields:
    def test_drops_a_condition_on_a_field_the_type_does_not_have(self) -> None:
        filter = group("and", [
            condition("sg_status_list", "is", "act"),
            condition("login", "contains", "a"),
        ])
        pruned = prune_filter_to_fields(filter, {"login"})
        assert pruned == group("and", [condition("login", "contains", "a")])

    def test_checks_only_the_root_of_a_dotted_path(self) -> None:
        filter = group("and", [condition("project.Project.name", "is", "x")])
        assert prune_filter_to_fields(filter, {"project"}) is not None
        assert prune_filter_to_fields(filter, {"projects"}) is None

    def test_drops_a_group_left_with_nothing_in_it(self) -> None:
        filter = group("and", [group("or", [condition("archived", "is", False)])])
        assert prune_filter_to_fields(filter, {"code"}) is None


class TestHighlightRuns:
    def test_is_the_one_splitting_under_the_name_the_pickers_use(self) -> None:
        assert highlight_runs is match_runs
        for label, query in [
            ("Published Anna", "pub an"),
            ("abcdef", "abc bcd"),
            ("", "x"),
            ("Ada Lovelace", ""),
        ]:
            assert highlight_runs(label, query) == match_runs(label, query)
            # The runs rebuild the label exactly, whatever the query was.
            assert "".join(run.text for run in highlight_runs(label, query)) == label

    def test_marks_every_occurrence_of_every_word(self) -> None:
        assert [(run.text, run.match) for run in highlight_runs("Published Anna", "pub an")] == [
            ("Pub", True),
            ("lished ", False),
            ("An", True),
            ("na", False),
        ]

    def test_merges_overlapping_words_into_one_run(self) -> None:
        assert [(run.text, run.match) for run in highlight_runs("abcdef", "abc bcd")] == [
            ("abcd", True),
            ("ef", False),
        ]

    def test_matches_case_insensitively_and_repeats(self) -> None:
        assert [(run.text, run.match) for run in highlight_runs("shot sh010", "SH")] == [
            ("sh", True),
            ("ot ", False),
            ("sh", True),
            ("010", False),
        ]

    def test_is_one_unmatched_run_with_no_query_and_empty_for_an_empty_label(self) -> None:
        assert [(r.text, r.match) for r in highlight_runs("sh010_0010", "  ")] == [("sh010_0010", False)]
        assert [(r.text, r.match) for r in highlight_runs("sh010", "zzz")] == [("sh010", False)]
        assert highlight_runs("", "sh") == []

    def test_rebuilds_the_label_exactly_so_nothing_is_lost_or_escaped(self) -> None:
        label = "A <b>bold</b> & brassy name"
        assert "".join(run.text for run in highlight_runs(label, "bold &")) == label


class TestKeysAndReferences:
    def test_keys_on_type_and_id_together(self) -> None:
        assert entity_key(EntityRef(type="Shot", id=1)) == "Shot:1"
        assert entity_key(EntityRef(type="Asset", id=1)) != entity_key(EntityRef(type="Shot", id=1))

    def test_treats_a_missing_name_and_the_type_id_placeholder_alike(self) -> None:
        assert is_bare_ref(EntityRef(type="Shot", id=862)) is True
        assert is_bare_ref(EntityRef(type="Shot", id=862, name="")) is True
        assert is_bare_ref(EntityRef(
            type="Shot", id=862, name=placeholder_name(EntityRef(type="Shot", id=862)),
        )) is True
        assert is_bare_ref(EntityRef(type="Shot", id=862, name="sh010_0010")) is False


class TestFlattenRow:
    def test_lifts_type_and_id_unwraps_relationships_and_keeps_a_dotted_key_literal(self) -> None:
        row = flatten_row(EntityRow(type="Shot", id=862, values={
            "code": "sh010_0010",
            "project.Project.name": "Blue Moon Rising",
            "project": {"type": "Project", "id": 70, "name": "Blue Moon Rising"},
        }))
        assert row == PickerRow(type="Shot", id=862, name="sh010_0010", values={
            "code": "sh010_0010",
            "project.Project.name": "Blue Moon Rising",
            "project": {"type": "Project", "id": 70, "name": "Blue Moon Rising"},
        })

    def test_falls_through_the_display_name_chain_and_then_to_type_id(self) -> None:
        assert flatten_row(EntityRow(type="Task", id=5700, values={"content": "FX"})).name == "FX"
        assert flatten_row(EntityRow(type="Version", id=17055, values={})).name == "Version 17055"

    def test_prefers_an_explicit_label_field(self) -> None:
        row = flatten_row(
            EntityRow(type="Shot", id=862, values={"code": "sh010_0010", "description": "A shot"}),
            "description",
        )
        assert row.name == "A shot"


class TestWithSelectedPinned:
    @staticmethod
    def row(entity_type: str, id: int, name: str) -> PickerRow:
        return PickerRow(type=entity_type, id=id, name=name, values={})

    def test_appends_selected_rows_the_results_do_not_hold_in_selection_order(self) -> None:
        rows = [self.row("Shot", 1, "a"), self.row("Shot", 2, "b")]
        known = {"Asset:1": self.row("Asset", 1, "charAda")}
        out = with_selected_pinned(
            rows, [EntityRef(type="Shot", id=2), EntityRef(type="Asset", id=1)], known,
        )
        assert [entity_key(row) for row in out] == ["Shot:1", "Shot:2", "Asset:1"]
        assert out[2].name == "charAda"

    def test_falls_back_to_type_id_for_a_selection_nothing_has_resolved(self) -> None:
        out = with_selected_pinned([], [EntityRef(type="Shot", id=9)], {})
        assert out[0].name == "Shot 9"


class TestFitChips:
    def test_keeps_every_chip_when_they_all_fit_and_holds_nothing_back(self) -> None:
        assert fit_chips([100, 80, 60], 240, 40) == ChipFit(visible=3, hidden=0)
        assert fit_chips([100, 80, 60], 1000, 40) == ChipFit(visible=3, hidden=0)

    def test_has_nothing_to_fit_for_an_empty_row(self) -> None:
        assert fit_chips([], 0, 40) == ChipFit(visible=0, hidden=0)

    def test_hides_every_chip_when_the_first_one_does_not_fit(self) -> None:
        assert fit_chips([100, 80], 90, 40) == ChipFit(visible=0, hidden=2)

    def test_cuts_at_a_whole_chip_never_inside_one(self) -> None:
        assert fit_chips([100, 80, 60], 200, 40) == ChipFit(visible=1, hidden=2)

    def test_spends_the_reserve_only_once_the_row_overflows(self) -> None:
        # 200 of chips in 205 is every chip; the same chips in 199 lose two, because the
        # "+n" pill takes its 40 out of what is left.
        assert fit_chips([100, 100], 205, 40) == ChipFit(visible=2, hidden=0)
        assert fit_chips([100, 100], 199, 40) == ChipFit(visible=1, hidden=1)

    def test_fits_nothing_into_a_row_narrower_than_its_reserve(self) -> None:
        assert fit_chips([100], 30, 40) == ChipFit(visible=0, hidden=1)


class TestSummariseSelection:
    codes = ["ip", "apr", "fin", "hld", "omt"]

    @staticmethod
    def same(code: str) -> str:
        return code

    def test_keeps_one_line_by_default_which_is_ellipsis(self) -> None:
        plan = summarise_selection(self.codes, self.same)
        assert plan.shown == ["ip", "apr", "fin"]
        assert plan.overflow == 2
        assert plan.one_line is True

    def test_draws_every_chip_and_wraps_under_chips(self) -> None:
        plan = summarise_selection(self.codes, self.same, summary="chips")
        assert plan.shown == self.codes
        assert plan.overflow == 0
        assert plan.one_line is False

    def test_caps_the_chips_at_max_and_counts_the_rest(self) -> None:
        plan = summarise_selection(self.codes, self.same, summary="chips", max=2)
        assert plan.shown == ["ip", "apr"]
        assert plan.overflow == 3

    def test_keeps_ellipsis_on_one_line_three_chips_wide_unless_max_says_otherwise(self) -> None:
        plan = summarise_selection(self.codes, self.same, summary="ellipsis")
        assert plan.shown == ["ip", "apr", "fin"]
        assert plan.overflow == 2
        assert plan.one_line is True
        assert summarise_selection(self.codes, self.same, summary="ellipsis", max=1).overflow == 4

    def test_draws_no_chip_under_count_and_reads_the_number_selected(self) -> None:
        plan = summarise_selection(self.codes, self.same, summary="count")
        assert plan.shown == []
        assert plan.count_label == "5 selected"

    def test_puts_every_label_in_the_title_whatever_the_mode(self) -> None:
        for summary in ("chips", "ellipsis", "count"):
            plan = summarise_selection(self.codes, lambda code: code.upper(), summary=summary, max=1)
            assert plan.title == "IP, APR, FIN, HLD, OMT"

    def test_fits_the_ellipsis_chips_to_a_measured_row(self) -> None:
        fit = ChipRow(widths=[60, 60, 60, 60, 60], available=150, reserve=30)
        plan = summarise_selection(self.codes, self.same, summary="ellipsis", fit=fit)
        assert plan.shown == ["ip", "apr"]
        assert plan.overflow == 3

    def test_lets_a_measured_row_draw_more_than_three_chips_and_max_still_caps_it(self) -> None:
        fit = ChipRow(widths=[40, 40, 40, 40, 40], available=400, reserve=30)
        assert summarise_selection(self.codes, self.same, summary="ellipsis", fit=fit).shown == self.codes
        assert summarise_selection(
            self.codes, self.same, summary="ellipsis", max=2, fit=fit,
        ).shown == ["ip", "apr"]

    def test_draws_no_chip_when_the_row_fits_none_and_counts_them_all(self) -> None:
        fit = ChipRow(widths=[60, 60, 60, 60, 60], available=40, reserve=30)
        plan = summarise_selection(self.codes, self.same, summary="ellipsis", fit=fit)
        assert plan.shown == []
        assert plan.overflow == 5

    def test_ignores_a_measured_row_outside_ellipsis(self) -> None:
        fit = ChipRow(widths=[60, 60, 60, 60, 60], available=40, reserve=30)
        assert summarise_selection(self.codes, self.same, summary="chips", fit=fit).shown == self.codes

    def test_is_empty_for_an_empty_selection(self) -> None:
        plan = summarise_selection([], self.same, summary="ellipsis")
        assert plan.shown == []
        assert plan.overflow == 0
        assert plan.title == ""
        assert plan.count_label == "0 selected"


class TestCreateEntitySearch:
    @staticmethod
    def harness(**overrides: Any) -> tuple[MockClient, EntitySearch]:
        mock = MockClient(seed=1, now=MOCK_NOW)
        client = create_query_cache(mock)
        options = {"client": client, "entity_types": ["Shot"], "page_size": 5}
        options.update(overrides)
        return mock, create_entity_search(EntitySearchOptions(**options))

    def test_lists_the_first_page_last_updated_first_with_nothing_typed(self) -> None:
        _, search = self.harness(fields=["updated_at"])
        search.set_query("")
        assert len(search.state.rows) == 5
        assert search.state.has_more is True
        dates = [str(row.values["updated_at"]) for row in search.state.rows]
        assert dates == sorted(dates, reverse=True)

    def test_drops_the_name_condition_under_the_minimum_query_length_instead_of_the_rows(self) -> None:
        _, search = self.harness(min_query_length=2, fields=["updated_at"])
        search.set_query("sh010")
        assert len(search.state.rows) > 0
        assert all(row.name.startswith("sh010") for row in search.state.rows)
        search.set_query("s")
        assert any(not row.name.startswith("sh010") for row in search.state.rows)
        assert search.state.too_short is True
        assert len(search.state.rows) == 5
        # Nothing is highlighted, because the rows answer no query.
        assert search.state.query == ""

    def test_keeps_the_project_scope_and_the_exclusions_on_the_unfiltered_list(self) -> None:
        _, search = self.harness(project_id=71, fields=["project"])
        search.set_query("")
        rows = search.state.rows
        assert len(rows) > 0
        assert all(row.values["project"]["id"] == 71 for row in rows)
        dropped = rows[0]
        search.update(exclude=[EntityRef(type="Shot", id=dropped.id)])
        assert len(search.state.rows) > 0
        assert not any(row.id == dropped.id for row in search.state.rows)

    def test_pages_the_unfiltered_list_with_the_load_more_row(self) -> None:
        _, search = self.harness(page_size=3)
        search.set_query("")
        assert len(search.state.rows) == 3
        search.load_more()
        assert len(search.state.rows) > 3
        assert len({entity_key(row) for row in search.state.rows}) == 6

    def test_does_not_match_every_person_through_the_domain_they_share(self) -> None:
        _, search = self.harness(entity_types=["HumanUser"], search_fields=user_search_fields)
        search.set_query("le")
        # `contains` on the whole address matches all eight through `example.studio`.
        assert [row.name for row in search.state.rows] == ["Cleo Dias"]

    def test_matches_the_whole_address_once_the_query_holds_an_at(self) -> None:
        _, search = self.harness(entity_types=["HumanUser"], search_fields=user_search_fields)
        search.set_query("bo.chen@example.studio")
        assert [row.name for row in search.state.rows] == ["Bo Chen"]

    def test_finds_rows_whose_label_holds_every_word(self) -> None:
        _, search = self.harness()
        search.set_query("sh010 0010")
        assert [row.name for row in search.state.rows] == ["sh010_0010"]

    def test_keys_the_rows_it_remembers_on_type_and_id(self) -> None:
        _, search = self.harness(entity_types=["Shot", "Asset"])
        search.set_query("char")
        assert len(search.state.rows) > 0
        for key in search.known:
            entity_type, _, id = key.partition(":")
            assert entity_type.isalpha() and id.isdigit()

    def test_never_lets_a_slow_earlier_response_overwrite_a_later_one(self) -> None:
        _, search = self.harness(page_size=5)
        # The slow query takes its ticket first and answers last.
        slow = search.begin()
        answer = search.fetch_page("sh010", 1)
        search.set_query("sh020")
        search.deliver(slow, "sh010", 1, answer)
        assert search.state.query == "sh020"
        assert all(row.name.startswith("sh020") for row in search.state.rows)

    def test_pages_appending_the_next_page_to_the_rows_already_shown(self) -> None:
        _, search = self.harness(page_size=3)
        search.set_query("sh0")
        assert len(search.state.rows) == 3
        assert search.state.has_more is True
        search.load_more()
        assert len(search.state.rows) == 6
        assert len({entity_key(row) for row in search.state.rows}) == 6

    def test_pushes_an_exclusion_into_the_server_filter(self) -> None:
        _, search = self.harness()
        search.set_query("sh010")
        first = search.state.rows
        assert len(first) > 0
        dropped = first[0]
        search.update(exclude=[EntityRef(type="Shot", id=dropped.id)])
        assert len(search.state.rows) > 0
        assert not any(row.id == dropped.id for row in search.state.rows)

    def test_scopes_by_project_through_the_field_the_type_actually_has(self) -> None:
        _, search = self.harness(entity_types=["Shot"], project_id=71)
        search.set_query("hb0")
        assert len(search.state.rows) > 0
        search.update(project_id=70)
        assert search.state.loading is False
        assert search.state.rows == []

    def test_scopes_a_site_wide_type_through_its_projects_field_rather_than_400ing(self) -> None:
        _, search = self.harness(entity_types=["HumanUser"], project_id=70)
        search.set_query("ada")
        assert search.state.error is None
        assert [row.name for row in search.state.rows] == ["Ada Lovelace"]

    def test_searches_the_fields_a_caller_adds_on_top_of_the_display_name_chain(self) -> None:
        _, search = self.harness(entity_types=["HumanUser"], search_fields=["login", "email"])
        search.set_query("bo.chen")
        assert [row.name for row in search.state.rows] == ["Bo Chen"]

    def test_drops_a_search_field_the_type_does_not_have_instead_of_failing_the_request(self) -> None:
        _, search = self.harness(entity_types=["HumanUser", "ApiUser"], search_fields=["login"])
        search.set_query("pipeline")
        assert search.state.error is None
        assert [row.name for row in search.state.rows] == ["pipeline_bot"]

    def test_applies_a_pre_filter_only_to_the_types_that_have_the_field(self) -> None:
        # ApiUser has no status field, so the condition is dropped there rather than 400ing.
        _, search = self.harness(
            entity_types=["HumanUser", "ApiUser"],
            filters=group("and", [condition("sg_status_list", "is", "act")]),
        )
        search.set_query("o")
        search.update(min_query_length=1)
        assert search.state.error is None
        names = [row.name for row in search.state.rows]
        assert "pipeline_bot" in names
        assert "Bo Chen" not in names

    def test_surfaces_a_failure_instead_of_swallowing_it(self) -> None:
        mock, search = self.harness()
        seen: list[Exception] = []
        search.update(on_error=seen.append)
        mock.fail_next(MockFailure(status=500, message="Flow PT API error 500"))
        search.set_query("sh010")
        assert search.state.error is not None
        assert str(search.state.error) == "Flow PT API error 500"
        assert len(seen) == 1
        assert search.state.loading is False

    def test_hydrates_bare_references_with_one_request_per_type(self) -> None:
        _, search = self.harness(entity_types=["Shot", "Asset"])
        search.hydrate([
            EntityRef(type="Shot", id=862),
            EntityRef(type="Shot", id=863),
            EntityRef(type="Asset", id=1226),
        ])
        assert len(search.known) >= 3
        assert search.known["Shot:862"].name == "sh010_0010"
        assert search.known["Asset:1226"].name == "charAda"

    def test_does_not_overwrite_a_hydrated_row_with_a_bare_reference_handed_in_later(self) -> None:
        _, search = self.harness()
        search.hydrate([EntityRef(type="Shot", id=862)])
        assert search.known["Shot:862"].name == "sh010_0010"
        search.hydrate([EntityRef(type="Shot", id=862)])
        assert search.known["Shot:862"].name == "sh010_0010"

    def test_leaves_a_reference_that_cannot_be_resolved_as_type_id(self) -> None:
        _, search = self.harness()
        search.hydrate([EntityRef(type="Shot", id=999999)])
        assert "Shot:999999" in search.known
        assert search.known["Shot:999999"].name == "Shot 999999"

    def test_keeps_a_hydration_failure_visible_and_still_names_the_row(self) -> None:
        mock, search = self.harness()
        mock.fail_next(MockFailure(status=503, message="Flow PT API error 503"))
        search.hydrate([EntityRef(type="Shot", id=862)])
        assert search.state.error is not None
        assert search.known["Shot:862"].name == "Shot 862"


class TestClearableForField:
    def test_drops_the_clear_on_a_mandatory_field_and_keeps_the_caller_answer_otherwise(self) -> None:
        assert clearable_for_field(True, a_field(True)) is False
        assert clearable_for_field(None, a_field(True)) is False
        assert clearable_for_field(True, a_field(False)) is True
        assert clearable_for_field(False, a_field(False)) is False
        # A field the widget has not read is not mandatory as far as it knows.
        assert clearable_for_field(None, None) is True
        assert clearable_for_field(False, None) is False

