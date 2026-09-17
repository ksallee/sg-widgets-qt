"""Statuses.

Usable statuses for a project are `valid_values` minus `hidden_values`, read with
`project_id`. REST does not enforce `hidden_values` on write, so the subtraction is
the client's job. A row may hold a code outside the usable set; that is a legal
stored value, not corruption (probe 009, field_types/status_list).
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Literal, Union

from .schema import FieldSchema
from .status_icons import SpriteCell, sprite_style, stock_icon_source

__all__ = [
    "CellGlyph",
    "DotGlyph",
    "HtmlGlyph",
    "HtmlIcon",
    "ImageGlyph",
    "ImageIcon",
    "ImageMapIcon",
    "NoGlyph",
    "Rgb",
    "SpriteGlyph",
    "StatusGlyph",
    "StatusIcon",
    "StatusOption",
    "StatusPaint",
    "StatusRecord",
    "foreground_for",
    "intersect_statuses",
    "parse_bg_color",
    "relative_luminance",
    "rgb_to_css",
    "status_glyph",
    "status_label",
    "status_paint",
    "usable_statuses",
]


@dataclass
class StatusOption:
    code: str
    label: str


def usable_statuses(field: FieldSchema) -> list[StatusOption]:
    """Codes a picker should offer for the project the schema was read with."""
    hidden = set(field.hidden_values or [])
    return [
        StatusOption(code=code, label=status_label(field, code))
        for code in (field.valid_values or [])
        if code not in hidden
    ]


def intersect_statuses(fields: list[FieldSchema]) -> list[StatusOption]:
    """Codes usable in every one of several projects: the intersection of their usable sets, in the first schema's order."""
    if not fields:
        return []
    first, rest = fields[0], fields[1:]
    others = [{s.code for s in usable_statuses(f)} for f in rest]
    return [s for s in usable_statuses(first) if all(s.code in other for other in others)]


def status_label(field: FieldSchema, code: str) -> str:
    return (field.display_values or {}).get(code, code)


@dataclass
class ImageMapIcon:
    """An icon named by its `image_map_key` in the stock sprite."""

    image_map_key: str
    display_type: Literal["image_map"] = "image_map"


@dataclass
class ImageIcon:
    """An icon the site holds as its own image."""

    data_url: str
    display_type: Literal["image"] = "image"


@dataclass
class HtmlIcon:
    """An icon the site draws as markup."""

    html: str
    display_type: Literal["html"] = "html"


StatusIcon = Union[ImageMapIcon, ImageIcon, HtmlIcon]
"""Icon entity. `display_type` picks one of three renderings (probe 010)."""


@dataclass
class StatusRecord:
    """Status entity as `GET /entity/statuses?fields=code,name,bg_color,icon` returns it, flattened.

    `bg_color` is comma-separated decimal RGB (`"25,118,27"`), never hex.
    """

    id: int
    code: str
    name: str
    bg_color: str | None = None
    icon: StatusIcon | None = None


@dataclass
class Rgb:
    r: int
    g: int
    b: int


def parse_bg_color(value: str | None) -> Rgb | None:
    """Parse `"25,118,27"` into channels. Returns None for anything else, including hex."""
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 3:
        return None
    channels: list[int] = []
    for p in parts:
        try:
            n = float(p.strip())
        except ValueError:
            return None
        if not n.is_integer() or n < 0 or n > 255:
            return None
        channels.append(int(n))
    return Rgb(r=channels[0], g=channels[1], b=channels[2])


def rgb_to_css(rgb: Rgb) -> str:
    return f"rgb({rgb.r} {rgb.g} {rgb.b})"


def relative_luminance(rgb: Rgb) -> float:
    """WCAG relative luminance, for choosing a readable foreground on a status badge."""

    def lin(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(rgb.r) + 0.7152 * lin(rgb.g) + 0.0722 * lin(rgb.b)


def foreground_for(rgb: Rgb) -> Literal["black", "white"]:
    """Black or white, whichever contrasts more with the given colour."""
    return "black" if relative_luminance(rgb) > 0.4 else "white"


@dataclass
class StatusPaint:
    """What a status paints with: its own `bg_color` and a readable ink on it."""

    background: str
    foreground: str


def status_paint(status: StatusRecord | None) -> StatusPaint | None:
    """The paint of a status. None when it carries no colour, which is every option of a plain `list` field."""
    rgb = parse_bg_color(status.bg_color if status is not None else None)
    if not rgb:
        return None
    return StatusPaint(background=rgb_to_css(rgb), foreground="#000" if foreground_for(rgb) == "black" else "#fff")


@dataclass
class NoGlyph:
    """A status naming no icon at all."""

    kind: Literal["none"] = "none"


@dataclass
class HtmlGlyph:
    """The label itself, so it replaces the text rather than preceding it."""

    html: str
    kind: Literal["html"] = "html"


@dataclass
class ImageGlyph:
    """A self-contained data URI."""

    src: str
    kind: Literal["image"] = "image"


@dataclass
class CellGlyph:
    """A bundled sprite cell, sized by that cell."""

    image_map_key: str
    src: str
    cell: SpriteCell
    kind: Literal["cell"] = "cell"


@dataclass
class SpriteGlyph:
    """A sprite cell the site serves, sized by that cell."""

    image_map_key: str
    style: dict[str, str] = dc_field(default_factory=dict)
    kind: Literal["sprite"] = "sprite"


@dataclass
class DotGlyph:
    """Stands in for a stock key this client has no cell for."""

    image_map_key: str
    kind: Literal["dot"] = "dot"


StatusGlyph = Union[NoGlyph, HtmlGlyph, ImageGlyph, CellGlyph, SpriteGlyph, DotGlyph]
"""What a status draws as its glyph (010_status_icons)."""


def status_glyph(status: StatusRecord | None, site_url: str | None = None) -> StatusGlyph:
    """The glyph a status draws, from its icon and whichever sprite can serve it."""
    icon = status.icon if status is not None else None
    if not icon:
        return NoGlyph()
    if icon.display_type == "html":
        return HtmlGlyph(html=icon.html)
    if icon.display_type == "image":
        return ImageGlyph(src=icon.data_url)
    source = stock_icon_source(icon.image_map_key, site_url)
    if source.kind == "data":
        return CellGlyph(image_map_key=icon.image_map_key, src=source.src, cell=source.cell)
    if source.kind == "sprite":
        return SpriteGlyph(image_map_key=icon.image_map_key, style=sprite_style(source))
    return DotGlyph(image_map_key=icon.image_map_key)
