"""Port of `packages/core/test/status-service.test.ts`."""
from __future__ import annotations

import pytest

from sg_widgets_core.client import SgApiError
from sg_widgets_core.status import ImageMapIcon, Rgb, parse_bg_color
from sg_widgets_core.status_service import create_status_service

from .fake_client import CountingClient, FakeClient, concurrently


def status_reads(client: CountingClient) -> int:
    return len([call for call in client.calls if call == "statuses"])


class TestTheStatusTable:
    def test_reads_the_site_table_once_however_many_widgets_ask(self) -> None:
        inner = FakeClient()
        client = CountingClient(inner)
        statuses = create_status_service(client)
        _, errors = concurrently(inner, statuses.all)
        assert errors == [None, None]
        statuses.record("apr")
        statuses.by_code()
        assert status_reads(client) == 1

    def test_indexes_by_code_not_by_entity_type(self) -> None:
        statuses = create_status_service(FakeClient())
        apr = statuses.record("apr")
        assert apr is not None
        assert apr.code == "apr"
        assert apr.name == "Approved"
        # The same row answers for every type that offers the code.
        assert statuses.record("ip") is statuses.by_code()["ip"]

    def test_carries_the_colour_as_decimal_rgb_and_an_icon(self) -> None:
        statuses = create_status_service(FakeClient())
        apr = statuses.record("apr")
        assert apr is not None
        assert apr.bg_color == "25,118,27"
        assert parse_bg_color(apr.bg_color) == Rgb(r=25, g=118, b=27)
        assert apr.icon == ImageMapIcon(image_map_key="icon_apr")

    def test_has_no_record_for_a_plain_list_value(self) -> None:
        statuses = create_status_service(FakeClient())
        # Project.sg_status is a `list`: no Status row stands behind its values.
        assert statuses.record("Bidding") is None

    def test_does_not_remember_a_failure_and_forgets_on_invalidate(self) -> None:
        client = FakeClient()
        statuses = create_status_service(client)
        client.fail_next(503, "Service Unavailable")
        with pytest.raises(SgApiError):
            statuses.all()
        assert len(statuses.all()) > 0

        counted = CountingClient(client)
        second = create_status_service(counted)
        second.all()
        second.invalidate()
        second.all()
        assert status_reads(counted) == 2
