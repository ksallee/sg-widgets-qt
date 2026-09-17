"""A `color` field, as a swatch and a text input.

Ported from `packages/react/src/registry/sg/components/color-editor.tsx`.

    editor = ColorEditor(value="253,94,99")
    editor.committed.connect(write)

The stored form is decimal `r,g,b` with no spaces and no `#`; hex is rejected on write and inside a
filter, so a hex code typed here is converted before it is emitted. `Task.color` also takes the
token `pipeline_step`, which is the only way to un-set it: a written null is a 400
(field_types/color).

The web halves open the browser's own colour picker. There is no such thing in Qt that is not the
host's dialog, so the swatch opens a popover this package paints: a saturation and value square over
a hue strip.
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QPoint, QRect, QSize, Qt, Signal

from sg_widgets_core.edit import parse_color_input
from sg_widgets_core.render import COLOR_SENTINEL
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.status import Rgb, parse_bg_color

from ..primitives.base import (
    CONTROL_HEIGHT,
    DURATION,
    ThemedWidget,
    fill_round_rect,
)
from ..primitives.input import Input
from ..primitives.popover import Popover
from ..theme import with_alpha
from .value_editor import VALUE_EDITOR_GAP, EditorNote, ValueEditor, ValueSession, fade_disabled

__all__ = ["SENTINEL_NOTE", "SWATCH_SIZE", "ColorEditor", "ColorPicker", "ColorSwatch"]

#: `SWATCH` of `color-editor.tsx`: the square beside the input, one step over the control ladder.
SWATCH_SIZE: dict[str, int] = {"sm": 32, "md": 36, "lg": 40}

#: What the line under the control says about the pipeline-step token.
SENTINEL_NOTE = "Takes the colour of the linked pipeline step."

#: The picker's square, its hue strip and the room around them.
SQUARE = QSize(184, 132)
STRIP_HEIGHT = 12
PICKER_PAD = 12
PICKER_GAP = 12

#: What one arrow key moves, as a fraction of the axis.
KEY_STEP = 0.01

#: The knob the picker drags.
KNOB = 10


def _triple(color: QtGui.QColor) -> str:
    """A colour as the decimal `r,g,b` the field stores."""
    return f"{color.red()},{color.green()},{color.blue()}"


def _color_of(rgb: Rgb | None) -> QtGui.QColor | None:
    return None if rgb is None else QtGui.QColor(rgb.r, rgb.g, rgb.b)


class _TripleInput(Input):
    """The triple as text: the monospace family with tabular figures, rule 6's spelling for a code."""

    def apply_theme_to_palette(self) -> None:
        super().apply_theme_to_palette()
        self.setFont(self.theme.font(14, mono=True, tabular=True))


class ColorSwatch(ThemedWidget):
    """The square beside the input: the previewed colour, or `muted` while there is none."""

    clicked = Signal()

    def __init__(
        self,
        color: QtGui.QColor | None = None,
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size_step=size if size in CONTROL_HEIGHT else "md")
        self._color = color
        self._readonly = False
        self._hover = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setToolTip("Pick a colour")

    @property
    def color(self) -> QtGui.QColor | None:
        return self._color

    def set_color(self, value: QtGui.QColor | None) -> None:
        self._color = value
        self.update()

    def set_readonly(self, value: bool) -> None:
        self._readonly = bool(value)
        self.setCursor(
            Qt.CursorShape.ArrowCursor if self._readonly else Qt.CursorShape.PointingHandCursor
        )
        self.setToolTip("" if self._readonly else "Pick a colour")
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        side = SWATCH_SIZE[self.size_step]
        return QSize(side, side)

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value and not self._readonly else 0.0)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self.disabled_opacity())
        radius = float(theme.radius_px("lg"))
        box = self.rect()
        # Colour that is data is painted as it is; every other pixel is a token.
        fill = self._color if self._color is not None else theme.color("muted")
        fill_round_rect(painter, box, radius, fill, theme.color("input"))
        if self._hover.value > 0:
            fill_round_rect(
                painter, box, radius, with_alpha(theme.foreground, 0.08 * self._hover.value)
            )
        if self.keyboard_focus:
            self.paint_focus_ring(painter, box, radius)
        painter.end()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and not self._readonly and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
        if event.key() in keys and self.isEnabled() and not self._readonly:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ColorPicker(ThemedWidget):
    """A saturation and value square over a hue strip, both dragged and both walked.

    `moved` carries the colour under the pointer as it travels, for a live preview; `picked`
    carries the one the pointer let go on.
    """

    moved = Signal(str)
    picked = Signal(str)

    def __init__(
        self,
        color: QtGui.QColor | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._hue = 0.0
        self._saturation = 1.0
        self._brightness = 1.0
        self._square_cache: QtGui.QImage | None = None
        self._cached_hue = -1.0
        self._dragging = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if color is not None:
            self.set_color(color)

    # --- the value -----------------------------------------------------------------------

    @property
    def color(self) -> QtGui.QColor:
        """The colour the knobs stand on."""
        return QtGui.QColor.fromHsvF(
            max(0.0, min(0.999, self._hue)), self._saturation, self._brightness
        )

    def set_color(self, color: QtGui.QColor) -> None:
        """Move the knobs to a colour, without emitting."""
        hue, saturation, value, _alpha = color.getHsvF()
        self._hue = max(0.0, hue)
        self._saturation = saturation
        self._brightness = value
        self.update()

    # --- geometry ------------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(SQUARE.width(), SQUARE.height() + PICKER_GAP + STRIP_HEIGHT)

    def _square_rect(self) -> QRect:
        return QRect(0, 0, SQUARE.width(), SQUARE.height())

    def _strip_rect(self) -> QRect:
        return QRect(0, SQUARE.height() + PICKER_GAP, SQUARE.width(), STRIP_HEIGHT)

    # --- painting ------------------------------------------------------------------------

    def _square_image(self) -> QtGui.QImage:
        if self._square_cache is not None and abs(self._cached_hue - self._hue) < 1e-4:
            return self._square_cache
        box = self._square_rect()
        image = QtGui.QImage(box.width(), box.height(), QtGui.QImage.Format.Format_RGB32)
        width = max(1, box.width() - 1)
        height = max(1, box.height() - 1)
        for y in range(box.height()):
            value = 1.0 - y / height
            for x in range(box.width()):
                image.setPixelColor(
                    x,
                    y,
                    QtGui.QColor.fromHsvF(max(0.0, min(0.999, self._hue)), x / width, value),
                )
        self._square_cache = image
        self._cached_hue = self._hue
        return image

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        radius = float(theme.radius_px("md"))

        square = self._square_rect()
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(square), radius, radius)
        painter.save()
        painter.setClipPath(path)
        painter.drawImage(square, self._square_image())
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.drawPath(path)

        strip = self._strip_rect()
        gradient = QtGui.QLinearGradient(
            QtCore.QPointF(strip.left(), 0.0), QtCore.QPointF(strip.right(), 0.0)
        )
        for step in range(7):
            gradient.setColorAt(step / 6.0, QtGui.QColor.fromHsvF(min(0.999, step / 6.0), 1.0, 1.0))
        fill_round_rect(painter, strip, STRIP_HEIGHT / 2.0, QtGui.QBrush(gradient), theme.color("border"))

        self._paint_knob(painter, self._square_knob())
        self._paint_knob(painter, self._strip_knob())
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), radius)
        painter.end()

    def _paint_knob(self, painter: QtGui.QPainter, centre: QPoint) -> None:
        box = QtCore.QRectF(0, 0, KNOB, KNOB)
        box.moveCenter(QtCore.QPointF(centre))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 120), 3.0))
        painter.drawEllipse(box)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2.0))
        painter.drawEllipse(box)

    def _square_knob(self) -> QPoint:
        box = self._square_rect()
        x = box.left() + round(self._saturation * (box.width() - 1))
        y = box.top() + round((1.0 - self._brightness) * (box.height() - 1))
        return QPoint(int(x), int(y))

    def _strip_knob(self) -> QPoint:
        box = self._strip_rect()
        x = box.left() + round(self._hue * (box.width() - 1))
        return QPoint(int(x), box.center().y())

    # --- the drag ------------------------------------------------------------------------

    def _take(self, where: str, point: QPoint) -> None:
        if where == "square":
            box = self._square_rect()
            self._saturation = _clamp((point.x() - box.left()) / max(1, box.width() - 1))
            self._brightness = 1.0 - _clamp((point.y() - box.top()) / max(1, box.height() - 1))
        else:
            box = self._strip_rect()
            self._hue = _clamp((point.x() - box.left()) / max(1, box.width() - 1))
        self.update()
        self.moved.emit(_triple(self.color))

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            event.ignore()
            return
        point = _point(event)
        self._dragging = "strip" if point.y() >= self._strip_rect().top() else "square"
        self._take(self._dragging, point)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self._take(self._dragging, _point(event))

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if not self._dragging:
            return
        self._take(self._dragging, _point(event))
        self._dragging = ""
        self.picked.emit(_triple(self.color))

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        step = KEY_STEP * (10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
        if key == Qt.Key.Key_Left:
            self._saturation = _clamp(self._saturation - step)
        elif key == Qt.Key.Key_Right:
            self._saturation = _clamp(self._saturation + step)
        elif key == Qt.Key.Key_Up:
            self._brightness = _clamp(self._brightness + step)
        elif key == Qt.Key.Key_Down:
            self._brightness = _clamp(self._brightness - step)
        elif key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            self._hue = _clamp(self._hue + (step if key == Qt.Key.Key_PageUp else -step))
        else:
            super().keyPressEvent(event)
            return
        self.update()
        self.picked.emit(_triple(self.color))
        event.accept()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _point(event: QtGui.QMouseEvent) -> QPoint:
    return event.position().toPoint() if hasattr(event, "position") else event.pos()


class ColorEditor(ValueEditor):
    """A `color` field: the swatch that picks, then the triple that is stored."""

    def __init__(
        self,
        value: str | None = None,
        field: FieldSchema | None = None,
        hint: bool = True,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "255,128,0",
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[str | None], None] | None = None,
        on_error_change: Callable[[str | None], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__("color-editor", size=size, error_message=error_message, parent=parent)
        self._hint = bool(hint)

        self.use_session(
            ValueSession(
                value,
                format=lambda stored: stored if stored else "",
                parse=parse_color_input,
                error=error,
                invalid=invalid,
                parent=self,
            )
        )
        self._build()

        self.set_placeholder(placeholder)
        self.set_field(field)
        self.set_invalid(invalid)
        self.set_readonly(readonly)
        self.set_disabled(disabled)
        self.connect_callbacks(on_value_change, on_error_change)
        self._refresh()

    # --- the parts -----------------------------------------------------------------------

    def _build(self) -> None:
        row = QtWidgets.QWidget(self)
        row.setObjectName("color-editor-row")
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(VALUE_EDITOR_GAP)

        self._swatch = ColorSwatch(size=self.size, parent=row)
        self._swatch.setObjectName("color-editor-swatch")
        self._swatch.clicked.connect(self.toggle)
        line.addWidget(self._swatch, 0)

        self._input = _TripleInput(placeholder=self.placeholder, size=self.size, parent=row)
        self._input.setObjectName("color-editor-input")
        self._session.bind(self._input)
        line.addWidget(self._input, 1)
        self.add_control(row)

        self._note = EditorNote("", parent=self)
        self._note.setObjectName("color-editor-note")
        self.add_control(self._note)

        panel = QtWidgets.QWidget()
        panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        column = QtWidgets.QVBoxLayout(panel)
        column.setContentsMargins(PICKER_PAD, PICKER_PAD, PICKER_PAD, PICKER_PAD)
        column.setSpacing(0)
        self._picker = ColorPicker(parent=panel)
        self._picker.setObjectName("color-editor-picker")
        self._picker.moved.connect(self._session.set_draft)
        self._picker.picked.connect(self._session.apply)
        column.addWidget(self._picker)
        self._popover = Popover(self._swatch, panel, side="bottom", align="start")

        self._session.draft_changed.connect(lambda _draft: self._refresh())
        self._session.committed.connect(lambda _value: self._refresh())

    # --- the picker ----------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the picker is showing."""
        return self._popover.is_open

    def set_open(self, value: bool) -> None:
        """Open or close the picker. Readonly and disabled never open."""
        wanted = bool(value) and not self.readonly and self.isEnabled()
        if wanted == self._popover.is_open:
            return
        if wanted:
            preview = self.preview
            if preview is not None:
                self._picker.set_color(preview)
            self._popover.open()
            self._popover.raise_()
            self._popover.activateWindow()
            self._picker.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self._popover.close()

    def toggle(self) -> None:
        """A press on the swatch."""
        self.set_open(not self.is_open)

    # --- props ---------------------------------------------------------------------------

    @property
    def value(self) -> str | None:
        """The stored string: decimal `r,g,b`, or the pipeline-step token."""
        return self._session.value

    def set_value(self, value: str | None) -> None:
        self._session.set_value(value)
        self._refresh()

    @property
    def hint(self) -> bool:
        """Explain the pipeline-step token under the control."""
        return self._hint

    def set_hint(self, value: bool) -> None:
        self._hint = bool(value)
        self._refresh()

    @property
    def preview(self) -> QtGui.QColor | None:
        """The colour the draft reads as, so a typed hex shows before it is committed."""
        result = parse_color_input(str(self._session.draft))
        value = getattr(result, "value", None)
        if value is None or value == COLOR_SENTINEL:
            return None
        return _color_of(parse_bg_color(str(value)))

    @property
    def sentinel(self) -> bool:
        """True while the draft reads as the pipeline-step token."""
        result = parse_color_input(str(self._session.draft))
        return getattr(result, "value", None) == COLOR_SENTINEL

    @property
    def swatch(self) -> ColorSwatch:
        """The square that opens the picker."""
        return self._swatch

    @property
    def picker(self) -> ColorPicker:
        """The square and the strip inside the popover."""
        return self._picker

    @property
    def input(self) -> Input:
        """The triple as text, in the monospace family."""
        return self._input

    def _refresh(self) -> None:
        self._swatch.set_color(self.preview)
        self._note.set_text(SENTINEL_NOTE if self._hint and self.sentinel else "")

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        self._swatch.set_size_step(size)
        self._input.set_size(size)

    def _apply_placeholder(self, placeholder: str) -> None:
        self._input.setPlaceholderText(placeholder)
        super()._apply_placeholder(placeholder)

    def _apply_state(self) -> None:
        swatch = getattr(self, "_swatch", None)
        if swatch is None:
            return
        swatch.set_readonly(self.readonly)
        swatch.setFocusPolicy(
            Qt.FocusPolicy.NoFocus if self.readonly else Qt.FocusPolicy.StrongFocus
        )
        self._input.setReadOnly(self.readonly)
        self._input.set_invalid(self.reads_invalid)
        fade_disabled(self._input)
        name = self.field_name()
        swatch.setAccessibleName(f"{name} colour" if name else "Colour")
        if self.readonly or not self.isEnabled():
            self.set_open(False)
