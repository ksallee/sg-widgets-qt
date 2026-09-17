"""The floating surface every menu, list and card in this package hangs off.

A popover is a frameless translucent top-level window that never takes focus, so the anchor
keeps the keyboard and its caret while the popup is open. It is placed against an anchor
widget on a side with an alignment, flips to the other side when it would leave the screen,
follows the anchor when its window moves, and closes on a press outside itself and outside
the anchor.

    popover = Popover(anchor, PopoverContent(title="Filters"), side="bottom", align="start")
    popover.open()

`Qt.Popup` is never used: it takes focus from the anchor, and a picker types into its own
input with the list open.
"""
from __future__ import annotations

from collections.abc import Callable

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal

from ..theme import Theme, apply_theme, theme_of, watch_theme, with_alpha
from .base import DURATION, EASE_IN, EASE_OUT, ThemedWidget, fill_round_rect, paint_shadow

__all__ = [
    "ALIGNS",
    "CONTENT_PADDING",
    "CONTENT_WIDTH",
    "DURATION_MS",
    "MIN_WIDTH",
    "SHADOW_MARGIN",
    "SIDES",
    "SIDE_OFFSET",
    "SLIDE",
    "Popover",
    "PopoverContent",
    "anchor_rect",
    "available_rect",
    "paint_surface",
    "place",
    "popup_flags",
]

Side = str
Align = str

#: The sides a popover hangs off, and the alignments along the other axis.
SIDES: tuple[str, ...] = ("bottom", "top", "left", "right")
ALIGNS: tuple[str, ...] = ("start", "center", "end")

#: The gap between the anchor and the surface.
SIDE_OFFSET = 4

#: The slide a popover enters with, from its anchor side. Upstream `slide-in-from-*-2`.
SLIDE = 8

#: A popover, a menu or a dialog enters and leaves in 100ms. `docs/design-rules.md` rule 4.
DURATION_MS = DURATION["popover"]

#: Room the painted shadow takes around the surface, and the room the slide moves in.
SHADOW_MARGIN = 14

#: `min-w-56` of `PICKER_ANCHORED_POPUP`: an anchored popup is never narrower than this.
MIN_WIDTH = 224

#: `w-72` of the plain popover content.
CONTENT_WIDTH = 288

#: `p-2.5` and `gap-2.5` of the plain popover content.
CONTENT_PADDING = 10

_SCALE_FROM = 0.95


def popup_flags(takes_focus: bool = False) -> Qt.WindowFlags:
    """The flags a popup window wears: a frameless tool window.

    It never takes focus, which is what a picker needs: the anchor keeps the caret and types into
    its own input with the list open. A popover that holds fields of its own, as the two date
    editors do, asks for `takes_focus`, because the caret has to land inside it.

    `NoDropShadowWindowHint` keeps the platform from drawing a square shadow behind the
    translucent window, so the rounded one this package paints is the only one.
    """
    flags = (
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    return flags if takes_focus else flags | Qt.WindowType.WindowDoesNotAcceptFocus


def anchor_rect(widget: QtWidgets.QWidget) -> QRect:
    """A widget's rectangle in global coordinates.

    The size comes from `width` and `height` rather than `size`, which a widget carrying a
    `size` prop of its own shadows.
    """
    top_left = widget.mapToGlobal(QPoint(0, 0))
    return QRect(top_left.x(), top_left.y(), widget.width(), widget.height())


def available_rect(widget: QtWidgets.QWidget) -> QRect:
    """The usable area of the screen the widget is on."""
    screen = None
    getter = getattr(widget, "screen", None)
    if callable(getter):
        screen = getter()
    if screen is None:
        app = QtGui.QGuiApplication.instance()
        if app is not None:
            screen = app.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1024, 768)
    return screen.availableGeometry()


def place(
    anchor: QRect,
    size: QSize,
    side: Side = "bottom",
    align: Align = "start",
    side_offset: int = SIDE_OFFSET,
    screen: QRect | None = None,
) -> tuple[QRect, Side]:
    """Where a surface of `size` sits against `anchor`, and the side it ended up on.

    The side flips to its opposite when the surface would leave the screen and the opposite
    side has room; the alignment axis is then clamped into the screen.
    """
    if side not in SIDES:
        side = "bottom"
    if align not in ALIGNS:
        align = "start"
    width, height = size.width(), size.height()
    if screen is None or screen.isEmpty():
        screen = QRect(0, 0, 1 << 20, 1 << 20)

    vertical = side in ("bottom", "top")
    span = height if vertical else width
    before = (anchor.top() if vertical else anchor.left()) - side_offset - span
    after = (anchor.bottom() if vertical else anchor.right()) + 1 + side_offset
    low = screen.top() if vertical else screen.left()
    high = (screen.bottom() if vertical else screen.right()) + 1

    leading = side in ("top", "left")
    start = before if leading else after
    fits = start >= low if leading else start + span <= high
    if not fits:
        other = after if leading else before
        other_fits = other + span <= high if leading else other >= low
        if other_fits:
            start = other
            side = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}[side]

    cross = _aligned(anchor, size, align, vertical)
    cross_low = screen.left() if vertical else screen.top()
    cross_high = (screen.right() if vertical else screen.bottom()) + 1
    cross_span = width if vertical else height
    cross = max(cross_low, min(cross, cross_high - cross_span))

    if vertical:
        return QRect(cross, start, width, height), side
    return QRect(start, cross, width, height), side


def _aligned(anchor: QRect, size: QSize, align: Align, vertical: bool) -> int:
    low = anchor.left() if vertical else anchor.top()
    extent = anchor.width() if vertical else anchor.height()
    span = size.width() if vertical else size.height()
    if align == "center":
        return low + (extent - span) // 2
    if align == "end":
        return low + extent - span
    return low


def paint_surface(
    painter: QtGui.QPainter,
    rect: QRect,
    theme: Theme,
    radius: str = "lg",
    shadow: bool = True,
) -> None:
    """Draw a popover surface: the painted shadow, the `popover` fill and the hairline ring.

    The ring is `foreground` at 10%, which is upstream's `ring-1 ring-foreground/10`. The shadow
    is painted rather than a `QGraphicsDropShadowEffect`, which leaves the rounded corners of a
    translucent frameless window opaque on PyQt5.
    """
    corner = float(theme.radius_px(radius))
    if shadow:
        paint_shadow(painter, rect, corner, theme)
    fill_round_rect(
        painter,
        rect,
        corner,
        brush=theme.color("popover"),
        border=with_alpha(theme.color("foreground"), 0.10),
    )


def _event_global_pos(event: QtCore.QEvent) -> QPoint | None:
    """The global position of a mouse event, on either Qt generation."""
    getter = getattr(event, "globalPosition", None)
    if getter is not None:
        return getter().toPoint()
    getter = getattr(event, "globalPos", None)
    if getter is not None:
        return getter()
    return None


class Popover(ThemedWidget):
    """A frameless translucent window placed against an anchor, which never takes focus.

    `side` and `align` say where it hangs, `side_offset` the gap; the side flips when the
    surface would leave the screen. `match_anchor_width` takes the anchor's width, never
    under 224, and `width` fixes it outright.
    """

    opened = Signal()
    closed = Signal()
    dismissed = Signal()

    def __init__(
        self,
        anchor: QtWidgets.QWidget,
        content: QtWidgets.QWidget | None = None,
        side: Side = "bottom",
        align: Align = "start",
        side_offset: int = SIDE_OFFSET,
        match_anchor_width: bool = False,
        width: int | None = None,
        takes_focus: bool = False,
    ) -> None:
        super().__init__(anchor.window())
        self._anchor = anchor
        self._content: QtWidgets.QWidget | None = None
        self._side = side if side in SIDES else "bottom"
        self._align = align if align in ALIGNS else "start"
        self._side_offset = int(side_offset)
        self._match_anchor_width = bool(match_anchor_width)
        self._width = width
        self._takes_focus = bool(takes_focus)
        self._placed_side = self._side
        self._open = False
        self._progress = 0.0
        self._animating = False
        self._closing = False
        # A popover is its own top-level, so the walk up to a theme stops at the window and misses
        # the stage under it. It wears the anchor's theme instead, and follows it.
        self._wear_anchor_theme()
        watch_theme(anchor, lambda _theme: self._wear_anchor_theme())
        self._frame = QtGui.QPixmap()
        self._guard: Callable[[QPoint], bool] | None = None
        self._anchor_rect: Callable[[], QRect] | None = None
        self._key_handler: Callable[[QtGui.QKeyEvent], bool] | None = None
        self._watched: list[QtWidgets.QWidget] = []
        self._repositioning = False
        self._pass_through: list[QtWidgets.QWidget] = []

        self.setWindowFlags(popup_flags(self._takes_focus))
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not self._takes_focus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # The surface itself never holds the caret: it is the window that accepts focus, so the
        # field inside it is what the caret lands on.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(
            SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN
        )
        self._layout.setSpacing(0)

        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(DURATION_MS)
        self._animation.valueChanged.connect(self._on_progress)
        self._animation.finished.connect(self._on_animation_done)

        if content is not None:
            self.set_content(content)

    # --- content ------------------------------------------------------------------------

    def content(self) -> QtWidgets.QWidget | None:
        """The widget inside the surface."""
        return self._content

    def set_content(self, widget: QtWidgets.QWidget | None) -> None:
        """Put a widget inside the surface. Its padding is its own."""
        if self._content is not None:
            self._layout.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        if widget is not None:
            self._layout.addWidget(widget)

    # --- placement ----------------------------------------------------------------------

    @property
    def anchor(self) -> QtWidgets.QWidget:
        """The widget the surface hangs off."""
        return self._anchor

    @property
    def side(self) -> Side:
        """The side asked for."""
        return self._side

    @property
    def placed_side(self) -> Side:
        """The side the surface landed on, which is the other one when it had to flip."""
        return self._placed_side

    @property
    def align(self) -> Align:
        """The alignment along the side's other axis."""
        return self._align

    def set_side(self, side: Side) -> None:
        """Change the side and place the surface again."""
        self._side = side if side in SIDES else "bottom"
        if self._open:
            self.reposition()

    def set_align(self, align: Align) -> None:
        """Change the alignment and place the surface again."""
        self._align = align if align in ALIGNS else "start"
        if self._open:
            self.reposition()

    def set_anchor_rect_provider(self, provider: Callable[[], QRect] | None) -> None:
        """Hang the surface off a rectangle inside the anchor, such as the row of a submenu."""
        self._anchor_rect = provider

    def anchor_geometry(self) -> QRect:
        """The rectangle the surface hangs off, in global coordinates."""
        if self._anchor_rect is not None:
            return self._anchor_rect()
        return anchor_rect(self._anchor)

    def surface_rect(self) -> QRect:
        """The surface inside the window, which holds the shadow in its margins."""
        return self.rect().adjusted(SHADOW_MARGIN, SHADOW_MARGIN, -SHADOW_MARGIN, -SHADOW_MARGIN)

    def surface_geometry(self) -> QRect:
        """The surface in global coordinates, the shadow margins left out."""
        rect = self.surface_rect()
        return QRect(self.mapToGlobal(rect.topLeft()), rect.size())

    def surface_size(self) -> QSize:
        """The size the surface wants: the width rule, and the height the content asks for."""
        width = self._width
        if width is None and self._match_anchor_width:
            width = max(MIN_WIDTH, self._anchor.width())
        if width is None:
            width = CONTENT_WIDTH
            if self._content is not None:
                width = max(
                    self._content.sizeHint().width(),
                    self._content.minimumSizeHint().width(),
                    self._content.minimumWidth(),
                )
        width = max(1, int(width))
        height = 0
        if self._content is not None:
            height = max(
                self._content.sizeHint().height(),
                self._content.minimumSizeHint().height(),
                self._content.minimumHeight(),
            )
            for_width = self._content.heightForWidth(width)
            if for_width > 0:
                height = max(height, for_width)
        return QSize(width, max(1, height))

    def reposition(self) -> None:
        """Size the surface, place it against the anchor and move the window under it.

        Resizing the window lays the content out again, which asks for another placement, so
        the walk is guarded: one pass settles the size the content asked for.
        """
        if self._repositioning:
            return
        self._repositioning = True
        try:
            self._reposition()
        finally:
            self._repositioning = False

    def _reposition(self) -> None:
        size = self.surface_size()
        self.resize(size.width() + 2 * SHADOW_MARGIN, size.height() + 2 * SHADOW_MARGIN)
        rect, placed = place(
            self.anchor_geometry(),
            size,
            self._side,
            self._align,
            self._side_offset,
            available_rect(self._anchor),
        )
        self._placed_side = placed
        self.move(rect.left() - SHADOW_MARGIN, rect.top() - SHADOW_MARGIN)

    # --- opening and closing ------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """True from `open` until `close`, the closing animation included."""
        return self._open

    def _wear_anchor_theme(self) -> None:
        anchor = self._anchor
        try:
            theme = theme_of(anchor)
        except RuntimeError:  # The anchor is gone; the popover follows shortly.
            return
        apply_theme(self, theme)

    def open(self) -> None:
        """Place the surface, show it without taking focus, and fade it in."""
        if self._open:
            return
        self._wear_anchor_theme()
        self._open = True
        self._closing = False
        self.reposition()
        self._watch_anchor()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.show()
        self.raise_()
        self._start(1.0)
        self.opened.emit()

    def close(self) -> bool:
        """Fade the surface out and hide it once the animation ends."""
        if not self._open:
            return True
        self._open = False
        self._closing = True
        self._start(0.0)
        return True

    def toggle(self) -> None:
        """Open a closed popover, close an open one."""
        if self._open:
            self.close()
        else:
            self.open()

    def _dismiss(self) -> None:
        if not self._open:
            return
        self.close()
        self.dismissed.emit()

    def _finish_close(self) -> None:
        self._release()
        self.hide()
        self._closing = False
        self.closed.emit()

    def _release(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        for widget in self._watched:
            try:
                widget.removeEventFilter(self)
            except RuntimeError:
                pass
        self._watched = []

    def _watch_anchor(self) -> None:
        self._release_watch()
        node: QtWidgets.QWidget | None = self._anchor
        while node is not None:
            node.installEventFilter(self)
            self._watched.append(node)
            node = node.parentWidget()

    def _release_watch(self) -> None:
        for widget in self._watched:
            try:
                widget.removeEventFilter(self)
            except RuntimeError:
                pass
        self._watched = []

    # --- animation ----------------------------------------------------------------------

    def _start(self, target: float) -> None:
        theme = theme_of(self)
        self._animation.stop()
        if self._content is not None and not self._content.isHidden():
            frame = self._content.grab()
            if not frame.isNull():
                self._frame = frame
        self._animation.setStartValue(float(self._progress))
        self._animation.setEndValue(float(target))
        opening = target >= 1.0
        self._animation.setEasingCurve(
            EASE_OUT if opening else EASE_IN
        )
        self._animating = True
        if self._content is not None and not theme.reduced_motion:
            self._content.setVisible(False)
        self._animation.start()

    def _on_progress(self, value: object) -> None:
        self._progress = float(value)  # type: ignore[arg-type]
        self.setWindowOpacity(self._progress)
        self.update()

    def _on_animation_done(self) -> None:
        self._animating = False
        self._progress = float(self._animation.endValue())
        self.setWindowOpacity(self._progress)
        self._frame = QtGui.QPixmap()
        if self._content is not None:
            self._content.setVisible(self._progress > 0.0)
        if self._progress <= 0.0:
            self._finish_close()
        self.update()

    # --- keyboard -----------------------------------------------------------------------

    def set_key_handler(self, handler: Callable[[QtGui.QKeyEvent], bool] | None) -> None:
        """A callable the anchor's keys reach before the popover's own Escape."""
        self._key_handler = handler

    def handle_key(self, event: QtGui.QKeyEvent) -> bool:
        """Take a key the anchor forwarded. True when the popover used it.

        The anchor keeps the focus and the caret, so the anchor owns its keys and calls this
        for the ones the open surface should answer.
        """
        if not self._open:
            return False
        if self._key_handler is not None and self._key_handler(event):
            return True
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss()
            return True
        return False

    # --- dismissal ----------------------------------------------------------------------

    def set_dismiss_guard(self, guard: Callable[[QPoint], bool] | None) -> None:
        """A callable taking a global point: a press it claims does not dismiss the popover."""
        self._guard = guard

    def add_pass_through(self, widget: QtWidgets.QWidget) -> None:
        """A window a press may land in without dismissing this one, such as a submenu."""
        if widget not in self._pass_through:
            self._pass_through.append(widget)

    def _claims(self, pos: QPoint) -> bool:
        if self.surface_geometry().contains(pos):
            return True
        if anchor_rect(self._anchor).contains(pos) or self.anchor_geometry().contains(pos):
            return True
        for widget in self._pass_through:
            try:
                if widget.isVisible() and widget.geometry().contains(pos):
                    return True
            except RuntimeError:
                continue
        return bool(self._guard is not None and self._guard(pos))

    def _took_activation(self) -> bool:
        """True when the window the anchor's window lost activation to is one of ours.

        Showing a popup deactivates the anchor's window on some platforms, so a deactivation
        that handed activation to this surface or to a submenu of it is not a dismissal.
        """
        app = QtWidgets.QApplication.instance()
        active = app.activeWindow() if app is not None else None
        if active is None:
            return False
        return active is self or any(active is widget for widget in self._pass_through)

    def event(self, event: QtCore.QEvent) -> bool:
        """A layout request means the content asked for another size, so place the surface again.

        The window of a frameless top level grows to its content on its own but never shrinks to
        it, so a calendar turning to a month of fewer weeks would leave a band of empty surface
        under the grid.
        """
        if event.type() == QEvent.Type.LayoutRequest and self._open:
            self.reposition()
        return super().event(event)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and self._open:
            pos = _event_global_pos(event)
            if pos is not None and not self._claims(pos):
                self._dismiss()
        elif obj in self._watched and self._open:
            if kind in (QEvent.Type.Move, QEvent.Type.Resize):
                self.reposition()
            elif kind == QEvent.Type.Hide:
                self._dismiss()
            elif kind == QEvent.Type.WindowDeactivate and not self._took_activation():
                self._dismiss()
        return False

    # --- painting -----------------------------------------------------------------------

    def _slide(self, progress: float) -> tuple[float, float]:
        left = SLIDE * (1.0 - progress)
        if self._placed_side == "bottom":
            return 0.0, -left
        if self._placed_side == "top":
            return 0.0, left
        if self._placed_side == "right":
            return -left, 0.0
        return left, 0.0

    def _origin(self, rect: QtCore.QRectF) -> QtCore.QPointF:
        if self._placed_side == "bottom":
            return QtCore.QPointF(rect.center().x(), rect.top())
        if self._placed_side == "top":
            return QtCore.QPointF(rect.center().x(), rect.bottom())
        if self._placed_side == "right":
            return QtCore.QPointF(rect.left(), rect.center().y())
        return QtCore.QPointF(rect.right(), rect.center().y())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        theme = theme_of(self)
        rect = QtCore.QRectF(self.surface_rect())
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._animating and not theme.reduced_motion:
            scale = _SCALE_FROM + (1.0 - _SCALE_FROM) * self._progress
            dx, dy = self._slide(self._progress)
            origin = self._origin(rect)
            painter.translate(dx, dy)
            painter.translate(origin)
            painter.scale(scale, scale)
            painter.translate(-origin)
        paint_surface(painter, self.surface_rect(), theme)
        if self._animating and not self._frame.isNull():
            painter.drawPixmap(rect, self._frame, QtCore.QRectF(self._frame.rect()))
        painter.end()

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        if self._open:
            self._open = False
            self._release()
            self.closed.emit()
        super().hideEvent(event)


class PopoverContent(QtWidgets.QWidget):
    """The plain contents of a popover: 10 of padding, 10 between the things stacked in it."""

    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(
            CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING, CONTENT_PADDING
        )
        layout.setSpacing(CONTENT_PADDING)
        self._layout = layout
        self.setMinimumWidth(CONTENT_WIDTH)
        if title is not None or description is not None:
            header = QtWidgets.QWidget(self)
            inner = QtWidgets.QVBoxLayout(header)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(2)
            if title is not None:
                inner.addWidget(_label(title, header, medium=True))
            if description is not None:
                inner.addWidget(_label(description, header, muted=True))
            layout.addWidget(header)

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        """Stack a widget under the ones already there."""
        self._layout.addWidget(widget)


def _label(
    text: str, parent: QtWidgets.QWidget, medium: bool = False, muted: bool = False
) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text, parent)
    label.setWordWrap(True)
    theme = theme_of(parent)
    weight = QtGui.QFont.Weight.Medium if medium else QtGui.QFont.Weight.Normal
    label.setFont(theme.font(14, weight))
    # A colour on the label itself, because the root's generated stylesheet sets `QLabel`'s
    # own `color` and would otherwise win over a palette role.
    ink = theme.color("muted_foreground" if muted else "popover_foreground")
    label.setStyleSheet(f"color: rgba({ink.red()}, {ink.green()}, {ink.blue()}, {ink.alpha()});")
    return label
