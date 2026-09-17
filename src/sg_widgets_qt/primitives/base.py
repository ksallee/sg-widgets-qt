"""What every painted primitive stands on: the ladders, the states, the motion and the chrome.

`ThemedWidget` is the mixin every leaf in this package wears. It reads the nearest theme, repaints
when one lands, and keeps the three states a painter needs: `hovered`, `pressed` and
`keyboard_focus`, the last one set only when the focus came from Tab, Backtab or a shortcut, so the
focus ring is a keyboard mark and never a mouse one.

The ladders are `docs/design-rules.md` rule 3, ported from the upstream `control-classes.ts`,
`leaf-classes.ts` and `picker-classes.ts` with their docstrings, in pixels rather than Tailwind
steps.

    class Dot(ThemedWidget):
        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            painter.fillRect(self.rect(), self.theme.color("primary"))
"""
from __future__ import annotations

from typing import Callable, Union

from qtpy import QtCore, QtGui, QtWidgets

from ..theme import Theme, theme_of, watch_theme, with_alpha

__all__ = [
    "CHIP_CROSS",
    "CHIP_GLYPH",
    "CHIP_HEIGHT",
    "CHIP_PAD",
    "CHIP_SPACING",
    "CONTROL_GLYPH",
    "CONTROL_HEIGHT",
    "CONTROL_PAD",
    "DURATION",
    "EASE_IN",
    "EASE_OUT",
    "FOCUS_RING_OFFSET",
    "FOCUS_RING_WIDTH",
    "THUMB_SIZE",
    "AnimatedValue",
    "ChipPad",
    "ChipSpacing",
    "ThemedMixin",
    "ThemedWidget",
    "elide",
    "text_width",
    "fill_round_rect",
    "painter_for",
    "paint_focus_ring",
    "paint_shadow",
]

# --- the ladders -----------------------------------------------------------------------------

#: The control ladder of `docs/design-rules.md`: 7 / 8 / 9, the shadcn button's own steps.
CONTROL_HEIGHT: dict[str, int] = {"sm": 28, "md": 32, "lg": 36}

#: The leading inset of a control whose value is plain text.
CONTROL_PAD: dict[str, int] = {"sm": 8, "md": 12, "lg": 12}

#: A glyph inside a control: 16 at sm and md, one step up at lg.
CONTROL_GLYPH: dict[str, int] = {"sm": 16, "md": 16, "lg": 20}

#: The pill a chip or a badge sits in. The chip ladder is the thumbnail ladder with a step under
#: it, so a chip inside the smallest control still has room around it.
CHIP_HEIGHT: dict[str, int] = {"xs": 20, "sm": 24, "md": 32, "lg": 40}

#: A glyph inside a chip or a badge, a step under the type so the label leads.
CHIP_GLYPH: dict[str, int] = {"xs": 12, "sm": 14, "md": 16, "lg": 20}

#: The type step a chip wears, medium weight.
CHIP_TEXT: dict[str, int] = {"xs": 12, "sm": 12, "md": 14, "lg": 14}

#: The cross inside a chip or a badge. It grows a step with the chip.
CHIP_CROSS: dict[str, int] = {"xs": 12, "sm": 14, "md": 16, "lg": 18}

#: Thumbnails and avatars: the three list steps, then the card and the detail pane.
THUMB_SIZE: dict[str, int] = {"sm": 24, "md": 32, "lg": 40, "xl": 64, "2xl": 96}


class ChipPad:
    """A chip's inline padding, optically aligned.

    A bare text edge takes `text`; the edge beside a leading glyph takes `lead`, a step less, since
    the glyph's own shape already reads as space. The edge beside a cross takes `trail`, the room
    above the cross's box, so the box sits as far from the right edge as from the top. A glyph with
    no text takes `icon`.
    """

    __slots__ = ("icon", "lead", "text", "trail")

    def __init__(self, text: int, lead: int, trail: int, icon: int) -> None:
        self.text = text
        self.lead = lead
        self.trail = trail
        self.icon = icon


class ChipSpacing:
    """The space inside a chip: `glyph` between a leading glyph and the label, `cross` before the
    cross, a step less, since the cross's own padding already reads as space."""

    __slots__ = ("cross", "glyph")

    def __init__(self, glyph: int, cross: int) -> None:
        self.glyph = glyph
        self.cross = cross


#: The chip padding ladder in pixels.
CHIP_PAD: dict[str, ChipPad] = {
    "xs": ChipPad(text=6, lead=4, trail=1, icon=4),
    "sm": ChipPad(text=8, lead=6, trail=2, icon=4),
    "md": ChipPad(text=8, lead=6, trail=5, icon=6),
    "lg": ChipPad(text=10, lead=8, trail=8, icon=8),
}

#: The chip spacing ladder in pixels.
CHIP_SPACING: dict[str, ChipSpacing] = {
    "xs": ChipSpacing(glyph=4, cross=2),
    "sm": ChipSpacing(glyph=4, cross=2),
    "md": ChipSpacing(glyph=6, cross=4),
    "lg": ChipSpacing(glyph=6, cross=4),
}

#: The hit box a remove, clear or open control keeps around its glyph.
ICON_HIT_BOX = 24

# --- motion ----------------------------------------------------------------------------------

#: The durations of `docs/design-rules.md` rule 4, in milliseconds. Nothing over 300.
DURATION: dict[str, int] = {
    "popover": 100,
    "hover": 150,
    "press": 150,
    "focus": 150,
    "item": 200,
    "panel": 300,
    "shimmer": 1500,
}

EASE_OUT = QtCore.QEasingCurve.Type.OutCubic
EASE_IN = QtCore.QEasingCurve.Type.InCubic

# --- the focus ring --------------------------------------------------------------------------

#: The ring is 2px wide and stands 2px off the control, which is where it is painted inward from
#: the widget's own edge: a widget cannot paint outside itself, so the ring rides the control's
#: rim, the way upstream's `PICKER_ARMED` draws an inset ring where an outer one would be clipped.
FOCUS_RING_WIDTH = 2
FOCUS_RING_OFFSET = 2

PainterOrMetrics = Union[QtGui.QPainter, QtGui.QFontMetrics]


def elide(source: PainterOrMetrics, text: str, width: float) -> str:
    """`text` cut at the end to fit `width`, measured with a painter's font or with metrics."""
    metrics = source.fontMetrics() if isinstance(source, QtGui.QPainter) else source
    return metrics.elidedText(text, QtCore.Qt.TextElideMode.ElideRight, max(0, int(width)))


def text_width(metrics: QtGui.QFontMetrics, text: str) -> int:
    """How wide a run of text needs to be to draw whole.

    `horizontalAdvance` rounds down while the text engine lays out in fractions, so a box measured
    at the advance elides the last glyph. One pixel is what that rounding costs.
    """
    return metrics.horizontalAdvance(text) + 1 if text else 0


def paint_focus_ring(
    painter: QtGui.QPainter, rect: QtCore.QRect, radius: float, theme: Theme
) -> None:
    """A 2px ring in `ring` with a 2px gap in `background`, drawn inward from `rect`'s edge."""
    box = QtCore.QRectF(rect)
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

    gap_inset = FOCUS_RING_WIDTH + FOCUS_RING_OFFSET / 2.0
    pen = QtGui.QPen(theme.color("background"), FOCUS_RING_OFFSET)
    painter.setPen(pen)
    painter.drawRoundedRect(
        box.adjusted(gap_inset, gap_inset, -gap_inset, -gap_inset),
        max(0.0, radius - gap_inset),
        max(0.0, radius - gap_inset),
    )

    ring_inset = FOCUS_RING_WIDTH / 2.0
    painter.setPen(QtGui.QPen(theme.color("ring"), FOCUS_RING_WIDTH))
    painter.drawRoundedRect(
        box.adjusted(ring_inset, ring_inset, -ring_inset, -ring_inset),
        max(0.0, radius - ring_inset),
        max(0.0, radius - ring_inset),
    )
    painter.restore()


def paint_shadow(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    radius: float,
    theme: Theme,
    spread: int = 6,
    opacity: float = 0.18,
) -> None:
    """A soft shadow under a surface, painted as falling bands of `foreground`."""
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    box = QtCore.QRectF(rect).translated(0, 2)
    for step in range(spread, 0, -1):
        fade = opacity * (1.0 - (step - 1) / float(spread)) ** 2
        painter.setPen(QtGui.QPen(with_alpha(theme.foreground, fade), 1))
        band = box.adjusted(-step, -step, step, step)
        painter.drawRoundedRect(band, radius + step, radius + step)
    painter.restore()


# --- the animated value ----------------------------------------------------------------------


class AnimatedValue(QtCore.QObject):
    """A float 0 to 1 a widget paints from, driven by `QVariantAnimation`.

    Under `theme.reduced_motion` a target lands at once, so nothing moves and the widget still
    reads the same number.
    """

    changed = QtCore.Signal(float)

    def __init__(
        self,
        widget: QtWidgets.QWidget,
        duration: int = DURATION["hover"],
        easing: QtCore.QEasingCurve.Type = EASE_OUT,
        value: float = 0.0,
    ) -> None:
        super().__init__(widget)
        self._widget = widget
        self._value = float(value)
        self._duration = int(duration)
        self._easing = easing
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setEasingCurve(QtCore.QEasingCurve(easing))
        self._animation.valueChanged.connect(self._on_step)
        self.changed.connect(widget.update)

    @property
    def value(self) -> float:
        return self._value

    @property
    def running(self) -> bool:
        return self._animation.state() == QtCore.QAbstractAnimation.State.Running

    def set(
        self,
        target: float,
        duration: int | None = None,
        easing: QtCore.QEasingCurve.Type | None = None,
    ) -> None:
        """Move to `target`, or land on it at once.

        A value set before the widget is on screen, and every value under reduced motion, lands
        without moving: motion explains a change a reader can see.
        """
        target = max(0.0, min(1.0, float(target)))
        self._animation.stop()
        instant = (
            theme_of(self._widget).reduced_motion
            or not self._widget.isVisible()
            or abs(target - self._value) < 1e-3
        )
        if instant:
            self.set_now(target)
            return
        self._animation.setDuration(int(self._duration if duration is None else duration))
        self._animation.setEasingCurve(QtCore.QEasingCurve(self._easing if easing is None else easing))
        self._animation.setStartValue(float(self._value))
        self._animation.setEndValue(target)
        self._animation.start()

    def set_now(self, target: float) -> None:
        """Land on `target` with no animation."""
        self._animation.stop()
        value = max(0.0, min(1.0, float(target)))
        if value != self._value:
            self._value = value
        self.changed.emit(self._value)

    def loop(self, duration: int, easing: QtCore.QEasingCurve.Type = QtCore.QEasingCurve.Type.Linear) -> None:
        """Run 0 to 1 forever, for a spinner or a shimmer. Inert under reduced motion."""
        self._animation.stop()
        if theme_of(self._widget).reduced_motion:
            self.set_now(0.0)
            return
        self._animation.setDuration(int(duration))
        self._animation.setEasingCurve(QtCore.QEasingCurve(easing))
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def stop(self) -> None:
        """Stop where it stands."""
        self._animation.stop()

    def _on_step(self, value: object) -> None:
        self._value = float(value)
        self.changed.emit(self._value)


# --- the mixin -------------------------------------------------------------------------------

#: The focus reasons that make a focus ring. A mouse press never does.
KEYBOARD_REASONS = (
    QtCore.Qt.FocusReason.TabFocusReason,
    QtCore.Qt.FocusReason.BacktabFocusReason,
    QtCore.Qt.FocusReason.ShortcutFocusReason,
)


class ThemedMixin:
    """The state and the chrome, in front of any Qt widget class.

    `ThemedWidget` is this mixin on a plain `QWidget`, which is what a painted leaf subclasses.
    A leaf built on a Qt class we keep for its behaviour mixes it in front of that class instead:
    `class Input(ThemedMixin, QLineEdit)`, which works because every handler here calls up the
    chain.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        size_step = kwargs.pop("size_step", "md")
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._size_step = str(size_step)
        self._hovered = False
        self._pressed = False
        self._keyboard_focus = False
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        watch_theme(self, self._on_theme)

    # --- theme ---

    @property
    def theme(self) -> Theme:
        """The nearest theme at or above this widget."""
        return theme_of(self)

    def _on_theme(self, theme: Theme) -> None:
        """A theme landed. Widgets that cache metrics from it override this and call up."""
        self.updateGeometry()
        self.update()

    # --- the ladder step ---

    @property
    def size_step(self) -> str:
        """`sm`, `md` or `lg`: which rung of the ladder this widget stands on."""
        return self._size_step

    @size_step.setter
    def size_step(self, value: str) -> None:
        self.set_size_step(value)

    def set_size_step(self, value: str) -> None:
        if value != self._size_step:
            self._size_step = value
            self.updateGeometry()
            self.update()

    # --- states ---

    @property
    def hovered(self) -> bool:
        return self._hovered

    @property
    def pressed(self) -> bool:
        return self._pressed

    @property
    def keyboard_focus(self) -> bool:
        """True while the focus arrived from the keyboard, which is when the ring is painted."""
        return self._keyboard_focus

    def set_hovered(self, value: bool) -> None:
        if value != self._hovered:
            self._hovered = value
            self.on_hover_changed(value)
            self.update()

    def set_pressed(self, value: bool) -> None:
        if value != self._pressed:
            self._pressed = value
            self.on_press_changed(value)
            self.update()

    def on_hover_changed(self, value: bool) -> None:
        """Hook for a subclass that animates on hover."""

    def on_press_changed(self, value: bool) -> None:
        """Hook for a subclass that animates on press."""

    # --- events ---

    def enterEvent(self, event: object) -> None:  # noqa: N802
        super().enterEvent(event)  # type: ignore[misc]
        if self.isEnabled():
            self.set_hovered(True)

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        super().leaveEvent(event)  # type: ignore[misc]
        self.set_hovered(False)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusInEvent(event)
        self._keyboard_focus = event.reason() in KEYBOARD_REASONS
        self.update()

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self._keyboard_focus = False
        self.set_pressed(False)
        self.update()

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            if not self.isEnabled():
                self._hovered = False
                self._pressed = False
            self.update()

    # --- chrome ---

    def animated(
        self,
        duration: int = DURATION["hover"],
        easing: QtCore.QEasingCurve.Type = EASE_OUT,
        value: float = 0.0,
    ) -> AnimatedValue:
        """An `AnimatedValue` bound to this widget, repainting it as it runs."""
        return AnimatedValue(self, duration=duration, easing=easing, value=value)

    def paint_focus_ring(
        self, painter: QtGui.QPainter, rect: QtCore.QRect, radius: float
    ) -> None:
        """The keyboard focus ring around `rect`."""
        paint_focus_ring(painter, rect, radius, self.theme)

    def paint_shadow(self, painter: QtGui.QPainter, rect: QtCore.QRect, radius: float) -> None:
        """A soft shadow under `rect`."""
        paint_shadow(painter, rect, radius, self.theme)

    def elide(self, source: PainterOrMetrics, text: str, width: float) -> str:
        """`text` cut at the end to fit `width`."""
        return elide(source, text, width)

    def set_elide_tooltip(self, text: str, fits: bool) -> None:
        """The full text as the tooltip while it does not fit, and nothing while it does."""
        self.setToolTip("" if fits else text)

    def disabled_opacity(self) -> float:
        """50% while the widget is inert, full otherwise."""
        return 1.0 if self.isEnabled() else 0.5


class ThemedWidget(ThemedMixin, QtWidgets.QWidget):
    """A painted leaf: a `QWidget` that reads the nearest theme and tracks its own states."""


def painter_for(widget: QtWidgets.QWidget) -> QtGui.QPainter:
    """An antialiased painter on `widget`, with the widget's own font."""
    painter = QtGui.QPainter(widget)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
    return painter


def fill_round_rect(
    painter: QtGui.QPainter,
    rect: QtCore.QRect,
    radius: float,
    brush: QtGui.QColor | None = None,
    border: QtGui.QColor | None = None,
    width: float = 1.0,
) -> None:
    """One rounded surface: its fill, then its 1px border drawn inside its own edge."""
    path_rect = QtCore.QRectF(rect)
    if border is not None:
        path_rect = path_rect.adjusted(width / 2.0, width / 2.0, -width / 2.0, -width / 2.0)
        radius = max(0.0, radius - width / 2.0)
    painter.save()
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(QtGui.QBrush(brush) if brush is not None else QtCore.Qt.BrushStyle.NoBrush)
    painter.setPen(QtGui.QPen(border, width) if border is not None else QtCore.Qt.PenStyle.NoPen)
    painter.drawRoundedRect(path_rect, radius, radius)
    painter.restore()


ThemeCallback = Callable[[Theme], None]
