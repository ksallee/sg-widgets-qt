"""Port of the status blocks of `packages/core/test/status.test.ts`."""
from __future__ import annotations

import dataclasses
from typing import Any

from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import (
    CellGlyph,
    DotGlyph,
    HtmlGlyph,
    HtmlIcon,
    ImageGlyph,
    ImageIcon,
    ImageMapIcon,
    NoGlyph,
    Rgb,
    SpriteGlyph,
    StatusOption,
    StatusPaint,
    StatusRecord,
    foreground_for,
    intersect_statuses,
    parse_bg_color,
    status_glyph,
    status_paint,
    usable_statuses,
)
from sg_widgets_core.status_icons import STOCK_ICON_CELLS


def status_field(**overrides: Any) -> FieldSchema:
    """A status field schema; only the value lists are under test."""
    return FieldSchema(
        name="sg_status_list",
        display_name="Status",
        entity_type="Version",
        data_type="status_list",
        editable=True,
        mandatory=False,
        unique=False,
        **overrides,
    )


def status_record(**overrides: Any) -> StatusRecord:
    """A status row; only the colour and the icon are under test."""
    return StatusRecord(id=1, code="rev", name="Pending Review", **overrides)


class TestUsableStatuses:
    field = status_field(
        valid_values=["na", "rev", "vwd", "apr", "fin", "part"],
        hidden_values=["part", "blk"],
        display_values={"rev": "Pending Review", "fin": "Final"},
    )

    def test_subtracts_hidden_from_valid_and_tolerates_hidden_codes_outside_valid(self) -> None:
        assert [s.code for s in usable_statuses(self.field)] == ["na", "rev", "vwd", "apr", "fin"]
        assert usable_statuses(self.field)[1] == StatusOption(code="rev", label="Pending Review")

    def test_intersects_across_projects_keeping_the_first_order(self) -> None:
        other = dataclasses.replace(self.field, hidden_values=["na", "vwd"])
        assert [s.code for s in intersect_statuses([self.field, other])] == ["rev", "apr", "fin"]


class TestColours:
    def test_parses_decimal_rgb_triples_and_rejects_hex(self) -> None:
        assert parse_bg_color("25,118,27") == Rgb(r=25, g=118, b=27)
        assert parse_bg_color("#19761b") is None
        assert foreground_for(Rgb(r=25, g=118, b=27)) == "white"
        assert foreground_for(Rgb(r=240, g=240, b=240)) == "black"

    def test_paints_a_status_in_its_own_colour_with_a_readable_ink_on_it(self) -> None:
        assert status_paint(status_record(bg_color="25,118,27")) == StatusPaint(
            background="rgb(25 118 27)", foreground="#fff"
        )
        paint = status_paint(status_record(bg_color="240,240,240"))
        assert paint is not None and paint.foreground == "#000"
        assert status_paint(status_record(bg_color=None)) is None
        assert status_paint(None) is None


class TestStatusGlyph:
    def test_answers_one_drawing_per_display_type_and_a_dot_for_a_key_it_cannot_serve(self) -> None:
        assert status_glyph(None) == NoGlyph()
        assert status_glyph(status_record(icon=None)) == NoGlyph()
        assert status_glyph(status_record(icon=HtmlIcon(html="<b>Active</b>"))) == HtmlGlyph(html="<b>Active</b>")
        assert status_glyph(status_record(icon=ImageIcon(data_url="data:image/png;base64,AA"))) == ImageGlyph(
            src="data:image/png;base64,AA"
        )

        bundled = status_glyph(status_record(icon=ImageMapIcon(image_map_key="icon_apr")))
        assert bundled.kind == "cell"
        if isinstance(bundled, CellGlyph):
            assert bundled.cell == STOCK_ICON_CELLS["icon_apr"]
            assert bundled.src.startswith("data:image/png;base64,")

        key = "icon_x_thin_white"
        served = status_glyph(status_record(icon=ImageMapIcon(image_map_key=key)), "https://studio.example.com/")
        assert served.kind == "sprite"
        if isinstance(served, SpriteGlyph):
            cell = STOCK_ICON_CELLS[key]
            assert served.style["backgroundPosition"] == f"-{cell.x}px -{cell.y}px"
        assert status_glyph(status_record(icon=ImageMapIcon(image_map_key=key))) == DotGlyph(image_map_key=key)
