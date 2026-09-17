"""One input surface holding an input and its addons.

`input-group.tsx`: a bordered frame on the control ladder with a leading and a trailing slot for
glyphs, text and small buttons, so a search row and a number editor's steppers wear the same
box. The frame draws the border, the fill and the focus ring; the input inside it has none of
its own.
"""
from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, QRect, QSize, Qt, Signal
from qtpy.QtGui import QFont, QFontMetrics, QPainter
from qtpy.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QWidget

from .. import icons
from ..theme import theme_of, watch_theme, with_alpha
from .base import CONTROL_GLYPH, CONTROL_HEIGHT, DURATION, ThemedWidget, fill_round_rect
from .input import TEXT_SIZE, apply_field_ink
from .type_scale import line_box

__all__ = [
    "ADDON_PAD",
    "GROUP_GAP",
    "IconButton",
    "InputGroup",
    "InputGroupButton",
    "InputGroupIcon",
    "InputGroupInput",
    "InputGroupText",
]

#: The frame's own inset, and the gap between the things inside it.
ADDON_PAD = 8
GROUP_GAP = 8

#: The hit box a small button inside the frame keeps.
BUTTON_SIZE = 24


class InputGroupInput(QLineEdit):
    """The caret inside an input group: no box of its own, it borrows the frame's."""

    def __init__(self, parent: QWidget | None = None, size: str = "md") -> None:
        super().__init__(parent)
        self._size = size
        self.setFrame(False)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        watch_theme(self, lambda _theme: self._apply_theme())
        self._apply_theme()

    def _apply_theme(self) -> None:
        theme = theme_of(self)
        # `Input` is `text-base md:text-sm` at every step of `CONTROL_BOX`, which changes the
        # box and never the type: a small control holds body text in a shorter box.
        self.setFont(theme.font(TEXT_SIZE))
        # The ink goes in the palette, never in a stylesheet: a stylesheet beats every palette
        # under it, and Qt 5 derives the placeholder from its `color`.
        apply_field_ink(self, theme)


class InputGroupText(ThemedWidget):
    """A muted label beside the caret: a unit, a prefix, a count."""

    def __init__(self, text: str = "", parent: QWidget | None = None, size: str = "md") -> None:
        super().__init__(parent, size_step=size)
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    def _step(self) -> int:
        # `text-sm` at every step, as the frame's own input is: the ladder moves the box.
        return TEXT_SIZE

    def _font(self) -> QFont:
        # `text-sm text-muted-foreground` of `input-group.tsx`: the body step at the body
        # weight, so the addon reads as the caret's neighbour and never as a label over it.
        return self.theme.font(self._step())

    def sizeHint(self) -> QSize:  # noqa: N802
        # The line box of the step, not the frame's height: upstream the addon is a span of its
        # own line and the row centres it, so a taller box would move nothing and measure wrong.
        metrics = QFontMetrics(self._font())
        return QSize(metrics.horizontalAdvance(self._text), line_box(self._step()))

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font())
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self._text)
        painter.end()


class InputGroupIcon(ThemedWidget):
    """A lucide glyph in a group's leading or trailing slot, muted as upstream's is."""

    def __init__(self, name: str, parent: QWidget | None = None, size: str = "md") -> None:
        super().__init__(parent, size_step=size)
        self._name = name
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_name(self, value: str) -> None:
        self._name = value
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        side = CONTROL_GLYPH[self.size_step]
        return QSize(side, CONTROL_HEIGHT[self.size_step])

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        if not icons.has_icon(self._name):
            return
        painter = QPainter(self)
        side = CONTROL_GLYPH[self.size_step]
        box = QRect(0, (self.height() - side) // 2, side, side)
        icons.paint_icon(painter, box, self._name, with_alpha(self.theme.foreground, 0.5))
        painter.end()


class IconButton(ThemedWidget):
    """A ghost button holding one glyph: the clear, the open, a stepper, a month step.

    It is the `ghost` variant of `button.tsx`: `muted` behind `foreground` on hover, half that
    wash on a dark page, the keyboard focus ring, and never the host style.
    """

    clicked = Signal()

    def __init__(
        self,
        name: str,
        parent: QWidget | None = None,
        side: int = BUTTON_SIZE,
        glyph: int = 16,
        tooltip: str = "",
        width: int = 0,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._side = int(side)
        # A stepper inside an input is wider than it is tall (`h-3.5 w-5` of `number-editor.tsx`),
        # so the box takes a width of its own where one is named and stays square otherwise.
        self._width = int(width) if width else int(side)
        self._glyph = int(glyph)
        self._wash = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if tooltip:
            self.setToolTip(tooltip)

    def set_name(self, value: str) -> None:
        self._name = value
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._width, self._side)

    def on_hover_changed(self, value: bool) -> None:
        self._wash.set(1.0 if value else 0.0)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.disabled_opacity())
        radius = float(theme.radius_px("sm"))
        if self._wash.value > 0:
            # `hover:bg-muted`, and `dark:hover:bg-muted/50` of the ghost variant.
            hover = with_alpha(theme.muted, 0.5) if theme.dark else theme.color("muted")
            fill_round_rect(
                painter, self.rect(), radius, with_alpha(hover, self._wash.value)
            )
        box = QRect(
            (self.width() - self._glyph) // 2,
            (self.height() - self._glyph) // 2,
            self._glyph,
            self._glyph,
        )
        ink = theme.color("foreground")
        icons.paint_icon(painter, box, self._name, with_alpha(ink, 0.85 + 0.15 * self._wash.value))
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), radius)
        painter.end()

    def mousePressEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.set_pressed(True)
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        was = self.pressed
        self.set_pressed(False)
        if was and self.rect().contains(_point(event)):
            self.clicked.emit()

    def keyPressEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


#: Upstream's name for the same thing.
InputGroupButton = IconButton


class InputGroup(ThemedWidget):
    """The bordered frame of `input-group.tsx`.

    `set_control` puts the input in the middle; `add_addon` hangs a glyph, a label or a button
    off either end. `surface` of `muted` gives the `bg-input/30` fill the command row wears.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        size: str = "md",
        surface: str = "background",
    ) -> None:
        super().__init__(parent, size_step=size)
        self._surface = surface
        self._control: QWidget | None = None
        self._leading = 0
        self._invalid = False
        self._focused = False

        row = QHBoxLayout(self)
        row.setContentsMargins(ADDON_PAD, 0, ADDON_PAD, 0)
        row.setSpacing(GROUP_GAP)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_insets(self, lead: int = ADDON_PAD, trail: int = ADDON_PAD, gap: int = GROUP_GAP) -> None:
        """The room before the first addon, after the last, and between the things inside.

        `input-group.tsx` gives an addon `pl-2` / `pr-2` and the caret beside it `pl-1.5`; a
        surface that wants another inset says so in its own class string, as the command box
        does with `*:data-[slot=input-group-addon]:pl-3!`.
        """
        row = self.layout()
        row.setContentsMargins(int(lead), 0, int(trail), 0)
        row.setSpacing(int(gap))

    def set_size_step(self, value: str) -> None:
        """Take a step, and hand it to the addons hanging off the frame's ends.

        An addon reads its own step for its type and its box, so a frame that changed step with
        a stale label beside the caret would draw that label at the step it was built at.
        """
        super().set_size_step(value)
        for addon in self.findChildren((InputGroupText, InputGroupIcon)):
            addon.set_size_step(self.size_step)

    # --- the parts -----------------------------------------------------------------------

    def set_control(self, widget: QWidget) -> None:
        """Put the input in the middle of the frame."""
        row = self.layout()
        if self._control is not None:
            row.removeWidget(self._control)
            self._control.deleteLater()
        self._control = widget
        widget.setParent(self)
        row.insertWidget(self._leading, widget, 1)
        widget.installEventFilter(self)

    def control(self) -> QWidget | None:
        """The input the frame holds."""
        return self._control

    def add_addon(self, widget: QWidget, align: str = "start") -> QWidget:
        """Hang a glyph, a label or a button off the leading or the trailing edge."""
        row = self.layout()
        widget.setParent(self)
        if align == "start":
            row.insertWidget(self._leading, widget, 0)
            self._leading += 1
        else:
            row.addWidget(widget, 0)
        return widget

    def add_icon(self, name: str, align: str = "start") -> InputGroupIcon:
        """A muted lucide glyph in one of the slots."""
        return self.add_addon(InputGroupIcon(name, self, self.size_step), align)  # type: ignore[return-value]

    def add_text(self, text: str, align: str = "end") -> InputGroupText:
        """A muted label in one of the slots."""
        return self.add_addon(InputGroupText(text, self, self.size_step), align)  # type: ignore[return-value]

    # --- states --------------------------------------------------------------------------

    @property
    def invalid(self) -> bool:
        """The border and the ring in `destructive`."""
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        self.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._control and event.type() in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            self._focused = event.type() == QEvent.Type.FocusIn
            self.update()
        return False

    # --- geometry and paint --------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(super().sizeHint().width(), CONTROL_HEIGHT[self.size_step])

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, CONTROL_HEIGHT[self.size_step])

    def _wash(self, theme: object) -> object:
        """The `bg-input/…` the frame wears, which is the one `input.tsx` wears.

        `input-group.tsx` carries no light background at all and `dark:bg-input/30` on a dark
        page; inert it takes that token at 50% light and 80% dark. A frame that filled with
        `background` instead would paint the page's own colour over the wash and read flat
        against the fields beside it on a dark page.
        """
        if not self.isEnabled():
            return with_alpha(theme.input, 0.8 if theme.dark else 0.5)
        return with_alpha(theme.input, 0.3) if theme.dark else None

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.disabled_opacity())
        radius = float(theme.radius_px("lg"))
        fill = with_alpha(theme.input, 0.3) if self._surface == "muted" else self._wash(theme)
        border = theme.color("destructive") if self._invalid else theme.color("input")
        if self._surface == "muted":
            border = with_alpha(border, 0.3)
        fill_round_rect(painter, self.rect(), radius, fill, border)
        if self._focused:
            self.paint_focus_ring(painter, self.rect(), radius)
        painter.end()


def _point(event: QEvent) -> object:
    """A mouse event's position, on either binding."""
    return event.position().toPoint() if hasattr(event, "position") else event.pos()
