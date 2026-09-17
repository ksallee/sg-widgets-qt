"""A `checkbox` field, as an editable switch.

Ported from `packages/react/src/registry/sg/components/checkbox-editor.tsx`.

    editor = CheckboxEditor(value=True, labels=("Approved", "Not approved"))
    editor.committed.connect(write)

The type is two-state and never null: a row that was never touched already reads false, a written
null is a 400, and `false` is the only off state there is (field_types/checkbox). So this control
has no empty state and no clear affordance, and no draft to hold: it writes on the toggle.
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.schema import FieldSchema

from ..primitives.base import CONTROL_HEIGHT
from ..primitives.checkbox import Switch
from ..primitives.label import Label
from .value_editor import VALUE_EDITOR_GAP, ValueEditor

__all__ = ["CHECKBOX_EDITOR_LABELS", "CHECKBOX_EDITOR_SWITCH", "CheckboxEditor"]

#: The two words shown beside the switch.
CHECKBOX_EDITOR_LABELS: tuple[str, str] = ("Yes", "No")

#: `SWITCH` of `checkbox-editor.tsx`: the switch primitive carries two steps, so the third
#: reuses the larger one.
CHECKBOX_EDITOR_SWITCH: dict[str, str] = {"sm": "sm", "md": "default", "lg": "default"}


class CheckboxEditor(ValueEditor):
    """A `checkbox` field: a switch, the word for its state, and the caller's message."""

    def __init__(
        self,
        value: bool = False,
        field: FieldSchema | None = None,
        labels: tuple[str, str] = CHECKBOX_EDITOR_LABELS,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "",
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[bool], None] | None = None,
        on_error_change: Callable[[str | None], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__("checkbox-editor", size=size, error_message=error_message, parent=parent)
        self._value = value is True
        self._labels = (str(labels[0]), str(labels[1]))

        row = QtWidgets.QWidget(self)
        row.setObjectName("checkbox-editor-row")
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(VALUE_EDITOR_GAP)
        self._switch = Switch(self._value, row, size=CHECKBOX_EDITOR_SWITCH[self.size])
        self._switch.setObjectName("checkbox-editor-switch")
        self._switch.toggled.connect(self._on_toggled)
        line.addWidget(self._switch, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        # The word beside the switch is the value, not a name: plain `text-sm`.
        self._label = Label(
            self._labels[0 if self._value else 1],
            weight=QtGui.QFont.Weight.Normal,
            parent=row,
        )
        self._label.setObjectName("checkbox-editor-label")
        line.addWidget(self._label, 1)
        row.setMinimumHeight(CONTROL_HEIGHT[self.size])
        self._row = self.add_control(row)

        self.set_placeholder(placeholder)
        self.set_field(field)
        self.set_error(error)
        self.set_invalid(invalid)
        self.set_readonly(readonly)
        self.set_disabled(disabled)
        self.connect_callbacks(on_value_change, on_error_change)

    # --- the value -----------------------------------------------------------------------

    @property
    def value(self) -> bool:
        """Two-state and never null: an untouched row already reads false."""
        return self._value

    def set_value(self, value: bool) -> None:
        """Take a value without emitting."""
        self._value = value is True
        self._show(self._value)
        self._label.set_text(self._labels[0 if self._value else 1])

    def _show(self, checked: bool) -> None:
        blocked = self._switch.blockSignals(True)
        try:
            self._switch.set_checked(checked)
        finally:
            self._switch.blockSignals(blocked)

    def _on_toggled(self, checked: bool) -> None:
        # `false` is the only off state: null is unwritable on this type (field_types/checkbox).
        if self.readonly or not self.isEnabled():
            self._show(self._value)
            return
        if checked is self._value:
            return
        self._value = checked is True
        self._label.set_text(self._labels[0 if self._value else 1])
        self.set_message(None)
        self.error_changed.emit(None)
        self.committed.emit(self._value)

    def toggle(self) -> None:
        """Move the switch, as a press or a Space does."""
        self._switch.toggle()

    # --- props ---------------------------------------------------------------------------

    @property
    def labels(self) -> tuple[str, str]:
        """The word for the on state and the word for the off one."""
        return self._labels

    def set_labels(self, value: tuple[str, str]) -> None:
        self._labels = (str(value[0]), str(value[1]))
        self._label.set_text(self._labels[0 if self._value else 1])

    @property
    def switch(self) -> Switch:
        """The control the value lives on."""
        return self._switch

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        self._row.setMinimumHeight(CONTROL_HEIGHT[size])
        switch = getattr(self, "_switch", None)
        if switch is not None:
            switch.set_size(CHECKBOX_EDITOR_SWITCH[size])

    def _apply_state(self) -> None:
        switch = getattr(self, "_switch", None)
        if switch is None:
            return
        # Disabled wins over readonly: readonly keeps full contrast and drops the affordance,
        # disabled greys the control and makes it inert.
        switch.setEnabled(self.isEnabled())
        switch.setFocusPolicy(
            QtCore.Qt.FocusPolicy.NoFocus if self.readonly else QtCore.Qt.FocusPolicy.StrongFocus
        )
        switch.setCursor(
            QtCore.Qt.CursorShape.ArrowCursor
            if self.readonly
            else QtCore.Qt.CursorShape.PointingHandCursor
        )
        name = self.field_name() or self._labels[0 if self._value else 1]
        switch.setAccessibleName(name)
