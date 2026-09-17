"""The badge and the chip: one pill, four variants, four steps of the chip ladder.

Ported from `packages/react/src/components/ui/badge.tsx` on the ladder of
`packages/react/src/registry/sg/components/leaf-classes.ts`. A badge is what a status is where it
is a value; a chip is the same surface with a leading picture, which the entity chip and every
picker's token field sit on.

The cross is the remove control of `REMOVE_CONTROL`: it hovers with a wash of its own foreground
at 8% rather than the destructive tint, keeps a 24px hit box whatever the chip's step, and takes
the focus ring.

    Badge("In progress", variant="secondary", size="sm")
    chip = Chip("Anna van der Meer", removable=True)
    chip.removed.connect(drop)
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from ..icons import paint_icon
from ..theme import with_alpha
from .base import (
    CHIP_CROSS,
    CHIP_GLYPH,
    CHIP_HEIGHT,
    CHIP_PAD,
    CHIP_SPACING,
    CHIP_TEXT,
    DURATION,
    ICON_HIT_BOX,
    ThemedWidget,
    fill_round_rect,
    painter_for,
    text_width,
)

__all__ = ["BADGE_VARIANT_VALUES", "Badge", "Chip"]

BADGE_VARIANT_VALUES: tuple[str, ...] = ("default", "secondary", "outline", "destructive")

#: The wash under the cross on hover: its own foreground, never the destructive tint (rule 5).
CROSS_WASH = 0.08

#: `REMOVE_CONTROL`'s `p-0.5`, which is what makes the cross's own rounded box.
CROSS_PAD = 2

#: The cross sits at 70% until it is hovered, as `REMOVE_CONTROL` has it.
CROSS_REST_OPACITY = 0.7


class Badge(ThemedWidget):
    """One pill with a label, an optional leading glyph and an optional cross."""

    removed = QtCore.Signal()

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
        size: str = "xs",
        icon: str | None = None,
        removable: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._variant = variant if variant in BADGE_VARIANT_VALUES else "default"
        self._icon = icon
        self._removable = bool(removable)
        self._cross_hovered = False
        self._cross_hover = self.animated(DURATION["hover"])
        self.set_size_step(size if size in CHIP_HEIGHT else "xs")

        self.setMouseTracking(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self._apply_focus_policy()

    # --- props ---

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, value: str) -> None:
        self._variant = value if value in BADGE_VARIANT_VALUES else "default"
        self.update()

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in CHIP_HEIGHT else "xs")

    @property
    def icon(self) -> str | None:
        return self._icon

    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self.updateGeometry()
        self.update()

    @property
    def removable(self) -> bool:
        return self._removable

    def set_removable(self, value: bool) -> None:
        self._removable = bool(value)
        self._apply_focus_policy()
        self.updateGeometry()
        self.update()

    def _apply_focus_policy(self) -> None:
        policy = QtCore.Qt.FocusPolicy
        self.setFocusPolicy(policy.TabFocus if self._removable else policy.NoFocus)

    # --- the ladder ---

    def _glyph(self) -> int:
        return CHIP_GLYPH[self.size_step]

    def _cross(self) -> int:
        return CHIP_CROSS[self.size_step]

    def _font(self) -> QtGui.QFont:
        return self.theme.font(CHIP_TEXT[self.size_step], QtGui.QFont.Weight.Medium)

    def has_leading(self) -> bool:
        """True when the chip shows something in its leading slot."""
        return self._icon is not None

    def _left_pad(self) -> int:
        pad = CHIP_PAD[self.size_step]
        if self.has_leading():
            return pad.lead
        return pad.text if self._text else pad.icon

    def _right_pad(self) -> int:
        pad = CHIP_PAD[self.size_step]
        return pad.trail if self._removable else pad.text

    def _label_width(self) -> int:
        if not self._text:
            return 0
        return text_width(QtGui.QFontMetrics(self._font()), self._text)

    def _natural_width(self) -> int:
        spacing = CHIP_SPACING[self.size_step]
        width = self._left_pad() + self._right_pad()
        if self.has_leading():
            width += self._glyph()
            if self._text:
                width += spacing.glyph
        width += self._label_width()
        if self._removable:
            width += spacing.cross + self._cross() + CROSS_PAD * 2
        return width

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        height = CHIP_HEIGHT[self.size_step]
        return QtCore.QSize(self._natural_width(), height)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(min(self._natural_width(), CHIP_HEIGHT[self.size_step]), CHIP_HEIGHT[self.size_step])

    def _corner(self) -> float:
        """A badge is a pill, `rounded-4xl` upstream."""
        return CHIP_HEIGHT[self.size_step] / 2.0

    def _box(self) -> QtCore.QRect:
        height = min(self.height(), CHIP_HEIGHT[self.size_step])
        box = QtCore.QRect(0, 0, self.width(), height)
        box.moveCenter(self.rect().center())
        return box

    def _cross_box(self) -> QtCore.QRect:
        """The cross's own rounded box: the glyph plus `REMOVE_CONTROL`'s 2px."""
        side = self._cross() + CROSS_PAD * 2
        box = self._box()
        rect = QtCore.QRect(0, 0, side, side)
        rect.moveCenter(
            QtCore.QPoint(box.right() - self._right_pad() - side // 2 + 1, box.center().y())
        )
        return rect

    def _cross_hit(self) -> QtCore.QRect:
        """The 24px hit box rule 3 gives an icon control, centred on the cross."""
        rect = QtCore.QRect(0, 0, ICON_HIT_BOX, ICON_HIT_BOX)
        rect.moveCenter(self._cross_box().center())
        return rect

    # --- colours ---

    def _surface(self) -> tuple[QtGui.QColor | None, QtGui.QColor | None, QtGui.QColor]:
        theme = self.theme
        if self._variant == "default":
            return theme.color("primary"), None, theme.color("primary_foreground")
        if self._variant == "secondary":
            return theme.color("secondary"), None, theme.color("secondary_foreground")
        if self._variant == "outline":
            return None, theme.color("border"), theme.color("foreground")
        return (
            with_alpha(theme.destructive, 0.2 if theme.dark else 0.1),
            None,
            theme.color("destructive"),
        )

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        box = self._box()
        corner = self._corner()
        fill, border, ink = self._surface()
        fill_round_rect(painter, box, corner, fill, border)

        spacing = CHIP_SPACING[self.size_step]
        x = box.x() + self._left_pad()
        if self.has_leading():
            glyph = self._glyph()
            slot = QtCore.QRect(0, 0, glyph, glyph)
            slot.moveCenter(QtCore.QPoint(x + glyph // 2, box.center().y()))
            self.paint_leading(painter, slot, ink)
            x += glyph + (spacing.glyph if self._text else 0)

        right = box.right() + 1 - self._right_pad()
        if self._removable:
            right -= self._cross() + CROSS_PAD * 2 + spacing.cross

        if self._text:
            font = self._font()
            painter.setFont(font)
            width = max(0, right - x)
            label = self.elide(QtGui.QFontMetrics(font), self._text, width)
            self.set_elide_tooltip(self._text, label == self._text)
            painter.setPen(ink)
            painter.drawText(
                QtCore.QRect(x, box.y(), width, box.height()),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                label,
            )

        if self._removable:
            self._paint_cross(painter, ink)
        painter.end()

    def paint_leading(self, painter: QtGui.QPainter, rect: QtCore.QRect, ink: QtGui.QColor) -> None:
        """The leading slot. A badge draws its glyph there; a chip draws its picture."""
        if self._icon is not None:
            paint_icon(painter, rect, self._icon, with_alpha(ink, 0.7))

    def _paint_cross(self, painter: QtGui.QPainter, ink: QtGui.QColor) -> None:
        box = self._cross_box()
        amount = self._cross_hover.value
        if amount > 0:
            wash = with_alpha(ink, CROSS_WASH * amount)
            fill_round_rect(painter, box, float(self.theme.radius_px("sm")), wash)
        glyph = QtCore.QRect(0, 0, self._cross(), self._cross())
        glyph.moveCenter(box.center())
        opacity = CROSS_REST_OPACITY + (1.0 - CROSS_REST_OPACITY) * amount
        paint_icon(painter, glyph, "x", with_alpha(ink, opacity))
        if self.keyboard_focus:
            self.paint_focus_ring(painter, box, float(self.theme.radius_px("sm")))

    # --- interaction ---

    def _set_cross_hovered(self, value: bool) -> None:
        if value != self._cross_hovered:
            self._cross_hovered = value
            self._cross_hover.set(1.0 if value else 0.0)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        self._set_cross_hovered(self._removable and self._cross_hit().contains(event.pos()))

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._set_cross_hovered(False)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if (
            self.isEnabled()
            and self._removable
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and self._cross_hit().contains(event.pos())
        ):
            self.set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.pressed and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.set_pressed(False)
            if self._cross_hit().contains(event.pos()):
                self.removed.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)
        if self.isEnabled() and self._removable and event.key() in keys:
            self.removed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class Chip(Badge):
    """A badge with a picture in its leading slot, which is what a picker's token field holds."""

    #: A chip with no picture yet still measures its leading slot, so the default is a class one.
    _pixmap: QtGui.QPixmap | None = None

    def __init__(
        self,
        text: str = "",
        variant: str = "secondary",
        size: str = "sm",
        icon: str | None = None,
        removable: bool = False,
        pixmap: QtGui.QPixmap | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            text=text,
            variant=variant,
            size=size,
            icon=icon,
            removable=removable,
            parent=parent,
        )
        self.set_pixmap(pixmap)

    @property
    def pixmap(self) -> QtGui.QPixmap | None:
        return self._pixmap

    def set_pixmap(self, value: QtGui.QPixmap | None) -> None:
        """The picture in the leading slot. Cleared, the chip falls back to its glyph."""
        self._pixmap = value
        self.updateGeometry()
        self.update()

    def has_leading(self) -> bool:
        return self._pixmap is not None or self._icon is not None

    def _corner(self) -> float:
        """A chip is `rounded-md`, not a pill, so it reads as a token and not as a status."""
        return float(self.theme.radius_px("md"))

    def paint_leading(self, painter: QtGui.QPainter, rect: QtCore.QRect, ink: QtGui.QColor) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            super().paint_leading(painter, rect, ink)
            return
        radius = float(self.theme.radius_px("sm"))
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(rect), radius, radius)
        painter.save()
        painter.setClipPath(path)
        scaled = self._pixmap.scaled(
            rect.width(),
            rect.height(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        target = QtCore.QRect(0, 0, rect.width(), rect.height())
        target.moveCenter(rect.center())
        painter.drawPixmap(target, scaled, QtCore.QRect(0, 0, rect.width(), rect.height()))
        painter.restore()
