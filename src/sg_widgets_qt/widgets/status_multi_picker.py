"""Several statuses, picked from the codes a project offers.

Ported from `packages/react/src/registry/sg/components/status-multi-picker.tsx` and its Svelte
twin. The options are `valid_values` minus the project's `hidden_values`, read with `project_id`;
over several projects they are the intersection of those sets. REST does not enforce
`hidden_values` on write, so the subtraction is the client's job (probe 009). A selected code the
option set does not carry keeps a row of its own, labelled with the code, so a selection is never
dropped from the display.

A status list has no substring operator, so there is no server-side type-ahead over it: the
vocabulary is read once and the search box narrows it here (field_types/status_list).

A row is the shared picker row of rule 9, after its checkbox: the status glyph as the leading
mark, the display label with the matched runs bold, and the code right-aligned. The badge stays
in the control, where a status is a value rather than an option.

    picker = StatusMultiPicker(context=context, entity_type="Version", project_id=70)
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qtpy import QtWidgets
from qtpy.QtCore import Signal

from sg_widgets_core.picker import PICKER_SUMMARIES
from sg_widgets_core.state import NO_MATCH_LABEL

from .list_multi_picker import ListMultiPicker
from .list_picker import ListPicker
from .picker_control import PICKER_CHIP
from .status_badge import STATUS_BADGE_VARIANT_VALUES, StatusBadge
from .status_picker import StatusPicker

__all__ = ["StatusMultiPicker"]


class _StatusList(ListMultiPicker):
    """The fixed-set multi picker under this one, saying `statuses` where it says `values`."""

    def _refresh(self) -> None:
        super()._refresh()
        self._control.set_overflow_label(f"Show all {len(self._keys())} statuses")


class StatusMultiPicker(StatusPicker):
    """Several statuses, picked from the codes a project offers.

    Every row carries a checkbox, a pick keeps the list open, and each chosen code is a status
    badge with a cross while the picker is interactive.
    """

    #: The selected codes, in the order they were ticked.
    value_changed = Signal(object)

    MULTIPLE = True
    SLOT = "status-multi-picker"

    def __init__(
        self,
        context: Any = None,
        entity_type: str = "",
        value: Sequence[str] = (),
        placeholder: str = "Select statuses",
        search_placeholder: str = "Search statuses…",
        empty_label: str = NO_MATCH_LABEL,
        summary: str = "ellipsis",
        badge: str = "both",
        max: int = 0,
        **props: Any,
    ) -> None:
        self._summary = summary if summary in PICKER_SUMMARIES else "ellipsis"
        self._badge = badge if badge in STATUS_BADGE_VARIANT_VALUES else "both"
        self._max = int(max)
        self._search_placeholder = search_placeholder
        super().__init__(
            context=context,
            entity_type=entity_type,
            value=list(value),
            placeholder=placeholder,
            empty_label=empty_label,
            **props,
        )

    def _build_list(self, **props: Any) -> ListPicker:
        return _StatusList(
            slot=self.SLOT,
            picker="status",
            size=self._size,
            loading=True,
            searchable=True,
            search_placeholder=self._search_placeholder,
            summary=self._summary,
            # A bare icon is half a badge wide, so a fixed cap fits twice as many.
            max=self._max * 2 if self._badge == "icon" else self._max,
            clear_label="Clear the statuses",
            trigger_label="Show the statuses",
            mark=lambda option: "",
            value_chip=self._badge_for,
            parent=self,
            **props,
        )

    # --- the value --------------------------------------------------------------------------

    @property
    def value(self) -> list[str]:
        """The selected codes."""
        return list(self._value or [])

    def set_value(self, value: Sequence[str]) -> None:
        self._set_value(list(value), emit=False)

    def _held(self) -> list[str]:
        return list(self._value or [])

    def _drop_missing(self) -> None:
        """A selected code outside the option set keeps its own row, so nothing is dropped."""
        self._seen = ",".join(option.code for option in self._load.options)

    # --- the badge --------------------------------------------------------------------------

    def _badge_for(self, code: str) -> QtWidgets.QWidget | None:
        if not code:
            return None
        return StatusBadge(
            code=code,
            status=self._load.statuses.get(code),
            field=self._load.field,
            variant=self._badge,
            size=PICKER_CHIP[self._size],
            site_url=self.site_url,
            removable=self._interactive(),
            remove_label=f"Remove {self.label_of(code)}",
        )

    # --- props --------------------------------------------------------------------------------

    @property
    def summary(self) -> str:
        """What the control shows for the selection."""
        return self._summary

    def set_summary(self, value: str) -> None:
        self._summary = value if value in PICKER_SUMMARIES else "ellipsis"
        self._list.set_summary(self._summary)

    @property
    def badge(self) -> str:
        """What one selected status is drawn as. Orthogonal to how many the control shows."""
        return self._badge

    def set_badge(self, value: str) -> None:
        self._badge = value if value in STATUS_BADGE_VARIANT_VALUES else "both"
        self._list.set_max(self._max * 2 if self._badge == "icon" else self._max)
        self._list.control.rebuild_chips()

    @property
    def max(self) -> int:
        """Badges drawn before the rest becomes `+n`. Zero lets the row fit what it can."""
        return self._max

    def set_max(self, value: int) -> None:
        self._max = int(value)
        self._list.set_max(self._max * 2 if self._badge == "icon" else self._max)

    @property
    def search_placeholder(self) -> str:
        """Placeholder of the search box."""
        return self._list.search_placeholder

    def set_search_placeholder(self, value: str) -> None:
        self._search_placeholder = value
        self._list.set_search_placeholder(value)
