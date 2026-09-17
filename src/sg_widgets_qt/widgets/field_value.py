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
from sg_widgets_core.picker import fit_chips
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
from ..theme import Theme, theme_for, with_alpha
from .entity_chip import ENTITY_CHIP_VARIANT_VALUES, EntityChip
from .entity_glyphs import entity_glyph
from .status_badge import StatusBadge
from .status_glyph import StatusGlyphSource
from .thumbnail import Thumbnail

__all__ = [
    "CHECK_GLYPH",
    "FIELD_VALUE_CHIP",
    "FIELD_VALUE_DENSITY_VALUES",
    "OVERFLOW_RESERVE",
    "SWATCH",
    "FieldValue",
    "FieldValueOptions",
    "FieldValuePlan",
    "field_value_size_hint",
    "paint_field_value",
    "plan_field_value",
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

#: Between the chips of a multi-entity value, and the room the `+n` pill keeps beside them.
CHIP_GAP = 6
OVERFLOW_RESERVE = 40

#: The tick a true checkbox draws, and the cross a false one takes.
CHECK_GLYPH = 16
CHECK_ICON = "check"
UNCHECK_ICON = "x"

#: The mark on a link that leaves the application.
LINK_GLYPH = 14
LINK_ICON = "external-link"

#: The picture an `image` value draws at, the bottom of the thumbnail ladder.
IMAGE_STEP = "sm"

#: Data types drawn in the monospace family with tabular figures (rule 6).
MONO_TYPES: tuple[str, ...] = ("uuid",)

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
        align=o.align if o.align is not None else (align or ("right" if kind == "number" else "left")),
        mono=data_type in MONO_TYPES,
        tabular=kind == "number" or data_type in MONO_TYPES,
    )
    if kind == "checkbox":
        plan.checked = value is True
        plan.text = field_text(value, data_type, text_options)
        return plan
    if kind == "entity" or kind == "multi_entity":
        plan.refs = _refs_of(value)
        plan.tooltip = field_text(value, data_type, text_options)
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
        plan.tooltip = plan.text
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


def _chip_width(theme: Theme, label: str, step: str, glyph: bool = True) -> int:
    pad = CHIP_PAD[step]
    width = (pad.lead if glyph else pad.text) + pad.text
    if glyph:
        width += CHIP_GLYPH[step] + CHIP_SPACING[step].glyph
    font = theme.font(CHIP_TEXT[step], QtGui.QFont.Weight.Medium)
    return width + text_width(QtGui.QFontMetrics(font), label)


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


def _paint_chips(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    """The linked rows, as many whole chips as fit and `+n` for the rest."""
    theme = _theme_of(options)
    step = _chip_step(options.density)
    if options.entity_variant != "chip":
        labels = ", ".join(_chip_label(ref) for ref in plan.refs)
        font = theme.font(VALUE_TEXT)
        font.setUnderline(options.entity_variant == "link")
        _draw_line(painter, rect, font, _ink(theme, options), labels, plan)
        return

    widths = [float(_chip_width(theme, _chip_label(ref), step) + CHIP_GAP) for ref in plan.refs]
    fit = fit_chips(widths, float(rect.width() + CHIP_GAP), float(OVERFLOW_RESERVE))
    height = min(CHIP_HEIGHT[step], rect.height())
    x = rect.left()
    for index in range(fit.visible):
        box = QtCore.QRect(x, 0, int(widths[index]) - CHIP_GAP, height)
        box.moveTop(rect.center().y() - height // 2 + 1)
        _paint_one_chip(painter, box, plan.refs[index], theme, step, options)
        x += int(widths[index])
    if fit.hidden > 0:
        font = theme.font(META_TEXT, tabular=True)
        painter.setFont(font)
        painter.setPen(_ink(theme, options, "muted_foreground"))
        painter.drawText(
            QtCore.QRect(x, rect.top(), max(0, rect.right() + 1 - x), rect.height()),
            int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            f"+{fit.hidden}",
        )


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
    slot = QtCore.QRect(box.left() + pad.lead, 0, glyph, glyph)
    slot.moveTop(box.center().y() - glyph // 2)
    paint_icon(painter, slot, entity_glyph(ref.type), with_alpha(ink, 0.7))
    left = slot.right() + 1 + CHIP_SPACING[step].glyph
    font = theme.font(CHIP_TEXT[step], QtGui.QFont.Weight.Medium)
    painter.setFont(font)
    painter.setPen(ink)
    room = max(0, box.right() + 1 - pad.text - left)
    painter.drawText(
        QtCore.QRect(left, box.top(), room, box.height()),
        int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
        elide(QtGui.QFontMetrics(font), _chip_label(ref), room),
    )


def _status_width(theme: Theme, plan: FieldValuePlan, options: FieldValueOptions) -> int:
    step = _chip_step(options.density)
    pad = CHIP_PAD[step]
    font = theme.font(CHIP_TEXT[step], QtGui.QFont.Weight.Medium)
    return (
        pad.lead
        + CHIP_GLYPH[step]
        + CHIP_SPACING[step].glyph
        + text_width(QtGui.QFontMetrics(font), plan.text)
        + pad.text
    )


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
    box.moveTop(rect.center().y() - height // 2 + 1)
    fill_round_rect(painter, box, float(theme.radius_px("md")), None, theme.color("border"))

    ink = theme.color("foreground")
    glyph = CHIP_GLYPH[step]
    slot = QtCore.QRect(box.left() + pad.lead, 0, glyph, glyph)
    slot.moveTop(box.center().y() - glyph // 2)
    record = (options.statuses or {}).get(plan.code)
    source = _status_source(record, options.site_url, options.loader, options.on_ready)
    source.paint(painter, slot, theme, fallback=True)

    left = slot.right() + 1 + CHIP_SPACING[step].glyph
    font = theme.font(CHIP_TEXT[step], QtGui.QFont.Weight.Medium)
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
    box.moveTop(rect.center().y() - box.height() // 2)
    radius = float(theme.radius_px("md"))
    fill_round_rect(painter, box, radius, theme.color("muted"), theme.color("border"))

    loader = options.loader if options.loader is not None else image_loader()
    url = plan.image or ""
    picture = loader.pixmap_cached(url)
    if picture is None and not loader.has(url):
        loader.load(url, lambda _pixmap: options.on_ready() if options.on_ready else None, size=size)
    if picture is None or picture.isNull():
        side = min(CHECK_GLYPH, box.width(), box.height())
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
    box.moveTop(rect.center().y() - SWATCH // 2)
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
    font.setUnderline(True)
    external = link.local is None
    room = rect.width() - (LINK_GLYPH + GLYPH_GAP if external else 0)
    shown = elide(QtGui.QFontMetrics(font), plan.text, max(0, room))
    painter.setFont(font)
    painter.setPen(ink)
    painter.drawText(
        QtCore.QRect(rect.left(), rect.top(), max(0, room), rect.height()),
        _align_flags(plan),
        shown,
    )
    if external:
        left = rect.left() + min(text_width(QtGui.QFontMetrics(font), shown), max(0, room)) + GLYPH_GAP
        slot = QtCore.QRect(left, 0, LINK_GLYPH, LINK_GLYPH)
        slot.moveTop(rect.center().y() - LINK_GLYPH // 2)
        paint_icon(painter, slot, LINK_ICON, with_alpha(ink, 0.7))


def _paint_checkbox(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    plan: FieldValuePlan,
    options: FieldValueOptions,
) -> None:
    theme = _theme_of(options)
    box = QtCore.QRect(rect.left(), 0, CHECK_GLYPH, CHECK_GLYPH)
    box.moveTop(rect.center().y() - CHECK_GLYPH // 2)
    if plan.checked:
        paint_icon(painter, box, CHECK_ICON, _ink(theme, options))
    else:
        paint_icon(painter, box, UNCHECK_ICON, _ink(theme, options, "muted_foreground"))


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
        widths = [_chip_width(theme, _chip_label(ref), step) for ref in plan.refs]
        total = sum(widths) + CHIP_GAP * max(0, len(widths) - 1)
        return QtCore.QSize(total, CHIP_HEIGHT[step])
    if plan.kind == "status":
        return QtCore.QSize(_status_width(theme, plan, o), CHIP_HEIGHT[step])
    if plan.kind == "image":
        return _image_size()
    if plan.kind == "checkbox":
        return QtCore.QSize(CHECK_GLYPH, max(CHECK_GLYPH, QtGui.QFontMetrics(theme.font(VALUE_TEXT)).height()))

    font = theme.font(META_TEXT) if plan.kind == "empty" else _value_font(theme, plan)
    metrics = QtGui.QFontMetrics(font)
    if o.wrap and plan.wrap and width is not None:
        box = metrics.boundingRect(
            QtCore.QRect(0, 0, max(1, int(width)), 1 << 16),
            int(QtCore.Qt.TextFlag.TextWordWrap),
            plan.text,
        )
        return QtCore.QSize(int(width), max(metrics.height(), box.height()))
    extra = 0
    if plan.kind == "color" and plan.rgb is not None:
        extra = SWATCH + GLYPH_GAP
    elif plan.kind == "url" and plan.link is not None and plan.link.href and plan.link.local is None:
        extra = LINK_GLYPH + GLYPH_GAP
    widest = max(
        (text_width(metrics, line) for line in plan.text.splitlines() or [""]),
        default=0,
    )
    return QtCore.QSize(widest + extra, max(metrics.height(), SWATCH))


# --- the widget face --------------------------------------------------------------------------


class _ChipRow(ThemedWidget):
    """The chips of a linked value, and the `+n` the row overflows into.

    A chip is never cut: one that does not fit whole is hidden, and so is every chip after it,
    which is core's `fit_chips`, the rule a picker's token field already draws by.
    """

    def __init__(self, step: str = "sm", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("field-value-chips")
        self._step = step
        self._chips: list[EntityChip] = []
        self._hidden = 0
        self._pill_left = 0
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    @property
    def chips(self) -> list[EntityChip]:
        """The chips, in order. Those past the fit are hidden."""
        return list(self._chips)

    @property
    def hidden(self) -> int:
        """How many chips the row had no room for."""
        return self._hidden

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

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        widths = [chip.sizeHint().width() for chip in self._chips]
        total = sum(widths) + CHIP_GAP * max(0, len(widths) - 1)
        return QtCore.QSize(total, CHIP_HEIGHT[self._step])

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, CHIP_HEIGHT[self._step])

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._lay()

    def _lay(self) -> None:
        widths = [float(chip.sizeHint().width() + CHIP_GAP) for chip in self._chips]
        fit = fit_chips(widths, float(self.width() + CHIP_GAP), float(OVERFLOW_RESERVE))
        self._hidden = fit.hidden
        x = 0
        height = CHIP_HEIGHT[self._step]
        top = max(0, (self.height() - height) // 2)
        for index, chip in enumerate(self._chips):
            if index < fit.visible:
                chip.setGeometry(QtCore.QRect(x, top, int(widths[index]) - CHIP_GAP, height))
                chip.show()
                x += int(widths[index])
            else:
                chip.hide()
        self._pill_left = x
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._hidden <= 0:
            return
        theme = self.theme
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        painter.setFont(theme.font(META_TEXT, tabular=True))
        painter.setPen(theme.color("muted_foreground"))
        left = self._pill_left
        painter.drawText(
            QtCore.QRect(left, 0, max(0, self.width() - left), self.height()),
            int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            f"+{self._hidden}",
        )
        painter.end()


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
        return self._child is None and self._plan.wrap

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return field_value_size_hint(self._value, self._data_type, self.options(), width=width).height()

    def _place_child(self) -> None:
        """The one widget a value is, at the top left of the room the value has."""
        child = self._child
        if child is None:
            return
        hint = child.sizeHint()
        expands = child.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Policy.Expanding
        width = self.width() if expands else min(hint.width(), self.width())
        child.setGeometry(0, 0, max(0, width), max(0, min(hint.height(), self.height())))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_child()
        if self._plan.wrap:
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
