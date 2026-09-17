"""A `text` field, as an input or a textarea.

Ported from `packages/react/src/registry/sg/components/text-editor.tsx`.

    editor = TextEditor(value="Plate delivered.")
    editor.committed.connect(write)

Both ends of the value are stripped on write and an empty string is stored as null, so clearing the
input and clearing the field are the same act (field_types/text).
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtWidgets

from sg_widgets_core.edit import parse_text_input
from sg_widgets_core.schema import FieldSchema

from ..primitives.input import Input, Textarea
from .value_editor import ValueEditor, ValueSession, fade_disabled, set_control_size

__all__ = ["TEXT_EDITOR_ROWS", "TextEditor"]

#: `rows` of `text-editor.tsx`, in lines of the textarea.
TEXT_EDITOR_ROWS = 3

#: What the padding of a textarea costs over its lines.
_ROW_PAD = 16


class TextEditor(ValueEditor):
    """A `text` field.

    `multiline` draws a textarea instead of a single-line input, and a newline is then what Enter
    means, so the commit is the blur alone. Newlines survive a one-line field either way.
    """

    def __init__(
        self,
        value: str | None = None,
        field: FieldSchema | None = None,
        multiline: bool = False,
        rows: int = TEXT_EDITOR_ROWS,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "",
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[str | None], None] | None = None,
        on_error_change: Callable[[str | None], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__("text-editor", size=size, error_message=error_message, parent=parent)
        self._multiline = bool(multiline)
        self._rows = max(1, int(rows))
        self._control: QtWidgets.QWidget | None = None

        self.use_session(
            ValueSession(
                value,
                format=lambda stored: "" if stored is None else str(stored),
                parse=parse_text_input,
                # A newline is what Enter means in a textarea.
                commit_on_enter=not self._multiline,
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

    # --- the control ---------------------------------------------------------------------

    def _build(self) -> None:
        old = self._control
        made: QtWidgets.QWidget
        if self._multiline:
            made = Textarea(placeholder=self.placeholder, size=self.size, parent=self)
            made.set_floor_height(self._text_height())
        else:
            made = Input(placeholder=self.placeholder, size=self.size, parent=self)
        made.setObjectName("text-editor-input")
        self._control = self.add_control(made)
        self._session.bind(made)
        if old is not None:
            self._session.unbind(old)
            old.setParent(None)
            old.deleteLater()
        self._apply_state()

    def _text_height(self) -> int:
        return max(64, self._rows * self.fontMetrics().lineSpacing() + _ROW_PAD)

    @property
    def control(self) -> QtWidgets.QWidget | None:
        """The input or the textarea the draft lives in."""
        return self._control

    # --- props ---------------------------------------------------------------------------

    @property
    def value(self) -> str | None:
        """The stored string. There is no empty string in the store (field_types/text)."""
        return self._session.value

    def set_value(self, value: str | None) -> None:
        self._session.set_value(value)

    @property
    def multiline(self) -> bool:
        """A textarea instead of a single-line input."""
        return self._multiline

    def set_multiline(self, value: bool) -> None:
        value = bool(value)
        if value == self._multiline:
            return
        self._multiline = value
        self._session.set_commit_on_enter(not value)
        self._build()

    @property
    def rows(self) -> int:
        """Rows of the textarea."""
        return self._rows

    def set_rows(self, value: int) -> None:
        self._rows = max(1, int(value))
        if self._multiline and self._control is not None:
            self._control.set_floor_height(self._text_height())

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        set_control_size(self._control, size)
        if self._multiline and self._control is not None:
            self._control.set_floor_height(self._text_height())

    def _apply_placeholder(self, placeholder: str) -> None:
        if self._control is not None:
            self._control.setPlaceholderText(placeholder)
        super()._apply_placeholder(placeholder)

    def _apply_state(self) -> None:
        if self._control is None:
            return
        self._control.setReadOnly(self.readonly)
        self._control.set_invalid(self.reads_invalid)
        fade_disabled(self._control)
        name = self.field_name()
        if name:
            self._control.setAccessibleName(name)
