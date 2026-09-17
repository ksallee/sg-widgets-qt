"""One attribute value, drawn by its data type.

Ported from `packages/react/src/registry/sg/components/field-value.tsx`. The rendering is chosen
by `data_type` through core's `render_kind_for`, and the value shapes are the ones the API
returns: an entity link is a `{type, id, name}` hash, a status is a bare code, a float comes back
quoted, a `url` is a map whose keys depend on `link_type`, and a date carries no zone
(`findings/field_types/*`).

Two faces read the same plan. `FieldValue` is the standalone widget, which composes EntityChip,
StatusBadge and Thumbnail where one of those is what the value is. `paint_field_value` and
`field_value_size_hint` draw the same value into a rectangle, so a table, a grid and a grouped
list draw their cells from a delegate with no widget per cell.

Upstream's dependency graph runs field-value to entity-chip to entity-card, never back, so nothing
here reaches for EntityCard: a card draws its own values.

    FieldValue(value=row.values["sg_status_list"], data_type="status_list", statuses=table)
    paint_field_value(painter, cell, value, column, FieldValueOptions(theme=theme_of(view)))
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Callable, Union

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.collection import CollectionColumn
from sg_widgets_core.context import SgContext, context_from_client, preferences_of
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.render import (
    COLOR_SENTINEL,
    FieldTextOptions,
    UrlLinkInfo,
    field_text,
    is_empty_value,
    render_kind_for,
    url_link,
)
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import Rgb, StatusRecord, parse_bg_color

from ..icons import paint_icon
from ..images import ImageLoader, image_loader
from ..primitives.base import (
    CHIP_GLYPH,
    CHIP_HEIGHT,
    CHIP_PAD,
    CHIP_SPACING,
    CHIP_TEXT,
    THUMB_SIZE,
    ThemedWidget,
    elide,
    fill_round_rect,
    painter_for,
    text_width,
)
from ..primitives.checkbox import (
    RING_ROOM,
    SWITCH_HEIGHT,
    SWITCH_INSET,
    SWITCH_THUMB,
    SWITCH_WIDTH,
    Switch,
)
from ..theme import Theme, theme_for, with_alpha
from .entity_chip import ENTITY_CHIP_VARIANT_VALUES, EntityChip
from .entity_glyphs import entity_glyph
from .status_badge import StatusBadge
from .status_glyph import StatusGlyphSource
from .thumbnail import Thumbnail

__all__ = [
    "CHIP_GAP",
    "FIELD_VALUE_CHIP",
    "FIELD_VALUE_DENSITY_VALUES",
    "SWATCH",
    "FieldValue",
    "FieldValueOptions",
    "FieldValuePlan",
    "field_value_size_hint",
    "paint_field_value",
    "plan_field_value",
    "warm_status_glyph",
]

#: The density of the collection around the value.
FIELD_VALUE_DENSITY_VALUES: tuple[str, ...] = ("compact", "default")

#: A chip or a badge sits one step under the row it is in (`docs/design-rules.md` rule 3).
FIELD_VALUE_CHIP: dict[str, str] = {"compact": "xs", "default": "sm"}

#: The body step, and the metadata step a colour, an id and the empty marker wear (rule 6).
VALUE_TEXT = 14
META_TEXT = 12

#: The colour swatch, and the room between an inline glyph and its text (rule 2).
SWATCH = 16
GLYPH_GAP = 6

#: Between the chips of a multi-entity value, across and down, which is rule 2's item gap.
CHIP_GAP = 8

#: The glyph the placeholder of a picture that has not landed draws at.
PLACEHOLDER_GLYPH = 16

#: The picture an `image` value draws at, the bottom of the thumbnail ladder.
IMAGE_STEP = "sm"

ColumnLike = Union[CollectionColumn, str]
"""What names the type of a value: a resolved column, or a bare `data_type`."""


@dataclass
class FieldValuePlan:
    """What one value draws, settled once and read by both faces."""

    kind: str
    data_type: str
    #: The one line of text, where the rendering has one.
    text: str = ""
    #: The whole value, for the tooltip. Empty where a rendering carries no tooltip.
    tooltip: str = ""
    #: The rows an `entity`, `multi_entity` or `tag_list` value links to.
    refs: list[EntityRef] = dc_field(default_factory=list)
    link: UrlLinkInfo | None = None
    rgb: Rgb | None = None
    #: True for `Task.color` holding the `pipeline_step` token (field_types/color).
    sentinel: bool = False
    checked: bool = False
    image: str | None = None
    #: The bare code of a status value.
    code: str = ""
    mono: bool = False
    tabular: bool = False
    align: str = "left"
    #: True for free text, which keeps its newlines.
    wrap: bool = False


@dataclass
class FieldValueOptions:
    """What the delegate face needs that a widget would read off itself."""

    #: The theme the cell is drawn from. A view takes it from `theme_of(view)`.
    theme: Theme | None = None
    #: The field schema, for a status label out of `display_values` (probe 009).
    field: FieldSchema | None = None
    #: `Status` rows by code, for the status name and icon (probe 010).
    statuses: Mapping[str, StatusRecord] | None = None
    #: The site the stock sprite is served from, and the site a linked row is addressed on.
    site_url: str = ""
    entity_variant: str = "chip"
    density: str = "default"
    empty_label: str = "empty"
    #: What the formatters take: the site preferences with the caller's own over them.
    text: FieldTextOptions | None = None
    local_href: Callable[[UrlLinkInfo], str | None] | None = None
    #: Overrides the column's own alignment.
    align: str | None = None
    #: A chosen row draws its value in `accent_foreground`.
    selected: bool = False
    enabled: bool = True
    #: Free text keeps its newlines. A cell is one line, so a view leaves this off.
    wrap: bool = False
    loader: ImageLoader | None = None
    #: Called on the GUI thread once a picture or a status sprite lands, so a view repaints.
    on_ready: Callable[[], None] | None = None


# --- the plan ---------------------------------------------------------------------------------


def _column_parts(column: ColumnLike) -> tuple[str, FieldSchema | None, str | None]:
    """The data type, the leaf schema and the alignment a column names."""
    if isinstance(column, str):
        return column, None, None
    return column.data_type, column.field, column.align


def _refs_of(value: Any) -> list[EntityRef]:
    """An entity value and a multi_entity value are one shape, one boxed (field_types/multi_entity)."""
    rows = value if isinstance(value, (list, tuple)) else [value]
    out: list[EntityRef] = []
    for row in rows:
        if isinstance(row, EntityRef):
            out.append(row)
        elif isinstance(row, Mapping):
            out.append(
                EntityRef(
                    type=str(row.get("type") or ""),
                    id=int(row.get("id") or 0),
                    name=row.get("name") if isinstance(row.get("name"), str) else None,
                )
            )
    return out


def _status_text(code: str, options: FieldValueOptions) -> str:
    """The Status row's name, then the field's display value, then the code itself."""
    record = (options.statuses or {}).get(code)
    name = getattr(record, "name", "") or ""
    if name:
        return name
    values = getattr(options.field, "display_values", None) or {}
    return values.get(code, code)


def plan_field_value(
    value: Any,
    column: ColumnLike,
    options: FieldValueOptions | None = None,
) -> FieldValuePlan:
    """What a value draws, by its data type.

    A checkbox is two-state and never null, so it is the one kind whose empty-looking value is a
    real one (field_types/checkbox).
    """
    o = options if options is not None else FieldValueOptions()
    data_type, schema, align = _column_parts(column)
    field = schema if schema is not None else o.field
    kind = render_kind_for(data_type)
    text_options = o.text if o.text is not None else FieldTextOptions()
    if kind == "status" and field is not None and text_options.display_values is None:
        text_options = FieldTextOptions(**{**text_options.__dict__, "display_values": field.display_values})

    if kind != "checkbox" and (kind == "empty" or is_empty_value(value)):
        return FieldValuePlan(kind="empty", data_type=data_type, text=o.empty_label)

    plan = FieldValuePlan(
        kind=kind,
        data_type=data_type,
        # A value reads left to right on its own. Alignment is the collection's business: a
        # table hands its column's through `align`, as the web widget's cell class does.
        align=o.align if o.align is not None else (align or "left"),
        tabular=kind == "number",
    )
    if kind == "checkbox":
        plan.checked = value is True
        plan.text = field_text(value, data_type, text_options)
        return plan
    if kind == "entity" or kind == "multi_entity":
        # A chip carries its own tooltip, so the value around it carries none: upstream leaves
        # the `title` off a linked value for the same reason.
        plan.refs = _refs_of(value)
        return plan
    if kind == "status":
        plan.code = str(value)
        plan.text = _status_text(plan.code, FieldValueOptions(field=field, statuses=o.statuses))
        plan.tooltip = plan.code if plan.text != plan.code else plan.text
        return plan
    if kind == "image":
        plan.image = str(value)
        return plan
    if kind == "url":
        raw = url_link(value)
        # A local link opens through `file:`; an app that opens paths its own way rewrites it.
        if raw is not None and raw.local is not None and o.local_href is not None:
            raw = UrlLinkInfo(href=o.local_href(raw), label=raw.label, local=raw.local)
        plan.link = raw
        plan.text = raw.label if raw is not None else ""
        plan.tooltip = (raw.local.path if raw is not None and raw.local is not None else None) or plan.text
        return plan
    if kind == "color":
        plan.sentinel = str(value) == COLOR_SENTINEL
        plan.rgb = None if plan.sentinel else parse_bg_color(str(value))
        plan.text = "pipeline step" if plan.sentinel else str(value)
        plan.mono = plan.rgb is not None
        plan.tabular = plan.rgb is not None
        # The tooltip is the value the row holds, so the sentinel shows its token and not the
        # words it is drawn as (field_types/color).
        plan.tooltip = str(value)
        return plan
    if kind in ("number", "date", "datetime"):
        plan.text = field_text(value, data_type, text_options)
        # A date shows in the locale and keeps the stored instant beside it.
        plan.tooltip = str(value) if kind in ("date", "datetime") else plan.text
        return plan
    plan.text = str(value)
    plan.tooltip = plan.text
    # Free text is often several lines: a description keeps its newlines.
    plan.wrap = kind == "text" and data_type == "text"
    return plan


# --- the ladders the plan draws on ------------------------------------------------------------


def _chip_step(density: str) -> str:
    return FIELD_VALUE_CHIP.get(density, FIELD_VALUE_CHIP["default"])


def _theme_of(options: FieldValueOptions) -> Theme:
    return options.theme if options.theme is not None else theme_for("default")


def _ink(theme: Theme, options: FieldValueOptions, token: str = "foreground") -> QtGui.QColor:
    return theme.color("accent_foreground" if options.selected else token)


def _value_font(theme: Theme, plan: FieldValuePlan) -> QtGui.QFont:
    size = META_TEXT if plan.kind == "color" and plan.rgb is not None else VALUE_TEXT
    return theme.font(size, mono=plan.mono, tabular=plan.tabular)


def _chip_label(ref: EntityRef) -> str:
    """The name, or `Type #id`, which is always addressable (probe 060)."""
    return str(ref.name) if ref.name else f"{ref.type} #{ref.id}"


def _chip_font(theme: Theme, step: str, named: bool) -> QtGui.QFont:
    """A chip's label: medium at its type step, and the mono face for a bare id (rule 6).

    `EntityChip._font` makes the same call, which is what keeps the two faces in step.
    """
    return theme.font(CHIP_TEXT[step], QtGui.QFont.Weight.Medium, mono=not named, tabular=not named)


def _glyph_slot(box: QtCore.QRect, left: int, glyph: int) -> QtCore.QRect:
    """The leading slot of a chip, where the badge primitive puts it.

    `primitives/badge.py` centres the glyph on the box's own centre line rather than sharing the
    room above and below, so the delegate face centres it the same way: the widget face composes
    that primitive, and the two faces must land on one pixel.
    """
    slot = QtCore.QRect(0, 0, glyph, glyph)
    slot.moveCenter(QtCore.QPoint(left + glyph // 2, box.center().y()))
    return slot


def _centre_top(rect: QtCore.QRect, height: int) -> int:
    """Where a box of that height sits to be centred in `rect`, the way a row centres.

    `QRect.center()` rounds down on an even height, which leaves a box a pixel high; the room
    above and below is what rule 2 asks to be equal, so it is shared here instead. Both faces
    centre through this, which is what keeps a cell and a widget pixel-identical.
    """
    return rect.top() + max(0, rect.height() - height) // 2


def _chip_width(theme: Theme, label: str, step: str, glyph: bool = True, named: bool = True) -> int:
    pad = CHIP_PAD[step]
    width = (pad.lead if glyph else pad.text) + pad.text
    if glyph:
        width += CHIP_GLYPH[step] + CHIP_SPACING[step].glyph
    return width + text_width(QtGui.QFontMetrics(_chip_font(theme, step, named)), label)


def _status_source(
    status: StatusRecord | None,
    site_url: str,
    loader: ImageLoader | None,
    on_ready: Callable[[], None] | None,
) -> StatusGlyphSource:
    """The glyph one status draws, shared so a table of a hundred rows costs one sprite read."""
    key = (getattr(status, "code", "") or "", site_url, id(loader))
    source = _SOURCES.get(key)
    if source is None:
        source = StatusGlyphSource(status, site_url, loader=loader)
        _SOURCES[key] = source
        _LISTENERS[key] = []
    if on_ready is not None and on_ready not in _LISTENERS[key]:
        _LISTENERS[key].append(on_ready)
        source.changed.connect(on_ready)
    return source


_SOURCES: dict[tuple[str, str, int], StatusGlyphSource] = {}
_LISTENERS: dict[tuple[str, str, int], list[Callable[[], None]]] = {}


# --- the delegate face ------------------------------------------------------------------------


def _align_flags(plan: FieldValuePlan) -> int:
    horizontal = (
        QtCore.Qt.AlignmentFlag.AlignRight
        if plan.align == "right"
        else QtCore.Qt.AlignmentFlag.AlignLeft
    )
    return int(horizontal | QtCore.Qt.AlignmentFlag.AlignVCenter)


def _draw_line(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    font: QtGui.QFont,
    ink: QtGui.QColor,
    text: str,
    plan: FieldValuePlan,
    wrap: bool = False,
) -> None:
    painter.setFont(font)
    painter.setPen(ink)
    if wrap:
        painter.drawText(
            rect,
            int(
                QtCore.Qt.AlignmentFlag.AlignTop
                | QtCore.Qt.AlignmentFlag.AlignLeft
                | QtCore.Qt.TextFlag.TextWordWrap
            ),
            text,
        )
        return
    one_line = text.replace("\n", " ")
    painter.drawText(rect, _align_flags(plan), elide(QtGui.QFontMetrics(font), one_line, rect.width()))


def chip_layout(widths: list[int], room: int, step: str) -> tuple[list[QtCore.QPoint], int]:
    """Where each chip of a linked value goes, and how tall the block is.

    The chips wrap onto a new line when the one they are on has no more room, which is the
    `flex-wrap` of the web widget; a chip too wide for the line keeps the line and elides. Both
    faces lay out through this, so a widget and a cell put every chip on the same pixel. A cell
    that is one line high simply shows the first line, the way the web table's own cell clips.
    """
    height = CHIP_HEIGHT[step]
    spots: list[QtCore.QPoint] = []
    x = 0
    y = 0
    for width in widths:
        if x > 0 and x + width > room:
            x = 0
            y += height + CHIP_GAP
        spots.append(QtCore.QPoint(x, y))
        x += width + CHIP_GAP
    return spots, (y + height if widths else 0)


def _paint_chips(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    """The linked rows, as chips wrapping across the room the value has."""
    theme = _theme_of(options)
    step = _chip_step(options.density)
    if options.entity_variant != "chip":
        labels = ", ".join(_chip_label(ref) for ref in plan.refs)
        font = theme.font(VALUE_TEXT)
        font.setUnderline(options.entity_variant == "link")
        _draw_line(painter, rect, font, _ink(theme, options), labels, plan)
        return

    widths = [_chip_width(theme, _chip_label(ref), step, named=bool(ref.name)) for ref in plan.refs]
    spots, block = chip_layout(widths, rect.width(), step)
    height = CHIP_HEIGHT[step]
    top = _centre_top(rect, block)
    for index, spot in enumerate(spots):
        box = QtCore.QRect(
            rect.left() + spot.x(),
            top + spot.y(),
            min(widths[index], rect.width()),
            height,
        )
        _paint_one_chip(painter, box, plan.refs[index], theme, step, options)


def _paint_one_chip(
    painter: QtGui.QPainter,
    box: QtCore.QRect,
    ref: EntityRef,
    theme: Theme,
    step: str,
    options: FieldValueOptions,
) -> None:
    pad = CHIP_PAD[step]
    fill = theme.color("secondary")
    ink = theme.color("secondary_foreground")
    fill_round_rect(painter, box, float(theme.radius_px("md")), fill, theme.color("border"))
    glyph = CHIP_GLYPH[step]
    slot = _glyph_slot(box, box.left() + pad.lead, glyph)
    paint_icon(painter, slot, entity_glyph(ref.type), with_alpha(ink, 0.7))
    # The badge walks its own cursor past the slot rather than reading the slot's right edge,
    # which `QRect.moveCenter` shifts by a pixel on an even glyph. The two must agree.
    left = box.left() + pad.lead + glyph + CHIP_SPACING[step].glyph
    font = _chip_font(theme, step, bool(ref.name))
    painter.setFont(font)
    painter.setPen(ink)
    room = max(0, box.right() + 1 - pad.text - left)
    painter.drawText(
        QtCore.QRect(left, box.top(), room, box.height()),
        int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
        elide(QtGui.QFontMetrics(font), _chip_label(ref), room),
    )


def _status_glyph_source(plan: FieldValuePlan, options: FieldValueOptions) -> StatusGlyphSource:
    record = (options.statuses or {}).get(plan.code)
    return _status_source(record, options.site_url, options.loader, options.on_ready)


def _status_width(theme: Theme, plan: FieldValuePlan, options: FieldValueOptions) -> int:
    step = _chip_step(options.density)
    pad = CHIP_PAD[step]
    font = _chip_font(theme, step, named=True)
    # A status the site draws nothing for is a bordered label, which is what StatusBadge draws:
    # no glyph, and the bare text inset in its place.
    glyph = _status_glyph_source(plan, options).draws()
    lead = pad.lead + CHIP_GLYPH[step] + CHIP_SPACING[step].glyph if glyph else pad.text
    return lead + text_width(QtGui.QFontMetrics(font), plan.text) + pad.text


def _paint_status(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    """The badge a status is where it is a value (`docs/design-rules.md` rule 9)."""
    theme = _theme_of(options)
    step = _chip_step(options.density)
    pad = CHIP_PAD[step]
    height = min(CHIP_HEIGHT[step], rect.height())
    width = min(_status_width(theme, plan, options), rect.width())
    box = QtCore.QRect(rect.left(), 0, width, height)
    box.moveTop(_centre_top(rect, height))
    # The badge's own surface, which an uncoloured status wears (`status_badge._surface`).
    fill_round_rect(
        painter, box, float(theme.radius_px("md")), theme.color("background"), theme.color("border")
    )

    ink = theme.color("foreground")
    source = _status_glyph_source(plan, options)
    left = box.left() + pad.text
    if source.draws():
        glyph = CHIP_GLYPH[step]
        slot = _glyph_slot(box, box.left() + pad.lead, glyph)
        source.paint(painter, slot, theme)
        left = box.left() + pad.lead + glyph + CHIP_SPACING[step].glyph
    font = _chip_font(theme, step, named=True)
    painter.setFont(font)
    painter.setPen(ink)
    room = max(0, box.right() + 1 - pad.text - left)
    painter.drawText(
        QtCore.QRect(left, box.top(), room, box.height()),
        int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
        elide(QtGui.QFontMetrics(font), plan.text, room),
    )


def _image_size() -> QtCore.QSize:
    height = THUMB_SIZE[IMAGE_STEP]
    return QtCore.QSize(int(round(height * 16 / 9)), height)


def _paint_image(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    theme = _theme_of(options)
    size = _image_size()
    box = QtCore.QRect(rect.left(), 0, min(size.width(), rect.width()), min(size.height(), rect.height()))
    box.moveTop(_centre_top(rect, box.height()))
    radius = float(theme.radius_px("md"))
    fill_round_rect(painter, box, radius, theme.color("muted"), theme.color("border"))

    loader = options.loader if options.loader is not None else image_loader()
    url = plan.image or ""
    picture = loader.pixmap_cached(url)
    if picture is None and not loader.has(url):
        loader.load(url, lambda _pixmap: options.on_ready() if options.on_ready else None, size=size)
    if picture is None or picture.isNull():
        side = min(PLACEHOLDER_GLYPH, box.width(), box.height())
        slot = QtCore.QRect(0, 0, side, side)
        slot.moveCenter(box.center())
        paint_icon(painter, slot, "image", theme.color("muted_foreground"))
        return
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(box), radius, radius)
    painter.save()
    painter.setClipPath(path)
    scaled = picture.scaled(
        box.size(),
        QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    target = QtCore.QRect(QtCore.QPoint(0, 0), scaled.size())
    target.moveCenter(box.center())
    painter.drawPixmap(target, scaled)
    painter.restore()


def _paint_color(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    theme = _theme_of(options)
    if plan.rgb is None:
        token = "muted_foreground" if plan.sentinel else "foreground"
        _draw_line(painter, rect, _value_font(theme, plan), _ink(theme, options, token), plan.text, plan)
        return
    box = QtCore.QRect(rect.left(), 0, SWATCH, SWATCH)
    box.moveTop(_centre_top(rect, SWATCH))
    # Status and swatch colour is data, which is the one colour a widget takes off the site (rule 1).
    swatch = QtGui.QColor(plan.rgb.r, plan.rgb.g, plan.rgb.b)
    fill_round_rect(painter, box, float(theme.radius_px("sm")), swatch, theme.color("border"))
    left = box.right() + 1 + GLYPH_GAP
    _draw_line(
        painter,
        QtCore.QRect(left, rect.top(), max(0, rect.right() + 1 - left), rect.height()),
        _value_font(theme, plan),
        _ink(theme, options, "muted_foreground"),
        plan.text,
        plan,
    )


def _paint_url(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    theme = _theme_of(options)
    link = plan.link
    font = theme.font(VALUE_TEXT)
    ink = _ink(theme, options)
    if link is None or not link.href:
        _draw_line(painter, rect, font, ink, plan.text, plan)
        return
    # A link is its underline and nothing else, as the web widget's anchor is.
    font.setUnderline(True)
    _draw_line(painter, rect, font, ink, plan.text, plan)


def _switch_size() -> QtCore.QSize:
    """The room the switch primitive asks for, its focus ring's included."""
    return QtCore.QSize(SWITCH_WIDTH + RING_ROOM * 2, SWITCH_HEIGHT + RING_ROOM * 2)


def _paint_checkbox(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    """The switch a checkbox is, inert and at full contrast.

    The two states of a checkbox are what a switch shows, and the web widget draws exactly that:
    a `Switch` that is disabled, out of the tab order and kept at full opacity. The widget face
    holds the primitive; this redraws it the way `_paint_one_chip` redraws a chip, on the
    primitive's own ladder so the two faces land on one pixel.
    """
    theme = _theme_of(options)
    size = _switch_size()
    box = QtCore.QRect(rect.left(), _centre_top(rect, size.height()), size.width(), size.height())
    track = QtCore.QRect(0, 0, SWITCH_WIDTH, SWITCH_HEIGHT)
    track.moveCenter(box.center())
    radius = track.height() / 2.0
    off = with_alpha(theme.input, 0.8) if theme.dark else theme.color("input")
    fill_round_rect(painter, track, radius, theme.color("primary") if plan.checked else off)

    travel = track.width() - SWITCH_THUMB - SWITCH_INSET * 2
    x = track.x() + SWITCH_INSET + (travel if plan.checked else 0)
    thumb = QtCore.QRectF(x, track.y() + SWITCH_INSET, SWITCH_THUMB, SWITCH_THUMB)
    if theme.dark:
        ink = theme.color("primary_foreground" if plan.checked else "foreground")
    else:
        ink = theme.color("background")
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    painter.drawEllipse(thumb)


def warm_status_glyph(code: str, options: FieldValueOptions) -> None:
    """Draw the badge of one status once, off screen, before anything paints it for real.

    Building the glyph source and painting a badge for the first time both cost a few
    milliseconds a status, and a list of them would pay all of it inside one repaint. A caller
    that knows its codes ahead of the frame warms them here, one at a time, so the cost falls
    between frames rather than inside one.
    """
    _status_source(
        (options.statuses or {}).get(code), options.site_url, options.loader, options.on_ready
    )
    scratch = QtGui.QPixmap(1, 1)
    painter = QtGui.QPainter(scratch)
    try:
        _paint_status(painter, QtCore.QRect(0, 0, 1, 1), plan_field_value(code, "status_list", options), options)
    finally:
        painter.end()


def paint_field_value(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    value: Any,
    column: ColumnLike,
    options: FieldValueOptions | None = None,
) -> None:
    """Draw one value inside `rect`, by its data type.

    The face a delegate draws through: no widget per cell, and the same plan the widget reads.
    """
    o = options if options is not None else FieldValueOptions()
    plan = plan_field_value(value, column, o)
    theme = _theme_of(o)
    painter.save()
    painter.setOpacity(1.0 if o.enabled else 0.5)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
    if plan.kind == "empty":
        font = theme.font(META_TEXT)
        font.setItalic(True)
        _draw_line(painter, rect, font, _ink(theme, o, "muted_foreground"), plan.text, plan)
    elif plan.kind in ("entity", "multi_entity"):
        _paint_chips(painter, rect, plan, o)
    elif plan.kind == "status":
        _paint_status(painter, rect, plan, o)
    elif plan.kind == "image":
        _paint_image(painter, rect, plan, o)
    elif plan.kind == "checkbox":
        _paint_checkbox(painter, rect, plan, o)
    elif plan.kind == "url":
        _paint_url(painter, rect, plan, o)
    elif plan.kind == "color":
        _paint_color(painter, rect, plan, o)
    else:
        _draw_line(
            painter,
            rect,
            _value_font(theme, plan),
            _ink(theme, o),
            plan.text,
            plan,
            wrap=o.wrap and plan.wrap,
        )
    painter.restore()


def field_value_size_hint(
    value: Any,
    column: ColumnLike,
    options: FieldValueOptions | None = None,
    width: int | None = None,
) -> QtCore.QSize:
    """The room one value needs. `width` bounds free text, which wraps."""
    o = options if options is not None else FieldValueOptions()
    plan = plan_field_value(value, column, o)
    theme = _theme_of(o)
    step = _chip_step(o.density)
    if plan.kind in ("entity", "multi_entity") and o.entity_variant == "chip":
        widths = [
            _chip_width(theme, _chip_label(ref), step, named=bool(ref.name)) for ref in plan.refs
        ]
        total = sum(widths) + CHIP_GAP * max(0, len(widths) - 1)
        if width is None:
            return QtCore.QSize(total, CHIP_HEIGHT[step])
        # Given a width, the chips wrap into it, and the block is as tall as the lines they take.
        _spots, block = chip_layout(widths, int(width), step)
        return QtCore.QSize(min(total, int(width)), max(CHIP_HEIGHT[step], block))
    if plan.kind == "status":
        return QtCore.QSize(_status_width(theme, plan, o), CHIP_HEIGHT[step])
    if plan.kind == "image":
        return _image_size()
    if plan.kind == "checkbox":
        return _switch_size()

    font = theme.font(META_TEXT) if plan.kind == "empty" else _value_font(theme, plan)
    metrics = QtGui.QFontMetrics(font)
    if o.wrap and plan.wrap and width is not None:
        box = metrics.boundingRect(
            QtCore.QRect(0, 0, max(1, int(width)), 1 << 16),
            int(QtCore.Qt.TextFlag.TextWordWrap),
            plan.text,
        )
        return QtCore.QSize(int(width), max(metrics.height(), box.height()))
    extra = SWATCH + GLYPH_GAP if plan.kind == "color" and plan.rgb is not None else 0
    widest = max(
        (text_width(metrics, line) for line in plan.text.splitlines() or [""]),
        default=0,
    )
    return QtCore.QSize(widest + extra, max(metrics.height(), SWATCH))


# --- the widget face --------------------------------------------------------------------------


class _ChipRow(ThemedWidget):
    """The chips of a linked value, wrapping across the room they are given.

    The web widget lays them out with `flex-wrap` and rule 2's item gap, so a chip that does not
    fit the line takes the next one; a cell only one line high shows the first line. The layout
    is `chip_layout`, which the delegate face draws by too.
    """

    def __init__(self, step: str = "sm", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("field-value-chips")
        self._step = step
        self._chips: list[EntityChip] = []
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

    @property
    def chips(self) -> list[EntityChip]:
        """The chips, in order."""
        return list(self._chips)

    @property
    def lines(self) -> int:
        """How many lines the chips take at the width the row has."""
        if not self._chips:
            return 0
        _spots, block = self._layout(self.width())
        return 1 + (block - CHIP_HEIGHT[self._step]) // (CHIP_HEIGHT[self._step] + CHIP_GAP)

    def set_chips(self, chips: list[EntityChip]) -> None:
        for chip in self._chips:
            chip.setParent(None)
            chip.deleteLater()
        self._chips = chips
        for chip in chips:
            chip.setParent(self)
            chip.show()
        self.updateGeometry()
        self._lay()

    def set_step(self, step: str) -> None:
        self._step = step
        for chip in self._chips:
            chip.set_size(step)
        self.updateGeometry()
        self._lay()

    def _widths(self) -> list[int]:
        return [chip.sizeHint().width() for chip in self._chips]

    def _layout(self, room: int) -> tuple[list[QtCore.QPoint], int]:
        return chip_layout(self._widths(), room, self._step)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        widths = self._widths()
        total = sum(widths) + CHIP_GAP * max(0, len(widths) - 1)
        return QtCore.QSize(total, CHIP_HEIGHT[self._step])

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, CHIP_HEIGHT[self._step])

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        _spots, block = self._layout(width)
        return max(CHIP_HEIGHT[self._step], block)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._lay()

    def _lay(self) -> None:
        """Every chip where `chip_layout` puts it, with the block centred in the room."""
        widths = self._widths()
        spots, block = self._layout(self.width())
        height = CHIP_HEIGHT[self._step]
        top = max(0, (self.height() - block) // 2)
        for index, chip in enumerate(self._chips):
            spot = spots[index]
            chip.setGeometry(
                QtCore.QRect(spot.x(), top + spot.y(), min(widths[index], self.width()), height)
            )
            chip.show()
        self.update()


class _ValueSwitch(Switch):
    """The switch a checkbox value shows: the two states, and no way to change them.

    The web widget draws the same primitive `disabled`, out of the tab order and with the
    disabled dimming turned off, so the value keeps full contrast and reads as a state rather
    than as a control.
    """

    def __init__(self, checked: bool = False, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(checked, parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)


class FieldValue(ThemedWidget):
    """One attribute value, rendered for display.

    The value is drawn by its data type: a linked row is a chip, a status a badge, an image a
    thumbnail, and everything else is painted here from the same plan the delegate face reads.
    """

    def __init__(
        self,
        value: Any = None,
        data_type: str = "text",
        field: FieldSchema | None = None,
        statuses: Mapping[str, StatusRecord] | None = None,
        site_url: str = "",
        entity_variant: str = "chip",
        density: str = "default",
        preview: list[str] | None = None,
        context: SgContext | None = None,
        client: object = None,
        hours_per_day: float | None = None,
        locale: str | None = None,
        time_zone: str | None = None,
        frame_rate: float | None = None,
        precision: int | None = None,
        currency_symbol: str | None = None,
        local_href: Callable[[UrlLinkInfo], str | None] | None = None,
        empty_label: str = "empty",
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("field-value")
        self._value = value
        self._data_type = data_type
        self._field = field
        self._statuses = statuses
        self._site_url = site_url
        self._entity_variant = (
            entity_variant if entity_variant in ENTITY_CHIP_VARIANT_VALUES else "chip"
        )
        self._density = density if density in FIELD_VALUE_DENSITY_VALUES else "default"
        self._preview = list(preview or [])
        self._context = context if context is not None else _context_of(client)
        self._hours_per_day = hours_per_day
        self._locale = locale
        self._time_zone = time_zone
        self._frame_rate = frame_rate
        self._precision = precision
        self._currency_symbol = currency_symbol
        self._local_href = local_href
        self._empty_label = empty_label
        self._loader = loader if loader is not None else image_loader()
        self._child: QtWidgets.QWidget | None = None
        self._plan = FieldValuePlan(kind="empty", data_type=data_type)

        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(0)
        # No layout: a widget that holds one carries its layout's `heightForWidth`, and an empty
        # one answers zero, which would flatten a value the widget paints itself.
        self._rebuild()

    # --- props ---

    @property
    def value(self) -> Any:
        """The raw attribute or relationship value, as the API returned it."""
        return self._value

    def set_value(self, value: Any) -> None:
        self._value = value
        self._rebuild()

    @property
    def data_type(self) -> str:
        """The field's data type. An unknown one renders as text."""
        return self._data_type

    def set_data_type(self, value: str) -> None:
        self._data_type = value
        self._rebuild()

    @property
    def field(self) -> FieldSchema | None:
        """Supplies a status label through its display values (probe 009)."""
        return self._field

    def set_field(self, value: FieldSchema | None) -> None:
        self._field = value
        self._rebuild()

    @property
    def statuses(self) -> Mapping[str, StatusRecord] | None:
        """Status rows by code, for the status name and icon (probe 010)."""
        return self._statuses

    def set_statuses(self, value: Mapping[str, StatusRecord] | None) -> None:
        self._statuses = value
        self._rebuild()

    @property
    def site_url(self) -> str:
        """The site the stock sprite is served from, and the site a linked row is addressed on."""
        return self._site_url or (self._context.site_url if self._context is not None else "")

    def set_site_url(self, value: str) -> None:
        self._site_url = value
        self._rebuild()

    @property
    def entity_variant(self) -> str:
        """How an entity or multi-entity value draws: `chip`, `link` or `text`."""
        return self._entity_variant

    def set_entity_variant(self, value: str) -> None:
        self._entity_variant = value if value in ENTITY_CHIP_VARIANT_VALUES else "chip"
        self._rebuild()

    @property
    def density(self) -> str:
        """`compact` draws the chip and the badge a step smaller."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value if value in FIELD_VALUE_DENSITY_VALUES else "default"
        self._rebuild()

    @property
    def preview(self) -> list[str]:
        """Field paths a linked row's hover card shows. Needs a context."""
        return list(self._preview)

    def set_preview(self, value: list[str] | None) -> None:
        self._preview = list(value or [])
        self._rebuild()

    @property
    def context(self) -> SgContext | None:
        """The site url, the site preferences and the hover card's read."""
        return self._context

    def set_context(self, value: SgContext | None) -> None:
        self._context = value
        self._rebuild()

    def set_client(self, value: object) -> None:
        """Read through a bare client. One context is built per client and shared."""
        self.set_context(_context_of(value))

    @property
    def hours_per_day(self) -> float | None:
        """The site's working day. Durations then render in days (field_types/duration)."""
        return self._hours_per_day

    def set_hours_per_day(self, value: float | None) -> None:
        self._hours_per_day = value
        self._rebuild()

    @property
    def locale(self) -> str | None:
        """Used for dates and numbers. A locale outside core's table formats as `en-US`."""
        return self._locale

    def set_locale(self, value: str | None) -> None:
        self._locale = value
        self._rebuild()

    @property
    def time_zone(self) -> str | None:
        """IANA zone a `date_time` is shown in."""
        return self._time_zone

    def set_time_zone(self, value: str | None) -> None:
        self._time_zone = value
        self._rebuild()

    @property
    def frame_rate(self) -> float | None:
        """Frames a second. A timecode then carries its frame digits (field_types/timecode)."""
        return self._frame_rate

    def set_frame_rate(self, value: float | None) -> None:
        self._frame_rate = value
        self._rebuild()

    @property
    def precision(self) -> int | None:
        """Decimals kept on a float, and the decimals of a currency."""
        return self._precision

    def set_precision(self, value: int | None) -> None:
        self._precision = value
        self._rebuild()

    @property
    def currency_symbol(self) -> str | None:
        """Shown before a currency amount."""
        return self._currency_symbol

    def set_currency_symbol(self, value: str | None) -> None:
        self._currency_symbol = value
        self._rebuild()

    @property
    def local_href(self) -> Callable[[UrlLinkInfo], str | None] | None:
        """Rewrites where a local file link opens."""
        return self._local_href

    def set_local_href(self, value: Callable[[UrlLinkInfo], str | None] | None) -> None:
        self._local_href = value
        self._rebuild()

    @property
    def empty_label(self) -> str:
        """The marker an unset value shows. Never a dash: a dash reads like a value."""
        return self._empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = value
        self._rebuild()

    # --- what it resolved to ---

    @property
    def plan(self) -> FieldValuePlan:
        """What the value draws: its kind, its text and what it resolved to."""
        return self._plan

    @property
    def kind(self) -> str:
        """The rendering core chose for the data type, or `empty`."""
        return self._plan.kind

    @property
    def child(self) -> QtWidgets.QWidget | None:
        """The widget the value is, where the value is a chip, a badge or a picture."""
        return self._child

    @property
    def url(self) -> str:
        """Where a `url` value opens, or an empty string."""
        link = self._plan.link
        return link.href or "" if link is not None else ""

    def options(self) -> FieldValueOptions:
        """The options both faces read this value through."""
        return FieldValueOptions(
            theme=self.theme,
            field=self._field,
            statuses=self._statuses,
            site_url=self.site_url,
            entity_variant=self._entity_variant,
            density=self._density,
            empty_label=self._empty_label,
            text=self._text_options(),
            local_href=self._local_href,
            enabled=self.isEnabled(),
            wrap=True,
            loader=self._loader,
            on_ready=self.update,
        )

    def _text_options(self) -> FieldTextOptions:
        """The site's preferences, with anything the caller named winning over them."""
        options = preferences_of(self._context)
        if self._hours_per_day is not None:
            options.hours_per_day = self._hours_per_day
        if self._locale is not None:
            options.locale = self._locale
        if self._time_zone is not None:
            options.time_zone = self._time_zone
        if self._frame_rate is not None:
            options.frame_rate = self._frame_rate
        if self._precision is not None:
            options.decimals = self._precision
        if self._currency_symbol is not None:
            options.currency_symbol = self._currency_symbol
        if self._field is not None:
            options.display_values = self._field.display_values
        return options

    # --- building ---

    def _rebuild(self) -> None:
        options = self.options()
        self._plan = plan_field_value(self._value, self._data_type, options)
        if self._child is not None:
            self._child.setParent(None)
            self._child.deleteLater()
            self._child = None
        self._child = self._build_child(options)
        if self._child is not None:
            self._child.show()
            self._place_child()
        self.setToolTip(self._plan.tooltip)
        self.setAccessibleName(self._plan.text or self._plan.tooltip)
        self._apply_focus_policy()
        self.updateGeometry()
        self.update()

    def _build_child(self, options: FieldValueOptions) -> QtWidgets.QWidget | None:
        """The widget a chip, a badge or a picture is. Every other kind is painted here."""
        plan = self._plan
        step = _chip_step(self._density)
        if plan.kind in ("entity", "multi_entity"):
            row = _ChipRow(step, self)
            row.set_chips([self._chip(ref, step) for ref in plan.refs])
            return row
        if plan.kind == "status":
            record = (self._statuses or {}).get(plan.code)
            return StatusBadge(
                code=plan.code,
                status=record,
                field=self._field,
                size=step,
                site_url=self.site_url,
                loader=self._loader,
                parent=self,
            )
        if plan.kind == "image":
            return Thumbnail(src=plan.image, size=IMAGE_STEP, loader=self._loader, parent=self)
        if plan.kind == "checkbox":
            # The two states of a checkbox are a switch, which is what the web widget draws.
            switch = _ValueSwitch(plan.checked, self)
            switch.setAccessibleName(plan.text)
            return switch
        return None

    def _chip(self, ref: EntityRef, step: str) -> EntityChip:
        return EntityChip(
            entity=ref,
            variant=self._entity_variant,
            size=step,
            site_url=self._site_url,
            preview=self._preview,
            context=self._context,
            loader=self._loader,
        )

    def _apply_focus_policy(self) -> None:
        policy = QtCore.Qt.FocusPolicy
        self.setFocusPolicy(policy.TabFocus if self.url else policy.NoFocus)

    # --- geometry ---

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        if self._child is not None:
            return self._child.sizeHint()
        return field_value_size_hint(
            self._value, self._data_type, self.options(), width=self.width() or None
        )

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        if isinstance(self._child, _ChipRow):
            return True
        return self._child is None and self._plan.wrap

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        if isinstance(self._child, _ChipRow):
            return self._child.heightForWidth(width)
        return field_value_size_hint(self._value, self._data_type, self.options(), width=width).height()

    def _place_child(self) -> None:
        """The one widget a value is, on the left of the room the value has and centred in it.

        The delegate face centres what it draws in the cell it is given, so the widget centres
        its child through the same helper: the two faces then land on the same pixels.
        """
        child = self._child
        if child is None:
            return
        if isinstance(child, _ChipRow):
            # A chip row wraps into the room it is given and centres its block inside it, which
            # is what the delegate face does with the same rectangle.
            child.setGeometry(0, 0, max(0, self.width()), max(0, self.height()))
            return
        hint = child.sizeHint()
        expands = child.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Policy.Expanding
        width = self.width() if expands else min(hint.width(), self.width())
        height = max(0, min(hint.height(), self.height()))
        child.setGeometry(0, _centre_top(self.rect(), height), max(0, width), height)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_child()
        if self._plan.wrap or isinstance(self._child, _ChipRow):
            self.updateGeometry()

    def _on_theme(self, theme: Theme) -> None:
        super()._on_theme(theme)
        self.updateGeometry()

    # --- interaction ---

    def _activate(self) -> None:
        url = self.url
        if url:
            # A row's page and an attachment are outside this application, and so is a local path.
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if (
            self.isEnabled()
            and self.url
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and self.rect().contains(event.pos())
        ):
            self._activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Space)
        if self.isEnabled() and self.url and event.key() in keys:
            self._activate()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._child is not None:
            return
        painter = painter_for(self)
        paint_field_value(painter, self.rect(), self._value, self._data_type, self.options())
        if self.keyboard_focus and self.url:
            self.paint_focus_ring(painter, self.rect(), float(self.theme.radius_px("sm")))
        painter.end()


def _context_of(client: object) -> SgContext | None:
    """The shared context for a bare client, so a value handed one shares the page's caches."""
    if client is None:
        return None
    return context_from_client(client)  # type: ignore[arg-type]
