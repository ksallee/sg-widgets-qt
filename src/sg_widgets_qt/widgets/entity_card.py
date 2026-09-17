"""One row as a card.

Ported from `packages/react/src/registry/sg/components/entity-card.tsx` over core's
`describe_entity_card` and `load_entity_card`.

Given a reference the card reads the row itself: one search asking for the type's identity chain,
its thumbnail, its status field and the caller's paths at once, through the context's cache, so a
second card on the same row costs nothing. Every path is labelled through the schema, and a hop
names the type it travels through only when the field could have gone somewhere else, which is the
same ambiguity the projection resolves (probe 059).

Values are drawn here rather than through FieldValue: FieldValue draws a linked row as a chip, and
a chip's own hover card is this card, so the two would depend on each other. A card is a compact
surface, so a linked row is a link and the rest is one line of text through core's `field_text`.

    card = EntityCard(context=context, entity=EntityRef("Version", 17055), fields=["user"])
    card.clicked.connect(open_it)
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import cell_value
from sg_widgets_core.context import SgContext, context_from_client, preferences_of
from sg_widgets_core.entity_card import (
    EntityCardColumn,
    EntityCardModel,
    EntityCardOptions,
    describe_entity_card,
    load_entity_card,
)
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.presentation import entity_detail_url
from sg_widgets_core.render import (
    FieldTextOptions,
    field_text,
    image_state,
    is_empty_value,
    render_kind_for,
    url_link,
)
from sg_widgets_core.row import FieldSpec, path_of
from sg_widgets_core.state import StateLabels, error_text
from sg_widgets_core.status import StatusRecord

from ..icons import paint_icon
from ..images import ImageLoader, grayscale, image_loader
from ..primitives.base import (
    CHIP_HEIGHT,
    THUMB_SIZE,
    ThemedWidget,
    elide,
    fill_round_rect,
    painter_for,
    text_width,
)
from ..primitives.skeleton import Skeleton
from ..theme import Theme, theme_for, with_alpha
from ..workers import JobPool, Ticket, default_pool
from .entity_glyphs import entity_glyph
from .field_value import FieldValueOptions, field_value_size_hint, paint_field_value
from .state_line import StateLine
from .status_badge import StatusBadge
from .thumbnail import THUMBNAIL_GLYPH, Thumbnail

__all__ = [
    "ENTITY_CARD_SIZE_VALUES",
    "ENTITY_CARD_VARIANT_VALUES",
    "CARD_BADGE",
    "CARD_HEADER_GAP",
    "CARD_NAME",
    "CARD_ROW_GAP",
    "CARD_STACK",
    "CARD_THUMB",
    "CARD_TILE_BODY",
    "CARD_TILE_WIDTH",
    "CardTile",
    "CardTileOptions",
    "EntityCard",
    "card_tile_checkbox_rect",
    "card_tile_media_rect",
    "card_tile_size",
    "paint_card_tile",
    "tile_of",
]

#: The three steps a card stands on.
ENTITY_CARD_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")

#: `card` is the stacked surface; `tile` is the thumbnail-first cell a grid lays out.
ENTITY_CARD_VARIANT_VALUES: tuple[str, ...] = ("card", "tile")

#: Cards and detail panes take the top of the thumbnail ladder (`docs/design-rules.md` rule 3).
CARD_THUMB: dict[str, str] = {"sm": "xl", "md": "xl", "lg": "2xl"}

#: A badge sits one step under the card it is in (rule 3).
CARD_BADGE: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: Between the thumbnail and the identity column, between the sections, and between the grid rows.
CARD_HEADER_GAP: dict[str, int] = {"sm": 8, "md": 12, "lg": 12}
CARD_STACK: dict[str, int] = {"sm": 8, "md": 12, "lg": 16}
CARD_ROW_GAP: dict[str, int] = {"sm": 6, "md": 8, "lg": 8}

#: The name's type step, and the metadata step under it (rule 6).
CARD_NAME: dict[str, int] = {"sm": 14, "md": 14, "lg": 16}
CARD_META = 12
CARD_VALUE = 14

#: Between the type glyph and its label, and between the columns of the grid.
GLYPH_GAP = 6
GRID_GAP = 12

#: The glyph beside the type label.
TYPE_GLYPH = 16

#: The skeleton lines the header stands behind, and the two the grid gives a row.
SKELETON_NAME = 16
SKELETON_META = 12
SKELETON_LABEL = 64

#: Between the header's two skeleton lines, which stand further apart than the lines they replace.
SKELETON_GAP = 8

#: The share of the header each line takes, so the block is shaped like the name under it.
SKELETON_NAME_SHARE = 0.75
SKELETON_META_SHARE = 0.5

#: What a failed read is drawn with.
ERROR_ICON = "circle-alert"


class _Link:
    """One run of a value that opens somewhere: where it is, what it says, where it goes."""

    __slots__ = ("label", "rect", "url")

    def __init__(self, rect: QtCore.QRect, label: str, url: str) -> None:
        self.rect = rect
        self.label = label
        self.url = url


class _FieldLabel(ThemedWidget):
    """A column's name, sitting on the baseline of the value beside it.

    The label is a size under the value, so a row that stretched would hang it above the value's
    first line. Drawing it at the value's own baseline holds the two level.
    """

    def __init__(self, text: str = "", baseline: int = 0, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card-label")
        self._text = text
        self._baseline = baseline
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    def set_baseline(self, value: int) -> None:
        """Where the value beside this label puts its first line's baseline."""
        self._baseline = int(value)
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(CARD_META)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(text_width(metrics, self._text), max(metrics.height(), self._baseline))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        font = self._font()
        painter.setFont(font)
        painter.setPen(self.theme.color("muted_foreground"))
        metrics = QtGui.QFontMetrics(font)
        shown = elide(metrics, self._text, self.width())
        self.set_elide_tooltip(self._text, shown == self._text)
        baseline = self._baseline if self._baseline > 0 else metrics.ascent()
        painter.drawText(0, baseline, shown)
        painter.end()


class _CardValue(ThemedWidget):
    """One value of the grid, drawn by its data type.

    A status is a badge, an image a thumbnail, a linked row a link to its own page, and everything
    else the text core's formatters give it. Free text keeps its newlines.
    """

    def __init__(
        self,
        column: EntityCardColumn | None = None,
        statuses: Mapping[str, StatusRecord] | None = None,
        site_url: str = "",
        text_options: FieldTextOptions | None = None,
        empty_label: str = "empty",
        size: str = "md",
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card-value")
        self._column = column
        self._statuses = statuses or {}
        self._site_url = site_url
        self._text_options = text_options if text_options is not None else FieldTextOptions()
        self._empty_label = empty_label
        self._size = size
        self._loader = loader if loader is not None else image_loader()
        self._links: list[_Link] = []
        self._cursor = 0
        #: Which link the pointer is on, so that one alone is underlined.
        self._hovered_link = -1
        self._child: QtWidgets.QWidget | None = None
        self.setMouseTracking(True)

        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(0)
        # No layout: a widget that holds one answers its layout's `heightForWidth`, and an empty
        # one answers zero, which would flatten a value the widget paints itself.
        self._build()

    # --- what it is ---

    @property
    def column(self) -> EntityCardColumn | None:
        return self._column

    @property
    def kind(self) -> str:
        """The rendering core chose for the column's data type, or `empty`."""
        column = self._column
        if column is None:
            return "empty"
        kind = render_kind_for(column.data_type)
        if kind == "empty" or is_empty_value(column.value):
            return "empty"
        return kind

    @property
    def child(self) -> QtWidgets.QWidget | None:
        """The badge or the picture the value is, where it is one."""
        return self._child

    @property
    def links(self) -> list[_Link]:
        """The runs of this value that open somewhere. Filled once the value has been drawn."""
        return list(self._links)

    @property
    def text(self) -> str:
        """The value as one line of text, which is what a compact surface shows."""
        column = self._column
        if column is None or self.kind == "empty":
            return ""
        options = self._options()
        if self.kind in ("entity", "multi_entity"):
            return field_text(column.value, column.data_type, options)
        if self.kind == "url":
            link = url_link(column.value)
            return link.label if link is not None else ""
        return field_text(column.value, column.data_type, options)

    def _options(self) -> FieldTextOptions:
        options = FieldTextOptions(**dict(self._text_options.__dict__))
        field = self._column.field if self._column is not None else None
        if field is not None and field.display_values is not None:
            options.display_values = field.display_values
        return options

    def _refs(self) -> list[EntityRef]:
        """An entity value and a multi_entity value are one shape, one boxed (field_types/multi_entity)."""
        raw = self._column.value if self._column is not None else None
        rows = raw if isinstance(raw, (list, tuple)) else [raw]
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

    # --- building ---

    def _build(self) -> None:
        if self._child is not None:
            self._child.setParent(None)
            self._child.deleteLater()
            self._child = None
        column = self._column
        kind = self.kind
        if column is not None and kind == "status":
            record = self._statuses.get(str(column.value))
            self._child = StatusBadge(
                code=str(column.value),
                status=record,
                field=column.field,
                size=CARD_BADGE[self._size],
                site_url=self._site_url,
                loader=self._loader,
                parent=self,
            )
        elif column is not None and kind == "image":
            self._child = Thumbnail(
                src=str(column.value), size="sm", loader=self._loader, parent=self
            )
        if self._child is not None:
            self._child.show()
            self._place_child()
        self.setToolTip("" if kind in ("empty", "image") else self.text)
        self._apply_focus_policy()
        self.updateGeometry()
        self.update()

    def _apply_focus_policy(self) -> None:
        policy = QtCore.Qt.FocusPolicy
        reachable = self.kind in ("entity", "multi_entity", "url")
        self.setFocusPolicy(policy.TabFocus if reachable else policy.NoFocus)

    # --- geometry ---

    def _font(self) -> QtGui.QFont:
        return self.theme.font(CARD_VALUE, tabular=self.kind == "number")

    def baseline(self) -> int:
        """Where this value puts its first line's baseline, which the label sits on too."""
        return QtGui.QFontMetrics(self._font()).ascent()

    def _wraps(self) -> bool:
        column = self._column
        return (
            column is not None
            and self.kind == "text"
            and column.data_type == "text"
        )

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        if self._child is not None:
            return QtCore.QSize(self._child.sizeHint().width(), self._child.sizeHint().height())
        metrics = QtGui.QFontMetrics(self._font())
        if self._wraps() and self.width() > 0:
            return QtCore.QSize(self.width(), self.heightForWidth(self.width()))
        return QtCore.QSize(text_width(metrics, self.text.replace("\n", " ")), metrics.height())

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return self._child is None and self._wraps()

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        if not self._wraps():
            return metrics.height()
        box = metrics.boundingRect(
            QtCore.QRect(0, 0, max(1, width), 1 << 16),
            int(QtCore.Qt.TextFlag.TextWordWrap),
            self.text,
        )
        return max(metrics.height(), box.height())

    def _place_child(self) -> None:
        """The badge or the picture, at the top left of the room the value has."""
        child = self._child
        if child is None:
            return
        hint = child.sizeHint()
        child.setGeometry(
            0, 0, max(0, min(hint.width(), self.width())), max(0, min(hint.height(), self.height()))
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_child()
        if self._wraps():
            self.updateGeometry()

    # --- interaction ---

    def _open(self, url: str) -> None:
        if url:
            # The row's own page and an attachment are outside this application.
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _link_at(self, point: QtCore.QPoint) -> int:
        """Which link the pointer is on, or -1."""
        for index, link in enumerate(self._links):
            if link.rect.contains(point):
                return index
        return -1

    def _set_hovered_link(self, index: int) -> None:
        if index == self._hovered_link:
            return
        self._hovered_link = index
        self.setCursor(
            QtCore.Qt.CursorShape.PointingHandCursor
            if index >= 0
            else QtCore.Qt.CursorShape.ArrowCursor
        )
        self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self._set_hovered_link(self._link_at(event.pos()) if self.isEnabled() else -1)
        super().mouseMoveEvent(event)

    def on_hover_changed(self, value: bool) -> None:
        """The pointer left the value, so no link is under it any more."""
        if not value:
            self._set_hovered_link(-1)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            for index, link in enumerate(self._links):
                if link.rect.contains(event.pos()):
                    self._cursor = index
                    self._open(link.url)
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if self.isEnabled() and self._links:
            if key in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Space):
                self._open(self._links[min(self._cursor, len(self._links) - 1)].url)
                event.accept()
                return
            if key in (QtCore.Qt.Key.Key_Right, QtCore.Qt.Key.Key_Left):
                step = 1 if key == QtCore.Qt.Key.Key_Right else -1
                self._cursor = max(0, min(len(self._links) - 1, self._cursor + step))
                self.update()
                event.accept()
                return
        super().keyPressEvent(event)

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        self._links = []
        if self._child is not None:
            return
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        kind = self.kind
        if kind == "empty":
            font = theme.font(CARD_META)
            font.setItalic(True)
            painter.setFont(font)
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                self.rect(),
                int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop),
                self._empty_label,
            )
            painter.end()
            return
        if kind in ("entity", "multi_entity"):
            self._paint_links(painter, theme)
        elif kind == "url":
            self._paint_url(painter, theme)
        elif self._wraps():
            painter.setFont(self._font())
            painter.setPen(theme.color("foreground"))
            painter.drawText(
                self.rect(),
                int(
                    QtCore.Qt.AlignmentFlag.AlignLeft
                    | QtCore.Qt.AlignmentFlag.AlignTop
                    | QtCore.Qt.TextFlag.TextWordWrap
                ),
                self.text,
            )
        else:
            font = self._font()
            painter.setFont(font)
            painter.setPen(theme.color("foreground"))
            painter.drawText(
                self.rect(),
                int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop),
                elide(QtGui.QFontMetrics(font), self.text.replace("\n", " "), self.width()),
            )
        if self.keyboard_focus and self._links:
            box = self._links[min(self._cursor, len(self._links) - 1)].rect
            self.paint_focus_ring(painter, box.adjusted(-2, -1, 2, 1), float(theme.radius_px("sm")))
        painter.end()

    def _paint_runs(self, painter: QtGui.QPainter, theme: Theme, runs: list[tuple[str, str]]) -> None:
        """The runs of a value on one line, each one its own link.

        A link reads as text until the pointer is on it, which is what upstream's link class does:
        a card is a stack of values, and underlining every one of them turns it into a rule.
        """
        marked = theme.font(CARD_VALUE)
        marked.setUnderline(True)
        plain = theme.font(CARD_VALUE)
        # Both fonts measure the same, so the runs land in the same place under the pointer.
        metrics = QtGui.QFontMetrics(plain)
        left = 0
        for index, (label, url) in enumerate(runs):
            if index > 0:
                painter.setFont(plain)
                painter.setPen(theme.color("muted_foreground"))
                separator = ", "
                painter.drawText(left, metrics.ascent(), separator)
                left += text_width(metrics, separator)
            room = max(0, self.width() - left)
            if room <= 0:
                break
            shown = elide(metrics, label, room)
            painter.setFont(marked if url and index == self._hovered_link else plain)
            painter.setPen(theme.color("foreground"))
            painter.drawText(left, metrics.ascent(), shown)
            width = text_width(metrics, shown)
            if url:
                self._links.append(
                    _Link(QtCore.QRect(left, 0, width, metrics.height()), label, url)
                )
            left += width

    def _paint_links(self, painter: QtGui.QPainter, theme: Theme) -> None:
        runs = []
        for ref in self._refs():
            name = field_text(ref, "entity")
            runs.append((name, entity_detail_url(self._site_url, ref) or ""))
        self._paint_runs(painter, theme, runs)

    def _paint_url(self, painter: QtGui.QPainter, theme: Theme) -> None:
        column = self._column
        link = url_link(column.value) if column is not None else None
        if link is None:
            return
        # A link is its underline and nothing else, as the web widget's anchor is.
        self._paint_runs(painter, theme, [(link.label, link.href or "")])


class _CardName(ThemedWidget):
    """The row's name, a link to its own page on the site when there is one."""

    activated = QtCore.Signal()

    def __init__(
        self,
        text: str = "",
        url: str = "",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card-name")
        self._text = text
        self._url = url
        self._size = size
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._apply_focus_policy()

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.setAccessibleName(value)
        self.updateGeometry()
        self.update()

    @property
    def url(self) -> str:
        """The row's page on the site, or an empty string when no site is known."""
        return self._url

    def set_url(self, value: str) -> None:
        self._url = value
        self._apply_focus_policy()
        self.update()

    def set_size(self, value: str) -> None:
        self._size = value
        self.updateGeometry()
        self.update()

    def _apply_focus_policy(self) -> None:
        policy = QtCore.Qt.FocusPolicy
        self.setFocusPolicy(policy.TabFocus if self._url else policy.NoFocus)

    def _font(self) -> QtGui.QFont:
        font = self.theme.font(CARD_NAME[self._size], QtGui.QFont.Weight.Medium)
        if self._url and self.hovered:
            font.setUnderline(True)
        return font

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(text_width(metrics, self._text), metrics.height())

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def on_hover_changed(self, value: bool) -> None:
        self.update()

    def _activate(self) -> None:
        if self._url:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._url))
        self.activated.emit()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if (
            self.isEnabled()
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and self.rect().contains(event.pos())
        ):
            self._activate()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Space)
        if self.isEnabled() and event.key() in keys:
            self._activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        font = self._font()
        painter.setFont(font)
        painter.setPen(self.theme.color("foreground"))
        metrics = QtGui.QFontMetrics(font)
        shown = elide(metrics, self._text, self.width())
        self.setToolTip(self._text)
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            shown,
        )
        if self.keyboard_focus and self._url:
            self.paint_focus_ring(painter, self.rect(), float(self.theme.radius_px("sm")))
        painter.end()


class _TypeLine(ThemedWidget):
    """The type's glyph and its display name, under the row's name."""

    def __init__(
        self,
        entity_type: str = "",
        label: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card-type")
        self._entity_type = entity_type
        self._label = label
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

    def set_type(self, entity_type: str, label: str) -> None:
        self._entity_type = entity_type
        self._label = label
        self.updateGeometry()
        self.update()

    @property
    def label(self) -> str:
        return self._label

    def _font(self) -> QtGui.QFont:
        return self.theme.font(CARD_META)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        width = TYPE_GLYPH + GLYPH_GAP + text_width(metrics, self._label)
        return QtCore.QSize(width, max(metrics.height(), TYPE_GLYPH))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(TYPE_GLYPH, self.sizeHint().height())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        ink = theme.color("muted_foreground")
        slot = QtCore.QRect(0, 0, TYPE_GLYPH, TYPE_GLYPH)
        slot.moveTop(self.rect().center().y() - TYPE_GLYPH // 2)
        paint_icon(painter, slot, entity_glyph(self._entity_type), with_alpha(ink, 0.7))
        font = self._font()
        painter.setFont(font)
        painter.setPen(ink)
        left = TYPE_GLYPH + GLYPH_GAP
        painter.drawText(
            QtCore.QRect(left, 0, max(0, self.width() - left), self.height()),
            int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            elide(QtGui.QFontMetrics(font), self._label, max(0, self.width() - left)),
        )
        painter.end()


class EntityCard(ThemedWidget):
    """One row as a card: its thumbnail, name, type, status and a grid of the paths you name."""

    #: The card's name was activated. The row's own page opens with it when a site is known.
    clicked = QtCore.Signal()
    #: The tile's checkbox was toggled.
    selected_changed = QtCore.Signal(bool)
    #: The read settled: True when the card holds a row, False when it failed.
    loaded = QtCore.Signal(bool)

    def __init__(
        self,
        context: SgContext | None = None,
        client: object = None,
        row: EntityRow | None = None,
        entity: EntityRef | None = None,
        fields: list[str] | None = None,
        variant: str = "card",
        size: str = "md",
        image_path: str = "image",
        label_field: str | None = None,
        sub_label_field: FieldSpec | None = None,
        sub_label: Callable[[EntityRow], str] | None = None,
        secondary_field: FieldSpec | None = None,
        secondary: Callable[[EntityRow], str] | None = None,
        show_code: bool = False,
        statuses: Mapping[str, StatusRecord] | None = None,
        selectable: bool = False,
        selected: bool = False,
        actions: QtWidgets.QWidget | None = None,
        site_url: str = "",
        hours_per_day: float | None = None,
        locale: str | None = None,
        time_zone: str | None = None,
        frame_rate: float | None = None,
        empty_label: str = "empty",
        error_label: str | None = None,
        loader: ImageLoader | None = None,
        pool: JobPool | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card")
        self._context = context if context is not None else _context_of(client)
        self._row = row
        self._entity = entity
        self._fields = list(fields or [])
        self._variant = variant if variant in ENTITY_CARD_VARIANT_VALUES else "card"
        self._size = size if size in ENTITY_CARD_SIZE_VALUES else "md"
        self._image_path = image_path
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._statuses = statuses
        self._selectable = bool(selectable)
        self._selected = bool(selected)
        self._actions = actions
        self._site_url = site_url
        self._hours_per_day = hours_per_day
        self._locale = locale
        self._time_zone = time_zone
        self._frame_rate = frame_rate
        self._empty_label = empty_label
        self._error_label = error_label
        self._loader = loader if loader is not None else image_loader()
        self._pool = pool if pool is not None else default_pool()
        self._ticket = Ticket()

        self._model: EntityCardModel | None = None
        self._table: dict[str, StatusRecord] = {}
        self._error: str | None = None
        self._values: list[_CardValue] = []

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(CARD_STACK[self._size])
        self._body: QtWidgets.QWidget | None = None
        self._read()

    # --- props ---

    @property
    def context(self) -> SgContext | None:
        """The cached client, the schema, the site url and the preferences the card reads through."""
        return self._context

    def set_context(self, value: SgContext | None) -> None:
        self._context = value
        self._read()

    def set_client(self, value: object) -> None:
        """Read through a bare client. One context is built per client and shared."""
        self.set_context(_context_of(value))

    @property
    def row(self) -> EntityRow | None:
        """A row you already read. Given, the card reads no row of its own."""
        return self._row

    def set_row(self, value: EntityRow | None) -> None:
        self._row = value
        self._read()

    @property
    def entity(self) -> EntityRef | None:
        """The row to read, when no row is given."""
        return self._entity

    def set_entity(self, value: EntityRef | None) -> None:
        self._entity = value
        self._read()

    @property
    def fields(self) -> list[str]:
        """Field paths for the grid, in order. Dotted paths allowed."""
        return list(self._fields)

    def set_fields(self, value: list[str] | None) -> None:
        self._fields = list(value or [])
        self._read()

    @property
    def variant(self) -> str:
        """`card`, the stacked surface, or `tile`, the thumbnail-first cell a grid lays out."""
        return self._variant

    def set_variant(self, value: str) -> None:
        self._variant = value if value in ENTITY_CARD_VARIANT_VALUES else "card"
        self._read()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the thumbnail step, with the gaps and the name scale to match."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in ENTITY_CARD_SIZE_VALUES else "md"
        self._column.setSpacing(CARD_STACK[self._size])
        self._rebuild()

    @property
    def image_path(self) -> str:
        """The image field the thumbnail comes from."""
        return self._image_path

    def set_image_path(self, value: str) -> None:
        self._image_path = value
        self._read()

    @property
    def label_field(self) -> str | None:
        """Field shown as the name. Tile only."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self._rebuild()

    @property
    def sub_label_field(self) -> FieldSpec | None:
        """The left of the tile's metadata line. Tile only."""
        return self._sub_label_field

    def set_sub_label_field(self, value: FieldSpec | None) -> None:
        self._sub_label_field = value
        self._read()

    @property
    def sub_label(self) -> Callable[[EntityRow], str] | None:
        """The caller's own sub-label. Wins over `sub_label_field`. Tile only."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[EntityRow], str] | None) -> None:
        self._sub_label = value
        self._rebuild()

    @property
    def secondary_field(self) -> FieldSpec | None:
        """The right of the tile's metadata line. Tile only."""
        return self._secondary_field

    def set_secondary_field(self, value: FieldSpec | None) -> None:
        self._secondary_field = value
        self._read()

    @property
    def secondary(self) -> Callable[[EntityRow], str] | None:
        """The caller's own text on the right of the metadata line. Tile only."""
        return self._secondary

    def set_secondary(self, value: Callable[[EntityRow], str] | None) -> None:
        self._secondary = value
        self._rebuild()

    @property
    def show_code(self) -> bool:
        """Show the row's `code` beside the name when the two differ. Tile only."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._rebuild()

    @property
    def statuses(self) -> Mapping[str, StatusRecord] | None:
        """`Status` rows by code (probe 010). Read through the context when not given."""
        return self._statuses

    def set_statuses(self, value: Mapping[str, StatusRecord] | None) -> None:
        self._statuses = value
        self._read()

    @property
    def selectable(self) -> bool:
        """Draws the tile's selection checkbox. Tile only."""
        return self._selectable

    def set_selectable(self, value: bool) -> None:
        self._selectable = bool(value)
        self._rebuild()

    @property
    def selected(self) -> bool:
        """Whether the tile is taken. Tile only."""
        return self._selected

    def set_selected(self, value: bool) -> None:
        value = bool(value)
        if value == self._selected:
            return
        self._selected = value
        if isinstance(self._body, _TilePane):
            self._body.set_selected(value)
        self.selected_changed.emit(value)
        self.update()

    @property
    def actions(self) -> QtWidgets.QWidget | None:
        """Controls in the thumbnail's top-right corner. Tile only."""
        return self._actions

    def set_actions(self, value: QtWidgets.QWidget | None) -> None:
        self._actions = value
        self._rebuild()

    @property
    def site_url(self) -> str:
        """The site the name and every linked row point at. Defaults to the context's."""
        return self._site_url or (self._context.site_url if self._context is not None else "")

    def set_site_url(self, value: str) -> None:
        self._site_url = value
        self._rebuild()

    @property
    def hours_per_day(self) -> float | None:
        """The site's working day. Durations then render in days (field_types/duration)."""
        return self._hours_per_day

    def set_hours_per_day(self, value: float | None) -> None:
        self._hours_per_day = value
        self._rebuild()

    @property
    def locale(self) -> str | None:
        """Used for dates and numbers."""
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
        """Frames a second. A timecode then carries its frame digits."""
        return self._frame_rate

    def set_frame_rate(self, value: float | None) -> None:
        self._frame_rate = value
        self._rebuild()

    @property
    def empty_label(self) -> str:
        """What a field with no value shows."""
        return self._empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = value
        self._rebuild()

    @property
    def error_label(self) -> str | None:
        """Shown in place of what the failed read said."""
        return self._error_label

    def set_error_label(self, value: str | None) -> None:
        self._error_label = value
        self._rebuild()

    # --- what it holds ---

    @property
    def model(self) -> EntityCardModel | None:
        """The card core described, once the read has settled."""
        return self._model

    @property
    def error(self) -> str | None:
        """What the failed read said, or None."""
        return self._error

    @property
    def loading(self) -> bool:
        """True while the card stands behind its skeleton."""
        return self._model is None and self._error is None

    @property
    def values(self) -> list[_CardValue]:
        """The value of each column of the grid, in order."""
        return list(self._values)

    @property
    def name(self) -> str:
        """The row's name, or an empty string while the read is in flight."""
        if self._model is None:
            return ""
        if self._label_field:
            return str(cell_value(self._model.row, self._label_field) or "")
        return self._model.name

    @property
    def url(self) -> str:
        """The row's own page on the site, or an empty string when no site is known."""
        if self._model is None:
            return ""
        return entity_detail_url(self.site_url, self._model.entity) or ""

    # --- the read ---

    def _paths(self) -> list[str]:
        """The paths the read asks for: the caller's grid, or the tile's metadata line."""
        if self._variant != "tile":
            return list(self._fields)
        named = [path_of(self._sub_label_field), path_of(self._secondary_field)]
        return list(dict.fromkeys(path for path in named if path))

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
        return options

    def _read(self) -> None:
        """Describe the row, or read it, on a worker. A stale answer is dropped."""
        self._model = None
        self._error = None
        self._rebuild()
        context = self._context
        if context is None:
            self._failed(ValueError("An entity card needs a context or a client."))
            return
        if self._row is None and self._entity is None:
            self._failed(ValueError("An entity card needs a row or a reference."))
            return
        options = EntityCardOptions(fields=self._paths(), image_path=self._image_path)
        n = self._ticket.next()
        self._pool.submit(
            _describe,
            context,
            self._row,
            self._entity,
            options,
            self._statuses,
            on_result=self._answered,
            on_error=self._failed,
            ticket=(self._ticket, n),
        )

    def _answered(self, answer: Any) -> None:
        model, table = answer
        self._model = model
        self._table = table
        self._error = None
        self._rebuild()
        self.loaded.emit(True)

    def _failed(self, error: BaseException) -> None:
        self._model = None
        self._error = error_text(error)
        self._rebuild()
        self.loaded.emit(False)

    # --- building ---

    def _clear(self) -> None:
        self._values = []
        if self._body is not None:
            self._column.removeWidget(self._body)
            self._body.setParent(None)
            self._body.deleteLater()
            self._body = None
        while self._column.count():
            self._column.takeAt(0)

    def _rebuild(self) -> None:
        self._clear()
        tile = self._variant == "tile"
        if self._error is not None:
            self._body = self._error_block()
        elif self._model is None:
            self._body = self._tile_skeleton() if tile else self._skeleton_block()
        elif tile:
            self._body = self._tile_block(self._model)
        else:
            self._body = self._card_block(self._model)
        self._column.addWidget(self._body)
        self.updateGeometry()
        self.update()

    def _tile_text(self, path: str, custom: Callable[[EntityRow], str] | None) -> str:
        """One side of the tile's metadata line: the caller's own, then the column's own text."""
        model = self._model
        if model is None:
            return ""
        if custom is not None:
            return custom(model.row)
        if not path:
            return ""
        column = next((entry for entry in model.columns if entry.path == path), None)
        if column is None or is_empty_value(column.value):
            return ""
        return field_text(column.value, column.data_type, self._text_options())

    def _tile_block(self, model: EntityCardModel) -> QtWidgets.QWidget:
        """The thumbnail-first cell a grid lays out, drawn through the shared tile face."""
        tile = tile_of(
            model,
            label_field=self._label_field,
            sub_label=self._tile_text(path_of(self._sub_label_field), self._sub_label),
            secondary=self._tile_text(path_of(self._secondary_field), self._secondary),
            show_code=self._show_code,
        )
        pane = _TilePane(
            tile,
            CardTileOptions(
                size=self._size,
                statuses=self._statuses if self._statuses is not None else self._table,
                site_url=self.site_url,
                selectable=self._selectable,
                selected=self._selected,
                loader=self._loader,
            ),
            self,
        )
        pane.toggled.connect(self.set_selected)
        pane.activated.connect(self.clicked.emit)
        return pane

    def _tile_skeleton(self) -> QtWidgets.QWidget:
        """A tile's own shape while the read is in flight: the picture, then two lines."""
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("entity-card-tile-skeleton")
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        picture = Skeleton(height=card_tile_size(self._size).height() // 2, parent=holder)
        picture.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        column.addWidget(picture)
        body = QtWidgets.QWidget(holder)
        lines = QtWidgets.QVBoxLayout(body)
        pad = CARD_TILE_BODY[self._size]
        lines.setContentsMargins(pad, pad, pad, pad)
        lines.setSpacing(CARD_TILE_GAP)
        lines.addWidget(Skeleton(height=SKELETON_NAME, parent=body))
        lines.addWidget(Skeleton(width=SKELETON_LABEL, height=SKELETON_META, parent=body))
        column.addWidget(body)
        return holder

    def _error_block(self) -> QtWidgets.QWidget:
        line = StateLine(pad="none", slot_name="entity-card-error", parent=self)
        line.set_icon(ERROR_ICON)
        line.apply_state("error", StateLabels(error_label=self._error_label), self._error)
        return line

    def _skeleton_block(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("entity-card-skeleton")
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(CARD_STACK[self._size])

        header = QtWidgets.QWidget(holder)
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(CARD_HEADER_GAP[self._size])
        side = THUMB_SIZE[CARD_THUMB[self._size]]
        row.addWidget(Skeleton(width=int(round(side * 16 / 9)), height=side, parent=header))
        lines = QtWidgets.QWidget(header)
        stack = QtWidgets.QVBoxLayout(lines)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(SKELETON_GAP)
        # A skeleton stands in for what it replaces, so the name's block runs three quarters of
        # the header and the line under it half, which is the shape a name and a type line have.
        stack.addWidget(_part(lines, SKELETON_NAME, SKELETON_NAME_SHARE))
        stack.addWidget(_part(lines, SKELETON_META, SKELETON_META_SHARE))
        stack.addStretch(1)
        row.addWidget(lines, 1)
        column.addWidget(header)

        if self._fields:
            grid_holder = QtWidgets.QWidget(holder)
            grid = QtWidgets.QGridLayout(grid_holder)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(GRID_GAP)
            grid.setVerticalSpacing(CARD_ROW_GAP[self._size])
            grid.setColumnStretch(1, 1)
            for index, _path in enumerate(self._fields):
                grid.addWidget(
                    Skeleton(width=SKELETON_LABEL, height=SKELETON_META, parent=grid_holder),
                    index,
                    0,
                )
                grid.addWidget(Skeleton(height=SKELETON_META, parent=grid_holder), index, 1)
            column.addWidget(grid_holder)
        return holder

    def _card_block(self, model: EntityCardModel) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("entity-card-body")
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(CARD_STACK[self._size])
        column.addWidget(self._header_block(model, holder))
        if model.columns:
            column.addWidget(self._grid_block(model, holder))
        return holder

    def _header_block(self, model: EntityCardModel, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        header = QtWidgets.QWidget(parent)
        header.setObjectName("entity-card-header")
        row = QtWidgets.QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(CARD_HEADER_GAP[self._size])
        row.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        row.addWidget(
            Thumbnail(
                src=model.thumbnail,
                size=CARD_THUMB[self._size],
                entity_type=model.entity.type,
                loader=self._loader,
                parent=header,
            )
        )

        identity = QtWidgets.QWidget(header)
        stack = QtWidgets.QVBoxLayout(identity)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(GLYPH_GAP)
        self._name = _CardName(self.name, self.url, self._size, identity)
        self._name.activated.connect(self.clicked.emit)
        stack.addWidget(self._name)

        meta = QtWidgets.QWidget(identity)
        meta.setObjectName("entity-card-meta")
        line = QtWidgets.QHBoxLayout(meta)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(GLYPH_GAP + 2)
        line.addWidget(_TypeLine(model.entity.type, model.type_label, meta))
        if model.status is not None:
            line.addWidget(
                StatusBadge(
                    code=model.status.code,
                    status=self._table.get(model.status.code),
                    field=model.status.field,
                    size=CARD_BADGE[self._size],
                    site_url=self.site_url,
                    loader=self._loader,
                    parent=meta,
                )
            )
        line.addStretch(1)
        stack.addWidget(meta)
        stack.addStretch(1)
        row.addWidget(identity, 1)
        return header

    def _grid_block(self, model: EntityCardModel, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(parent)
        holder.setObjectName("entity-card-fields")
        grid = QtWidgets.QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(GRID_GAP)
        grid.setVerticalSpacing(CARD_ROW_GAP[self._size])
        grid.setColumnStretch(1, 1)
        options = self._text_options()
        for index, column in enumerate(model.columns):
            value = _CardValue(
                column=column,
                statuses=self._table,
                site_url=self.site_url,
                text_options=options,
                empty_label=self._empty_label,
                size=self._size,
                loader=self._loader,
                parent=holder,
            )
            label = _FieldLabel(column.label, value.baseline(), holder)
            grid.addWidget(label, index, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, index, 1, QtCore.Qt.AlignmentFlag.AlignTop)
            self._values.append(value)
        return holder

    # --- geometry ---

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        hint = self._column.sizeHint()
        return QtCore.QSize(hint.width(), max(hint.height(), CHIP_HEIGHT["sm"]))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())


def _describe(
    context: SgContext,
    row: EntityRow | None,
    entity: EntityRef | None,
    options: EntityCardOptions,
    statuses: Mapping[str, StatusRecord] | None,
) -> tuple[EntityCardModel, dict[str, StatusRecord]]:
    """The card model and the status table, both read on a worker thread."""
    model = (
        describe_entity_card(context, row, options)
        if row is not None
        else load_entity_card(context, entity, options)  # type: ignore[arg-type]
    )
    table = dict(statuses) if statuses is not None else dict(context.statuses.by_code())
    return model, table


def _part(parent: QtWidgets.QWidget, height: int, share: float) -> QtWidgets.QWidget:
    """One skeleton line taking `share` of the width it is given.

    A `Skeleton` is fixed or expanding, and what a header line stands in for is neither: it is a
    fraction of the room, the way upstream's `w-3/4` is. The fraction is a layout's stretch.
    """
    holder = QtWidgets.QWidget(parent)
    row = QtWidgets.QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    taken = max(1, min(99, int(round(share * 100))))
    row.addWidget(Skeleton(height=height, parent=holder), taken)
    row.addStretch(100 - taken)
    return holder


def _context_of(client: object) -> SgContext | None:
    """The shared context for a bare client, so a card handed one shares the page's caches."""
    if client is None:
        return None
    return context_from_client(client)  # type: ignore[arg-type]


# --- the tile ---------------------------------------------------------------------------------

#: Tile widths, which are also the grid's column minimum (upstream `TILE`).
CARD_TILE_WIDTH: dict[str, int] = {"sm": 160, "md": 224, "lg": 288}

#: The inset of the tile's body, upstream's `p-3` and `p-4`.
CARD_TILE_BODY: dict[str, int] = {"sm": 12, "md": 12, "lg": 16}

#: Between the name and the metadata line under it, rule 2's inline gap.
CARD_TILE_GAP = 6

#: The chrome over the picture: the corner inset and the gap between the marks in a corner.
CARD_TILE_OVERLAY = 8
CARD_TILE_OVERLAY_GAP = 6

#: The checkbox drawn over the picture, and the ground it sits on so it reads over any picture.
CARD_TILE_CHECKBOX = 16
CARD_TILE_GROUND = 0.8

#: What a status draws as in a tile corner: the value's own face, rule 9.
STATUS_TYPE = "status_list"


@dataclass
class CardTile:
    """One row as a tile reads it: the picture, the name, and one metadata line."""

    name: str = ""
    code: str = ""
    sub_label: str = ""
    secondary: str = ""
    thumbnail: str | None = None
    entity_type: str | None = None
    #: The row's status code, drawn in the picture's trailing corner.
    status_code: str = ""
    status_field: Any = None
    #: True on a Version whose media is ready, which is the one tile that carries the play mark.
    playable: bool = False


@dataclass
class CardTileOptions:
    """What the tile face needs that a widget would read off itself."""

    theme: Theme | None = None
    size: str = "md"
    statuses: Mapping[str, StatusRecord] | None = None
    site_url: str = ""
    selectable: bool = False
    selected: bool = False
    enabled: bool = True
    loader: ImageLoader | None = None
    #: Called on the GUI thread once the picture lands, so a view repaints.
    on_ready: Callable[[], None] | None = None


def card_tile_size(size: str = "md") -> QtCore.QSize:
    """The room one tile takes: its width, its picture and the two lines under it."""
    step = size if size in ENTITY_CARD_SIZE_VALUES else "md"
    width = CARD_TILE_WIDTH[step]
    return QtCore.QSize(width, _tile_height(width, step))


def _tile_height(width: int, size: str) -> int:
    pad = CARD_TILE_BODY[size]
    name = QtGui.QFontMetrics(theme_for("default").font(CARD_NAME[size], QtGui.QFont.Weight.Medium))
    meta = QtGui.QFontMetrics(theme_for("default").font(CARD_META))
    media = int(round(width * 9 / 16))
    return media + 2 * pad + name.height() + CARD_TILE_GAP + meta.height()


def card_tile_media_rect(rect: QtCore.QRect) -> QtCore.QRect:
    """Where the picture sits inside a tile: the full width, 16:9 tall."""
    height = min(rect.height(), int(round(rect.width() * 9 / 16)))
    return QtCore.QRect(rect.left(), rect.top(), rect.width(), height)


def card_tile_checkbox_rect(rect: QtCore.QRect) -> QtCore.QRect:
    """Where the tile's selection box sits, so a view can tell a press on it apart."""
    media = card_tile_media_rect(rect)
    return QtCore.QRect(
        media.left() + CARD_TILE_OVERLAY,
        media.top() + CARD_TILE_OVERLAY,
        CARD_TILE_CHECKBOX,
        CARD_TILE_CHECKBOX,
    )


def paint_card_tile(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    tile: CardTile,
    options: CardTileOptions | None = None,
) -> None:
    """Draw one tile inside `rect`: the picture, the marks over it, the name and the metadata line.

    The face the grid's delegate and the card's own `tile` variant both draw through, so a grid
    cell and a card show the same row the same way. The value of an `image` field is the only
    state marker there is, so a row with no picture, one still transcoding and one ready all
    render (field_types/image).
    """
    o = options if options is not None else CardTileOptions()
    theme = o.theme if o.theme is not None else theme_for("default")
    size = o.size if o.size in ENTITY_CARD_SIZE_VALUES else "md"
    radius = float(theme.radius_px("lg"))

    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
    painter.setOpacity(1.0 if o.enabled else 0.5)

    ground = theme.color("accent") if o.selected else theme.color("card")
    fill_round_rect(painter, rect, radius, ground, theme.color("border"))

    clip = QtGui.QPainterPath()
    clip.addRoundedRect(QtCore.QRectF(rect), radius, radius)
    painter.save()
    painter.setClipPath(clip)
    media = card_tile_media_rect(rect)
    _paint_tile_media(painter, media, tile, o, theme)
    painter.restore()

    _paint_tile_body(painter, rect, media, tile, o, theme, size)
    painter.restore()


def _paint_tile_media(
    painter: QtGui.QPainter,
    media: QtCore.QRect,
    tile: CardTile,
    o: CardTileOptions,
    theme: Theme,
) -> None:
    painter.fillRect(media, theme.color("muted"))
    picture = None
    loader = o.loader if o.loader is not None else image_loader()
    if tile.thumbnail and image_state(tile.thumbnail) == "ready":
        picture = loader.pixmap_cached(tile.thumbnail)
        if picture is None and not loader.has(tile.thumbnail):
            loader.load(tile.thumbnail, lambda _pixmap: _ready(o))
    if picture is not None and not picture.isNull():
        if not o.enabled:
            picture = grayscale(picture)
        scaled = picture.scaled(
            media.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        target = QtCore.QRect(QtCore.QPoint(0, 0), scaled.size())
        target.moveCenter(media.center())
        painter.save()
        painter.setClipRect(media)
        painter.drawPixmap(target, scaled)
        painter.restore()
    else:
        side = THUMBNAIL_GLYPH[CARD_THUMB[o.size if o.size in CARD_THUMB else "md"]]
        slot = QtCore.QRect(0, 0, side, side)
        slot.moveCenter(media.center())
        name = "hourglass" if image_state(tile.thumbnail) == "pending" else entity_glyph(tile.entity_type)
        paint_icon(painter, slot, name, theme.color("muted_foreground"))

    if o.selectable:
        _paint_tile_checkbox(painter, card_tile_checkbox_rect(media), o.selected, theme)
    if tile.status_code:
        _paint_tile_status(painter, media, tile, o, theme)


def _paint_tile_checkbox(
    painter: QtGui.QPainter, box: QtCore.QRect, checked: bool, theme: Theme
) -> None:
    """The tile's own box, on a ground so it reads over any picture."""
    radius = float(theme.radius_px("sm"))
    fill = theme.color("primary") if checked else with_alpha(theme.background, CARD_TILE_GROUND)
    fill_round_rect(painter, box, radius, fill, None if checked else theme.color("border"))
    if checked:
        paint_icon(painter, box.adjusted(3, 3, -3, -3), "check", theme.color("primary_foreground"))


def _paint_tile_status(
    painter: QtGui.QPainter,
    media: QtCore.QRect,
    tile: CardTile,
    o: CardTileOptions,
    theme: Theme,
) -> None:
    options = FieldValueOptions(
        theme=theme,
        field=tile.status_field,
        statuses=o.statuses,
        site_url=o.site_url,
        density="compact",
        loader=o.loader,
        on_ready=lambda: _ready(o),
    )
    wanted = field_value_size_hint(tile.status_code, STATUS_TYPE, options)
    width = min(wanted.width(), media.width() - 2 * CARD_TILE_OVERLAY)
    height = min(wanted.height(), media.height() - 2 * CARD_TILE_OVERLAY)
    if width <= 0 or height <= 0:
        return
    box = QtCore.QRect(
        media.right() + 1 - CARD_TILE_OVERLAY - width, media.top() + CARD_TILE_OVERLAY, width, height
    )
    fill_round_rect(
        painter,
        box.adjusted(-2, -1, 2, 1),
        float(theme.radius_px("sm")),
        with_alpha(theme.background, CARD_TILE_GROUND),
        None,
    )
    paint_field_value(painter, box, tile.status_code, STATUS_TYPE, options)


def _paint_tile_body(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    media: QtCore.QRect,
    tile: CardTile,
    o: CardTileOptions,
    theme: Theme,
    size: str,
) -> None:
    pad = CARD_TILE_BODY[size]
    left = rect.left() + pad
    width = max(0, rect.width() - 2 * pad)
    top = media.bottom() + 1 + pad
    ink = theme.color("accent_foreground" if o.selected else "foreground")

    name_font = theme.font(CARD_NAME[size], QtGui.QFont.Weight.Medium)
    name_metrics = QtGui.QFontMetrics(name_font)
    code_font = theme.font(CARD_META)
    code_font.setFamily(theme.font_mono)
    code_metrics = QtGui.QFontMetrics(code_font)
    code_width = text_width(code_metrics, tile.code) + GLYPH_GAP if tile.code else 0
    painter.setFont(name_font)
    painter.setPen(ink)
    painter.drawText(
        QtCore.QRect(left, top, max(0, width - code_width), name_metrics.height()),
        int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
        elide(name_metrics, tile.name, max(0, width - code_width)),
    )
    if tile.code:
        painter.setFont(code_font)
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            QtCore.QRect(left + width - code_width + GLYPH_GAP, top, code_width, name_metrics.height()),
            int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter),
            tile.code,
        )

    if not tile.sub_label and not tile.secondary:
        return
    meta_font = theme.font(CARD_META)
    meta_metrics = QtGui.QFontMetrics(meta_font)
    line = top + name_metrics.height() + CARD_TILE_GAP
    right_width = min(text_width(meta_metrics, tile.secondary), width // 2) if tile.secondary else 0
    painter.setFont(meta_font)
    painter.setPen(theme.color("muted_foreground"))
    if tile.sub_label:
        room = max(0, width - right_width - (GLYPH_GAP if right_width else 0))
        painter.drawText(
            QtCore.QRect(left, line, room, meta_metrics.height()),
            int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
            elide(meta_metrics, tile.sub_label, room),
        )
    if right_width:
        painter.drawText(
            QtCore.QRect(left + width - right_width, line, right_width, meta_metrics.height()),
            int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter),
            elide(meta_metrics, tile.secondary, right_width),
        )


def _ready(o: CardTileOptions) -> None:
    """Tell the view a picture landed, unless the view has gone.

    A picture is read once and kept by url, so an answer can arrive after the tile that asked
    for it was taken off the page; a deleted wrapper raises, and the answer is dropped.
    """
    if o.on_ready is None:
        return
    try:
        o.on_ready()
    except RuntimeError:
        return


def tile_of(
    model: EntityCardModel,
    label_field: str | None = None,
    sub_label: str = "",
    secondary: str = "",
    show_code: bool = False,
) -> CardTile:
    """The tile one card model reads as, with the row-anatomy strings the caller resolved."""
    name = (
        str(cell_value(model.row, label_field) or "") if label_field else model.name
    )
    raw = cell_value(model.row, "code")
    code = raw if show_code and isinstance(raw, str) and raw and raw != name else ""
    return CardTile(
        name=name,
        code=code,
        sub_label=sub_label,
        secondary=secondary,
        thumbnail=model.thumbnail,
        entity_type=model.entity.type,
        status_code=model.status.code if model.status is not None else "",
        status_field=model.status.field if model.status is not None else None,
        playable=model.entity.type == "Version" and image_state(model.thumbnail) == "ready",
    )


class _TilePane(ThemedWidget):
    """The tile face as a widget: one `paint_card_tile`, and the press its checkbox takes."""

    toggled = QtCore.Signal(bool)
    activated = QtCore.Signal()

    def __init__(
        self,
        tile: CardTile,
        options: CardTileOptions,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card-tile")
        self._tile = tile
        self._options = options
        self._options.on_ready = self.update
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    def set_tile(self, tile: CardTile) -> None:
        self._tile = tile
        self.update()

    def set_selected(self, value: bool) -> None:
        self._options.selected = bool(value)
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        hint = card_tile_size(self._options.size)
        width = self.width() if self.width() > 0 else hint.width()
        return QtCore.QSize(width, _tile_height(width, self._options.size))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.setFixedHeight(_tile_height(max(1, self.width()), self._options.size))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        self._options.theme = self.theme
        self._options.enabled = self.isEnabled()
        paint_card_tile(painter, self.rect(), self._tile, self._options)
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), float(self.theme.radius_px("lg")))
        painter.end()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self._options.selectable and card_tile_checkbox_rect(self.rect()).contains(point):
            self.toggled.emit(not self._options.selected)
            return
        self.activated.emit()
