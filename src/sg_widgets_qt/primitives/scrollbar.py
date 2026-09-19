"""The thin overlay scrollbar every scrolling surface wears.

Rule 0 of `docs/design-rules.md`: a scrollbar the host style drew is a defect. This one is a
6px bar in `muted_foreground` at 40%, 8px and 60% under the pointer, with no arrows, no groove
and no track, lying over the edge of a viewport and fading out 600ms after the last scroll.

`install_overlay_scrollbars(area)` puts one on each axis of any `QAbstractScrollArea` and turns
the native pair off. The bars read the area's own `QScrollBar` objects, so the view keeps its
scrolling, its wheel and its keyboard, and only the drawing changes.
"""
from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer, QVariantAnimation
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import QAbstractScrollArea, QApplication, QScrollBar, QWidget

from ..theme import theme_of, watch_theme, with_alpha

__all__ = [
    "EDGE_MARGIN",
    "FADE_AFTER_MS",
    "FADE_MS",
    "HOVER_WIDTH",
    "MIN_HANDLE",
    "WIDTH",
    "OverlayScrollBar",
    "install_overlay_scrollbars",
    "overlay_scrollbars_of",
]

#: The bar at rest and under the pointer.
WIDTH = 6
HOVER_WIDTH = 8

#: The room the bar leaves between itself and the edge it lies on.
EDGE_MARGIN = 2

#: The handle never shrinks below this, however long the content is.
MIN_HANDLE = 24

#: The bar stands for this long after the last scroll, then fades over `FADE_MS`.
FADE_AFTER_MS = 600
FADE_MS = 150

#: Where the pair is kept on the area it was installed on.
_PROPERTY = "_sg_overlay_scrollbars"


class OverlayScrollBar(QWidget):
    """A painted bar lying over one edge of a viewport, driven by a `QScrollBar`.

    It is a plain widget rather than a `QScrollBar` subclass: nothing of the host style takes
    part, and the handle the pointer drags is the handle that was drawn.
    """

    def __init__(
        self,
        target: QScrollBar,
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bar = target
        self._orientation = orientation
        self._hovered = False
        self._dragging = False
        self._grab = 0
        self._opacity = 0.0
        #: How long the bar stands before it fades. A test shortens it.
        self.fade_delay_ms = FADE_AFTER_MS

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._fade = QVariantAnimation(self)
        self._fade.setDuration(FADE_MS)
        self._fade.valueChanged.connect(self._on_fade)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade)

        target.valueChanged.connect(self._on_scrolled)
        target.rangeChanged.connect(self._on_scrolled)
        watch_theme(self, lambda _theme: self.update())

    # --- what it shows -------------------------------------------------------------------

    def opacity(self) -> float:
        """How far the bar is drawn, 0 while it is faded out."""
        return self._opacity

    def thickness(self) -> int:
        """The bar's width across the axis it lies on."""
        return HOVER_WIDTH if (self._hovered or self._dragging) else WIDTH

    def scrollable(self) -> bool:
        """True while the content is longer than the viewport on this axis."""
        return self._bar.maximum() > self._bar.minimum()

    def wake(self) -> None:
        """Show the bar and start the wait before it fades."""
        if not self.scrollable():
            self._set_opacity(0.0)
            return
        self._fade.stop()
        self._set_opacity(1.0)
        if not (self._hovered or self._dragging):
            self._timer.start(max(0, int(self.fade_delay_ms)))

    def set_hovered(self, hovered: bool) -> None:
        """Tell the bar the pointer is over it, which widens it and holds it open."""
        if hovered == self._hovered:
            return
        self._hovered = hovered
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, not (hovered or self._dragging)
        )
        if hovered:
            self.wake()
        else:
            self._timer.start(max(0, int(self.fade_delay_ms)))
        self.update()

    def _on_scrolled(self, *_: object) -> None:
        # `wake` repaints only when the opacity moves; a shown bar still has to move its handle.
        self.wake()
        self.update()

    def _start_fade(self) -> None:
        if self._hovered or self._dragging:
            return
        if theme_of(self).reduced_motion:
            self._set_opacity(0.0)
            return
        self._fade.stop()
        self._fade.setStartValue(float(self._opacity))
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_fade(self, value: object) -> None:
        self._set_opacity(float(value))

    def _set_opacity(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self._opacity) < 0.001:
            return
        self._opacity = value
        if value <= 0.0:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.update()

    # --- where the handle is -------------------------------------------------------------

    def _span(self) -> int:
        return self.height() if self._orientation == Qt.Orientation.Vertical else self.width()

    def handle_rect(self) -> QRect:
        """The handle in the bar's own coordinates."""
        span = self._span()
        low, high, page = self._bar.minimum(), self._bar.maximum(), max(1, self._bar.pageStep())
        total = (high - low) + page
        if span <= 0 or total <= 0 or high <= low:
            return QRect()
        length = max(MIN_HANDLE, int(round(span * page / total)))
        length = min(length, span)
        offset = int(round((span - length) * (self._bar.value() - low) / (high - low)))
        thick = self.thickness()
        if self._orientation == Qt.Orientation.Vertical:
            return QRect(self.width() - thick, offset, thick, length)
        return QRect(offset, self.height() - thick, length, thick)

    def _value_at(self, position: int, grab: int) -> int:
        span, handle = self._span(), self.handle_rect()
        length = handle.height() if self._orientation == Qt.Orientation.Vertical else handle.width()
        room = span - length
        low, high = self._bar.minimum(), self._bar.maximum()
        if room <= 0:
            return low
        share = max(0.0, min(1.0, (position - grab) / room))
        return int(round(low + share * (high - low)))

    # --- events ---------------------------------------------------------------------------

    def paintEvent(self, _event: object) -> None:
        if self._opacity <= 0.0 or not self.scrollable():
            return
        handle = self.handle_rect()
        if handle.isEmpty():
            return
        theme = theme_of(self)
        strength = 0.6 if (self._hovered or self._dragging) else 0.4
        color = with_alpha(theme.muted_foreground, strength * self._opacity)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        radius = self.thickness() / 2.0
        painter.drawRoundedRect(handle, radius, radius)
        painter.end()

    def mousePressEvent(self, event: object) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        position = _along(event, self._orientation)
        handle = self.handle_rect()
        start = handle.y() if self._orientation == Qt.Orientation.Vertical else handle.x()
        length = handle.height() if self._orientation == Qt.Orientation.Vertical else handle.width()
        self._dragging = True
        if start <= position < start + length:
            self._grab = position - start
        else:
            self._grab = length // 2
            self._bar.setValue(self._value_at(position, self._grab))
        self.wake()
        event.accept()

    def mouseMoveEvent(self, event: object) -> None:
        if not self._dragging:
            self.set_hovered(True)
            event.ignore()
            return
        self._bar.setValue(self._value_at(_along(event, self._orientation), self._grab))
        event.accept()

    def mouseReleaseEvent(self, event: object) -> None:
        self._dragging = False
        self.wake()
        event.accept()

    def wheelEvent(self, event: object) -> None:
        QApplication.sendEvent(self._bar, event)

    def enterEvent(self, event: object) -> None:  # noqa: N802
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        self.set_hovered(False)
        super().leaveEvent(event)


def _along(event: object, orientation: Qt.Orientation) -> int:
    """The press position along the bar's own axis, on either binding."""
    point = event.position().toPoint() if hasattr(event, "position") else event.pos()
    return point.y() if orientation == Qt.Orientation.Vertical else point.x()


class _Overlay(QObject):
    """Keeps a pair of bars on the edges of one scroll area."""

    def __init__(self, area: QAbstractScrollArea) -> None:
        super().__init__(area)
        self.area = area
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vertical = OverlayScrollBar(area.verticalScrollBar(), Qt.Orientation.Vertical, area)
        self.horizontal = OverlayScrollBar(
            area.horizontalScrollBar(), Qt.Orientation.Horizontal, area
        )
        for bar in (self.vertical, self.horizontal):
            bar.raise_()
        area.verticalScrollBar().rangeChanged.connect(self._on_range)
        area.horizontalScrollBar().rangeChanged.connect(self._on_range)
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        area.viewport().setMouseTracking(True)
        self.relayout()

    def _on_range(self, *_: object) -> None:
        self.relayout()

    def relayout(self) -> None:
        area, viewport = self.area, self.area.viewport()
        edge = area.contentsRect()
        top_left = viewport.mapTo(area, QPoint(0, 0))
        box = QRect(top_left, viewport.size())
        reserve = HOVER_WIDTH + EDGE_MARGIN

        width = HOVER_WIDTH
        self.vertical.setGeometry(
            QRect(
                max(box.left(), edge.right() + 1 - EDGE_MARGIN - width),
                box.top() + EDGE_MARGIN,
                width,
                max(0, box.height() - 2 * EDGE_MARGIN - (reserve if self.horizontal.scrollable() else 0)),
            )
        )
        self.horizontal.setGeometry(
            QRect(
                box.left() + EDGE_MARGIN,
                max(box.top(), edge.bottom() + 1 - EDGE_MARGIN - width),
                max(0, box.width() - 2 * EDGE_MARGIN - (reserve if self.vertical.scrollable() else 0)),
                width,
            )
        )
        for bar in (self.vertical, self.horizontal):
            bar.setVisible(bar.scrollable())
            bar.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.relayout()
        elif kind == QEvent.Type.MouseMove and watched is self.area.viewport():
            self._on_pointer(event)
        elif kind == QEvent.Type.Leave and watched is self.area.viewport():
            self.vertical.set_hovered(False)
            self.horizontal.set_hovered(False)
        elif kind == QEvent.Type.Wheel:
            self.vertical.wake()
            self.horizontal.wake()
        return False

    def _on_pointer(self, event: QEvent) -> None:
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        where = self.area.viewport().mapTo(self.area, point)
        for bar in (self.vertical, self.horizontal):
            bar.set_hovered(bar.isVisible() and bar.geometry().contains(where))


def install_overlay_scrollbars(area: QAbstractScrollArea) -> tuple[OverlayScrollBar, OverlayScrollBar]:
    """Put the thin overlay bars on a scroll area and turn the native pair off.

    Returns the vertical and the horizontal bar. Calling it twice on one area returns the pair
    that is already there.
    """
    found = getattr(area, _PROPERTY, None)
    if not isinstance(found, _Overlay):
        found = _Overlay(area)
        setattr(area, _PROPERTY, found)
    return found.vertical, found.horizontal


def overlay_scrollbars_of(area: QAbstractScrollArea) -> tuple[OverlayScrollBar, OverlayScrollBar] | None:
    """The bars on this area, or None where none were installed."""
    found = getattr(area, _PROPERTY, None)
    if isinstance(found, _Overlay):
        return found.vertical, found.horizontal
    return None
