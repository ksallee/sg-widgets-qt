"""The text field and its multi-line sibling, drawn by us over Qt's editing behaviour.

Ported from `packages/react/src/components/ui/input.tsx` and `textarea.tsx`. `QLineEdit` and
`QPlainTextEdit` are kept for the caret, the selection, the undo stack and the input method; the
frame is off and every pixel of chrome is painted here from the tokens.

    field = Input(placeholder="Search shots")
    field.set_leading_icon("search")
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from ..icons import paint_icon
from ..theme import mix, with_alpha
from .base import (
    CONTROL_GLYPH,
    CONTROL_HEIGHT,
    CONTROL_PAD,
    DURATION,
    ThemedMixin,
    fill_round_rect,
    painter_for,
)

__all__ = ["GLYPH_GAP", "TEXTAREA_MIN_HEIGHT", "Input", "Textarea"]

#: Between an inline glyph and its text, `docs/design-rules.md` rule 2.
GLYPH_GAP = 6

#: `min-h-16` of `textarea.tsx`.
TEXTAREA_MIN_HEIGHT = 64

#: The body step of rule 6.
TEXT_SIZE = 14

#: The vertical inset of a textarea, which has no ladder height to centre one line in.
TEXTAREA_PAD_Y = 8

#: `bg-input/30` of `input.tsx`: the wash a field wears at rest on a dark page.
REST_WASH_DARK = 0.3

#: `disabled:bg-input/50` and `dark:disabled:bg-input/80`: the wash an inert field wears.
DISABLED_WASH = 0.5
DISABLED_WASH_DARK = 0.8

#: `disabled:opacity-50`, on the ink Qt draws itself, which no painter opacity reaches.
DISABLED_INK = 0.5


class _Field(ThemedMixin):
    """The chrome both fields wear: the surface, the border, the states and the focus ring."""

    def _init_field(self, size: str, invalid: bool) -> None:
        self._invalid = bool(invalid)
        self._leading_icon: str | None = None
        self._trailing: QtWidgets.QWidget | None = None
        self._hover = self.animated(DURATION["hover"])
        self.set_size_step(size if size in CONTROL_HEIGHT else "md")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.apply_theme_to_palette()

    # --- props ---

    @property
    def invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        """The border and the ring in `destructive`, rule 5."""
        self._invalid = bool(value)
        self.update()

    @property
    def leading_icon(self) -> str | None:
        return self._leading_icon

    def set_leading_icon(self, name: str | None) -> None:
        """A glyph in the field's leading slot, inset from the text."""
        self._leading_icon = name
        self.layout_slots()
        self.update()

    @property
    def trailing_widget(self) -> QtWidgets.QWidget | None:
        return self._trailing

    def set_trailing_widget(self, widget: QtWidgets.QWidget | None) -> None:
        """A control in the field's trailing slot: a clear button, a unit, a spinner."""
        if self._trailing is not None and self._trailing is not widget:
            self._trailing.setParent(None)
        self._trailing = widget
        if widget is not None:
            widget.setParent(self)
            widget.show()
        self.layout_slots()
        self.update()

    # --- geometry ---

    def _pad(self) -> int:
        return CONTROL_PAD[self.size_step]

    def _glyph(self) -> int:
        return CONTROL_GLYPH[self.size_step]

    def _leading_width(self) -> int:
        return self._glyph() + GLYPH_GAP if self._leading_icon else 0

    def _trailing_width(self) -> int:
        if self._trailing is None:
            return 0
        return self._trailing.sizeHint().width() + GLYPH_GAP

    def layout_slots(self) -> None:
        """Place the trailing widget and give the editor the room the slots leave."""
        raise NotImplementedError

    # --- palette ---

    def apply_theme_to_palette(self) -> None:
        """The tokens Qt's own text drawing reads: the ink, the placeholder and the selection."""
        theme = self.theme
        palette = self.palette()
        role = QtGui.QPalette.ColorRole
        palette.setColor(role.Base, QtGui.QColor(QtCore.Qt.GlobalColor.transparent))
        palette.setColor(role.Window, QtGui.QColor(QtCore.Qt.GlobalColor.transparent))
        palette.setColor(role.Text, theme.color("foreground"))
        palette.setColor(role.WindowText, theme.color("foreground"))
        palette.setColor(role.Highlight, theme.color("accent"))
        palette.setColor(role.HighlightedText, theme.color("accent_foreground"))
        placeholder = getattr(role, "PlaceholderText", None)
        if placeholder is not None:
            # The painter's opacity never reaches Qt's own text, so the inert step is on the ink.
            ink = theme.color("muted_foreground")
            palette.setColor(
                placeholder, ink if self.isEnabled() else with_alpha(ink, DISABLED_INK)
            )
        self.setPalette(palette)
        self.setFont(theme.font(TEXT_SIZE))

    def _on_theme(self, theme: object) -> None:
        self.apply_theme_to_palette()
        self.layout_slots()
        super()._on_theme(theme)

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.EnabledChange:
            self.apply_theme_to_palette()
            self.update()

    # --- chrome ---

    def paint_chrome(self, device: QtWidgets.QWidget, rect: QtCore.QRect) -> None:
        theme = self.theme
        radius = float(theme.radius_px("lg"))
        painter = painter_for(device)
        painter.setOpacity(self.disabled_opacity())

        # The shadcn input has no hover state; the wash on hover belongs to the picker control alone.
        surface = theme.color("background")
        wash = self._wash(theme)
        if wash is not None:
            surface = mix(surface, QtGui.QColor(wash.rgb()), wash.alphaF())
        border = theme.color("destructive") if self._invalid else theme.color("input")
        fill_round_rect(painter, rect, radius, surface, border)

        if self._invalid:
            ring = with_alpha(theme.destructive, 0.4 if theme.dark else 0.2)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(ring, 2))
            inset = QtCore.QRectF(rect).adjusted(2.0, 2.0, -2.0, -2.0)
            painter.drawRoundedRect(inset, radius - 2.0, radius - 2.0)

        if self._leading_icon:
            glyph = self._glyph()
            box = QtCore.QRect(0, 0, glyph, glyph)
            box.moveCenter(QtCore.QPoint(rect.x() + self._pad() + glyph // 2, self._glyph_centre(rect)))
            paint_icon(painter, box, self._leading_icon, theme.color("muted_foreground"))

        if self.keyboard_focus:
            self.paint_focus_ring(painter, rect, radius)
        painter.end()

    def _wash(self, theme: object) -> QtGui.QColor | None:
        """The `bg-input/…` of `input.tsx`, or nothing where the field is a plain box.

        A field is transparent at rest on a light page and wears the `input` token at 30% on a
        dark one; inert, it wears that token at 50% light and 80% dark. The `input` token carries
        its own alpha, so the fraction is of that.
        """
        if not self.isEnabled():
            return with_alpha(theme.input, DISABLED_WASH_DARK if theme.dark else DISABLED_WASH)
        return with_alpha(theme.input, REST_WASH_DARK) if theme.dark else None

    def _glyph_centre(self, rect: QtCore.QRect) -> int:
        return rect.center().y()

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)


class Input(_Field, QtWidgets.QLineEdit):
    """One line of text in our own box: no native frame, our border, our states."""

    def __init__(
        self,
        placeholder: str = "",
        size: str = "md",
        invalid: bool = False,
        readonly: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._init_field(size, invalid)
        self.setFrame(False)
        self.setPlaceholderText(placeholder)
        self.setReadOnly(readonly)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)
        self.layout_slots()

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in CONTROL_HEIGHT else "md")
        self.layout_slots()

    def set_size_step(self, value: str) -> None:
        super().set_size_step(value)
        self.layout_slots()

    def layout_slots(self) -> None:
        pad = self._pad()
        self.setTextMargins(pad + self._leading_width(), 0, pad + self._trailing_width(), 0)
        if self._trailing is not None:
            hint = self._trailing.sizeHint()
            x = self.width() - pad - hint.width()
            y = (self.height() - hint.height()) // 2
            self._trailing.setGeometry(x, y, hint.width(), hint.height())

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        height = CONTROL_HEIGHT[self.size_step]
        return QtCore.QSize(max(160, super().sizeHint().width()), height)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, CONTROL_HEIGHT[self.size_step])

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.layout_slots()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        self.paint_chrome(self, self.rect())
        super().paintEvent(event)


class Textarea(_Field, QtWidgets.QPlainTextEdit):
    """Several lines of text in the same box, at least 64 high."""

    def __init__(
        self,
        placeholder: str = "",
        size: str = "md",
        invalid: bool = False,
        readonly: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._init_field(size, invalid)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setPlaceholderText(placeholder)
        self.setReadOnly(readonly)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(TEXTAREA_PAD_Y)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumHeight(TEXTAREA_MIN_HEIGHT)
        self.layout_slots()

    def layout_slots(self) -> None:
        # The viewport covers the whole field, because `QPlainTextEdit` paints on it and the
        # border belongs to the field's own edge. The text is inset by the document instead.
        pad = self._pad()
        frame = self.document().rootFrame()
        form = frame.frameFormat()
        form.setLeftMargin(max(0, pad + self._leading_width() - TEXTAREA_PAD_Y))
        form.setRightMargin(max(0, pad + self._trailing_width() - TEXTAREA_PAD_Y))
        frame.setFrameFormat(form)
        if self._trailing is not None:
            hint = self._trailing.sizeHint()
            self._trailing.setGeometry(
                self.width() - pad - hint.width(), TEXTAREA_PAD_Y, hint.width(), hint.height()
            )

    def _glyph_centre(self, rect: QtCore.QRect) -> int:
        return rect.y() + TEXTAREA_PAD_Y + self._glyph() // 2

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(240, TEXTAREA_MIN_HEIGHT)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, TEXTAREA_MIN_HEIGHT)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.layout_slots()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        self.paint_chrome(self.viewport(), self.viewport().rect())
        super().paintEvent(event)
