"""Port of `packages/core/test/context.test.ts`."""
from __future__ import annotations

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.context import (
    SgContextOptions,
    SitePreferences,
    context_from_client,
    create_sg_context,
    preferences_of,
)
from sg_widgets_core.render import FieldTextOptions

from .fake_client import CountingClient, FakeClient


class TestTheContext:
    def test_caches_rows_schema_and_the_status_table_behind_one_object(self) -> None:
        client = CountingClient(FakeClient())
        sg = create_sg_context(client)
        sg.client.search("Shot", SearchOptions(fields=["code"]))
        sg.client.search("Shot", SearchOptions(fields=["code"]))
        sg.schema.fields("Shot")
        sg.schema.status_field("Shot")
        sg.statuses.all()
        sg.statuses.record("apr")
        assert client.calls == ["search Shot", "fields Shot -", "statuses"]

    def test_drops_everything_on_invalidate(self) -> None:
        client = CountingClient(FakeClient())
        sg = create_sg_context(client)
        sg.client.search("Shot", SearchOptions(fields=["code"]))
        sg.schema.fields("Shot")
        sg.statuses.all()
        sg.invalidate()
        sg.client.search("Shot", SearchOptions(fields=["code"]))
        sg.schema.fields("Shot")
        sg.statuses.all()
        assert client.calls == [
            "search Shot", "fields Shot -", "statuses",
            "search Shot", "fields Shot -", "statuses",
        ]

    def test_keeps_schema_past_the_row_ttl(self) -> None:
        client = CountingClient(FakeClient())
        # Rows go stale at once; schema keeps its own hour.
        sg = create_sg_context(client, SgContextOptions(ttl_ms=0))
        sg.client.search("Shot", SearchOptions(fields=["code"]))
        sg.client.search("Shot", SearchOptions(fields=["code"]))
        sg.schema.fields("Shot")
        sg.schema.fields("Shot")
        assert client.calls == ["search Shot", "search Shot", "fields Shot -"]

    def test_carries_the_site_preferences_a_formatter_takes(self) -> None:
        # hours_per_day comes from GET /preferences; nothing on the site names a frame rate
        # (field_types/duration, field_types/timecode).
        sg = create_sg_context(FakeClient(), SgContextOptions(
            hours_per_day=8, locale="en-GB", time_zone="Europe/Paris", frame_rate=23.976,
        ))
        assert sg.preferences == SitePreferences(
            hours_per_day=8, locale="en-GB", time_zone="Europe/Paris", frame_rate=23.976
        )
        assert preferences_of(sg) == FieldTextOptions(
            hours_per_day=8, locale="en-GB", time_zone="Europe/Paris", frame_rate=23.976
        )

    def test_has_no_preferences_when_the_app_named_none(self) -> None:
        sg = create_sg_context(FakeClient())
        assert sg.preferences == SitePreferences()
        assert preferences_of(sg) == FieldTextOptions()
        assert preferences_of(None) == FieldTextOptions()

    def test_answers_the_widgets_a_picker_needs_from_one_place(self) -> None:
        sg = create_sg_context(FakeClient())
        options = sg.schema.status_options("Shot", 70)
        first = options[0]
        assert first.code == "wtg"
        record = sg.statuses.record(first.code)
        assert record is not None
        assert record.bg_color == "178,178,178"


class TestAContextFromABareClient:
    def test_builds_one_context_per_client_so_two_widgets_share_the_caches(self) -> None:
        client = CountingClient(FakeClient())
        first = context_from_client(client, SgContextOptions(hours_per_day=8))
        second = context_from_client(client)
        assert second is first
        assert second.preferences == SitePreferences(hours_per_day=8)
        first.schema.fields("Shot")
        second.schema.fields("Shot")
        first.statuses.all()
        second.statuses.all()
        assert client.calls == ["fields Shot -", "statuses"]

    def test_gives_another_client_its_own_context(self) -> None:
        one = context_from_client(FakeClient())
        other = context_from_client(FakeClient())
        assert other is not one
