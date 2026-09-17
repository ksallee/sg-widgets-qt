"""Several entity types, as a searchable combobox.

Ported from `packages/react/src/registry/sg/components/entity-type-multi-picker.tsx` and its
Svelte twin. The same derived list as the single picker, with a checkbox on every row. `allow`
and `deny` narrow the derived options rather than the read, so a caller switching sets sees the
list change without a second call. A pick keeps the list open.

    picker = EntityTypeMultiPicker(context=context, deny=["HumanUser", "ApiUser"])
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qtpy.QtCore import Signal

from sg_widgets_core.picker import PICKER_SUMMARIES

from .entity_type_picker import EntityTypePicker

__all__ = ["EntityTypeMultiPicker"]


class EntityTypeMultiPicker(EntityTypePicker):
    """Several entity types, as a searchable combobox.

    The control is a token field while `summary` is `chips`, and a summary trigger otherwise.
    """

    #: The chosen type codes, in the order they were ticked.
    value_changed = Signal(object)

    MULTIPLE = True

    def __init__(
        self,
        context: Any = None,
        value: Sequence[str] = (),
        placeholder: str = "Select entity types",
        summary: str = "ellipsis",
        max: int = 0,
        **props: Any,
    ) -> None:
        super().__init__(
            context=context,
            value=list(value),
            placeholder=placeholder,
            summary=summary if summary in PICKER_SUMMARIES else "ellipsis",
            max=max,
            **props,
        )

    # --- the value --------------------------------------------------------------------------

    @property
    def value(self) -> list[str]:
        """The chosen type codes, in the order they were ticked."""
        return list(self._value or [])

    def set_value(self, value: Sequence[str]) -> None:
        self._value = list(value)
        self._refresh()

    def _keys(self) -> list[str]:
        return list(self._value or [])

    def _on_selected(self, keys: list) -> None:
        self._emit([str(key) for key in keys])

    def _on_remove_at(self, index: int) -> None:
        held = self._keys()
        if not 0 <= index < len(held):
            return
        dropped = held[index]
        self._emit([code for code in held if code != dropped])

    def _on_clear(self) -> None:
        self._emit([])

    # --- props ------------------------------------------------------------------------------

    @property
    def summary(self) -> str:
        """What the control shows for the selection."""
        return self._control.summary

    def set_summary(self, value: str) -> None:
        wanted = value if value in PICKER_SUMMARIES else "ellipsis"
        self._control.set_summary(wanted)
        self._control.set_inline(wanted == "chips")
        self._control.rebuild_chips()

    @property
    def max(self) -> int:
        """Chips drawn before the rest becomes `+n`. Zero lets the row fit what it can."""
        return self._control.max

    def set_max(self, value: int) -> None:
        self._control.set_max(int(value))
