"""One project, chosen by server-side search.

Ported from `packages/react/src/registry/sg/components/project-picker.tsx` and its Svelte twin.
The entity picker configured for Project: the project thumbnail, the status under the name so an
active project can be told from a bidding one, and archived projects left out unless asked for.

    picker = ProjectPicker(context=context)
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import PROJECT_PICKER_FIELDS, project_picker_filters

from .entity_picker import EntityPicker

__all__ = ["ProjectPicker", "ProjectPreset"]

#: The only type either project picker searches.
PROJECT_TYPES = ["Project"]


class ProjectPreset:
    """The project configuration both project pickers wear.

    `archived`, `is_template` and `is_demo` are the discriminators a project listing goes by;
    `sg_status` is not a liveness filter and is null on most projects (018_project_listing). The
    caller's own pre-filter and extra fields are recomposed with the preset on every change.
    """

    def _start_preset(
        self, include_archived: bool, filters: Any, fields: Sequence[str]
    ) -> dict[str, Any]:
        self._include_archived = bool(include_archived)
        self._own_filters = filters
        self._own_fields = list(fields)
        return {
            "fields": [*PROJECT_PICKER_FIELDS, *self._own_fields],
            "filters": project_picker_filters(self._include_archived, filters),
            "sub_label_field": "sg_status",
        }

    @property
    def include_archived(self) -> bool:
        """Offer projects whose `archived` checkbox is set."""
        return self._include_archived

    def set_include_archived(self, value: bool) -> None:
        self._include_archived = bool(value)
        self._apply_filters()

    @property
    def filters(self) -> Any:
        """Pre-filter, merged into the archived condition with `and`."""
        return self._own_filters

    def set_filters(self, value: Any) -> None:
        self._own_filters = value
        self._apply_filters()

    def _apply_filters(self) -> None:
        super().set_filters(project_picker_filters(self._include_archived, self._own_filters))

    @property
    def fields(self) -> list[str]:
        """Extra fields to request, on top of the status and the archived flag."""
        return list(self._own_fields)

    def set_fields(self, value: Sequence[str]) -> None:
        self._own_fields = list(value)
        super().set_fields([*PROJECT_PICKER_FIELDS, *self._own_fields])


class ProjectPicker(ProjectPreset, EntityPicker):
    """One project, chosen by server-side search."""

    def __init__(
        self,
        context: Any = None,
        value: EntityRef | None = None,
        include_archived: bool = False,
        filters: Any = None,
        fields: Sequence[str] = (),
        placeholder: str = "Search for a project",
        **props: Any,
    ) -> None:
        preset = self._start_preset(include_archived, filters, fields)
        preset.update(props)
        preset.pop("entity_types", None)
        super().__init__(
            entity_types=list(PROJECT_TYPES),
            context=context,
            value=value,
            placeholder=placeholder,
            **preset,
        )
