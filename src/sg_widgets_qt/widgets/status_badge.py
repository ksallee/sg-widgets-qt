"""One Flow Production Tracking status, as a badge.

Ported from `packages/react/src/registry/sg/components/status-badge.tsx` onto the chip ladder of
`primitives/badge.py`.

The label resolves in one order: the Status row's name, then the field's display value, then the
raw code, so an unknown code renders as itself rather than blank (field_types/status_list). The
one of the name and the code that is not on show is the tooltip. The badge is neutral by default;
`color` paints it in the status's own `bg_color`, comma-separated decimal RGB and never hex
(probe 010), which with the name hue behind initials is the only colour design rule 1 lets a
widget take from data.

`glyph` is the icon alone, with no pill around it: the leading mark of a row whose label is a
name, where a bordered pill would read as a second surface.

    badge = StatusBadge(code="ip", status=statuses.record("ip"), color=True, removable=True)
    badge.removed.connect(drop)
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import Rgb, StatusRecord, foreground_for, parse_bg_color, status_label

from ..images import ImageLoader
from ..primitives.badge import Badge
from ..primitives.base import CHIP_GLYPH, CHIP_HEIGHT, CHIP_PAD, painter_for
from ..theme import with_alpha
from .status_glyph import StatusGlyphSource

__all__ = [
    "BARE_GLYPH",
    "STATUS_BADGE_LABEL_VALUES",
    "STATUS_BADGE_VARIANT_VALUES",
    "StatusBadge",
]

#: How much of the status the badge shows.
STATUS_BADGE_VARIANT_VALUES: tuple[str, ...] = ("both", "icon", "text", "glyph")

#: Which of the two names is on show. The other one is the tooltip.
STATUS_BADGE_LABEL_VALUES: tuple[str, ...] = ("name", "code")

#: The bare glyph is sized like a row's leading mark, not like a chip's glyph.
BARE_GLYPH: dict[str, int] = {"xs": 16, "sm": 16, "md": 16, "lg": 20}

#: The inset ring a painted badge wears, so its own edge reads on its colour.
PAINT_RING = 0.1

#: The keys the cross answers to, the same ones the badge primitive takes.
REMOVE_KEYS = (QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)


class StatusBadge(Badge):
    """One status code as a badge: its icon, its name, its colour and an optional cross."""

    #: The cross was pressed. Carries the status code.
    removed = QtCore.Signal(str)

    #: A badge measures itself before its glyph source is built, so both have a class default.
    _source: StatusGlyphSource | None = None
    _status_variant = "both"
    _remove_asked = False

    def __init__(
        self,
        code: str = "",
        status: StatusRecord | None = None,
        field: FieldSchema | None = None,
        variant: str = "both",
        size: str = "md",
        color: bool = False,
        label: str = "name",
        site_url: str = "",
        removable: bool = False,
        on_remove: Callable[[str], None] | None = None,
        remove_label: str = "",
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self._code = code
        self._status = status
        self._field = field
        self._status_variant = variant if variant in STATUS_BADGE_VARIANT_VALUES else "both"
        self._color = bool(color)
        self._label_mode = label if label in STATUS_BADGE_LABEL_VALUES else "name"
        self._remove_label = remove_label
        self._remove_asked = bool(removable)
        self._on_remove: Callable[[str], None] | None = None
        super().__init__(
            text="",
            variant="outline",
            size=size if size in CHIP_HEIGHT else "md",
            removable=False,
            parent=parent,
        )
        self.setObjectName("status-badge")
        self._source = StatusGlyphSource(status, site_url, loader=loader, parent=self)
        self._source.changed.connect(self._refresh)
        self.set_on_remove(on_remove)
        self._refresh()

    # --- props ---

    @property
    def code(self) -> str:
        """The stored code. An empty code renders nothing."""
        return self._code

    def set_code(self, value: str) -> None:
        self._code = value
        self._refresh()

    @property
    def status(self) -> StatusRecord | None:
        return self._status

    def set_status(self, value: StatusRecord | None) -> None:
        self._status = value
        if self._source is not None:
            self._source.set_status(value)
        self._refresh()

    @property
    def field(self) -> FieldSchema | None:
        """The schema whose display values are the other source of a label."""
        return self._field

    def set_field(self, value: FieldSchema | None) -> None:
        self._field = value
        self._refresh()

    @property
    def variant(self) -> str:
        """`both`, `icon`, `text` or `glyph`."""
        return self._status_variant

    def set_variant(self, value: str) -> None:
        self._status_variant = value if value in STATUS_BADGE_VARIANT_VALUES else "both"
        self._refresh()

    @property
    def color(self) -> bool:
        """Paint the badge in the status colour instead of the neutral surface."""
        return self._color

    def set_color(self, value: bool) -> None:
        self._color = bool(value)
        self.update()

    @property
    def label(self) -> str:
        """`name` or `code`: which of the two is on show."""
        return self._label_mode

    def set_label(self, value: str) -> None:
        self._label_mode = value if value in STATUS_BADGE_LABEL_VALUES else "name"
        self._refresh()

    @property
    def site_url(self) -> str:
        """The site the stock sprite is served from."""
        return self._source.site_url if self._source is not None else ""

    def set_site_url(self, value: str) -> None:
        if self._source is not None:
            self._source.set_site_url(value)

    @property
    def removable(self) -> bool:
        """Whether a cross was asked for. The icon and glyph variants have no room and ignore it."""
        return self._remove_asked

    def set_removable(self, value: bool) -> None:
        self._remove_asked = bool(value)
        self._refresh()

    @property
    def remove_label(self) -> str:
        """The accessible name of the cross."""
        return self._remove_label or f"Remove {self.status_text}"

    def set_remove_label(self, value: str) -> None:
        self._remove_label = value
        self._apply_accessible()

    @property
    def on_remove(self) -> Callable[[str], None] | None:
        """The callable the cross calls, beside the `removed` signal."""
        return self._on_remove

    def set_on_remove(self, value: Callable[[str], None] | None) -> None:
        if self._on_remove is not None:
            try:
                self.removed.disconnect(self._on_remove)
            except (RuntimeError, TypeError):
                pass
        self._on_remove = value
        if value is not None:
            self.removed.connect(value)

    def set_size(self, value: str) -> None:
        super().set_size(value if value in CHIP_HEIGHT else "md")
        self._refresh()

    # --- what it resolved to ---

    @property
    def known(self) -> bool:
        """True when a Status row or the schema names this code."""
        if self._status is not None:
            return True
        values = (self._field.display_values or {}) if self._field is not None else {}
        return self._code in values

    @property
    def status_name(self) -> str:
        """The Status row's name, else the schema's display value, else the code itself."""
        if self._status is not None and self._status.name:
            return self._status.name
        if self._field is not None:
            return status_label(self._field, self._code) or self._code
        return self._code

    @property
    def status_text(self) -> str:
        """Whichever of the name and the code `label` puts on show."""
        return self._code if self._label_mode == "code" else self.status_name

    @property
    def other_text(self) -> str:
        """The one that is not on show, which is the tooltip."""
        return self.status_name if self._label_mode == "code" else self._code

    @property
    def glyph(self) -> StatusGlyphSource | None:
        """What the status's icon resolved to."""
        return self._source

    @property
    def bare(self) -> bool:
        """True for the glyph variant: the icon alone, with no pill around it."""
        return self._status_variant == "glyph"

    def _html_text(self) -> str:
        """An `html` icon is the label itself, so it replaces the text rather than preceding it."""
        if self._source is None or self._source.kind != "html":
            return ""
        return self._source.html or self.status_text

    def _shows_glyph(self) -> bool:
        if self._source is None or self._status_variant == "text":
            return False
        return self._source.kind != "none" and not self._html_text()

    def _shows_text(self) -> bool:
        return self._status_variant != "icon" or bool(self._html_text())

    def _shows_remove(self) -> bool:
        return self._remove_asked and self._status_variant not in ("icon", "glyph")

    # --- layout ---

    def _refresh(self) -> None:
        shown = self._html_text() or self.status_text
        self._text = shown if self._shows_text() else ""
        # The badge primitive draws its cross off this flag, and the two bare variants have no room.
        self._removable = self._shows_remove()
        self._apply_focus_policy()
        self._apply_accessible()
        self.updateGeometry()
        self.update()

    def _apply_accessible(self) -> None:
        self.setAccessibleName(self.status_text)
        # The one of the name and the code that is not on show, whether or not the badge is drawn.
        self.setToolTip(self.other_text)

    def has_leading(self) -> bool:
        return self._shows_glyph()

    def leading_size(self) -> QtCore.QSize:
        """The glyph's own box: a sprite cell is its own pixel size, the dot is 8, an
        `image` icon takes the chip ladder's step (010_status_icons)."""
        if self._source is None:
            return super().leading_size()
        return self._source.natural_size(CHIP_GLYPH[self.size_step])

    def _left_pad(self) -> int:
        if self._status_variant == "icon":
            return CHIP_PAD[self.size_step].icon
        return super()._left_pad()

    def _right_pad(self) -> int:
        pad = CHIP_PAD[self.size_step]
        if self._status_variant == "icon":
            return pad.icon
        return pad.trail if self._shows_remove() else pad.text

    def _corner(self) -> float:
        """A status badge is `rounded-md`, not a pill."""
        return float(self.theme.radius_px("md"))

    def _bare_side(self) -> int:
        return BARE_GLYPH[self.size_step]

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        if not self._code:
            return QtCore.QSize(0, 0)
        if self.bare:
            side = self._bare_side()
            return QtCore.QSize(side, side)
        return super().sizeHint()

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        if not self._code:
            return QtCore.QSize(0, 0)
        if self.bare:
            return self.sizeHint()
        return super().minimumSizeHint()

    # --- colours ---

    def status_rgb(self) -> Rgb | None:
        """The status's own colour under `color`, parsed.

        `bg_color` is comma-separated decimal RGB and never hex (probe 010). None here is a status
        that carries no colour, which is every option of a plain `list` field.
        """
        if not self._color or self._status is None:
            return None
        return parse_bg_color(self._status.bg_color)

    def _surface(self) -> tuple[QtGui.QColor | None, QtGui.QColor | None, QtGui.QColor]:
        theme = self.theme
        rgb = self.status_rgb()
        if rgb is not None:
            fill = QtGui.QColor(rgb.r, rgb.g, rgb.b)
            ink = QtGui.QColor(0, 0, 0) if foreground_for(rgb) == "black" else QtGui.QColor(255, 255, 255)
            return fill, with_alpha(ink, PAINT_RING), ink
        if self._color:
            # A status with no colour of its own reads as muted rather than as a bordered pill.
            return theme.color("muted"), None, theme.color("muted_foreground")
        return theme.color("background"), theme.color("border"), theme.color("foreground")

    # --- painting ---

    def set_elide_tooltip(self, text: str, fits: bool) -> None:
        """The other of the name and the code, always, plus the label when it did not fit."""
        other = self.other_text
        if not fits and text and text != other:
            self.setToolTip(f"{text}\n{other}" if other else text)
            return
        self.setToolTip(other)

    def paint_leading(
        self, painter: QtGui.QPainter, rect: QtCore.QRect, ink: QtGui.QColor
    ) -> None:
        if self._source is not None:
            self._source.paint(painter, rect, self.theme, on_color=self.status_rgb() is not None)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._code or self._source is None:
            return
        if not self.bare:
            super().paintEvent(event)
            return
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        side = min(self._bare_side(), self.width(), self.height())
        box = QtCore.QRect(0, 0, side, side)
        box.moveCenter(self.rect().center())
        self._source.paint(painter, box, self.theme, on_color=False, fallback=True)
        painter.end()

    # --- the cross ---
    # The badge primitive's own `removed` carries nothing; this one carries the code, so the two
    # presses that fire it are answered here rather than inherited.

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.pressed and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.set_pressed(False)
            if self._cross_hit().contains(event.pos()):
                self.removed.emit(self._code)
            event.accept()
            return
        QtWidgets.QWidget.mouseReleaseEvent(self, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self.isEnabled() and self._removable and event.key() in REMOVE_KEYS:
            self.removed.emit(self._code)
            event.accept()
            return
        QtWidgets.QWidget.keyPressEvent(self, event)
