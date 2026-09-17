"""The placeholder a widget shows while its read is in flight.

Ported from `packages/react/src/components/ui/skeleton.tsx`, with the pulse replaced by the
shimmer `docs/design-rules.md` rule 4 asks for: a translucent highlight sweeping across the block
every 1.5 seconds, still under `theme.reduced_motion`.

A skeleton stands in for the thing it replaces, so it takes that thing's size and its radius.

    Skeleton(width=160, height=14)
    Skeleton(width=32, height=32, round=True)
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from ..theme import with_alpha
from .base import DURATION, AnimatedValue, ThemedWidget, painter_for

__all__ = ["Skeleton"]

#: How far past each edge the highlight starts and ends, as a share of the block's width.
SHIMMER_OVERSHOOT = 0.6

#: The highlight, as a share of the block's width.
SHIMMER_WIDTH = 0.45

#: What the highlight is: `foreground` at this opacity over `accent`.
SHIMMER_OPACITY = 0.14

DEFAULT_WIDTH = 80
DEFAULT_HEIGHT = 16


class Skeleton(ThemedWidget):
    """A block in `accent` with a shimmer, shaped like the content it stands in for."""

    def __init__(
        self,
        width: int | None = None,
        height: int | None = None,
        radius: str = "md",
        round: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._width = width
        self._height = height
        self._radius = radius
        self._round = bool(round)
        self._animated = True
        self._shimmer = AnimatedValue(self, duration=DURATION["shimmer"])

        policy = QtWidgets.QSizePolicy.Policy
        self.setSizePolicy(
            policy.Fixed if width is not None else policy.Expanding,
            policy.Fixed if height is not None else policy.Preferred,
        )
        if width is not None:
            self.setFixedWidth(int(width))
        if height is not None:
            self.setFixedHeight(int(height))
        self._restart()

    # --- props ---

    @property
    def animated(self) -> bool:
        return self._animated

    def set_animated(self, value: bool) -> None:
        """Run the shimmer, or hold the block still."""
        self._animated = bool(value)
        self._restart()

    @property
    def running(self) -> bool:
        """True while the shimmer is moving. Always false under reduced motion."""
        return self._shimmer.running

    @property
    def round(self) -> bool:
        return self._round

    def set_round(self, value: bool) -> None:
        self._round = bool(value)
        self.update()

    def _restart(self) -> None:
        if self._animated and self.isEnabled():
            self._shimmer.loop(DURATION["shimmer"])
        else:
            self._shimmer.stop()
        self.update()

    def _on_theme(self, theme: object) -> None:
        self._restart()
        super()._on_theme(theme)

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            self._restart()

    # --- geometry ---

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(
            DEFAULT_WIDTH if self._width is None else int(self._width),
            DEFAULT_HEIGHT if self._height is None else int(self._height),
        )

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def _corner(self) -> float:
        if self._round:
            return min(self.width(), self.height()) / 2.0
        return float(self.theme.radius_px(self._radius))

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        corner = self._corner()

        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(self.rect()), corner, corner)
        painter.setClipPath(path)
        painter.fillPath(path, theme.color("accent"))

        if self._shimmer.running:
            width = self.width()
            band = max(24.0, width * SHIMMER_WIDTH)
            travel = width * (1.0 + 2.0 * SHIMMER_OVERSHOOT)
            start = -width * SHIMMER_OVERSHOOT + travel * self._shimmer.value
            gradient = QtGui.QLinearGradient(start, 0.0, start + band, 0.0)
            clear = with_alpha(theme.foreground, 0.0)
            gradient.setColorAt(0.0, clear)
            gradient.setColorAt(0.5, with_alpha(theme.foreground, SHIMMER_OPACITY))
            gradient.setColorAt(1.0, clear)
            painter.fillPath(path, QtGui.QBrush(gradient))
        painter.end()
