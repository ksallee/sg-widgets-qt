"""The cross that takes a thing away: a chip's, a filter row's, a facet pill's.

Ported from `REMOVE_CONTROL` in `packages/react/src/registry/sg/components/leaf-classes.ts`. The
control is the cross glyph and 2px around it and nothing more — 16 at the smallest chip step, 18
at the next, 20 above that — so a row of them sits level with the chips and the text beside them
rather than standing a button's height above.

Rule 3 of `docs/design-rules.md` asks for a hit box of at least 24 all the same. The widget is
that box, and the box it paints is centred inside it, so the pointer has its 24 pixels while the
layout only ever sees the 16. That is what upstream does with the `pointer-coarse` pseudo-element
it hangs off the same control.

It hovers with a wash of its own foreground at 8% — never the destructive tint, rule 5 — and sits
at 70% until the pointer is on it.

    cross = RemoveControl(step="sm", label="Remove Status filter", parent=row)
    cross.clicked.connect(drop)
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from ..icons import paint_icon
from .accessible import AccessibleControl
from .base import (
    CHIP_CROSS,
    DURATION,
    ICON_HIT_BOX,
    ThemedWidget,
    fill_round_rect,
    painter_for,
    with_alpha,
)

__all__ = ["CROSS_PAD", "RemoveControl"]

#: `p-0.5`: the room the control keeps around its glyph, which is all the box it has.
CROSS_PAD = 2

#: `opacity-70`, up to full under the pointer.
REST_OPACITY = 0.7


class RemoveControl(AccessibleControl, ThemedWidget):
    """A cross on the chip ladder, with the hit box rule 3 asks for centred on it."""

    accessible_role = "button"

    #: The control was pressed, by the pointer or by Space and Enter. Named as the button's own
    #: signal is, so a caller swapping one for the other changes nothing else.
    clicked = Signal()

    def __init__(
        self,
        step: str = "sm",
        label: str = "Remove",
        glyph: str = "x",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._step = step if step in CHIP_CROSS else "sm"
        self._glyph = glyph
        self._hover = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    @property
    def step(self) -> str:
        """Which rung of the chip-cross ladder the glyph stands on."""
        return self._step

    def set_step(self, value: str) -> None:
        self._step = value if value in CHIP_CROSS else "sm"
        self.updateGeometry()
        self.update()

    def box_side(self) -> int:
        """The box the control draws and the layout sees: the glyph and its 2px."""
        return CHIP_CROSS[self._step] + 2 * CROSS_PAD

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        side = max(ICON_HIT_BOX, self.box_side())
        return QtCore.QSize(side, side)

    def painted_box(self) -> QtCore.QRect:
        """Where the cross is drawn inside the hit box the widget is."""
        side = self.box_side()
        box = QtCore.QRect(0, 0, side, side)
        box.moveCenter(self.rect().center())
        return box

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        box = self.painted_box()
        if self.pressed and not theme.reduced_motion:
            centre = QtCore.QPointF(box.center())
            painter.translate(centre)
            painter.scale(0.98, 0.98)
            painter.translate(-centre)
        amount = self._hover.value
        ink = theme.color("foreground")
        if amount > 0:
            # `hover:bg-current/8`: a wash of the control's own ink, never the destructive tint.
            fill_round_rect(
                painter, box, float(theme.radius_px("sm")), with_alpha(ink, 0.08 * amount)
            )
        glyph = QtCore.QRect(0, 0, CHIP_CROSS[self._step], CHIP_CROSS[self._step])
        glyph.moveCenter(box.center())
        paint_icon(painter, glyph, self._glyph, with_alpha(ink, REST_OPACITY + 0.3 * amount))
        if self.keyboard_focus:
            self.paint_focus_ring(painter, box, float(theme.radius_px("sm")))
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.pressed and event.button() == Qt.MouseButton.LeftButton:
            self.set_pressed(False)
            if self.rect().contains(event.pos()):
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)
