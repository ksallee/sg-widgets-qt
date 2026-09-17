"""A glyph per field data type.

The name is a lucide icon name in kebab case, so every UI package resolves the
same glyph from its own icon set. Types with no obvious glyph share a document,
which is also the answer for a data type this build does not know.
"""
from __future__ import annotations

__all__ = [
    "DEFAULT_FIELD_ICON",
    "FIELD_ICON_NAMES",
    "ICONS",
    "icon_name_for",
]

ICONS: dict[str, str] = {
    "text": "type",
    "number": "hash",
    "float": "hash",
    "percent": "percent",
    "currency": "circle-dollar-sign",
    "duration": "timer",
    "timecode": "timer",
    "footage": "ruler",
    "checkbox": "square-check",
    "date": "calendar",
    "date_time": "calendar-clock",
    "list": "list",
    "status_list": "circle-dot",
    "entity": "link",
    "multi_entity": "link-2",
    "tag_list": "tag",
    "entity_type": "shapes",
    "image": "image",
    "url": "globe",
    "color": "palette",
    "uuid": "fingerprint",
    "jsonb": "braces",
    "calculated": "sigma",
    "summary": "sigma",
    "serializable": "file-text",
    "password": "key-round",
    "pivot_column": "file-text",
}

#: The catch-all glyph, used for a data type this build does not know.
DEFAULT_FIELD_ICON = "file-text"


def icon_name_for(data_type: str) -> str:
    """The lucide icon name for a field's data type."""
    return ICONS.get(data_type, DEFAULT_FIELD_ICON)


#: Every icon name this module can return, for a UI package's name-to-widget map.
FIELD_ICON_NAMES: tuple[str, ...] = tuple(sorted(set(ICONS.values()) | {DEFAULT_FIELD_ICON}))
