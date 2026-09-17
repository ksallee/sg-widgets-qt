"""A card that opens under the pointer and stays while the pointer is on it.

The card is a `Popover`, so it never takes the anchor's focus. It opens `open_delay` after the
pointer lands on the anchor and closes `close_delay` after the pointer leaves both the anchor
and the card, which is what lets the pointer travel from one to the other.

    card = HoverCard(avatar, HoverCardContent(title="Ada Lovelace", description="Rigging"))
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, Qt

from .base import ThemedWidget, elide
from .popover import CONTENT_PADDING, Popover

__all__ = ["HOVER_CARD_WIDTH", "CLOSE_DELAY_MS", "OPEN_DELAY_MS", "HoverCard", "HoverCardContent"]

#: `w-64` of `hover-card.tsx`.
HOVER_CARD_WIDTH = 256

#: The pause before the card opens, and the grace it leaves for the pointer to reach it.
OPEN_DELAY_MS = 700
CLOSE_DELAY_MS = 300


class HoverCardContent(ThemedWidget):
    """The plain contents of a hover card: `p-2.5` around a title and a muted paragraph."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._description = description
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(HOVER_CARD_WIDTH)

    def set_text(self, title: str, description: str = "") -> None:
        """Replace what the card reads."""
        self._title = title
        self._description = description
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        theme = self.theme
        width = HOVER_CARD_WIDTH
        inner = width - 2 * CONTENT_PADDING
        height = 2 * CONTENT_PADDING
        if self._title:
            height += QtGui.QFontMetrics(theme.font(14, QtGui.QFont.Weight.Medium)).height()
        if self._description:
            metrics = QtGui.QFontMetrics(theme.font(14))
            box = metrics.boundingRect(
                QtCore.QRect(0, 0, inner, 1 << 16), int(Qt.TextFlag.TextWordWrap), self._description
            )
            height += box.height() + (4 if self._title else 0)
        return QtCore.QSize(width, height)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect().adjusted(
            CONTENT_PADDING, CONTENT_PADDING, -CONTENT_PADDING, -CONTENT_PADDING
        )
        top = rect.top()
        if self._title:
            painter.setFont(theme.font(14, QtGui.QFont.Weight.Medium))
            painter.setPen(theme.color("popover_foreground"))
            line = painter.fontMetrics().height()
            painter.drawText(
                QtCore.QRect(rect.left(), top, rect.width(), line),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                elide(painter, self._title, rect.width()),
            )
            top += line + 4
        if self._description:
            painter.setFont(theme.font(14))
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                QtCore.QRect(rect.left(), top, rect.width(), rect.bottom() + 1 - top),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
                self._description,
            )
        painter.end()


class HoverCard(QtCore.QObject):
    """Opens a card on hover of the anchor and keeps it while the pointer is on either."""

    opened = QtCore.Signal()
    closed = QtCore.Signal()

    def __init__(
        self,
        anchor: QtWidgets.QWidget,
        content: QtWidgets.QWidget | None = None,
        open_delay: int = OPEN_DELAY_MS,
        close_delay: int = CLOSE_DELAY_MS,
        side: str = "bottom",
        align: str = "center",
        width: int = HOVER_CARD_WIDTH,
    ) -> None:
        super().__init__(anchor)
        self._anchor = anchor
        # `w-64` is the plain card's own width; a caller whose content asks for another says so,
        # the way the entity chip's `w-72` preview does.
        self._popover = Popover(anchor, content, side=side, align=align, width=width)
        self._popover.opened.connect(self.opened.emit)
        self._popover.closed.connect(self.closed.emit)

        self._open_timer = QtCore.QTimer(self)
        self._open_timer.setSingleShot(True)
        self._open_timer.setInterval(int(open_delay))
        self._open_timer.timeout.connect(self._popover.open)

        self._close_timer = QtCore.QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(int(close_delay))
        self._close_timer.timeout.connect(self._popover.close)

        anchor.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        anchor.installEventFilter(self)
        self._popover.installEventFilter(self)

    @property
    def popover(self) -> Popover:
        """The window the card is drawn on."""
        return self._popover

    @property
    def is_open(self) -> bool:
        """True while the card is up."""
        return self._popover.is_open

    def set_content(self, widget: QtWidgets.QWidget | None) -> None:
        """Put a widget inside the card."""
        self._popover.set_content(widget)

    def open(self) -> None:
        """Show the card at once."""
        self._open_timer.stop()
        self._close_timer.stop()
        self._popover.open()

    def close(self) -> None:
        """Hide the card at once."""
        self._open_timer.stop()
        self._close_timer.stop()
        self._popover.close()

    def _enter(self) -> None:
        self._close_timer.stop()
        if not self._popover.is_open:
            self._open_timer.start()

    def _leave(self) -> None:
        self._open_timer.stop()
        if self._popover.is_open:
            self._close_timer.start()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
            self._enter()
        elif kind in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self._leave()
        return False
