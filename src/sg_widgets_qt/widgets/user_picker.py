"""One person, chosen by server-side search.

Ported from `packages/react/src/registry/sg/components/user-picker.tsx` and its Svelte twin. The
entity picker with the person preset: HumanUser and, unless a caller says otherwise, ApiUser; the
active condition; the query matched against the display-name chain, the email and, while the query
holds no whitespace, the login; an avatar per row and the address under the name.

    picker = UserPicker(context=context)
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import (
    USER_PICKER_FIELDS,
    SearchFieldSpec,
    user_picker_filters,
    user_picker_search_fields,
    user_picker_sub_label,
    user_picker_types,
)

from .entity_picker import EntityPicker

__all__ = ["UserPicker", "UserPreset"]


class UserPreset:
    """The person configuration both user pickers wear.

    The four person props are held here and recomposed into the entity picker's own
    `entity_types`, `fields`, `filters` and `search_fields` whenever one of them changes, so a
    caller's pre-filter and extra fields are never lost to the preset.
    """

    def _start_preset(
        self,
        include_api_users: bool,
        include_inactive: bool,
        filters: Any,
        fields: Sequence[str],
        search_fields: Any,
    ) -> dict[str, Any]:
        self._include_api_users = bool(include_api_users)
        self._include_inactive = bool(include_inactive)
        self._own_filters = filters
        self._own_fields = list(fields)
        self._own_search_fields = search_fields
        return {
            "entity_types": user_picker_types(self._include_api_users),
            "search_fields": user_picker_search_fields(search_fields),
            "fields": [*USER_PICKER_FIELDS, *self._own_fields],
            "filters": user_picker_filters(self._include_inactive, filters),
            "sub_label": user_picker_sub_label,
            # A person's picture is an avatar, which is a circle.
            "round_thumbnail": True,
        }

    @property
    def include_api_users(self) -> bool:
        """Search script accounts alongside people."""
        return self._include_api_users

    def set_include_api_users(self, value: bool) -> None:
        self._include_api_users = bool(value)
        self.set_entity_types(user_picker_types(self._include_api_users))

    @property
    def include_inactive(self) -> bool:
        """Offer people whose status is `dis`."""
        return self._include_inactive

    def set_include_inactive(self, value: bool) -> None:
        self._include_inactive = bool(value)
        self._apply_filters()

    @property
    def filters(self) -> Any:
        """Pre-filter, merged into the active condition with `and`."""
        return self._own_filters

    def set_filters(self, value: Any) -> None:
        self._own_filters = value
        self._apply_filters()

    def _apply_filters(self) -> None:
        super().set_filters(user_picker_filters(self._include_inactive, self._own_filters))

    @property
    def fields(self) -> list[str]:
        """Extra fields to request, on top of the login, the email and the status."""
        return list(self._own_fields)

    def set_fields(self, value: Sequence[str]) -> None:
        self._own_fields = list(value)
        super().set_fields([*USER_PICKER_FIELDS, *self._own_fields])

    @property
    def search_fields(self) -> Any:
        """Fields matched on top of the ones a person is searched by."""
        return self._own_search_fields

    def set_search_fields(self, value: Sequence[SearchFieldSpec] | Any) -> None:
        self._own_search_fields = value
        super().set_search_fields(user_picker_search_fields(value))


class UserPicker(UserPreset, EntityPicker):
    """One person or script account, chosen by server-side search.

    The chosen row is an `EntityRef`; a bare `{type, id}` handed in is resolved by one batched
    read. A row's sub-label is the address, or `API user` for a script account.
    """

    def __init__(
        self,
        context: Any = None,
        value: EntityRef | None = None,
        include_api_users: bool = True,
        include_inactive: bool = False,
        filters: Any = None,
        fields: Sequence[str] = (),
        search_fields: Any = (),
        placeholder: str = "Search for a person",
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
