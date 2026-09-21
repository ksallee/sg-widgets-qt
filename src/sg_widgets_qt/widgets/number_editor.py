"""The numeric family, as one number field.

Ported from `packages/react/src/registry/sg/components/number-editor.tsx` and its Svelte twin.

    editor = NumberEditor(value=480, data_type="duration", hint=True)
    editor.committed.connect(write)

One control covers six data types because they differ only in what they accept: a `number`, a
`percent` and a `timecode` take whole numbers, a `float` is rounded to six decimals on write, a
`duration` is minutes, and a `timecode` is milliseconds. Nothing is clamped server-side, so the
bounds here are the client's (sg-groundtruth `findings/field_types/*`).

The arithmetic is core's, so this and the two web halves land on the same number. The steppers, the
hold that repeats and the scrub are written here against the state model the React half gets from
Base UI's NumberField.

`inline` is the form a row of a table or a filter takes: the width the type needs, the steppers
inside the input rather than beside it, and nothing under the control.
"""
from __future__ import annotations

from typing import Any, Callable

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, QObject, Qt, QTimer, Signal

from sg_widgets_core.edit import (
    NumberShape,
    NumberStepsOptions,
    StepOptions,
    is_parse_error,
    number_draft,
    number_steps,
    number_wire,
    parse_number_input,
    step_number,
    stored_number,
)
from sg_widgets_core.schema import FieldSchema

from ..primitives.base import CONTROL_HEIGHT, ThemedWidget
from ..primitives.button import Button
from ..primitives.input_group import IconButton, InputGroup, InputGroupInput
from ..theme import theme_of
from .value_editor import (
    VALUE_EDITOR_GAP,
    EditorNote,
    ValueEditor,
    ValueSession,
    fade_disabled,
)

__all__ = ["INLINE_WIDTH", "NUMBER_DATA_TYPES", "NumberEditor"]

#: The data types this control edits.
NUMBER_DATA_TYPES: tuple[str, ...] = (
    "number",
    "float",
    "percent",
    "duration",
    "timecode",
    "currency",
)

#: The hold before a pressed stepper repeats, and the gap between repeats.
HOLD_DELAY = 400
HOLD_TICK = 60

#: Steps taken at once by Shift and by Page Up or Page Down.
SHIFT_STEPS = 10
PAGE_STEPS = 100

#: `STEPPER` of `number-editor.tsx`: `size-8` / `size-9` / `size-10`, one step over the control
#: the pair steps, drawn as the square icon button of the same height.
STEPPER_SIZE: dict[str, str] = {"sm": "icon", "md": "icon-lg", "lg": "icon-xl"}

#: The comfortable width of each numeric type in the row form: eight characters of number,
#: eleven of timecode.
INLINE_WIDTH: dict[str, int] = {
    "number": 96,
    "float": 96,
    "percent": 96,
    "currency": 96,
    "duration": 96,
    "timecode": 112,
}

#: The tiny pair the row form puts inside the input: `h-3.5 w-5` with a `size-3` glyph.
INLINE_STEPPER = 14
INLINE_STEPPER_WIDTH = 20
INLINE_GLYPH = 12


class _NumberInput(InputGroupInput):
    """The caret of a number field: the theme's family with tabular figures, rule 6."""

    def _apply_theme(self) -> None:
        super()._apply_theme()
        self.setFont(theme_of(self).font(14 if self._size != "sm" else 12, tabular=True))

    def set_size(self, value: str) -> None:
        """Take a rung of the control ladder, which is what the type step follows."""
        self._size = value
        self._apply_theme()


class _Hold(QObject):
    """The press that repeats: one step at once, then every 60ms after a 400ms wait."""

    stepped = Signal(int)

    def __init__(self, button: QtWidgets.QWidget, parent: QObject | None = None) -> None:
        super().__init__(parent if parent is not None else button)
        self._button = button
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._repeat)
        self._multiplier = 1
        self._held = False
        self._consumed = False
        button.installEventFilter(self)
        button.clicked.connect(self._on_clicked)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and self._button.isEnabled():
            if event.button() == Qt.MouseButton.LeftButton:
                self._multiplier = SHIFT_STEPS if _shift(event.modifiers()) else 1
                self._held = True
                self.stepped.emit(self._multiplier)
                self._timer.start(HOLD_DELAY)
        elif kind == QEvent.Type.MouseButtonRelease:
            self._timer.stop()
            self._consumed, self._held = self._held, False
        return False

    def _repeat(self) -> None:
        self.stepped.emit(self._multiplier)
        self._timer.start(HOLD_TICK)

    # A pointer press has already stepped by the time the click lands; a click with no press
    # behind it is a programmatic one and steps once.
    def _on_clicked(self) -> None:
        if self._consumed:
            self._consumed = False
            return
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        self.stepped.emit(SHIFT_STEPS if _shift(modifiers) else 1)


def _shift(modifiers: Any) -> bool:
    return bool(modifiers & Qt.KeyboardModifier.ShiftModifier)


class _ScrubArea(ThemedWidget):
    """The name over the control, which a drag across changes the value by."""

    #: One step, with the multiplier the modifiers ask for.
    scrubbed = Signal(int, int)

    #: Pixels of drag one step costs.
    PIXELS = 2

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._dragging = False
        self._travelled = 0
        self._last = 0
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    def set_text(self, value: str) -> None:
        self._text = value or ""
        self.setVisible(bool(self._text))
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(12, QtGui.QFont.Weight.Medium)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(metrics.horizontalAdvance(self._text) + 2, metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font())
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            event.ignore()
            return
        self._dragging = True
        self._travelled = 0
        self._last = _x_of(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if not self._dragging:
            return
        x = _x_of(event)
        self._travelled += x - self._last
        self._last = x
        multiplier = SHIFT_STEPS if _shift(event.modifiers()) else 1
        while abs(self._travelled) >= self.PIXELS:
            direction = 1 if self._travelled > 0 else -1
            self.scrubbed.emit(direction, multiplier)
            self._travelled -= self.PIXELS * direction

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self._dragging = False
        self._travelled = 0


def _x_of(event: QtGui.QMouseEvent) -> int:
    return int(event.position().x()) if hasattr(event, "position") else int(event.x())


class NumberEditor(ValueEditor):
    """A `number`, `float`, `percent`, `duration`, `timecode` or `currency` field."""

    def __init__(
        self,
        value: int | float | str | None = None,
        data_type: str = "number",
        field: FieldSchema | None = None,
        precision: int | None = None,
        hours_per_day: float | None = None,
        frame_rate: float | None = None,
        symbol: str = "$",
        hint: bool = False,
        inline: bool = False,
        min: int | None = None,  # noqa: A002
        max: int | None = None,  # noqa: A002
        step: float | None = None,
        scrub: bool = False,
        label: str = "",
        locale: str | None = None,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "",
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[Any], None] | None = None,
        on_error_change: Callable[[str | None], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            "number-editor", size=size, inline=inline, error_message=error_message, parent=parent
        )
        self._data_type = data_type if data_type in NUMBER_DATA_TYPES else "number"
        self._precision = precision
        self._hours_per_day = hours_per_day
        self._frame_rate = frame_rate
        self._symbol = symbol
        self._hint = bool(hint)
        self._min = min
        self._max = max
        self._step = step
        self._scrub = bool(scrub)
        self._label = label
        self._locale = locale

        self.use_session(
            ValueSession(
                value,
                format=lambda stored: number_draft(stored, self._data_type, self._shape()),
                parse=self._parse,
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
        self._scrub_area = _ScrubArea("", self)
        self._scrub_area.setObjectName("number-editor-scrub-area")
        self._scrub_area.scrubbed.connect(self._step_by)
        self._scrub_area.setVisible(False)
        self.add_control(self._scrub_area)

        self._group_row = QtWidgets.QWidget(self)
        self._group_row.setObjectName("number-editor-group")
        row = QtWidgets.QHBoxLayout(self._group_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(VALUE_EDITOR_GAP)

        self._decrement = Button(icon="minus", variant="outline", size=STEPPER_SIZE[self.size])
        self._decrement.setObjectName("number-editor-decrement")
        self._decrement.setToolTip("Decrease")
        self._decrement.setAccessibleName("Decrease")
        self._decrement.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _Hold(self._decrement, self).stepped.connect(lambda m: self._step_by(-1, m))
        row.addWidget(self._decrement)

        self._group = InputGroup(self._group_row, size=self.size)
        self._group.setObjectName("number-editor-field")
        self._input = _NumberInput(self._group, size=self.size)
        self._input.setObjectName("number-editor-input")
        self._group.set_control(self._input)
        self._session.bind(self._input)
        self._input.installEventFilter(self)
        row.addWidget(self._group, 1)

        self._prefix = self._group.add_text(self._symbol, "start")
        self._prefix.setObjectName("number-editor-affix")
        self._suffix = self._group.add_text("%", "end")
        self._suffix.setObjectName("number-editor-affix")

        self._inline_steppers = QtWidgets.QWidget(self._group)
        stack = QtWidgets.QVBoxLayout(self._inline_steppers)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)
        self._inline_up = IconButton(
            "plus",
            self._inline_steppers,
            side=INLINE_STEPPER,
            glyph=INLINE_GLYPH,
            width=INLINE_STEPPER_WIDTH,
        )
        self._inline_up.setObjectName("number-editor-increment")
        self._inline_up.setAccessibleName("Increase")
        self._inline_down = IconButton(
            "minus",
            self._inline_steppers,
            side=INLINE_STEPPER,
            glyph=INLINE_GLYPH,
            width=INLINE_STEPPER_WIDTH,
        )
        self._inline_down.setObjectName("number-editor-decrement")
        self._inline_down.setAccessibleName("Decrease")
        for button in (self._inline_up, self._inline_down):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            stack.addWidget(button)
        _Hold(self._inline_up, self).stepped.connect(lambda m: self._step_by(1, m))
        _Hold(self._inline_down, self).stepped.connect(lambda m: self._step_by(-1, m))
        self._group.add_addon(self._inline_steppers, "end")

        self._increment = Button(icon="plus", variant="outline", size=STEPPER_SIZE[self.size])
        self._increment.setObjectName("number-editor-increment")
        self._increment.setToolTip("Increase")
        self._increment.setAccessibleName("Increase")
        self._increment.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _Hold(self._increment, self).stepped.connect(lambda m: self._step_by(1, m))
        row.addWidget(self._increment)

        self.add_control(self._group_row)

        self._hint_line = EditorNote("", tabular=True, parent=self)
        self._hint_line.setObjectName("number-editor-hint")
        self.add_control(self._hint_line)

        self._session.draft_changed.connect(lambda _draft: self._refresh())
        self._session.committed.connect(lambda _value: self._refresh())

    # --- the shape -----------------------------------------------------------------------

    def _shape(self) -> NumberShape:
        limits = self._limits()
        return NumberShape(
            hours_per_day=self._hours_per_day,
            frame_rate=self._frame_rate,
            precision=self._precision,
            min=limits.min,
            max=limits.max,
            locale=self._locale,
        )

    def _limits(self) -> StepOptions:
        options = NumberStepsOptions(frame_rate=self._frame_rate)
        fallback = number_steps(self._data_type, options)
        return StepOptions(
            step=self._step if self._step is not None else fallback.step,
            min=self._min if self._min is not None else fallback.min,
            max=self._max if self._max is not None else fallback.max,
        )

    def _parse(self, draft: str) -> Any:
        result = parse_number_input(draft, self._data_type, self._shape())
        if is_parse_error(result):
            return result
        result.value = self._wire(result.value)
        return result

    def _wire(self, parsed: float | None) -> Any:
        """The wire value.

        A step lands on a float where JavaScript has one number, and every type but `float` sits in
        an integer column, so a whole value goes as a whole number (field_types/number, percent,
        duration, timecode).
        """
        value = number_wire(parsed, self._data_type)
        if self._data_type != "float" and isinstance(value, float) and value.is_integer():
            return int(value)
        return value

    # --- stepping ------------------------------------------------------------------------

    def _step_by(self, direction: int, multiplier: int = 1) -> None:
        """A step reads what is in the input, so a typed `1h 30m` steps from ninety."""
        if self.readonly or not self.isEnabled():
            return
        result = parse_number_input(self._session.draft, self._data_type, self._shape())
        if is_parse_error(result):
            return
        limits = self._limits()
        limits.multiplier = multiplier
        moved = step_number(result.value, 1 if direction > 0 else -1, limits)
        self._session.apply(self._wire(moved))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            multiplier = SHIFT_STEPS if _shift(event.modifiers()) else 1
            if key == Qt.Key.Key_Up:
                self._step_by(1, multiplier)
                return True
            if key == Qt.Key.Key_Down:
                self._step_by(-1, multiplier)
                return True
            if key == Qt.Key.Key_PageUp:
                self._step_by(1, PAGE_STEPS)
                return True
            if key == Qt.Key.Key_PageDown:
                self._step_by(-1, PAGE_STEPS)
                return True
        return super().eventFilter(watched, event)

    # --- what shows ----------------------------------------------------------------------

    def _refresh(self) -> None:
        inline = self.inline
        steppers = not self.readonly
        self._decrement.setVisible(steppers and not inline)
        self._increment.setVisible(steppers and not inline)
        self._inline_steppers.setVisible(steppers and inline)

        self._prefix.setVisible(self._data_type == "currency")
        self._prefix.set_text(self._symbol)
        self._suffix.setVisible(self._data_type == "percent")

        limits = self._limits()
        stored = stored_number(self._session.value)
        at_min = stored is not None and limits.min is not None and stored <= limits.min
        at_max = stored is not None and limits.max is not None and stored >= limits.max
        self._decrement.setEnabled(not at_min)
        self._inline_down.setEnabled(not at_min)
        self._increment.setEnabled(not at_max)
        self._inline_up.setEnabled(not at_max)

        if inline:
            self._group.setFixedWidth(INLINE_WIDTH.get(self._data_type, 96))
        else:
            self._group.setMinimumWidth(0)
            self._group.setMaximumWidth(16777215)

        self._scrub_area.set_text(self._name() if self._scrub else "")
        self._hint_line.set_text("" if inline or not self._hint else self._hint_text())

    def _name(self) -> str:
        if self._label:
            return self._label
        return self.field.display_name if self.field is not None else ""

    def _hint_text(self) -> str:
        """A duration is a whole number of minutes and the field names no unit, so the number
        that will be written is shown outright (field_types/duration)."""
        if self._data_type != "duration":
            return ""
        result = parse_number_input(self._session.draft, self._data_type, self._shape())
        if is_parse_error(result) or result.value is None:
            return ""
        minutes = result.value
        return f"{minutes} {'minute' if abs(minutes) == 1 else 'minutes'}"

    # --- props ---------------------------------------------------------------------------

    @property
    def value(self) -> Any:
        """The stored value. A float is a decimal string, the rest bare numbers."""
        return self._session.value

    def set_value(self, value: Any) -> None:
        self._session.set_value(value)
        self._refresh()

    @property
    def data_type(self) -> str:
        """Which numeric type is being edited."""
        return self._data_type

    def set_data_type(self, value: str) -> None:
        self._data_type = value if value in NUMBER_DATA_TYPES else "number"
        self._session.reset()
        self._refresh()

    @property
    def precision(self) -> int | None:
        """Decimals kept on a float. The store itself keeps six (field_types/float)."""
        return self._precision

    def set_precision(self, value: int | None) -> None:
        self._precision = value
        self._session.reset()

    @property
    def hours_per_day(self) -> float | None:
        """The site's `hours_per_day`, for the `d` unit (field_types/duration)."""
        return self._hours_per_day

    def set_hours_per_day(self, value: float | None) -> None:
        self._hours_per_day = value
        self._session.reset()

    @property
    def frame_rate(self) -> float | None:
        """Frames per second, for `HH:MM:SS:FF` and the one-frame step (field_types/timecode)."""
        return self._frame_rate

    def set_frame_rate(self, value: float | None) -> None:
        self._frame_rate = value
        self._session.reset()

    @property
    def symbol(self) -> str:
        """Shown before the value on a currency field."""
        return self._symbol

    def set_symbol(self, value: str) -> None:
        self._symbol = value
        self._refresh()

    @property
    def hint(self) -> bool:
        """Show the stored form under the control."""
        return self._hint

    def set_hint(self, value: bool) -> None:
        self._hint = bool(value)
        self._refresh()

    @property
    def min(self) -> int | None:
        return self._min

    def set_min(self, value: int | None) -> None:
        self._min = value
        self._refresh()

    @property
    def max(self) -> int | None:
        return self._max

    def set_max(self, value: int | None) -> None:
        self._max = value
        self._refresh()

    @property
    def step(self) -> float | None:
        """What one step moves. Defaults to the step the data type reads in."""
        return self._step

    def set_step(self, value: float | None) -> None:
        self._step = value

    @property
    def scrub(self) -> bool:
        """Name the control and let a drag across that name change the value."""
        return self._scrub

    def set_scrub(self, value: bool) -> None:
        self._scrub = bool(value)
        self._refresh()

    @property
    def label(self) -> str:
        """The name over a scrub area. Defaults to the field's display name."""
        return self._label

    def set_label(self, value: str) -> None:
        self._label = value
        self._refresh()

    @property
    def locale(self) -> str | None:
        """Locale the value is written in."""
        return self._locale

    def set_locale(self, value: str | None) -> None:
        self._locale = value
        self._session.reset()

    @property
    def input(self) -> QtWidgets.QLineEdit:
        """The caret the draft lives in."""
        return self._input

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        self._group.set_size_step(size)
        self._input.set_size(size)
        for stepper in (self._decrement, self._increment):
            stepper.set_size(STEPPER_SIZE[size])
        self._group.setMinimumHeight(CONTROL_HEIGHT[size])
        self._refresh()

    def _apply_placeholder(self, placeholder: str) -> None:
        self._input.setPlaceholderText(placeholder)
        super()._apply_placeholder(placeholder)

    def _apply_state(self) -> None:
        group = getattr(self, "_group", None)
        if group is None:
            return
        self._input.setReadOnly(self.readonly)
        fade_disabled(self._input)
        group.set_invalid(self.reads_invalid)
        name = self.field_name()
        if name:
            self._input.setAccessibleName(name)
        self._refresh()
