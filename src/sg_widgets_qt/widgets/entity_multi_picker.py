"""Several entities, chosen by server-side search.

Ported from `packages/react/src/registry/sg/components/entity-multi-picker.tsx` and its Svelte
twin. The same request model as the single picker: one `contains` condition per word, `or`'d
across the type's display-name fields, one search per searched type, no filtering here, and
abandoned answers dropped. The option list is the results followed by any selected row they do
not hold, so a selection is always there to be unticked.

The control is a token field while `summary` is `chips`, and a summary trigger otherwise: the
chip row then measures itself against the room it has, draws whole chips only and follows the
last one with a `+n` pill.

    picker = EntityMultiPicker(entity_types=["Asset"], context=context, summary="ellipsis")
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qtpy.QtCore import Signal

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import PICKER_SUMMARIES, PickerRow, entity_key

from .entity_picker import EntitySearchPicker

__all__ = ["EntityMultiPicker"]


class EntityMultiPicker(EntitySearchPicker):
    """Several entities, chosen by server-side search.

    Every row carries a checkbox in its indicator column, a pick keeps the list open, and `max`
    bounds the chips the control draws whatever room it has.
    """

    #: The chosen references and the rows behind them.
    value_changed = Signal(object, object)

    MULTIPLE = True

    def __init__(
        self,
        entity_types: Sequence[str] = (),
        context: Any = None,
        value: Sequence[EntityRef] = (),
        summary: str = "ellipsis",
        max: int = 0,
        placeholder: str = "Search for entities",
        **props: Any,
    ) -> None:
        self._value: list[EntityRef] = []
        super().__init__(
            entity_types=entity_types,
            context=context,
            summary=summary if summary in PICKER_SUMMARIES else "ellipsis",
            max=max,
            placeholder=placeholder,
            **props,
        )
        self.setObjectName("entity-multi-picker")
        self.set_value(value)

    @property
    def value(self) -> list[EntityRef]:
        """The chosen rows. Bare `{type, id}` members are resolved on the way in."""
        return list(self._value)

    def set_value(self, value: Sequence[EntityRef]) -> None:
        """Choose rows. Bare references are hydrated by one batched read per type."""
        self._value = list(value)
        if self._value:
            self._hydrate(self._value)
        self._refresh()

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
        """Chips drawn before the rest becomes `+n`. Zero draws what the row fits."""
        return self._control.max

    def set_max(self, value: int) -> None:
        self._control.set_max(int(value))

    # --- the value -----------------------------------------------------------------------

    def _refs(self) -> list[EntityRef]:
        return list(self._value)

    def _emit_value(self, refs: Sequence[EntityRef]) -> None:
        self._value = list(refs)
        self._refresh()
        rows = [self._row_of(ref) for ref in self._value]
        self.value_changed.emit(list(self._value), rows)

    def _rows_for(self, keys: Sequence[str]) -> list[PickerRow]:
        by_key = {entity_key(row): row for row in self._options()}
        out: list[PickerRow] = []
        for key in keys:
            found = by_key.get(key)
            if found is None:
                found = self._search.known.get(key)
            if found is not None:
                out.append(found)
        return out

    def _on_selected(self, keys: list) -> None:
        rows = self._rows_for(keys)
        self._search.remember(rows)
        self._emit_value([EntityRef(type=row.type, id=row.id, name=row.name) for row in rows])

    def _on_remove_at(self, index: int) -> None:
        if not 0 <= index < len(self._value):
            return
        dropped = self._value[index]
        self._emit_value([
            ref for ref in self._value if entity_key(ref) != entity_key(dropped)
        ])
