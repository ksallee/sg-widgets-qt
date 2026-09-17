"""A glyph per entity type.

Ported from `packages/react/src/registry/sg/components/entity-glyphs.ts`. A stock site has 114
entity types plus any number of custom ones, so the map covers the types a widget meets constantly
and everything else falls back to a tag.

The values are lucide glyph names, which `sg_widgets_qt.icons` draws at any size and colour, so a
caller with a custom type adds one entry and needs no widget of its own.

    ENTITY_GLYPHS["CustomEntity07"] = "layers"
    paint_icon(painter, box, entity_glyph(ref.type), theme.color("foreground"))
"""
from __future__ import annotations

__all__ = ["DEFAULT_ENTITY_GLYPH", "ENTITY_GLYPHS", "entity_glyph"]

ENTITY_GLYPHS: dict[str, str] = {
    "Shot": "clapperboard",
    "Asset": "box",
    "Sequence": "film",
    "Version": "video",
    "Task": "list-checks",
    "HumanUser": "user",
    "Project": "folder",
    "Note": "message-square",
    "PublishedFile": "file-box",
}

#: The glyph every unlisted type takes, a site's custom entities included.
DEFAULT_ENTITY_GLYPH = "tag"


def entity_glyph(entity_type: str | None) -> str:
    """The lucide glyph name for one type, or the tag every unlisted type takes."""
    return ENTITY_GLYPHS.get(entity_type or "", DEFAULT_ENTITY_GLYPH)
