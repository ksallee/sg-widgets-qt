"""The text field and its multi-line sibling, drawn by us over Qt's editing behaviour.

Ported from `packages/react/src/components/ui/input.tsx` and `textarea.tsx`. `QLineEdit` and
`QPlainTextEdit` are kept for the caret, the selection, the undo stack and the input method; the
frame is off and every pixel of chrome is painted here from the tokens.

    field = Input(placeholder="Search shots")
    field.set_leading_icon("search")
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

from ..icons import paint_icon
from ..theme import with_alpha
from .base import (
    CONTROL_GLYPH,
    CONTROL_HEIGHT,
    CONTROL_PAD,
    DURATION,
    ThemedMixin,
    fill_round_rect,
    keep_themed,
    painter_for,
)
from .scrollbar import install_overlay_scrollbars

__all__ = ["GLYPH_GAP", "TEXTAREA_MIN_HEIGHT", "Input", "Textarea", "apply_field_ink"]

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


def apply_field_ink(widget: QtWidgets.QWidget, theme: object) -> None:
    """Write the ink Qt draws itself into a field's palette: text, placeholder and selection.

    The three groups are written, not one: the painter's opacity never reaches the text Qt draws
    itself, so `disabled:opacity-50` is a colour here, and Qt picks it from the `Disabled` group
    on its own. Nothing about the ink goes through a stylesheet, because a stylesheet anywhere
    over a field beats every palette under it, and Qt 5 then derives the placeholder from it too.

    The first call also gives the field a keeper, so the ink is written again whenever Qt rebuilds
    the palette out from under it or the field arrives under a theme it has not read.
    """
    keep_themed(widget, lambda theme: apply_field_ink(widget, theme))
    palette = widget.palette()
    role = QtGui.QPalette.ColorRole
    group = QtGui.QPalette.ColorGroup
    clear = QtGui.QColor(QtCore.Qt.GlobalColor.transparent)
    ink = theme.color("foreground")
    muted = theme.color("muted_foreground")
    placeholder = getattr(role, "PlaceholderText", None)
    for state in (group.Active, group.Inactive, group.Disabled):
        inert = state == group.Disabled
        palette.setColor(state, role.Base, clear)
        palette.setColor(state, role.Window, clear)
        for text_role in (role.Text, role.WindowText):
            palette.setColor(state, text_role, with_alpha(ink, DISABLED_INK) if inert else ink)
        palette.setColor(state, role.Highlight, theme.color("accent"))
        palette.setColor(state, role.HighlightedText, theme.color("accent_foreground"))
        if placeholder is not None:
            palette.setColor(
                state, placeholder, with_alpha(muted, DISABLED_INK) if inert else muted
            )
    widget.setPalette(palette)
    # `QPlainTextEdit` draws its text from the viewport's palette, which is a widget of its own
    # and does not always take the one set here.
    viewport = getattr(widget, "viewport", None)
    if callable(viewport):
        viewport().setPalette(palette)


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
        # After the first dressing: `apply_field_ink` leaves a keeper that writes back the ink
        # alone, and a field's dressing is the type step too.
        keep_themed(self, lambda _theme: self.apply_theme_to_palette())

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
        apply_field_ink(self, theme)
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
        # `input.tsx` and `textarea.tsx` are `bg-transparent dark:bg-input/30`: the box is the
        # surface it stands on, lifted by the wash on a dark page. Filling `background` under
        # that wash would paint the page's own ground over a popover's or a card's, and the
        # field would read as a hole cut in the surface rather than as a box on it.
        surface = self._wash(theme)
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


#: The corner a textarea is dragged taller by, in pixels of its bottom-right.
TEXTAREA_GRIP = 12


class Textarea(_Field, QtWidgets.QPlainTextEdit):
    """Several lines of text in the same box, at least 64 high.

    The box grows with its text, which is `field-sizing-content` on the upstream textarea, and
    a drag on its bottom-right corner sets its height by hand, which is the resize handle a
    browser gives every textarea; a height set by hand holds, as a browser's does, until
    `set_dragged_height(None)`.
    """

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
        # The thin overlay pair, as every other scroll area here wears, rule 0: the bars turn
        # both native policies off and draw themselves over the viewport.
        install_overlay_scrollbars(self)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        #: The least the box stands at: 64px, or the rows a caller asks for.
        self._floor_height = TEXTAREA_MIN_HEIGHT
        #: A height the reader dragged the box to, or None while it follows its text.
        self._dragged_height: int | None = None
        self._drag_from: tuple[int, int] | None = None
        self.viewport().setMouseTracking(True)
        self.document().documentLayout().documentSizeChanged.connect(self._on_text_grew)
        self.layout_slots()

    # --- the height -----------------------------------------------------------------------

    def content_height(self) -> int:
        """The height its text asks for: every wrapped line, the document margin above and below."""
        lines = 0
        block = self.document().firstBlock()
        while block.isValid():
            layout = block.layout()
            lines += max(1, layout.lineCount() if layout is not None else 1)
            block = block.next()
        margin = int(self.document().documentMargin())
        return max(1, lines) * self.fontMetrics().lineSpacing() + 2 * margin + 2

    @property
    def floor_height(self) -> int:
        """The least height the box asks for; a caller sets it from the rows it wants."""
        return self._floor_height

    def set_floor_height(self, value: int) -> None:
        # A floor set here rather than through `setMinimumHeight`: a layout prefers an explicit
        # minimum to the hint, which would pin the box at the floor when its text or a drag
        # asks for more.
        self._floor_height = max(TEXTAREA_MIN_HEIGHT, int(value))
        self.updateGeometry()

    @property
    def dragged_height(self) -> int | None:
        """The height set by a drag on the corner, or None while the box follows its text."""
        return self._dragged_height

    def set_dragged_height(self, value: int | None) -> None:
        self._dragged_height = max(self._floor_height, int(value)) if value is not None else None
        self.updateGeometry()

    def _on_text_grew(self, *_args: Any) -> None:
        self.updateGeometry()

    def _grip_rect(self) -> QtCore.QRect:
        view = self.viewport().rect()
        return QtCore.QRect(
            view.right() - TEXTAREA_GRIP + 1, view.bottom() - TEXTAREA_GRIP + 1, TEXTAREA_GRIP, TEXTAREA_GRIP
        )

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
        height = self._dragged_height if self._dragged_height is not None else self.content_height()
        return QtCore.QSize(240, max(self._floor_height, height))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        # The height is the box's own, as a browser textarea's intrinsic height is: a page in
        # a scroll area lays its content out at the minimum, so the minimum carries it.
        return QtCore.QSize(0, self.sizeHint().height())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.layout_slots()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and self._grip_rect().contains(event.pos())
            and not self.isReadOnly()
        ):
            self._drag_from = (int(event.globalPos().y()), self.height())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._drag_from is not None:
            start_y, start_height = self._drag_from
            self.set_dragged_height(start_height + int(event.globalPos().y()) - start_y)
            event.accept()
            return
        over = self._grip_rect().contains(event.pos()) and not self.isReadOnly()
        self.viewport().setCursor(
            QtCore.Qt.CursorShape.SizeVerCursor if over else QtCore.Qt.CursorShape.IBeamCursor
        )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._drag_from is not None:
            self._drag_from = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        self.paint_chrome(self.viewport(), self.viewport().rect())
        super().paintEvent(event)
        if self.isReadOnly():
            return
        # The corner grip a browser draws on a textarea: two short diagonals in the muted ink.
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(self.theme.color("muted_foreground"), 1.0))
        grip = self._grip_rect()
        right, bottom = grip.right() - 2, grip.bottom() - 2
        painter.drawLine(right - 7, bottom, right, bottom - 7)
        painter.drawLine(right - 3, bottom, right, bottom - 3)
        painter.end()
