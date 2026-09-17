"""Deprecated. `ListSelect` is `ListPicker`: import `list_picker` and use that.

This module keeps an existing import resolving for one release and adds nothing of its own.
Ported from `packages/react/src/registry/sg/components/list-select.tsx` and its Svelte twin,
which are the same re-export.
"""
from __future__ import annotations

from .list_picker import LIST_ROW_TYPE, ListOption, ListPicker
from .list_picker import ListPicker as ListSelect

__all__ = ["LIST_ROW_TYPE", "ListOption", "ListPicker", "ListSelect"]
