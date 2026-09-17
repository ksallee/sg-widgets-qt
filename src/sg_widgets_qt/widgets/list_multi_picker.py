"""Several values of a `list` field, picked from the set its schema declares.

Ported from `packages/react/src/registry/sg/components/list-multi-picker.tsx` and its Svelte
twin. The vocabulary is the field's `valid_values`, byte for byte: a value outside it is a 400
and the comparison is case-sensitive (field_types/list). With a project id the field's hidden
values are subtracted, which REST does not do on write (probe 009).

The set is fixed and read once, so there is no search row unless a caller asks for one. The
control is the base's summary trigger, and a chosen value is a plain chip.

    picker = ListMultiPicker(field=schema.field("Shot", "sg_shot_type"), value=["VFX"])
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtWidgets
from qtpy.QtCore import Signal

from sg_widgets_core.picker import PICKER_SUMMARIES
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.state import NO_ROWS_LABEL

from ..primitives.badge import Chip
from .list_picker import LIST_ROW_TYPE, ListOption, ListPicker
from .picker_control import PICKER_CHIP

__all__ = ["LIST_ROW_TYPE", "ListMultiPicker"]


class ListMultiPicker(ListPicker):
    """Several values of a `list` field, picked from the set its schema declares.

    Every row carries a checkbox, a pick keeps the list open, and each chosen value is a plain
    chip with a cross while the picker is interactive.
    """

    #: The chosen values, in the order they were ticked.
    value_changed = Signal(object)

    MULTIPLE = True

    def __init__(
        self,
        value: Sequence[str] = (),
        field: FieldSchema | None = None,
        project_id: int | None = None,
        options: Sequence[ListOption] | None = None,
        summary: str = "ellipsis",
        max: int = 0,
        slot: str = "list-multi-picker",
        picker: str = "list",
        placeholder: str = "Select values",
        empty_label: str = NO_ROWS_LABEL,
        clear_label: str = "Clear the values",
        trigger_label: str = "Show the values",
        **props: Any,
    ) -> None:
        self._summary = summary if summary in PICKER_SUMMARIES else "ellipsis"
        self._max = int(max)
        super().__init__(
            value=list(value),
            field=field,
            project_id=project_id,
            options=options,
            slot=slot,
            picker=picker,
            placeholder=placeholder,
            empty_label=empty_label,
            clear_label=clear_label,
            trigger_label=trigger_label,
            **props,
        )

    def _control_options(self) -> dict[str, Any]:
        return {
            "chip_row": True,
            "summary": self._summary,
            "inline": self._summary == "chips",
            "max": self._max,
            "overflow_label": f"Show all {len(self._keys())} values",
        }

    def _refresh(self) -> None:
        super()._refresh()
        self._control.set_overflow_label(f"Show all {len(self._keys())} values")

    # --- the value --------------------------------------------------------------------------

    @property
    def value(self) -> list[str]:
        """The chosen values, each one of the field's valid values (field_types/list)."""
        return list(self._value or [])

    def set_value(self, value: Sequence[str]) -> None:
        self._value = list(value)
        self._refresh()

    def _keys(self) -> list[str]:
        return list(self._value or [])

    def _rows_for(self) -> list[ListOption]:
        """The options, then every chosen value the offered set does not carry (probe 009)."""
        rows = self.options
        held = {option.code for option in rows}
        for code in self._keys():
            if code not in held:
                held.add(code)
                rows = [*rows, ListOption(code=code, label=code)]
        return rows

    def _emit(self, value: Sequence[str]) -> None:
        self._value = list(value)
        self._refresh()
        self.set_error(None)
        if self._on_value_change is not None:
            self._on_value_change(list(self._value))
        self.value_changed.emit(list(self._value))

    def _clear(self) -> None:
        self._emit([])

    def _on_selected(self, keys: list) -> None:
        self._emit([str(key) for key in keys])

    def _on_remove_at(self, index: int) -> None:
        held = self._keys()
        if not 0 <= index < len(held):
            return
        dropped = held[index]
        self._emit([code for code in held if code != dropped])

    # --- the chip ---------------------------------------------------------------------------

    def _chip_for(self, index: int) -> QtWidgets.QWidget | None:
        held = self._keys()
        if not 0 <= index < len(held):
            return None
        code = held[index]
        if self._value_chip is not None:
            return self._value_chip(code)
        interactive = not self._control.readonly and not self._control.disabled
        chip = Chip(
            self.label_of(code),
            size=PICKER_CHIP[self._size],
            removable=interactive,
            parent=self._control,
        )
        chip.setToolTip(self.label_of(code))
        return chip

    # --- props ------------------------------------------------------------------------------

    @property
    def summary(self) -> str:
        """What the control shows for the selection."""
        return self._summary

    def set_summary(self, value: str) -> None:
        self._summary = value if value in PICKER_SUMMARIES else "ellipsis"
        self._control.set_summary(self._summary)
        self._control.set_inline(self._summary == "chips")
        self._control.rebuild_chips()

    @property
    def max(self) -> int:
        """Chips drawn before the rest becomes `+n`. Zero lets the row fit what it can."""
        return self._max

    def set_max(self, value: int) -> None:
        self._max = int(value)
        self._control.set_max(self._max)

    def set_value_chip(self, value: Callable[[str], QtWidgets.QWidget | None] | None) -> None:
        self._value_chip = value
        self._control.rebuild_chips()
