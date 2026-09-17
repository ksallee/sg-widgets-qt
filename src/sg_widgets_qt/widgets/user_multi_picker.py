"""Several people, chosen by server-side search.

Ported from `packages/react/src/registry/sg/components/user-multi-picker.tsx` and its Svelte twin.
The same person preset as the single user picker, on the multi picker: checkbox rows, removable
chips, and a selection pinned into the list so it can be unticked whatever the query.

    picker = UserMultiPicker(context=context, summary="chips")
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import user_picker_types

from .entity_multi_picker import EntityMultiPicker
from .user_picker import UserPreset

__all__ = ["UserMultiPicker"]


class UserMultiPicker(UserPreset, EntityMultiPicker):
    """Several people or script accounts, chosen by server-side search.

    The value is the chosen references in the order they were ticked. Bare `{type, id}` members
    are resolved by one batched read per type.
    """

    def __init__(
        self,
        context: Any = None,
        value: Sequence[EntityRef] = (),
        include_api_users: bool = True,
        include_inactive: bool = False,
        filters: Any = None,
        fields: Sequence[str] = (),
        search_fields: Any = (),
        placeholder: str = "Search for people",
        **props: Any,
    ) -> None:
        preset = self._start_preset(
            include_api_users, include_inactive, filters, fields, search_fields
        )
        preset.update(props)
        preset.pop("entity_types", None)
        super().__init__(
            entity_types=user_picker_types(self._include_api_users),
            context=context,
            value=value,
            placeholder=placeholder,
            **preset,
        )
