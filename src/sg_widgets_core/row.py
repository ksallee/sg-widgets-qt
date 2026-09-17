"""Row anatomy, rule 9 of `docs/design-rules.md`.

Every widget that lists entity rows draws the same row from the same six props: a
picture, a label with the matched runs bold, a muted sub-label, a right-aligned
secondary rendered by its data type, an optional programmatic code, and the extra
fields a caller's own sub-label or secondary needs. What each part reads off a row
lives here, so a picker row, a tree row and a search row cannot drift.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Protocol, Union

from .collection import CollectionColumn

__all__ = [
    "FieldSpec",
    "RowAnatomy",
    "RowValues",
    "path_of",
    "row_code",
    "row_fields",
    "row_secondary",
    "row_sub_label",
    "row_thumbnail",
    "secondary_type",
    "thumbnail_field",
]

FieldSpec = Union[str, CollectionColumn]
"""A field named by a row-anatomy prop: a bare path, or a column already resolved from
the schema so the value renders by its data type. One type everywhere."""


def path_of(spec: FieldSpec | None) -> str:
    """The path a field spec names. Empty when nothing is named."""
    if spec is None:
        return ""
    return spec if isinstance(spec, str) else spec.path


@dataclass
class RowAnatomy:
    """The six props of rule 9, as a widget holds them."""

    #: `False`, or the field name holding the image URL.
    thumbnail: Union[str, bool, None] = None
    #: The field shown as the main label. The display-name chain answers it when absent.
    label_field: str | None = None
    #: The muted line under the label.
    sub_label_field: FieldSpec | None = None
    #: The right-aligned column, rendered by data type.
    secondary_field: FieldSpec | None = None
    #: Show programmatic names beside display names.
    show_code: bool = False
    #: Extra fields to request, so a caller's own sub-label or secondary can read them.
    fields: list[str] = dc_field(default_factory=list)


def thumbnail_field(anatomy: RowAnatomy) -> str | None:
    """The field a row's thumbnail is read from, or None when there is none."""
    if anatomy.thumbnail is False:
        return None
    return anatomy.thumbnail if anatomy.thumbnail is not None else "image"


def row_fields(anatomy: RowAnatomy, base: Sequence[str] = ()) -> list[str]:
    """Every field a row anatomy has to read, `base` first and duplicates dropped.

    An unknown field name is a silent 200 with the key absent (003_query), so asking for
    a path a type does not carry costs nothing.
    """
    wanted = list(base)
    if anatomy.label_field:
        wanted.append(anatomy.label_field)
    sub = path_of(anatomy.sub_label_field)
    if sub:
        wanted.append(sub)
    secondary = path_of(anatomy.secondary_field)
    if secondary:
        wanted.append(secondary)
    image = thumbnail_field(anatomy)
    if image:
        wanted.append(image)
    if anatomy.show_code:
        wanted.append("code")
    wanted.extend(anatomy.fields)
    return list(dict.fromkeys(name for name in wanted if len(name) > 0))


def row_thumbnail(values: dict[str, Any], anatomy: RowAnatomy) -> str | None:
    """The picture a row shows, or None when the field is off or holds no URL."""
    field = thumbnail_field(anatomy)
    if not field:
        return None
    raw = values.get(field)
    return raw if isinstance(raw, str) and len(raw) > 0 else None


def row_sub_label(values: dict[str, Any], anatomy: RowAnatomy) -> str:
    """The muted line under the label. Empty when nothing names it or the value is blank."""
    path = path_of(anatomy.sub_label_field)
    if not path:
        return ""
    raw = values.get(path)
    if raw is None:
        return ""
    # A relationship is unwrapped to `{type, id, name}`, so its name is the line.
    if isinstance(raw, dict):
        name = raw.get("name")
        return name if isinstance(name, str) else ""
    return str(raw)


def row_code(values: dict[str, Any], label: str, show_code: bool = False) -> str:
    """The programmatic name beside the label, when it says something the label does not."""
    if not show_code:
        return ""
    raw = values.get("code")
    return raw if isinstance(raw, str) and len(raw) > 0 and raw != label else ""


class RowValues(Protocol):
    """What the secondary reads a row through: its id, and its values by path."""

    id: int
    values: dict[str, Any]


def row_secondary(row: RowValues, anatomy: RowAnatomy) -> Any:
    """The raw value the secondary column draws.

    `id` is on the row itself rather than among the values a read returns, so it is
    answered from the reference.
    """
    path = path_of(anatomy.secondary_field)
    if not path:
        return None
    return row.id if path == "id" else row.values.get(path)


def secondary_type(anatomy: RowAnatomy, field_type: str | None = None) -> str:
    """The data type the secondary renders as.

    The resolved column's own, the schema's when one was read, and `number` for `id`,
    which is a code rather than a name.
    """
    spec = anatomy.secondary_field
    if spec is not None and not isinstance(spec, str) and spec.data_type:
        return spec.data_type
    if field_type:
        return field_type
    return "number" if path_of(spec) == "id" else "text"
