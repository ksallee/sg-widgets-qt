"""Several projects, chosen by server-side search.

Ported from `packages/react/src/registry/sg/components/project-multi-picker.tsx` and its Svelte
twin. The same configuration as the single project picker, on the multi picker.

    picker = ProjectMultiPicker(context=context, summary="chips")
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sg_widgets_core.filter import EntityRef

from .entity_multi_picker import EntityMultiPicker
from .project_picker import PROJECT_TYPES, ProjectPreset

__all__ = ["ProjectMultiPicker"]


class ProjectMultiPicker(ProjectPreset, EntityMultiPicker):
    """Several projects, chosen by server-side search."""

    def __init__(
        self,
        context: Any = None,
        value: Sequence[EntityRef] = (),
        include_archived: bool = False,
        filters: Any = None,
        fields: Sequence[str] = (),
        placeholder: str = "Search for projects",
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
