"""The button, in every variant and every step of its ladder, painted rather than styled.

Ported from `packages/react/src/components/ui/button.tsx`. The six variants and the eight sizes
are the upstream ones; the Tailwind steps are pixels here, and the transitions are
`AnimatedValue` rather than `transition-all`.

    row.addWidget(Button("Save", variant="default"))
    row.addWidget(Button(icon="plus", size="icon-sm", variant="ghost"))
"""
from __future__ import annotations

from typing import Literal

from qtpy import QtCore, QtGui, QtWidgets

from ..icons import paint_icon
from ..theme import mix, with_alpha
from .base import (
    CHIP_HEIGHT,
    DURATION,
    ThemedWidget,
    fill_round_rect,
    painter_for,
    text_width,
)

__all__ = ["BUTTON_SIZES", "Button", "ButtonSize", "ButtonVariant"]

ButtonVariant = Literal["default", "outline", "secondary", "ghost", "destructive", "link"]
BUTTON_VARIANT_VALUES: tuple[str, ...] = (
    "default",
    "outline",
    "secondary",
    "ghost",
    "destructive",
    "link",
)

ButtonSize = Literal["default", "xs", "sm", "lg", "icon", "icon-xs", "icon-sm", "icon-lg"]
BUTTON_SIZE_VALUES: tuple[str, ...] = (
    "default",
    "xs",
    "sm",
    "lg",
    "icon",
    "icon-xs",
    "icon-sm",
    "icon-lg",
)


class ButtonSpec:
    """One step of the button ladder: its height, its insets, its type and its glyph."""

    __slots__ = ("gap", "glyph", "height", "lead_pad", "pad", "radius", "square", "text")

    def __init__(
        self,
        height: int,
        pad: int,
        lead_pad: int,
        gap: int,
        text: int,
        glyph: int,
        radius: str,
        square: bool = False,
    ) -> None:
        self.height = height
        self.pad = pad
        self.lead_pad = lead_pad
        self.gap = gap
        self.text = text
        self.glyph = glyph
        self.radius = radius
        self.square = square


#: The ladder of `button.tsx`: h-8 / h-6 / h-7 / h-9, and the four square icon steps beside them.
#: A glyph edge takes a step less inset than a bare text edge, which is the `has-data-[icon]` rule.
BUTTON_SIZES: dict[str, ButtonSpec] = {
    "default": ButtonSpec(32, 10, 8, 6, 14, 16, "lg"),
    "xs": ButtonSpec(24, 8, 6, 4, 12, 12, "md"),
    "sm": ButtonSpec(28, 10, 6, 4, 13, 14, "md"),
    "lg": ButtonSpec(36, 10, 8, 6, 14, 16, "lg"),
    "icon": ButtonSpec(32, 0, 0, 0, 14, 16, "lg", square=True),
    "icon-xs": ButtonSpec(24, 0, 0, 0, 12, 12, "md", square=True),
    "icon-sm": ButtonSpec(28, 0, 0, 0, 14, 16, "md", square=True),
    "icon-lg": ButtonSpec(36, 0, 0, 0, 14, 16, "lg", square=True),
}

#: `rounded-[min(var(--radius-md),10px)]` and its 12px sibling, which cap the small steps.
RADIUS_CAP: dict[str, int] = {"xs": 10, "sm": 12, "icon-xs": 10, "icon-sm": 12}

#: The press: `active:translate-y-px` plus the 0.98 scale of `docs/design-rules.md` rule 4.
PRESS_SCALE = 0.98
PRESS_SHIFT = 1

#: The arc of `loader-circle`, in degrees, and how long one turn takes.
SPINNER_SPAN = 280
SPINNER_MS = 900

#: The default step of the count chip a trigger carries, the step under a `default` control.
COUNT_CHIP_DEFAULT = "sm"


class Button(ThemedWidget):
    """A button with a label, a leading glyph, a trailing glyph, or any pair of them.

    A trigger that carries a count — the filter dialog's applied conditions, the sort picker's
    keys — draws it as a `secondary` text chip inside its own border, which is the `COUNT_CHIP`
    span both upstream triggers hold.
    """

    clicked = QtCore.Signal()

    def __init__(
        self,
        text: str = "",
        icon: str | None = None,
        variant: str = "default",
        size: str = "default",
        trailing_icon: str | None = None,
        count: str = "",
        count_size: str = COUNT_CHIP_DEFAULT,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self._trailing_icon = trailing_icon
        self._count = str(count)
        self._count_size = count_size if count_size in CHIP_HEIGHT else COUNT_CHIP_DEFAULT
        self._variant = variant if variant in BUTTON_VARIANT_VALUES else "default"
        self._size = size if size in BUTTON_SIZE_VALUES else "default"
        self._expanded = False
        self._busy = False

        self._hover = self.animated(DURATION["hover"])
        self._press = self.animated(DURATION["press"])
        self._spin = self.animated(SPINNER_MS)

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)

    # --- props ---

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    @property
    def icon(self) -> str | None:
        return self._icon

    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self.updateGeometry()
        self.update()

    @property
    def trailing_icon(self) -> str | None:
        return self._trailing_icon

    def set_trailing_icon(self, name: str | None) -> None:
        self._trailing_icon = name
        self.updateGeometry()
        self.update()

    @property
    def count(self) -> str:
        """The chip the trigger carries after its label, empty for none."""
        return self._count

    def set_count(self, value: str) -> None:
        self._count = str(value)
        self.updateGeometry()
        self.update()

    @property
    def count_size(self) -> str:
        """The chip ladder step the count stands on, a step under the control."""
        return self._count_size

    def set_count_size(self, value: str) -> None:
        self._count_size = value if value in CHIP_HEIGHT else COUNT_CHIP_DEFAULT
        self.updateGeometry()
        self.update()

    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, value: str) -> None:
        self._variant = value if value in BUTTON_VARIANT_VALUES else "default"
        self.update()

    @property
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in BUTTON_SIZE_VALUES else "default"
        self.updateGeometry()
        self.update()

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, value: bool) -> None:
        """The `aria-expanded` look: the trigger of an open popup keeps its hover background."""
        value = bool(value)
        if value != self._expanded:
            self._expanded = value
            self.update()

    @property
    def busy(self) -> bool:
        return self._busy

    def set_busy(self, value: bool) -> None:
        """A spinner in place of the leading glyph while the button's work runs."""
        value = bool(value)
        if value == self._busy:
            return
        self._busy = value
        if value:
            self._spin.loop(SPINNER_MS)
        else:
            self._spin.stop()
        self.updateGeometry()
        self.update()

    # --- geometry ---

    @property
    def spec(self) -> ButtonSpec:
        return BUTTON_SIZES[self._size]

    def _radius(self) -> float:
        spec = self.spec
        value = float(self.theme.radius_px(spec.radius))
        cap = RADIUS_CAP.get(self._size)
        return min(value, float(cap)) if cap is not None else value

    def _has_leading(self) -> bool:
        return self._busy or self._icon is not None

    def _count_font(self) -> QtGui.QFont:
        return self.theme.font(CHIP_TEXT[self._count_size], QtGui.QFont.Weight.Medium)

    def _count_width(self) -> int:
        """The chip's own width: its label between two bare-text insets of the chip ladder."""
        if not self._count:
            return 0
        pad = CHIP_PAD[self._count_size].text
        return pad * 2 + text_width(QtGui.QFontMetrics(self._count_font()), self._count)

    def _content_width(self) -> int:
        spec = self.spec
        if spec.square:
            return spec.height
        width = 0
        parts = 0
        if self._has_leading():
            width += spec.glyph
            parts += 1
        if self._text:
            width += text_width(QtGui.QFontMetrics(self._font()), self._text)
            parts += 1
        if self._count:
            width += self._count_width()
            parts += 1
        if self._trailing_icon is not None:
            width += spec.glyph
            parts += 1
        width += spec.gap * max(0, parts - 1)
        left = spec.lead_pad if self._has_leading() else spec.pad
        right = spec.lead_pad if self._trailing_icon is not None else spec.pad
        return width + left + right

    def _font(self) -> QtGui.QFont:
        return self.theme.font(self.spec.text, QtGui.QFont.Weight.Medium)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        spec = self.spec
        return QtCore.QSize(max(spec.height, self._content_width()), spec.height)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        spec = self.spec
        return QtCore.QSize(spec.height, spec.height)

    # --- colours ---

    def _hover_amount(self) -> float:
        if self._expanded and self._variant in ("outline", "ghost", "secondary"):
            return 1.0
        return self._hover.value

    def _surface(self) -> tuple[QtGui.QColor | None, QtGui.QColor | None, QtGui.QColor]:
        """The fill, the border and the text colour of the variant at its current hover."""
        theme = self.theme
        amount = self._hover_amount()
        dark = theme.dark
        if self._variant == "default":
            fill = mix(theme.primary, with_alpha(theme.primary, 0.8), amount)
            return fill, None, theme.color("primary_foreground")
        if self._variant == "outline":
            base = with_alpha(theme.input, 0.3) if dark else theme.color("background")
            top = with_alpha(theme.input, 0.5) if dark else theme.color("muted")
            border = theme.color("input") if dark else theme.color("border")
            return mix(base, top, amount), border, theme.color("foreground")
        if self._variant == "secondary":
            top = mix(theme.secondary, theme.foreground, 0.05)
            return mix(theme.secondary, top, amount), None, theme.color("secondary_foreground")
        if self._variant == "ghost":
            top = with_alpha(theme.muted, 0.5) if dark else theme.color("muted")
            return mix(with_alpha(theme.muted, 0.0), top, amount), None, theme.color("foreground")
        if self._variant == "destructive":
            base = with_alpha(theme.destructive, 0.2 if dark else 0.1)
            top = with_alpha(theme.destructive, 0.3 if dark else 0.2)
            return mix(base, top, amount), None, theme.color("destructive")
        return None, None, theme.color("primary")

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        radius = self._radius()
        box = self._box()

        painter.save()
        press = self._press.value
        if press > 0:
            centre = QtCore.QPointF(box.center())
            scale = 1.0 - (1.0 - PRESS_SCALE) * press
            painter.translate(centre)
            painter.scale(scale, scale)
            painter.translate(-centre)
            painter.translate(0.0, PRESS_SHIFT * press)

        fill, border, ink = self._surface()
        if fill is not None or border is not None:
            fill_round_rect(painter, box, radius, fill, border)

        self._paint_content(painter, box, ink)
        painter.restore()

        if self.keyboard_focus:
            self.paint_focus_ring(painter, box, radius)
        painter.end()

    def _box(self) -> QtCore.QRect:
        spec = self.spec
        height = min(self.height(), spec.height)
        top = (self.height() - height) // 2
        return QtCore.QRect(0, top, self.width(), height)

    def _paint_content(self, painter: QtGui.QPainter, box: QtCore.QRect, ink: QtGui.QColor) -> None:
        spec = self.spec
        font = self._font()
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)

        if spec.square:
            side = spec.glyph
            glyph_box = QtCore.QRect(0, 0, side, side)
            glyph_box.moveCenter(box.center())
            if self._busy:
                self._paint_spinner(painter, glyph_box, ink)
            elif self._icon is not None:
                paint_icon(painter, glyph_box, self._icon, ink)
            elif self._text:
                painter.setPen(ink)
                painter.drawText(box, QtCore.Qt.AlignmentFlag.AlignCenter, self._text)
            return

        left = spec.lead_pad if self._has_leading() else spec.pad
        right = spec.lead_pad if self._trailing_icon is not None else spec.pad
        inner = box.adjusted(left, 0, -right, 0)
        content = min(self._content_width() - left - right, inner.width())
        x = inner.x() + (inner.width() - content) // 2
        centre_y = box.center().y()

        if self._has_leading():
            glyph_box = QtCore.QRect(0, 0, spec.glyph, spec.glyph)
            glyph_box.moveCenter(QtCore.QPoint(x + spec.glyph // 2, centre_y))
            if self._busy:
                self._paint_spinner(painter, glyph_box, ink)
            else:
                paint_icon(painter, glyph_box, self._icon or "", ink)
            x += spec.glyph + spec.gap

        if self._text:
            trailing = spec.glyph + spec.gap if self._trailing_icon is not None else 0
            if self._count:
                trailing += self._count_width() + spec.gap
            width = max(0, inner.right() - x + 1 - trailing)
            label = self.elide(metrics, self._text, width)
            self.set_elide_tooltip(self._text, label == self._text)
            painter.setPen(ink)
            text_box = QtCore.QRect(x, box.y(), width, box.height())
            painter.drawText(
                text_box,
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                label,
            )
            if self._variant == "link" and self._hover_amount() > 0.5:
                baseline = text_box.center().y() + metrics.ascent() // 2 + 2
                painter.setPen(QtGui.QPen(ink, 1))
                painter.drawLine(x, baseline, x + metrics.horizontalAdvance(label), baseline)
            x += min(width, metrics.horizontalAdvance(label)) + spec.gap

        if self._count:
            self._paint_count(painter, box, x, centre_y)

        if self._trailing_icon is not None:
            glyph_box = QtCore.QRect(0, 0, spec.glyph, spec.glyph)
            glyph_box.moveCenter(QtCore.QPoint(inner.right() - spec.glyph // 2, centre_y))
            paint_icon(painter, glyph_box, self._trailing_icon, ink)

    def _paint_count(
        self, painter: QtGui.QPainter, box: QtCore.QRect, x: int, centre_y: int
    ) -> None:
        """The count chip: the `secondary` surface, bordered, at the chip step it was given."""
        theme = self.theme
        step = self._count_size
        height = min(CHIP_HEIGHT[step], box.height())
        chip = QtCore.QRect(x, centre_y - height // 2, self._count_width(), height)
        fill_round_rect(
            painter,
            chip,
            float(theme.radius_px("md")),
            theme.color("secondary"),
            theme.color("border"),
        )
        painter.setFont(self._count_font())
        painter.setPen(theme.color("secondary_foreground"))
        painter.drawText(chip, QtCore.Qt.AlignmentFlag.AlignCenter, self._count)

    def _paint_spinner(self, painter: QtGui.QPainter, box: QtCore.QRect, ink: QtGui.QColor) -> None:
        """The `loader-circle` look: one arc turning inside the glyph's own box."""
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        width = max(1.5, box.width() / 8.0)
        pen = QtGui.QPen(ink, width)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        inset = width / 2.0
        arc = QtCore.QRectF(box).adjusted(inset, inset, -inset, -inset)
        start = int(round((90 - self._spin.value * 360) * 16))
        painter.drawArc(arc, start, -SPINNER_SPAN * 16)
        painter.restore()

    # --- interaction ---

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def on_press_changed(self, value: bool) -> None:
        self._press.set(1.0 if value else 0.0)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if not self.isEnabled() or event.button() != QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        self.set_pressed(True)
        event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if not self.isEnabled() or event.button() != QtCore.Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        was = self.pressed
        self.set_pressed(False)
        if was and self.rect().contains(event.pos()):
            self.clicked.emit()
        event.accept()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (
            QtCore.Qt.Key.Key_Space,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        )
        if self.isEnabled() and event.key() in keys and not event.isAutoRepeat():
            self.set_pressed(True)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (
            QtCore.Qt.Key.Key_Space,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        )
        if self.isEnabled() and event.key() in keys and not event.isAutoRepeat():
            was = self.pressed
            self.set_pressed(False)
            if was:
                self.clicked.emit()
            event.accept()
            return
        super().keyReleaseEvent(event)
