"""The session every leaf value editor runs on, and the box it stands in.

Ported from `packages/react/src/registry/sg/components/value-editor.tsx`. Text, number, url,
colour, date and date-time differ in what they parse, what they write back into their control, and
what sits beside it. Everything else is the same in all six and lives here: the draft, the commit
on blur and on Enter, the Escape that restores, the parse error and the message it becomes, and the
invalid reading the control wears.

    class RangeEditor(ValueEditor):
        def __init__(self, value=None, parent=None):
            super().__init__("range-editor", parent=parent)
            self.use_session(ValueSession(value, format=str, parse=parse_range, parent=self))
            field = Input(placeholder="1001-1120", parent=self)
            self._session.bind(field)
            self.add_control(field)

The checkbox editor is not one of them: it has no draft, so it writes on the toggle. It still
stands in this box, for the error line and the states.
"""
from __future__ import annotations

from typing import Any, Callable

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, QObject, Qt, Signal

from sg_widgets_core.edit import ParseResult, ParseValue, is_parse_error
from sg_widgets_core.schema import FieldSchema

from ..primitives.base import CONTROL_HEIGHT, ThemedWidget, retheme
from ..theme import theme_of, watch_theme, with_alpha
from .field_error import FieldError

__all__ = [
    "NOTE_SIZE",
    "VALUE_EDITOR_GAP",
    "EditorNote",
    "ValueEditor",
    "ValueSession",
    "disabled_ink",
    "fade_disabled",
    "set_control_size",
]

#: `gap-2` of `VALUE_EDITOR_ROOT`: between the control and the line under it.
VALUE_EDITOR_GAP = 8

#: `text-xs` of every note an editor puts under its control, rule 6's metadata step.
NOTE_SIZE = 12

#: The keys a session answers.
_ENTER_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)


def _default_same(next_value: Any, current: Any) -> bool:
    """Whether a value is the stored one. `Object.is` with Python's own equality behind it."""
    if next_value is current:
        return True
    try:
        return bool(next_value == current)
    except Exception:
        return False


def _text_of(widget: QtWidgets.QWidget) -> str:
    reader = getattr(widget, "toPlainText", None)
    if callable(reader):
        return str(reader())
    reader = getattr(widget, "text", None)
    return str(reader()) if callable(reader) else ""


#: Where the inert ink rule starts inside a control's own stylesheet.
_FADE_MARK = "/* inert ink */"


def disabled_ink(theme: object) -> str:
    """Rule 5's 50% foreground, as a stylesheet colour."""
    color = with_alpha(theme.foreground, 0.5)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def fade_disabled(widget: QtWidgets.QWidget | None) -> None:
    """Grey the ink Qt draws itself while a control is inert.

    A painted leaf fades with the painter's opacity, but the text inside a `QLineEdit` is Qt's own,
    and the root's generated stylesheet sets its colour, which beats any palette. The rule goes on
    the control itself, where it is the more specific one.
    """
    if widget is None:
        return
    rule = (
        f"{_FADE_MARK} QLineEdit:disabled, QPlainTextEdit:disabled "
        f"{{ color: {disabled_ink(theme_of(widget))}; }}"
    )
    base = widget.styleSheet().split(_FADE_MARK)[0]
    widget.setStyleSheet(base + rule)


def set_control_size(widget: QtWidgets.QWidget | None, size: str) -> None:
    """Hand a size step to whichever spelling a control answers to."""
    if widget is None:
        return
    for name in ("set_size", "set_size_step"):
        setter = getattr(widget, name, None)
        if callable(setter):
            setter(size)
            return


def _set_text(widget: QtWidgets.QWidget, text: str) -> None:
    """Write a draft into a field without moving a caret that is already where it belongs."""
    if _text_of(widget) == text:
        return
    blocked = widget.blockSignals(True)
    try:
        setter = getattr(widget, "setPlainText", None)
        if callable(setter):
            setter(text)
        else:
            widget.setText(text)
    finally:
        widget.blockSignals(blocked)


class EditorNote(ThemedWidget):
    """One 12px line of `muted_foreground` under a control: a hint, a zone, a note.

    It wraps to the width it is given and takes no room at all while it says nothing.
    """

    def __init__(
        self,
        text: str = "",
        tabular: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._tabular = bool(tabular)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        self.setMinimumWidth(0)
        self.setVisible(bool(text))

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value or ""
        self.setVisible(bool(self._text))
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(NOTE_SIZE, tabular=self._tabular)

    def _flags(self) -> int:
        return int(
            QtCore.Qt.AlignmentFlag.AlignTop
            | QtCore.Qt.AlignmentFlag.AlignLeft
            | QtCore.Qt.TextFlag.TextWordWrap
        )

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        if not self._text:
            return QtCore.QSize(0, 0)
        metrics = QtGui.QFontMetrics(self._font())
        box = metrics.boundingRect(
            QtCore.QRect(0, 0, max(80, self.width()), 10000), self._flags(), self._text
        )
        return QtCore.QSize(0, max(metrics.height(), box.height()))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, 0)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.updateGeometry()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._text:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font())
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(self.rect(), self._flags(), self._text)
        painter.end()


class ValueSession(QObject):
    """The draft, the commit and the error one control runs on.

    `format` turns the stored value into the draft the control shows and `parse` turns it back, or
    names the reason it was refused. A draft is a string, or a map of them where an editor holds
    two fields.
    """

    #: A committed value that differs from the stored one.
    committed = Signal(object)
    #: The parse error appeared or cleared.
    error_changed = Signal(object)
    #: The caller's message, the parse error, or nothing.
    message_changed = Signal(object)
    #: The draft the control shows.
    draft_changed = Signal(object)
    #: After Enter, with whether the parse held.
    entered = Signal(bool)
    #: After Escape.
    escaped = Signal()

    def __init__(
        self,
        value: Any = None,
        format: Callable[[Any], Any] | None = None,  # noqa: A002
        parse: Callable[[Any], ParseResult] | None = None,
        same: Callable[[Any, Any], bool] | None = None,
        commit_on_enter: bool = True,
        error: str | None = None,
        invalid: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._format = format if format is not None else (lambda v: "" if v is None else str(v))
        self._parse = parse if parse is not None else (lambda draft: ParseValue(draft))
        self._same = same if same is not None else _default_same
        self._value = value
        self._draft = self._format(value)
        self._parse_error: str | None = None
        self._error = error if error else None
        self._invalid = bool(invalid)
        self._commit_on_enter = bool(commit_on_enter)
        self._editing = False
        self._bound: list[tuple[QtWidgets.QWidget, str | None]] = []

    # --- the value -----------------------------------------------------------------------

    @property
    def value(self) -> Any:
        """The stored value."""
        return self._value

    def set_value(self, value: Any) -> None:
        """Take a value from outside.

        The control is the draft's owner while it has focus, so typing is never fought by an
        incoming value; the change lands as soon as the control is left.
        """
        self._value = value
        if not self._editing:
            self.set_draft(self._format(value))

    # --- the draft -----------------------------------------------------------------------

    @property
    def draft(self) -> Any:
        """What the control shows."""
        return self._draft

    def set_draft(self, draft: Any) -> None:
        """Write a draft into the session and into every field bound to it."""
        self._draft = draft
        self._write(draft)
        self.draft_changed.emit(draft)

    def set_draft_part(self, key: str | None, text: str) -> None:
        """One half of a two-field draft, as a person types it."""
        if key is None:
            if self._draft == text:
                return
            self._draft = text
            self.draft_changed.emit(text)
            return
        current = dict(self._draft) if isinstance(self._draft, dict) else {}
        if current.get(key) == text:
            return
        current[key] = text
        self._draft = current
        self.draft_changed.emit(current)

    def _write(self, draft: Any) -> None:
        for widget, key in self._bound:
            try:
                if key is None:
                    _set_text(widget, draft if isinstance(draft, str) else "")
                elif isinstance(draft, dict):
                    _set_text(widget, str(draft.get(key, "")))
            except RuntimeError:  # The field went while the session still held it.
                continue

    # --- the message ---------------------------------------------------------------------

    @property
    def message(self) -> str | None:
        """The caller's message, the parse error, or nothing."""
        return self._error if self._error is not None else self._parse_error

    @property
    def invalid(self) -> bool:
        """The reading the control wears."""
        return self._invalid or self.message is not None

    @property
    def error(self) -> str | None:
        """The message the caller named."""
        return self._error

    def set_error(self, error: str | None) -> None:
        """A message from the caller, shown in place of the parse error."""
        self._error = error if error else None
        self.message_changed.emit(self.message)

    def set_invalid(self, value: bool) -> None:
        """Forced invalid state. A failed parse sets it on its own."""
        self._invalid = bool(value)
        self.message_changed.emit(self.message)

    @property
    def commit_on_enter(self) -> bool:
        """Enter commits. False where a newline is what Enter means."""
        return self._commit_on_enter

    def set_commit_on_enter(self, value: bool) -> None:
        self._commit_on_enter = bool(value)

    def _clear(self) -> None:
        self._parse_error = None
        self.error_changed.emit(None)
        self.message_changed.emit(self.message)

    # --- committing ----------------------------------------------------------------------

    def apply(self, value: Any) -> None:
        """Take a value that needs no parse: a picked colour, a picked day, a step."""
        self._clear()
        self.set_draft(self._format(value))
        if self._same(value, self._value):
            return
        self._value = value
        self.committed.emit(value)

    def commit(self, override: Any = None) -> bool:
        """Parse the draft and take it. Answers whether it parsed, so Enter knows."""
        source = self._draft if override is None else override
        if override is not None:
            self.set_draft(override)
        result = self._parse(source)
        if is_parse_error(result):
            self._parse_error = result.error
            self.error_changed.emit(result.error)
            self.message_changed.emit(self.message)
            return False
        self.apply(result.value)
        return True

    def reset(self) -> None:
        """Back to the stored value, with nothing left to report."""
        self.set_draft(self._format(self._value))
        self._clear()

    # --- the control's own handlers -------------------------------------------------------

    @property
    def editing(self) -> bool:
        """Whether the control has focus. A blur that follows a teardown reads it."""
        return self._editing

    def set_editing(self, value: bool) -> None:
        self._editing = bool(value)

    def focus_in(self) -> None:
        self._editing = True

    def focus_out(self) -> None:
        self._editing = False
        self.commit()

    def handle_key(self, event: QtGui.QKeyEvent) -> bool:
        """Answer Enter and Escape. True when the key was answered here."""
        key = event.key()
        if key in _ENTER_KEYS:
            if not self._commit_on_enter:
                return False
            committed = self.commit()
            self.entered.emit(committed)
            return True
        if key == Qt.Key.Key_Escape:
            self.reset()
            self.escaped.emit()
            return True
        return False

    def bind(self, widget: QtWidgets.QWidget, key: str | None = None) -> None:
        """Route a field's typing, focus and keys into this session.

        `key` names the half of the draft the field holds, for an editor with two of them.
        """
        self._bound.append((widget, key))
        widget.installEventFilter(self)
        if hasattr(widget, "toPlainText"):
            widget.textChanged.connect(
                lambda w=widget, k=key: self.set_draft_part(k, _text_of(w))
            )
        else:
            widget.textChanged.connect(lambda text, k=key: self.set_draft_part(k, text))
        self._write(self._draft)

    def unbind(self, widget: QtWidgets.QWidget) -> None:
        """Let a field go, for an editor that swaps its control."""
        self._bound = [pair for pair in self._bound if pair[0] is not widget]
        try:
            widget.removeEventFilter(self)
            widget.textChanged.disconnect()
        except (RuntimeError, TypeError):
            pass

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.FocusIn:
            self.focus_in()
        elif kind == QEvent.Type.FocusOut:
            # Losing focus because the control was taken off the page is not a commit.
            if isinstance(watched, QtWidgets.QWidget) and watched.isVisible():
                self.focus_out()
            else:
                self._editing = False
        elif kind == QEvent.Type.KeyPress and self.handle_key(event):
            return True
        return False


class ValueEditor(QtWidgets.QWidget):
    """The box a value editor stands in: the control and its extras, then the error line.

    It carries the editor's slot name as its object name, its size step, and, on the row form,
    a width that follows the value instead of the room it is given. Every editor in this package
    subclasses it, so `readonly`, `disabled`, `invalid`, `size` and the error line are the same
    everywhere.
    """

    #: A committed value, in the shape the API takes.
    committed = Signal(object)
    #: The parse error appeared or cleared.
    error_changed = Signal(object)

    def __init__(
        self,
        slot_name: str = "value-editor",
        size: str = "md",
        inline: bool = False,
        message: str | None = None,
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slot_name = slot_name
        self._size = size if size in CONTROL_HEIGHT else "md"
        self._inline = bool(inline)
        self._readonly = False
        self._invalid = False
        self._field: FieldSchema | None = None
        self._placeholder = ""
        self._session: ValueSession | None = None
        self.setObjectName(slot_name)

        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(VALUE_EDITOR_GAP)
        self._error = FieldError(message, error_message, self)
        self._column.addWidget(self._error)
        self._apply_width()
        watch_theme(self, lambda _theme: self._apply_state())

    # --- the parts -----------------------------------------------------------------------

    def add_control(self, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """Put a control, or a row of them, above the error line."""
        widget.setParent(self)
        self._column.insertWidget(self._column.count() - 1, widget)
        return widget

    def add_row(self, layout: QtWidgets.QLayout) -> QtWidgets.QLayout:
        """Put a layout of controls above the error line."""
        self._column.insertLayout(self._column.count() - 1, layout)
        return layout

    @property
    def error_line(self) -> FieldError:
        """The line under the control."""
        return self._error

    @property
    def session(self) -> ValueSession | None:
        """The session the control runs on, where the editor has one."""
        return self._session

    def use_session(self, session: ValueSession) -> None:
        """Hang the box off a session: its message, its error and its committed value."""
        self._session = session
        session.message_changed.connect(self._error.set_message)
        session.message_changed.connect(lambda _message: self._apply_state())
        session.error_changed.connect(self.error_changed.emit)
        session.committed.connect(self.committed.emit)
        self._error.set_message(session.message)
        self._apply_state()

    def connect_callbacks(
        self,
        on_value_change: Callable[[Any], None] | None = None,
        on_error_change: Callable[[Any], None] | None = None,
    ) -> None:
        """Wire the two callbacks upstream takes as props to the signals they became."""
        if on_value_change is not None:
            self.committed.connect(on_value_change)
        if on_error_change is not None:
            self.error_changed.connect(on_error_change)

    # --- props ---------------------------------------------------------------------------

    @property
    def slot_name(self) -> str:
        """The editor's own slot name, which is its object name."""
        return self._slot_name

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the rung of the control ladder the editor stands on."""
        return self._size

    def set_size(self, value: str) -> None:
        value = value if value in CONTROL_HEIGHT else "md"
        if value == self._size:
            return
        self._size = value
        self._apply_size(value)
        self._apply_width()
        self.updateGeometry()

    @property
    def inline(self) -> bool:
        """The row form: the control takes the width of its value."""
        return self._inline

    def set_inline(self, value: bool) -> None:
        value = bool(value)
        if value == self._inline:
            return
        self._inline = value
        self._apply_width()
        self._apply_size(self._size)
        self.updateGeometry()

    @property
    def message(self) -> str | None:
        """The line under the control, or None when there is nothing to say."""
        return self._error.message

    def set_message(self, value: str | None) -> None:
        self._error.set_message(value)

    def set_error_message(self, renderer: Callable[[str], QtWidgets.QWidget] | None) -> None:
        """Draw the message some other way than the line under the control."""
        self._error.set_error_message(renderer)

    @property
    def error(self) -> str | None:
        """A message from the caller, shown in place of the parse error."""
        return self._session.error if self._session is not None else self._error.message

    def set_error(self, value: str | None) -> None:
        if self._session is not None:
            self._session.set_error(value)
        else:
            self._error.set_message(value)
            self._apply_state()

    @property
    def invalid(self) -> bool:
        """Forced invalid state. A failed parse sets it on its own."""
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        if self._session is not None:
            self._session.set_invalid(self._invalid)
        self._apply_state()

    @property
    def reads_invalid(self) -> bool:
        """The reading the control wears: forced, or a message standing under it."""
        if self._session is not None:
            return self._session.invalid
        return self._invalid or self._error.message is not None

    @property
    def readonly(self) -> bool:
        """Full contrast, and no affordances."""
        return self._readonly

    def set_readonly(self, value: bool) -> None:
        self._readonly = bool(value)
        self._apply_state()

    @property
    def disabled(self) -> bool:
        """Inert, at half opacity."""
        return not self.isEnabled()

    def set_disabled(self, value: bool) -> None:
        self.setEnabled(not bool(value))
        self._apply_state()

    @property
    def field(self) -> FieldSchema | None:
        """The field schema, for the accessible name and the required flag."""
        return self._field

    def set_field(self, value: FieldSchema | None) -> None:
        self._field = value
        self._apply_field(value)

    @property
    def placeholder(self) -> str:
        return self._placeholder

    def set_placeholder(self, value: str) -> None:
        self._placeholder = value
        self._apply_placeholder(value)

    def field_name(self) -> str:
        """What to call the control: the field's display name, or the placeholder."""
        if self._field is not None and self._field.display_name:
            return self._field.display_name
        return self._placeholder

    # --- hooks a subclass fills ------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        """A size step landed. Hand it to the controls in the box."""

    def _apply_state(self) -> None:
        """A state changed. Put it on the controls in the box."""

    def _apply_field(self, field: FieldSchema | None) -> None:
        """A field schema landed."""
        self._name_control()

    def _apply_placeholder(self, placeholder: str) -> None:
        """A placeholder landed."""
        self._name_control()

    def _name_control(self) -> None:
        name = self.field_name()
        if name:
            self.setAccessibleName(name)

    def _apply_width(self) -> None:
        # The row form takes the width of its value: `Maximum` caps the box at its own hint, where
        # the default form expands into whatever room the caller gives it.
        policy = (
            QtWidgets.QSizePolicy.Policy.Maximum
            if self._inline
            else QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.setSizePolicy(policy, QtWidgets.QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    # --- the accessible reading ------------------------------------------------------------

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        kind = event.type()
        if kind == QtCore.QEvent.Type.EnabledChange:
            self._apply_state()
        elif kind == QtCore.QEvent.Type.ParentChange:
            # An editor built before it joined a themed tree read the host's theme; joining one is
            # the other moment a theme reaches it, so the box and its controls read it again.
            retheme(self)
            self._apply_state()
