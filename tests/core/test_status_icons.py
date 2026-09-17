"""Port of `packages/core/test/status-icons.test.ts`."""
from __future__ import annotations

from sg_widgets_core.status_icons import (
    NATIVE_STATUSES,
    STOCK_ICON_CELLS,
    STOCK_ICON_DATA_URLS,
    STOCK_ICON_KEYS,
    is_native_status,
    sprite_style,
    stock_icon_source,
)


class TestNativeStatuses:
    def test_ships_19_codes_six_of_them_system_locked(self) -> None:
        assert len(NATIVE_STATUSES) == 19
        assert [s.code for s in NATIVE_STATUSES if s.system] == ["act", "dis", "ip", "na", "cfrm", "pndng"]
        assert is_native_status("apr") is True
        assert is_native_status("pndl") is False

    def test_bundles_a_data_url_for_every_stock_status_icon_shipped_ones_included(self) -> None:
        assert len(STOCK_ICON_KEYS) == 94
        for k in STOCK_ICON_KEYS:
            assert STOCK_ICON_DATA_URLS[k].startswith("data:image/png;base64,")
        for s in NATIVE_STATUSES:
            if s.image_map_key:
                assert s.image_map_key in STOCK_ICON_KEYS


class TestStockIconSource:
    def test_prefers_the_bundle_then_the_site_sprite_then_nothing(self) -> None:
        assert stock_icon_source("icon_apr").kind == "data"
        assert stock_icon_source("icon_trophy").kind == "data"
        assert stock_icon_source("icon_x_thin_white").kind == "none"
        s = stock_icon_source("icon_x_thin_white", "https://studio.example.com/")
        assert s.kind == "sprite"
        if s.kind == "sprite":
            assert s.src == "https://studio.example.com/images/sg_icon_image_map.png"
            cell = STOCK_ICON_CELLS["icon_x_thin_white"]
            assert sprite_style(s)["backgroundPosition"] == f"-{cell.x}px -{cell.y}px"
        assert stock_icon_source("icon_nope", "https://x").kind == "none"
        assert stock_icon_source(None).kind == "none"
