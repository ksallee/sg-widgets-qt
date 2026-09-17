"""Deprecated. `ListMultiSelect` is `ListMultiPicker`: import `list_multi_picker` and use that.

This module keeps an existing import resolving for one release and adds nothing of its own.
Ported from `packages/react/src/registry/sg/components/list-multi-select.tsx` and its Svelte
twin, which are the same re-export.
"""
from __future__ import annotations

from .list_multi_picker import ListMultiPicker
from .list_multi_picker import ListMultiPicker as ListMultiSelect
from .list_picker import LIST_ROW_TYPE, ListOption

__all__ = ["LIST_ROW_TYPE", "ListMultiPicker", "ListMultiSelect", "ListOption"]
