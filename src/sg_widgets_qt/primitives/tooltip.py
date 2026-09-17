"""The small popover a widget shows after a pause under the pointer.

The host's `QToolTip` wears the host style, which rule 0 of `docs/design-rules.md` calls a
defect, so a tooltip here is a `Popover` carrying one line at 12px on the popover surface.

    Tooltip.attach(button, "Copy the id")

One tooltip lives per widget: attaching again replaces its text.
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, QSize, Qt

from .base import ThemedWidget
from .popover import Popover

__all__ = ["TOOLTIP_DELAY_MS", "TOOLTIP_TEXT", "Tooltip", "TooltipContent"]

#: The pause the pointer has to hold before the tooltip appears.
TOOLTIP_DELAY_MS = 700

#: `text-xs` and `px-3 py-1.5` of the tooltip surface.
TOOLTIP_TEXT = 12
TOOLTIP_PAD_X = 12
TOOLTIP_PAD_Y = 6

_PROPERTY = "_sg_tooltip"


class TooltipContent(ThemedWidget):
    """One line of text on the popover surface, at the metadata step."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    @property
    def text(self) -> str:
        """What the tooltip reads."""
        return self._text

    def set_text(self, text: str) -> None:
        """Replace the line."""
        self._text = text
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self.theme.font(TOOLTIP_TEXT))
        return QSize(
            metrics.horizontalAdvance(self._text) + 2 * TOOLTIP_PAD_X,
            metrics.height() + 2 * TOOLTIP_PAD_Y,
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self.theme.font(TOOLTIP_TEXT))
        painter.setPen(self.theme.color("popover_foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignCenter),
            self._text,
        )
        painter.end()


class Tooltip(QtCore.QObject):
    """A tooltip on one widget, shown after a pause and hidden when the pointer leaves."""

    def __init__(
        self,
        widget: QtWidgets.QWidget,
        text: str = "",
        delay: int = TOOLTIP_DELAY_MS,
        side: str = "bottom",
    ) -> None:
        super().__init__(widget)
        self._widget = widget
        self._content = TooltipContent(text)
        self._popover = Popover(widget, self._content, side=side, align="center")
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(int(delay))
        self._timer.timeout.connect(self._show)
        widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        widget.installEventFilter(self)

    @staticmethod
    def attach(widget: QtWidgets.QWidget, text: str, delay: int = TOOLTIP_DELAY_MS) -> Tooltip:
        """Put a tooltip on a widget, or change the text of the one already there."""
        found = widget.property(_PROPERTY)
        if isinstance(found, Tooltip):
            found.set_text(text)
            return found
        made = Tooltip(widget, text, delay)
        widget.setProperty(_PROPERTY, made)
        return made

    @property
    def text(self) -> str:
        """What the tooltip reads."""
        return self._content.text

    def set_text(self, text: str) -> None:
        """Replace the line."""
        self._content.set_text(text)

    @property
    def popover(self) -> Popover:
        """The window the line is drawn on."""
        return self._popover

    @property
    def is_open(self) -> bool:
        """True while the tooltip is up."""
        return self._popover.is_open

    def hide(self) -> None:
        """Take the tooltip away and forget the pause."""
        self._timer.stop()
        self._popover.close()

    def _show(self) -> None:
        if self._content.text and self._widget.isVisible():
            self._popover.open()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
            self._timer.start()
        elif kind in (
            QEvent.Type.Leave,
            QEvent.Type.HoverLeave,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.Hide,
        ):
            self.hide()
        return False
