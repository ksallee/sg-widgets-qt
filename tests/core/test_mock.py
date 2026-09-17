"""Port of `packages/core/test/mock.test.ts`.

A row is `EntityRow(type, id, values)`, one flat map, so where upstream reads
`row.attributes[x]` or `row.relationships[x].data` these read `row.values[x]`. The
assertions are otherwise the upstream ones.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

import pytest

from sg_widgets_core.client import (
    EntityRow,
    EventLogOptions,
    FollowingOptions,
    HierarchyRef,
    SearchOptions,
    SgApiError,
    SummarizeOptions,
    SummaryGrouping,
    UploadFile,
    hierarchy_entity,
)
from sg_widgets_core.filter import EntityRef, WireGroup
from sg_widgets_core.mock import MOCK_NOW, MockClient, MockFailure
from sg_widgets_core.schema import status_field_for
from sg_widgets_core.status import parse_bg_color, usable_statuses


def client() -> MockClient:
    return MockClient()


def only(path: str, operator: str, value: Any) -> WireGroup:
    """One condition, wrapped in the `and` group a search wants."""
    return {"logical_operator": "and", "conditions": [[path, operator, value]]}


def attrs(c: MockClient, entity_type: str, filters: WireGroup | None, field: str) -> list[Any]:
    res = c.search(entity_type, SearchOptions(filters=filters, fields=[field], page={"size": 500}))
    return [row.values[field] for row in res.data]


def count(c: MockClient, entity_type: str, filters: WireGroup | None) -> int:
    res = c.search(entity_type, SearchOptions(filters=filters, fields=["id"], page={"size": 500}))
    return len(res.data)


class TestFixtures:
    def test_has_the_sizes_a_demo_needs_and_stable_ids_across_runs(self) -> None:
        c = client()
        assert len(c.rows_of("Project")) == 3
        assert len(c.rows_of("Sequence")) == 6
        # 30 under a sequence, and 3 under a project that has none.
        assert len(c.rows_of("Shot")) == 33
        assert len(c.rows_of("Asset")) == 10
        assert len(c.rows_of("Version")) == 60
        assert len(c.rows_of("Task")) == 40
        assert len(c.rows_of("HumanUser")) == 8
        assert len(c.rows_of("ApiUser")) == 2

        again = MockClient(seed=1)
        assert [r["code"] for r in again.rows_of("Version")] == [r["code"] for r in c.rows_of("Version")]
        # A different seed shuffles the generated values but keeps the shape.
        other = MockClient(seed=7)
        assert len(other.rows_of("Version")) == 60
        assert [r["sg_status_list"] for r in other.rows_of("Version")] != [
            r["sg_status_list"] for r in c.rows_of("Version")
        ]

    def test_has_inactive_people_logins_emails_and_thumbnails(self) -> None:
        users = client().rows_of("HumanUser")
        assert len([u for u in users if u["sg_status_list"] == "dis"]) > 0
        assert len([u for u in users if u["sg_status_list"] == "act"]) > 0
        for u in users:
            assert re.match(r"^[a-z]+\.[a-z]+$", str(u["login"]))
            assert "@" in str(u["email"])
            assert re.match(r"^https?:", str(u["image"]))


class TestRowShape:
    def test_returns_only_the_requested_fields_with_entity_fields_under_relationships(self) -> None:
        res = client().search(
            "Version", SearchOptions(fields=["code", "sg_status_list", "entity"], page={"size": 1})
        )
        row: EntityRow = res.data[0]
        assert sorted(row.values) == ["code", "entity", "sg_status_list"]
        # An entity link is `{type, id, name}`, and `name` is the target's cached_display_name (060).
        link = row.values["entity"]
        assert link["type"] == "Shot"
        assert isinstance(link["id"], int)
        assert isinstance(link["name"], str)

    def test_gives_an_empty_relationships_object_when_no_entity_field_was_asked_for_and_drops_unknown_names(
        self,
    ) -> None:
        res = client().search("Shot", SearchOptions(fields=["code", "sg_not_a_field"], page={"size": 1}))
        row = res.data[0]
        # A bogus `fields` name is dropped at HTTP 200; only a filter 400s (003_query).
        assert list(row.values) == ["code"]

    def test_returns_a_dotted_path_flat_under_its_literal_key_in_attributes(self) -> None:
        res = client().search("Version", SearchOptions(fields=["code", "entity.Shot.code"], page={"size": 1}))
        assert res.data[0].values["entity.Shot.code"] == "sh010_0010"

    def test_drops_a_dotted_path_through_a_multi_entity_field_at_200(self) -> None:
        res = client().search("Shot", SearchOptions(fields=["code", "assets.Asset.code"], page={"size": 1}))
        assert list(res.data[0].values) == ["code"]


class TestFilterOperatorsOnText:
    def test_is_is_not(self) -> None:
        c = client()
        assert attrs(c, "Shot", only("code", "is", "sh010_0010"), "code") == ["sh010_0010"]
        assert count(c, "Shot", only("code", "is_not", "sh010_0010")) == 32
        # Matching is case-insensitive on a text field (field_types/text).
        assert attrs(c, "Shot", only("code", "is", "SH010_0010"), "code") == ["sh010_0010"]

    def test_in_not_in(self) -> None:
        c = client()
        assert count(c, "Shot", only("code", "in", ["sh010_0010", "sh010_0020"])) == 2
        assert count(c, "Shot", only("code", "not_in", ["sh010_0010", "sh010_0020"])) == 31
        assert count(c, "Shot", only("code", "in", ["ZZZNOPE"])) == 0

    def test_contains_not_contains_starts_with_ends_with(self) -> None:
        c = client()
        codes = [str(r["code"]) for r in c.rows_of("Shot")]
        contains = len([code for code in codes if "010_00" in code])
        assert count(c, "Shot", only("code", "contains", "010_00")) == contains
        assert count(c, "Shot", only("code", "not_contains", "010_00")) == 33 - contains
        assert count(c, "Shot", only("code", "starts_with", "sh01")) == len(
            [code for code in codes if code.startswith("sh01")]
        )
        assert count(c, "Shot", only("code", "ends_with", "0010")) == len(
            [code for code in codes if code.endswith("0010")]
        )
        assert count(c, "Shot", only("code", "contains", "ZZZNOPE")) == 0


class TestNegationIncludesNulls:
    def test_is_not_and_not_in_match_rows_where_the_field_is_unset_comparisons_do_not(self) -> None:
        c = client()
        departments = [r["sg_department"] for r in c.rows_of("Version")]
        nulls = len([d for d in departments if d is None])
        assert nulls > 0

        comp = len([d for d in departments if d == "Comp"])
        # 60 rows: every row that is not "Comp", the null ones included.
        assert count(c, "Version", only("sg_department", "is_not", "Comp")) == 60 - comp
        assert count(c, "Version", only("sg_department", "not_in", ["Comp"])) == 60 - comp
        assert count(c, "Version", only("sg_department", "not_contains", "Comp")) == 60 - comp
        assert count(c, "Version", only("sg_department", "is", None)) == nulls

        # client_approved_at is null on every fixture row, so a comparison returns nothing.
        assert count(c, "Version", only("client_approved_at", "greater_than", "2000-01-01T00:00:00Z")) == 0
        assert count(c, "Version", only("client_approved_at", "is_not", "2000-01-01T00:00:00Z")) == 60


class TestFilterOperatorsOnStatusListListAndNumber:
    def test_is_is_not_in_not_in_on_a_status_list(self) -> None:
        c = client()
        statuses = [r["sg_status_list"] for r in c.rows_of("Shot")]
        ip = len([s for s in statuses if s == "ip"])
        assert count(c, "Shot", only("sg_status_list", "is", "ip")) == ip
        assert count(c, "Shot", only("sg_status_list", "is_not", "ip")) == 33 - ip
        both = len([s for s in statuses if s in ("ip", "fin")])
        assert count(c, "Shot", only("sg_status_list", "in", ["ip", "fin"])) == both
        assert count(c, "Shot", only("sg_status_list", "not_in", ["ip", "fin"])) == 33 - both
        # The display label is not a filter value (field_types/status_list).
        assert count(c, "Shot", only("sg_status_list", "is", "In Progress")) == 0

    def test_filters_a_list_case_insensitively_where_a_write_is_case_sensitive(self) -> None:
        c = client()
        characters = len([a for a in c.rows_of("Asset") if a["sg_asset_type"] == "Character"])
        assert count(c, "Asset", only("sg_asset_type", "is", "character")) == characters

    def test_greater_than_less_than_between_on_a_number_inclusive_and_order_insensitive(self) -> None:
        c = client()
        durations = [int(r["sg_cut_duration"]) for r in c.rows_of("Shot")]
        assert count(c, "Shot", only("sg_cut_duration", "greater_than", 100)) == len(
            [d for d in durations if d > 100]
        )
        assert count(c, "Shot", only("sg_cut_duration", "less_than", 100)) == len(
            [d for d in durations if d < 100]
        )
        inside = len([d for d in durations if 100 <= d <= 150])
        assert count(c, "Shot", only("sg_cut_duration", "between", [100, 150])) == inside
        assert count(c, "Shot", only("sg_cut_duration", "between", [150, 100])) == inside
        # A numeric string is coerced, the way the site coerces it (field_types/number).
        first = durations[0]
        assert count(c, "Shot", only("sg_cut_duration", "is", str(first))) == len(
            [d for d in durations if d == first]
        )

    def test_greater_than_less_than_between_on_a_date(self) -> None:
        c = client()
        due = [str(r["due_date"]) for r in c.rows_of("Task")]
        assert count(c, "Task", only("due_date", "greater_than", "2026-03-01")) == len(
            [d for d in due if d > "2026-03-01"]
        )
        assert count(c, "Task", only("due_date", "between", ["2026-02-01", "2026-03-01"])) == len(
            [d for d in due if "2026-02-01" <= d <= "2026-03-01"]
        )


#: The mock's own today, a Monday, at midday UTC.
NOW = MOCK_NOW

#: Asset ids, and the date each carries around that Monday. 1234 and 1235 keep none.
DATES: dict[int, str] = {
    1226: "2026-01-05",  # today
    1227: "2026-01-04",  # yesterday, the Sunday that ends the previous week
    1228: "2026-01-06",  # tomorrow
    1229: "2025-12-31",  # the last day of the previous month, and of the previous year
    1230: "2026-01-11",  # the Sunday that ends this week
    1231: "2026-01-12",  # the Monday that starts the next one
    1232: "2026-02-01",  # next month
    1233: "2025-12-06",  # 30 days back
}

#: Version ids, and the moment each carries. The other 52 rows keep none.
MOMENTS: dict[int, str] = {
    17055: "2026-01-05T11:00:00Z",  # exactly one hour back
    17056: "2026-01-05T10:59:59Z",  # a second before that
    17057: "2026-01-05T00:00:00Z",  # midnight today
    17058: "2026-01-04T23:59:59Z",  # the last second of yesterday
    17059: "2026-01-05T13:00:00Z",  # exactly one hour ahead
    17060: "2026-01-11T23:59:59Z",  # the last second of this week
    17061: "2026-01-12T00:00:00Z",  # the first second of the next one
    17062: "2025-12-31T23:59:59Z",  # the last second of the previous year
}


def sited(entity_type: str, field: str, values: dict[int, str], now: Any = NOW) -> MockClient:
    """A pinned-clock site carrying `values` on `field`, and null on every other row of the type."""
    c = MockClient(now=now)
    for row in c.rows_of(entity_type):
        id = int(row["id"])
        c.update(entity_type, id, {field: values.get(id)})
    return c


def ids(c: MockClient, entity_type: str, field: str, operator: str, value: Any) -> list[int]:
    res = c.search(
        entity_type,
        SearchOptions(filters=only(field, operator, value), fields=["id"], page={"size": 500}),
    )
    return [row.id for row in res.data]


class TestRelativeAndCalendarDateOperatorsADateField:
    @staticmethod
    def matching(operator: str, value: Any) -> list[int]:
        return ids(sited("Asset", "sg_due_date", DATES), "Asset", "sg_due_date", operator, value)

    def test_counts_in_last_back_from_the_clock_in_every_unit(self) -> None:
        # A date has no time of day, so a window shorter than a day still matches today
        # (field_types/date).
        assert self.matching("in_last", [1, "HOUR"]) == [1226]
        assert self.matching("in_last", [1, "DAY"]) == [1226, 1227]
        assert self.matching("in_last", [1, "WEEK"]) == [1226, 1227, 1229]
        assert self.matching("in_last", [30, "DAY"]) == [1226, 1227, 1229, 1233]
        assert self.matching("in_last", [1, "MONTH"]) == [1226, 1227, 1229, 1233]
        assert self.matching("in_last", [1, "YEAR"]) == [1226, 1227, 1229, 1233]

    def test_counts_in_next_forward_from_the_clock_in_every_unit(self) -> None:
        assert self.matching("in_next", [1, "HOUR"]) == [1226]
        assert self.matching("in_next", [1, "DAY"]) == [1226, 1228]
        assert self.matching("in_next", [1, "WEEK"]) == [1226, 1228, 1230, 1231]
        assert self.matching("in_next", [1, "MONTH"]) == [1226, 1228, 1230, 1231, 1232]
        assert self.matching("in_next", [1, "YEAR"]) == [1226, 1228, 1230, 1231, 1232]

    def test_adds_the_rows_with_no_date_to_the_negating_forms(self) -> None:
        assert self.matching("not_in_last", [1, "DAY"]) == [1228, 1229, 1230, 1231, 1232, 1233, 1234, 1235]
        assert self.matching("not_in_next", [1, "DAY"]) == [1227, 1229, 1230, 1231, 1232, 1233, 1234, 1235]
        # The positive forms never do.
        assert 1234 not in self.matching("in_last", [100, "YEAR"])
        assert 1234 not in self.matching("in_next", [100, "YEAR"])

    def test_buckets_a_calendar_day_week_month_and_year_at_the_utc_boundary(self) -> None:
        assert self.matching("in_calendar_day", 0) == [1226]
        assert self.matching("in_calendar_day", -1) == [1227]
        assert self.matching("in_calendar_day", 1) == [1228]
        # A week runs Monday to Sunday, so yesterday is the previous one and this Sunday
        # is this one.
        assert self.matching("in_calendar_week", 0) == [1226, 1228, 1230]
        assert self.matching("in_calendar_week", -1) == [1227, 1229]
        assert self.matching("in_calendar_week", 1) == [1231]
        assert self.matching("in_calendar_month", 0) == [1226, 1227, 1228, 1230, 1231]
        assert self.matching("in_calendar_month", -1) == [1229, 1233]
        assert self.matching("in_calendar_month", 1) == [1232]
        assert self.matching("in_calendar_year", 0) == [1226, 1227, 1228, 1230, 1231, 1232]
        assert self.matching("in_calendar_year", -1) == [1229, 1233]
        assert self.matching("in_calendar_year", 1) == []
        # A bare offset and a one-element array are the same value (field_types/date).
        assert self.matching("in_calendar_day", [0]) == [1226]


class TestRelativeAndCalendarDateOperatorsADateTimeField:
    @staticmethod
    def matching(operator: str, value: Any) -> list[int]:
        return ids(
            sited("Version", "client_approved_at", MOMENTS), "Version", "client_approved_at", operator, value
        )

    def test_counts_in_last_and_in_next_to_the_second(self) -> None:
        # Where a date stands for its whole day, a moment is a point: midnight today is an
        # hour out.
        assert self.matching("in_last", [1, "HOUR"]) == [17055]
        assert self.matching("in_next", [1, "HOUR"]) == [17059]
        assert self.matching("in_last", [1, "DAY"]) == [17055, 17056, 17057, 17058]
        assert self.matching("in_next", [1, "WEEK"]) == [17059, 17060, 17061]
        assert self.matching("in_last", [1, "MONTH"]) == [17055, 17056, 17057, 17058, 17062]
        assert self.matching("in_last", [1, "YEAR"]) == [17055, 17056, 17057, 17058, 17062]

    def test_adds_the_rows_with_no_moment_to_the_negating_forms(self) -> None:
        negated = self.matching("not_in_last", [1, "HOUR"])
        assert len(negated) == 59
        assert 17055 not in negated
        # 52 of the 60 Versions carry nothing at all, and every one of them is in the answer.
        assert 17063 in negated
        assert 17063 not in self.matching("in_last", [1, "HOUR"])

    def test_buckets_a_calendar_day_week_month_and_year_at_the_utc_boundary(self) -> None:
        assert self.matching("in_calendar_day", 0) == [17055, 17056, 17057, 17059]
        assert self.matching("in_calendar_day", -1) == [17058]
        assert self.matching("in_calendar_week", 0) == [17055, 17056, 17057, 17059, 17060]
        assert self.matching("in_calendar_week", 1) == [17061]
        assert self.matching("in_calendar_month", 0) == [
            17055, 17056, 17057, 17058, 17059, 17060, 17061,
        ]
        assert self.matching("in_calendar_month", -1) == [17062]
        assert self.matching("in_calendar_year", 0) == [
            17055, 17056, 17057, 17058, 17059, 17060, 17061,
        ]
        assert self.matching("in_calendar_year", -1) == [17062]


class TestRelativeAndCalendarDateOperators:
    def test_clamps_a_month_and_a_year_onto_a_day_the_target_does_not_have(self) -> None:
        march = sited(
            "Asset", "sg_due_date", {1226: "2026-02-28", 1227: "2026-02-27"}, "2026-03-31T12:00:00Z"
        )
        assert ids(march, "Asset", "sg_due_date", "in_last", [1, "MONTH"]) == [1226]
        leap = sited(
            "Asset", "sg_due_date", {1226: "2027-02-28", 1227: "2027-02-27"}, "2028-02-29T12:00:00Z"
        )
        assert ids(leap, "Asset", "sg_due_date", "in_last", [1, "YEAR"]) == [1226]

    def test_400s_on_a_value_that_is_not_count_unit(self) -> None:
        c = sited("Asset", "sg_due_date", DATES)

        def refused(operator: str, value: Any) -> Any:
            return c.search("Asset", SearchOptions(filters=only("sg_due_date", operator, value)))

        with pytest.raises(SgApiError) as one:
            refused("in_last", 1)
        assert one.value.status == 400
        assert str(one.value) == "API read() 'in_last' 'relation' expects a 2-element array: [1]"
        with pytest.raises(SgApiError) as two:
            refused("in_last", [1])
        assert two.value.status == 400
        with pytest.raises(SgApiError) as three:
            refused("in_next", [100, "day"])
        assert three.value.status == 400
        assert str(three.value) == (
            "API read() 'in_next' 'relation' doesn't support the 'day' time unit: [100, \"day\"]"
            '  Valid time units: ["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]'
        )
        with pytest.raises(SgApiError) as four:
            refused("in_last", [-10, "DAY"])
        assert four.value.status == 400
        assert str(four.value) == "API read() 'in_last' 'relation' expects at a positive Integer time unit"
        # The value is refused before the rows are read, so a negating form on a row with
        # no date still 400s.
        with pytest.raises(SgApiError):
            refused("not_in_last", [0, "DAY"])

    def test_reads_the_clock_on_every_call_and_defaults_it_to_now(self) -> None:
        pinned = [float(_parse(NOW))]
        c = sited("Asset", "sg_due_date", {1226: "2026-01-05"}, lambda: pinned[0])
        assert ids(c, "Asset", "sg_due_date", "in_calendar_day", 0) == [1226]
        pinned[0] += 86_400_000
        assert ids(c, "Asset", "sg_due_date", "in_calendar_day", 0) == []
        assert ids(c, "Asset", "sg_due_date", "in_calendar_day", -1) == [1226]

        live = client()
        live.update("Asset", 1226, {"sg_due_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")})
        assert 1226 in ids(live, "Asset", "sg_due_date", "in_calendar_day", 0)

    def test_reaches_the_fixtures_from_mock_now(self) -> None:
        c = MockClient(now=MOCK_NOW)
        # Every Version is created inside the 120 days before the mock's today, and none after it.
        assert count(c, "Version", only("created_at", "in_last", [120, "DAY"])) == 60
        assert count(c, "Version", only("created_at", "in_next", [1, "YEAR"])) == 0
        assert count(c, "Version", only("created_at", "not_in_next", [1, "YEAR"])) == 60


def _parse(iso: str) -> float:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000


class TestFilterOperatorsOnEntityFields:
    def test_is_in_take_type_id_hashes(self) -> None:
        c = client()
        shot = {"type": "Shot", "id": 862}
        linked = len([v for v in c.rows_of("Version") if v["entity"]["id"] == 862])
        assert linked > 0
        assert count(c, "Version", only("entity", "is", shot)) == linked
        assert count(c, "Version", only("entity", "in", [shot])) == linked
        assert count(c, "Version", only("entity", "is", {"type": "Shot", "id": 99_999_999})) == 0
        assert count(c, "Version", only("entity", "is_not", shot)) == 60 - linked

    def test_type_is_type_is_not_read_the_link_type(self) -> None:
        c = client()
        assets = len([v for v in c.rows_of("Version") if v["entity"]["type"] == "Asset"])
        assert assets > 0
        assert count(c, "Version", only("entity", "type_is", "Asset")) == assets
        assert count(c, "Version", only("entity", "type_is_not", "Asset")) == 60 - assets
        # A name string in a type slot matches nothing (field_types/entity).
        assert count(c, "Version", only("entity", "type_is", "sh010_0010")) == 0

    def test_name_is_name_contains_read_the_target_cached_display_name(self) -> None:
        c = client()
        linked = len([v for v in c.rows_of("Version") if v["entity"]["id"] == 862])
        assert count(c, "Version", only("entity", "name_is", "sh010_0010")) == linked
        assert count(c, "Version", only("entity", "name_contains", "sh010_")) > linked
        assert count(c, "Version", only("entity", "name_contains", "ZZZNOPE")) == 0


class TestDottedPaths:
    def test_filters_one_hop_through_an_entity_field(self) -> None:
        c = client()
        linked = len([v for v in c.rows_of("Version") if v["entity"]["id"] == 862])
        assert count(c, "Version", only("entity.Shot.code", "is", "sh010_0010")) == linked
        assert count(c, "Version", only("entity.Shot.code", "contains", "010_00")) > linked
        assert count(c, "Version", only("entity.Shot.code", "is", "ZZZNOPE")) == 0

    def test_scopes_by_project_through_project_project_id(self) -> None:
        c = client()
        in_project = len([s for s in c.rows_of("Shot") if s["project"]["id"] == 70])
        assert count(c, "Shot", only("project.Project.id", "is", 70)) == in_project
        assert count(c, "Shot", only("project.Project.name", "contains", "Harbour")) == 30 - in_project

    def test_a_hop_whose_target_type_does_not_match_the_stored_link_matches_nothing(self) -> None:
        c = client()
        # Versions linked to a Shot are not reachable through `entity.Asset.code`.
        assets = len([v for v in c.rows_of("Version") if v["entity"]["type"] == "Asset"])
        assert count(c, "Version", only("entity.Asset.code", "contains", "char")) <= assets


class TestFilterGroups:
    def test_nests_and_or_and_mixes_leaves_with_sub_groups(self) -> None:
        c = client()
        filters: WireGroup = {
            "logical_operator": "and",
            "conditions": [
                ["project", "is", {"type": "Project", "id": 70}],
                {
                    "logical_operator": "or",
                    "conditions": [["sg_status_list", "is", "ip"], ["sg_status_list", "is", "fin"]],
                },
            ],
        }
        expected = len([
            s for s in c.rows_of("Shot")
            if s["project"]["id"] == 70 and s["sg_status_list"] in ("ip", "fin")
        ])
        assert count(c, "Shot", filters) == expected

        conjunction: WireGroup = {
            "logical_operator": "and", "conditions": [["id", "is", 862], ["id", "is", 863]],
        }
        assert count(c, "Shot", conjunction) == 0
        disjunction: WireGroup = {
            "logical_operator": "or", "conditions": [["id", "is", 862], ["id", "is", 863]],
        }
        assert count(c, "Shot", disjunction) == 2

    def test_treats_an_empty_group_and_a_null_filter_as_no_filter(self) -> None:
        c = client()
        assert count(c, "Shot", {"logical_operator": "and", "conditions": []}) == 33
        assert count(c, "Shot", None) == 33


class TestFilterErrors:
    def test_400s_on_an_unknown_field_an_unfilterable_type_and_an_operator_the_type_refuses(self) -> None:
        c = client()
        with pytest.raises(SgApiError):
            c.search("Shot", SearchOptions(filters=only("sg_not_a_field", "is", "x")))
        with pytest.raises(SgApiError) as one:
            c.search("Version", SearchOptions(filters=only("sg_uploaded_movie", "is", "x")))
        assert one.value.status == 400
        with pytest.raises(SgApiError) as two:
            c.search("Version", SearchOptions(filters=only("sg_status_list", "contains", "re")))
        assert two.value.status == 400
        # Project is site-wide: it has no `project` field at all.
        with pytest.raises(SgApiError) as three:
            c.search("Project", SearchOptions(filters=only("project.Project.id", "is", 70)))
        assert three.value.status == 400

    def test_404s_on_a_type_the_site_does_not_have(self) -> None:
        with pytest.raises(SgApiError) as error:
            client().fields("NotAType")
        assert error.value.status == 404


class TestPaginationAndSort:
    def test_walks_pages_and_stops_on_an_empty_one(self) -> None:
        c = client()
        seen: list[int] = []
        page = 1
        last = None
        while True:
            res = c.search("Shot", SearchOptions(fields=["id"], page={"size": 7, "number": page}))
            if len(res.data) == 0:
                break
            seen.extend(row.id for row in res.data)
            last = res
            page += 1
            if page > 20:
                raise AssertionError("paging did not terminate")
        assert len(seen) == 33
        assert len(set(seen)) == 33
        # 33 rows in pages of 7: the fifth page holds 5, so has_more is false there (006_pagination).
        assert last is not None and last.has_more is False
        assert page == 6

    def test_defaults_to_id_ascending_and_honours_field_and_minus_field(self) -> None:
        c = client()
        plain = c.search("Shot", SearchOptions(fields=["id"], page={"size": 500}))
        assert [r.id for r in plain.data] == sorted(r.id for r in plain.data)

        ascending = attrs(c, "Shot", None, "code")
        sorted_res = c.search("Shot", SearchOptions(fields=["code"], sort="code", page={"size": 500}))
        assert [r.values["code"] for r in sorted_res.data] == sorted(ascending)
        descending = c.search("Shot", SearchOptions(fields=["code"], sort="-code", page={"size": 500}))
        assert [r.values["code"] for r in descending.data] == sorted(ascending, reverse=True)

    def test_ignores_a_sort_on_a_field_that_does_not_exist(self) -> None:
        c = client()
        plain = c.search("Shot", SearchOptions(fields=["id"], page={"size": 500}))
        bogus = c.search(
            "Shot", SearchOptions(fields=["id"], sort="sg_not_a_field_at_all", page={"size": 500})
        )
        assert [r.id for r in bogus.data] == [r.id for r in plain.data]


class TestTextSearch:
    def test_matches_every_word_case_insensitively_anywhere_in_the_name(self) -> None:
        c = client()
        one = c.text_search("sh010", {"Shot": None})
        assert len(one) > 0
        assert all("sh010" in row.name for row in one)

        assert [r.name for r in c.text_search("SH010_0010", {"Shot": None})] == ["sh010_0010"]
        # Both orders of two words return the rows holding both.
        assert [r.name for r in c.text_search("sh010 0010", {"Shot": None})] == ["sh010_0010"]
        assert [r.name for r in c.text_search("0010 sh010", {"Shot": None})] == ["sh010_0010"]
        # Every word has to match.
        assert c.text_search("sh010 nomatch", {"Shot": None}) == []

    def test_matches_on_the_name_of_the_row_it_links_to(self) -> None:
        c = client()
        # Task content is a step name; the shot code lives on `entity` (053_text_search_matching).
        hits = c.text_search("sh010_0010", {"Task": None})
        assert len(hits) > 0
        assert all(row.type == "Task" for row in hits)
        assert any("sh010_0010" not in row.name for row in hits)

    def test_respects_the_per_type_filter_and_returns_the_flattened_row(self) -> None:
        c = client()
        # The map's value is a filter array, which is the only shape `entity_types` takes.
        scoped = c.text_search("0010", {"Shot": [["project", "is", {"type": "Project", "id": 71}]]})
        assert len(scoped) > 0
        assert all(row.name.startswith("hb") for row in scoped)
        row = scoped[0]
        # There is no `fields` parameter: name, links and status, whatever the type.
        assert sorted(f.name for f in row.__dataclass_fields__.values()) == [
            "id", "links", "name", "status", "type",
        ]
        assert row.links == ("Sequence", "hb010")

    def test_takes_an_and_group_as_well_and_refuses_a_shape_the_array_form_cannot_carry(self) -> None:
        c = client()
        group = c.text_search("0010", {
            "Shot": {
                "logical_operator": "and",
                "conditions": [["project", "is", {"type": "Project", "id": 71}]],
            },
        })
        assert [r.name for r in group] == [
            r.name
            for r in c.text_search("0010", {"Shot": [["project", "is", {"type": "Project", "id": 71}]]})
        ]
        with pytest.raises(ValueError, match="'and' only"):
            c.text_search("0010", {"Shot": {"logical_operator": "or", "conditions": []}})

    def test_caps_page_size_at_25_and_pages_with_page_number(self) -> None:
        c = client()
        types: dict[str, Any] = {"Shot": None, "Version": None, "Task": None}
        first = c.text_search("_", types)
        assert len(first) == 25
        second = c.text_search("_", types, {"number": 2})
        assert len(second) == 25
        assert [f"{r.type}:{r.id}" for r in first] != [f"{r.type}:{r.id}" for r in second]
        with pytest.raises(SgApiError) as one:
            c.text_search("x", {"Shot": None}, {"size": 26})
        assert one.value.status == 400
        with pytest.raises(SgApiError) as two:
            c.text_search("x", {"Shot": None}, {"size": 0})
        assert two.value.status == 400
        with pytest.raises(SgApiError) as three:
            c.text_search("   ", {"Shot": None})
        assert three.value.status == 400

    def test_returns_the_shortest_names_first_across_types(self) -> None:
        c = client()
        rows = c.text_search("sh010", {"Shot": None, "Version": None})
        lengths = [len(r.name) for r in rows]
        assert lengths == sorted(lengths)


class TestSchema:
    def test_adds_hidden_values_only_when_a_project_id_is_passed_and_varies_them_per_project(self) -> None:
        c = client()
        site_wide = c.fields("Version")
        assert site_wide["sg_status_list"].hidden_values is None
        assert "pndl" in site_wide["sg_status_list"].valid_values

        p70 = c.fields("Version", 70)
        p71 = c.fields("Version", 71)
        assert "part" in p70["sg_status_list"].hidden_values
        assert p71["sg_status_list"].hidden_values == ["pndl", "pndvs"]
        # valid_values is byte-identical at every scope; only hidden_values moves (009_status_lists).
        assert p70["sg_status_list"].valid_values == p71["sg_status_list"].valid_values

        usable70 = [s.code for s in usable_statuses(p70["sg_status_list"])]
        usable71 = [s.code for s in usable_statuses(p71["sg_status_list"])]
        assert usable70 != usable71
        assert "part" not in usable70
        assert "part" in usable71

    def test_hides_codes_that_are_not_in_valid_values_which_the_site_also_does(self) -> None:
        task = client().fields("Task", 71)["sg_status_list"]
        assert "blk" in task.hidden_values
        assert "blk" not in task.valid_values
        # The subtraction still yields only real codes.
        assert "blk" not in [s.code for s in usable_statuses(task)]

    def test_uses_sg_status_a_list_for_projects_status_field(self) -> None:
        c = client()
        project = c.fields("Project")
        assert project["sg_status"].data_type == "list"
        assert "sg_status_list" not in project
        assert status_field_for("Project", project) is project["sg_status"]
        # Every other type keeps sg_status_list, a status_list.
        assert c.fields("Shot")["sg_status_list"].data_type == "status_list"

    def test_normalises_entity_fields_with_valid_types_and_status_fields_with_display_values(self) -> None:
        version = client().fields("Version")
        assert "Shot" in version["entity"].valid_types
        assert version["sg_status_list"].display_values["rev"] == "Pending Review"
        assert version["sg_first_frame"].data_type == "number"
        assert version["sg_uploaded_movie_frame_rate"].data_type == "float"
        assert version["client_approved"].data_type == "checkbox"
        assert version["client_approved_at"].data_type == "date_time"
        assert version["image"].data_type == "image"
        assert version["sg_uploaded_movie"].data_type == "url"
        task = client().fields("Task")
        assert task["duration"].data_type == "duration"
        assert task["time_percent_of_est"].data_type == "percent"
        assert task["start_date"].data_type == "date"

    def test_lists_the_enabled_types_with_display_names(self) -> None:
        types = client().entity_types()
        assert "HumanUser" in [t.name for t in types]
        assert next(t for t in types if t.name == "HumanUser").display_name == "Person"


class TestStatuses:
    def test_returns_decimal_rgb_colours_and_icons_of_all_three_display_types(self) -> None:
        statuses = client().statuses()
        assert len(statuses) > 10
        assert parse_bg_color(statuses[0].bg_color) is not None

        kinds = {s.icon.display_type if s.icon else None for s in statuses}
        assert kinds == {"image_map", "image", "html"}

        stock = next(s for s in statuses if s.icon and s.icon.display_type == "image_map")
        # The stock sprite is addressed by its CSS class, and `url` is empty (010_status_icons).
        assert stock.icon.image_map_key == f"icon_{stock.code}"

        custom = next(s for s in statuses if s.icon and s.icon.display_type == "image")
        assert custom.icon.data_url.startswith("data:image/png;base64,")
        assert not re.search(r"\s", custom.icon.data_url)

        html = next(s for s in statuses if s.icon and s.icon.display_type == "html")
        assert html.icon.html == "Active"


class TestDemoHooks:
    def test_fails_the_next_call_only_with_an_sg_api_error(self) -> None:
        c = client()
        c.fail_next(MockFailure(status=503, message="Service Unavailable"))
        with pytest.raises(SgApiError) as error:
            c.entity_types()
        assert error.value.status == 503
        assert str(error.value) == "Service Unavailable"
        assert isinstance(c.entity_types(), list)

        armed = MockClient(fail_next=MockFailure(status=401))
        with pytest.raises(SgApiError) as second:
            armed.statuses()
        assert second.value.status == 401
        assert isinstance(armed.statuses(), list)

    def test_simulates_latency(self) -> None:
        c = MockClient(latency_ms=20)
        started = time.monotonic() * 1000
        c.entity_types()
        assert time.monotonic() * 1000 - started >= 10


class TestUpdate:
    def test_changes_only_the_named_fields_and_answers_the_whole_record(self) -> None:
        c = client()
        before = c.search("Shot", SearchOptions(fields=["code", "description"], page={"size": 1})).data[0]
        row = c.update("Shot", before.id, {"description": "written by a test"})
        assert row.values["description"] == "written by a test"
        # A key left out of the body is unchanged, not cleared (put_entity_type_id).
        assert row.values["code"] == before.values["code"]
        # The answer is the whole record, not the change (024_read_after_write).
        assert len(row.values) > 2

    def test_is_a_no_op_on_an_empty_patch(self) -> None:
        c = client()
        row = c.update("Shot", 862, {})
        assert row.id == 862

    def test_stores_null_for_an_empty_string_on_a_text_field(self) -> None:
        c = client()
        row = c.update("Shot", 862, {"description": ""})
        assert row.values["description"] is None

    def test_refuses_a_read_only_field_a_create_only_one_and_an_unknown_one(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as one:
            c.update("Shot", 862, {"id": 1})
        assert one.value.status == 400
        assert str(one.value) == "API update() Shot.id is read only."
        # A timestamp is stored on create and refused on update (070_authored_timestamps).
        with pytest.raises(SgApiError) as two:
            c.update("Shot", 862, {"created_at": "2026-01-01T00:00:00Z"})
        assert two.value.status == 400
        assert str(two.value) == "API update() Shot.created_at is editable on create only."
        with pytest.raises(SgApiError):
            c.update("Shot", 862, {"sg_not_a_field": 1})

    def test_refuses_a_bare_id_where_an_entity_link_hash_is_required(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as one:
            c.update("Version", 17055, {"entity": 862})
        assert one.value.status == 400
        assert re.match(
            r"^API update\(\) Version\.entity expected \[Hash, .* but got Integer: 862$", str(one.value)
        )
        with pytest.raises(SgApiError) as two:
            c.update("Version", 17055, {"entity": {"id": 862}})
        assert two.value.status == 400
        assert str(two.value) == "API update() invalid/missing entity hash string 'type': {\"id\":862}"

    def test_404s_on_an_id_that_is_not_there(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.update("Shot", 999999999, {"description": "x"})
        assert error.value.status == 404
        assert str(error.value) == "Entity of type [Shot] with id=999999999 does not exist."


class TestTheNavigationTree:
    def test_answers_one_level_and_names_the_next_paths(self) -> None:
        c = client()
        root = c.hierarchy_expand("/Project/70")
        assert root.ref == HierarchyRef(kind="entity", value=EntityRef(type="Project", id=70))
        assert [n.label for n in root.children] == ["Assets", "Shots"]
        # A child names the path that opens it, and `has_children` says whether that is
        # worth doing.
        assert [n.path for n in root.children] == ["/Project/70/Asset", "/Project/70/Shot"]
        assert all(len(n.children) == 0 for n in root.children)
        assert all(n.has_children for n in root.children)

    def test_walks_project_sequence_shot_task(self) -> None:
        c = client()
        shots = c.hierarchy_expand("/Project/70/Shot")
        sequence = shots.children[0]
        # The path runs through the field name the site navigates by (post_hierarchy_search).
        assert re.match(r"^/Project/70/Shot/sg_sequence/Sequence/\d+$", sequence.path)
        level = c.hierarchy_expand(sequence.path)
        assert len(level.children) > 0
        shot = level.children[0]
        assert hierarchy_entity(shot.ref).type == "Shot"
        # A Shot carries its Tasks, so the tree goes one level further.
        assert shot.has_children is True
        shot_node = c.hierarchy_expand(shot.path)
        assert [n.label for n in shot_node.children] == ["Tasks"]
        tasks = c.hierarchy_expand(shot_node.children[0].path)
        assert len(tasks.children) > 0
        assert hierarchy_entity(tasks.children[0].ref).type == "Task"

    def test_walks_project_asset_task(self) -> None:
        c = client()
        assets = c.hierarchy_expand("/Project/70/Asset")
        asset = assets.children[0]
        assert hierarchy_entity(asset.ref).type == "Asset"
        asset_node = c.hierarchy_expand(asset.path)
        tasks = c.hierarchy_expand(asset_node.children[0].path)
        assert hierarchy_entity(tasks.children[0].ref).type == "Task"

    def test_400s_on_a_project_that_is_not_there(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.hierarchy_expand("/Project/999999999")
        assert error.value.status == 400

    def test_hides_every_row_of_a_level_whose_grouping_field_has_no_rows(self) -> None:
        c = client()
        shots = c.hierarchy_expand("/Project/72/Shot")
        # One `empty` child, no bucket among the children, and no path of its own
        # (064_hierarchy_expand_buckets).
        assert [n.ref.kind for n in shots.children] == ["empty"]
        assert shots.children[0].path == "/Project/72/Shot"

    def test_answers_the_bucket_path_at_both_its_spellings(self) -> None:
        c = client()
        long = c.hierarchy_expand("/Project/72/Shot/sg_sequence/Sequence/__none__")
        short = c.hierarchy_expand("/Project/72/Shot/sg_sequence/__none__")
        assert [n.label for n in long.children] == ["nf_0010", "nf_0020", "nf_0030"]
        assert [n.label for n in short.children] == [n.label for n in long.children]

    def test_names_the_grouping_field_a_level_takes_in_the_400_it_answers_a_bogus_one(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.hierarchy_expand("/Project/72/Shot/nope")
        assert error.value.status == 400
        assert str(error.value) == "Unexpected field name in path: nope (expecting sg_sequence)"

    def test_places_an_ungrouped_row_under_the_bucket_the_search_endpoint_spells(self) -> None:
        c = client()
        found = c.hierarchy_search("/Project/72", EntityRef(type="Shot", id=892))[0]
        assert found.incremental_path == [
            "/Project/72",
            "/Project/72/Shot",
            "/Project/72/Shot/sg_sequence/__none__",
            "/Project/72/Shot/sg_sequence/__none__/id/892",
        ]


class TestSummarize:
    def test_counts_without_paging_rows(self) -> None:
        c = client()
        all_rows = c.search("Version", SearchOptions(fields=["id"], page={"size": 500}))
        summary = c.summarize("Version")
        assert summary.summaries["id"] == len(all_rows.data)
        assert summary.groups == []

    def test_counts_the_rows_a_filter_matches(self) -> None:
        c = client()
        filters: WireGroup = {"logical_operator": "and", "conditions": [["sg_status_list", "is", "ip"]]}
        rows = c.search("Version", SearchOptions(filters=filters, fields=["id"], page={"size": 500}))
        summary = c.summarize("Version", SummarizeOptions(filters=filters))
        assert summary.summaries["id"] == len(rows.data)

    def test_returns_one_group_per_distinct_value_keyed_on_group_value(self) -> None:
        c = client()
        summary = c.summarize("Version", SummarizeOptions(grouping=[SummaryGrouping(field="sg_status_list")]))
        assert len(summary.groups) > 1
        total = sum(g.summaries.get("id", 0) for g in summary.groups)
        assert total == summary.summaries["id"]
        for group in summary.groups:
            assert isinstance(group.group_value, str)

    def test_groups_an_entity_field_on_the_reference_with_the_name_as_the_label(self) -> None:
        c = client()
        summary = c.summarize("Note", SummarizeOptions(grouping=[SummaryGrouping(field="user")]))
        assert len(summary.groups) > 0
        for group in summary.groups:
            assert group.group_value["type"] == "HumanUser"
            assert isinstance(group.group_value["id"], int)
            assert group.group_value["name"] == group.group_name
            assert group.group_value["valid"] == "valid"
            assert group.group_name != ""
        links = c.summarize("Note", SummarizeOptions(grouping=[SummaryGrouping(field="addressings_to")]))
        assert len(links.groups) > 0
        for group in links.groups:
            assert len(group.group_value) == 1
            assert group.group_value[0]["type"] == "HumanUser"
            assert group.group_value[0]["name"] == group.group_name
            assert group.group_value[0]["valid"] == "valid"

    def test_refuses_to_group_the_read_state_and_an_image(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as one:
            c.summarize("Note", SummarizeOptions(grouping=[SummaryGrouping(field="read_by_current_user")]))
        assert one.value.status == 400
        assert str(one.value) == "Grouping is not allowed for field Note.read_by_current_user."
        with pytest.raises(SgApiError) as two:
            c.summarize("Version", SummarizeOptions(grouping=[SummaryGrouping(field="image")]))
        assert two.value.status == 400


class TestANoteThread:
    def test_returns_the_note_its_attachments_and_its_replies_in_time_order(self) -> None:
        c = client()
        thread = c.thread_contents(11030)
        assert [(row.type, row.id) for row in thread] == [
            ("Note", 11030),
            ("Attachment", 2626),
            ("Reply", 610),
            ("Attachment", 2627),
            ("Reply", 611),
        ]
        times = [str(row.created_at) for row in thread]
        assert sorted(times) == times

    def test_names_the_author_under_created_by_on_a_note_and_an_attachment_and_under_user_on_a_reply(
        self,
    ) -> None:
        thread = client().thread_contents(11030)
        note, attachment, reply = thread[0], thread[1], thread[2]
        assert note.fields["created_by"] == note.author
        assert "user" not in note.fields
        assert attachment.fields["created_by"] == attachment.author
        assert reply.fields["user"] == reply.author
        assert "created_by" not in reply.fields
        # Only a Reply's author hash carries the presigned avatar.
        assert reply.author.image.startswith("https://")
        assert note.author.image is None

    def test_carries_no_content_on_an_attachment_row(self) -> None:
        thread = client().thread_contents(11030)
        attachment = next(row for row in thread if row.type == "Attachment")
        assert attachment.content is None
        assert "content" not in attachment.fields

    def test_widens_a_note_and_an_attachment_and_ignores_the_reply_entry(self) -> None:
        thread = client().thread_contents(11030, {
            "Note": ["subject", "sg_status_list"],
            "Attachment": ["filename"],
            "Reply": ["updated_at"],
        })
        assert thread[0].fields["subject"] == "Key light reads flat"
        assert thread[0].fields["sg_status_list"] == "opn"
        assert thread[1].fields["filename"] == "key_light_ref.png"
        assert "updated_at" not in thread[2].fields

    def test_answers_one_row_for_a_note_with_no_replies_and_404s_on_an_unknown_note(self) -> None:
        c = client()
        alone = c.thread_contents(11032)
        assert [row.type for row in alone] == ["Note"]
        with pytest.raises(SgApiError) as error:
            c.thread_contents(999999999)
        assert error.value.status == 404

    def test_reads_read_by_current_user_as_a_code_and_types_it_as_a_list(self) -> None:
        c = client()
        fields = c.fields("Note")
        assert fields["read_by_current_user"].data_type == "list"
        assert fields["read_by_current_user"].valid_values == ["unread", "read"]
        note = c.search(
            "Note",
            SearchOptions(filters=only("id", "is", 11030), fields=["read_by_current_user"]),
        ).data[0]
        assert note.values["read_by_current_user"] == "unread"

    def test_has_no_project_field_on_reply(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.search("Reply", SearchOptions(filters=only("project", "is", {"type": "Project", "id": 70})))
        assert error.value.status == 400
        assert str(error.value) == "API read() Reply.project doesn't exist."


class TestTheEventLog:
    def test_answers_newest_first_by_id(self) -> None:
        log = client().event_log(EventLogOptions(page={"size": 10}))
        entry_ids = [entry.id for entry in log.data]
        assert len(entry_ids) == 10
        assert sorted(entry_ids, reverse=True) == entry_ids

    def test_narrows_on_entity_event_type_and_attribute_name_and_reads_the_values_out_of_meta(self) -> None:
        c = client()
        shot = c.search("Shot", SearchOptions(fields=["sg_status_list"], page={"size": 1})).data[0]
        log = c.event_log(EventLogOptions(
            entity=EntityRef(type="Shot", id=shot.id),
            event_type="Shotgun_Shot_Change",
            attribute_name="sg_status_list",
        ))
        assert len(log.data) == 1
        entry = log.data[0]
        assert entry.entity.type == "Shot"
        assert entry.entity.id == shot.id
        assert entry.meta["type"] == "attribute_change"
        assert entry.old_value == "wtg"
        # The newest entry's new_value is what the row holds now, which is what makes a
        # restore safe.
        assert entry.new_value == shot.values["sg_status_list"]

    def test_keeps_an_event_whose_target_is_deleted_with_entity_null_and_meta_naming_it(self) -> None:
        log = client().event_log(
            EventLogOptions(event_type="Shotgun_Shot_Change", page={"size": 50})
        )
        orphan = next(entry for entry in log.data if entry.entity is None)
        assert orphan.meta["entity_id"] == 9001
        assert orphan.new_value == "omt"

    def test_cuts_on_project_and_on_a_date_window(self) -> None:
        c = client()
        all_rows = c.event_log(EventLogOptions(page={"size": 100}))
        mine = c.event_log(EventLogOptions(project_id=71, page={"size": 100}))
        assert len(mine.data) > 0
        assert len(mine.data) < len(all_rows.data)
        for entry in mine.data:
            assert entry.project.id == 71

        recent = c.event_log(EventLogOptions(since="2026-01-02T00:00:00Z", page={"size": 100}))
        assert len(recent.data) > 0
        for entry in recent.data:
            assert str(entry.created_at) > "2026-01-02T00:00:00Z"

    def test_refuses_a_filter_on_meta_the_field_that_holds_the_answer(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.search("EventLogEntry", SearchOptions(filters=only("meta", "is", None)))
        assert error.value.status == 400
        assert str(error.value) == (
            "API read() EventLogEntry.meta's 'serializable' data type cannot be used in a filter."
        )


class TestWhatAPersonFollows:
    def test_answers_a_type_and_an_id_per_row_unpaged(self) -> None:
        rows = client().following(20)
        assert len(rows) > 0
        for row in rows:
            # A follow is a type and an id and nothing else: no name comes back.
            assert row.name is None
            assert isinstance(row.type, str)
            assert isinstance(row.id, int)
        assert {row.type for row in rows} == {"Note", "Task"}

    def test_takes_the_schema_name_and_the_plural_alike_and_cuts_on_the_project(self) -> None:
        c = client()
        notes = c.following(20, FollowingOptions(entity="Note"))
        assert c.following(20, FollowingOptions(entity="notes")) == notes
        assert all(row.type == "Note" for row in notes)
        # A type nobody follows is an empty list, not an error.
        assert c.following(20, FollowingOptions(entity="shots")) == []
        in_project = c.following(20, FollowingOptions(project_id=70))
        assert len(in_project) > 0
        assert len(in_project) <= len(c.following(20))

    def test_404s_on_a_user_who_is_not_a_human_user_and_on_an_unknown_project(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as one:
            c.following(90)
        assert one.value.status == 404
        with pytest.raises(SgApiError) as two:
            c.following(20, FollowingOptions(project_id=999999999))
        assert two.value.status == 404
        with pytest.raises(SgApiError) as three:
            c.following(20, FollowingOptions(entity="nonsense"))
        assert three.value.status == 400


class TestCreate:
    def test_refuses_a_project_scoped_create_with_no_project_and_echoes_the_body(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.create("Note", {"subject": "No project"})
        assert error.value.status == 400
        assert str(error.value) == 'API create() missing \'project\' attribute: {"subject":"No project"}'

    def test_fills_the_identity_field_the_server_generates_and_leaves_a_note_titleless(self) -> None:
        c = client()
        shot = c.create("Shot", {"project": {"type": "Project", "id": 70}})
        assert shot.values["code"] == f"New Shot {shot.id}"
        # A Note's subject is optional and is not auto-filled (entity_types/Note).
        note = c.create("Note", {"project": {"type": "Project", "id": 70}})
        assert note.values["subject"] is None
        assert note.values["cached_display_name"] == ""
        # The defaults come back on the answer, so they are read off it (entity_types/Note).
        assert note.values["sg_status_list"] == "opn"
        assert note.values["read_by_current_user"] == "unread"
        assert note.values["publish_status"] == "published"

    def test_stores_an_authored_created_at_and_updated_at_and_has_no_updated_at_on_a_reply(self) -> None:
        c = client()
        project = {"type": "Project", "id": 70}
        # Both are flagged `editable: false` and both are taken by a create (070_authored_timestamps).
        dated = c.create("Note", {
            "project": project,
            "subject": "Imported",
            "created_at": "2019-03-04T05:06:07Z",
            "updated_at": "2020-01-02T03:04:05Z",
        })
        assert dated.values["created_at"] == "2019-03-04T05:06:07Z"
        assert dated.values["updated_at"] == "2020-01-02T03:04:05Z"
        with pytest.raises(SgApiError) as error:
            c.create("Reply", {
                "entity": {"type": "Note", "id": 11030},
                "updated_at": "2020-01-02T03:04:05Z",
            })
        assert error.value.status == 400
        assert str(error.value) == "API create() Reply.updated_at doesn't exist."

    def test_takes_this_file_on_an_attachment_create_and_never_after(self) -> None:
        c = client()
        project = {"type": "Project", "id": 70}
        link = {"url": "https://example.com/probe.png", "name": "probe.png"}
        made = c.create("Attachment", {"project": project, "this_file": link})
        assert made.values["this_file"] == link
        with pytest.raises(SgApiError) as error:
            c.update("Attachment", made.id, {"this_file": link})
        assert error.value.status == 400
        assert str(error.value) == "API update() Attachment.this_file is editable on create only."

    def test_refuses_a_bare_id_where_an_entity_link_hash_is_required(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as error:
            c.create("Reply", {"entity": 11030, "content": "On it."})
        assert error.value.status == 400
        assert re.match(
            r"^API create\(\) Reply\.entity expected \[Hash, .* but got Integer: 11030$", str(error.value)
        )

    def test_puts_a_reply_in_the_thread_it_names_and_keeps_one_that_names_nothing(self) -> None:
        c = client()
        reply = c.create("Reply", {"entity": {"type": "Note", "id": 11030}, "content": "On it."})
        assert reply.values["entity"]["type"] == "Note"
        assert reply.values["entity"]["id"] == 11030
        thread = c.thread_contents(11030)
        assert thread[-1].id == reply.id
        # A Reply created without `entity` is legal and is permanent litter (entity_types/Reply).
        orphan = c.create("Reply", {"content": "Nowhere."})
        assert orphan.values["entity"] is None

    def test_refuses_an_unknown_field_a_read_only_one_and_an_empty_identity(self) -> None:
        c = client()
        project = {"type": "Project", "id": 70}
        with pytest.raises(SgApiError) as one:
            c.create("Note", {"project": project, "nope": 1})
        assert str(one.value) == "API create() Note.nope doesn't exist."
        with pytest.raises(SgApiError) as two:
            c.create("Attachment", {"project": project, "filename": "probe.png"})
        assert str(two.value) == "API create() Attachment.filename is read only."
        with pytest.raises(SgApiError) as three:
            c.create("Shot", {"project": project, "code": ""})
        assert str(three.value) == (
            "Create failed for [Shot]: Cannot set identifier field to empty. (Shot)"
        )


BYTES = bytes([137, 80, 78, 71])


class TestUpload:
    def test_puts_an_attachment_on_the_row_and_names_the_kind_after_the_field(self) -> None:
        c = client()
        before = len(c.rows_of("Attachment"))
        result = c.upload(
            "Note", 11030, UploadFile(filename="screenshot.png", data=BYTES, field="attachments")
        )
        assert result.upload_type == "Attachment"
        assert result.upload_info["original_filename"] == "screenshot.png"
        assert len(c.rows_of("Attachment")) == before + 1
        thread = c.thread_contents(11030)
        made = c.rows_of("Attachment")[before]["id"]
        assert made in [row.fields["id"] for row in thread if row.type == "Attachment"]

    def test_is_a_thumbnail_on_image_and_the_field_reads_a_placeholder_until_the_transcode_lands(
        self,
    ) -> None:
        c = client()
        result = c.upload("Shot", 862, UploadFile(filename="frame.png", data=BYTES, field="image"))
        assert result.upload_type == "Thumbnail"
        shot = c.search("Shot", SearchOptions(filters=only("id", "is", 862), fields=["image"])).data[0]
        # Absolute, on the site root (013_upload_media).
        assert re.match(r"^https://[^/]+/images/status/transient/", str(shot.values["image"]))

    def test_leaves_the_size_and_the_extension_unset_as_an_uploaded_row_reads_them(self) -> None:
        c = client()
        c.upload("Version", 17055, UploadFile(filename="workflow.json", data=BYTES))
        attachment = c.rows_of("Attachment")[-1]
        assert attachment["file_size"] is None
        assert attachment["file_extension"] is None
        # Not one of the four values its own `valid_values` declares (entity_types/Attachment).
        assert attachment["processing_status"] == "thumbnail_pending_us"

    def test_404s_on_a_field_the_type_does_not_have_and_on_a_row_that_is_not_there(self) -> None:
        c = client()
        with pytest.raises(SgApiError) as one:
            c.upload("Shot", 862, UploadFile(filename="x.png", data=BYTES, field="attachments"))
        assert one.value.status == 404
        assert str(one.value) == "Field 'Shot.attachments' does not exist."
        with pytest.raises(SgApiError) as two:
            c.upload("Shot", 999999, UploadFile(filename="x.png", data=BYTES))
        assert two.value.status == 404
