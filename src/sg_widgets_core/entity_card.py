"""The model behind an entity card.

A card shows one row: its thumbnail, name, type, status and a chosen list of field
paths. Working out which fields to ask for, what each path is called and what type
its value has is schema work, not rendering, so it lives here and the widget reads
the same model.

Every call here is synchronous. The Qt layer (`src/sg_widgets_qt/workers.py`) runs
the read on a thread and calls back on the GUI thread.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from .client import EntityRow, SearchOptions
from .collection import cell_value
from .context import SgContext
from .filter import EntityRef
from .presentation import PathLabelOptions, path_label
from .schema import DISPLAY_NAME_FIELDS, FieldSchema, display_name_of, status_field_for

__all__ = [
    "EntityCardColumn",
    "EntityCardModel",
    "EntityCardOptions",
    "EntityCardStatus",
    "describe_entity_card",
    "entity_card_fields",
    "load_entity_card",
]


@dataclass
class EntityCardOptions:
    #: Dotted field paths for the grid, in order.
    fields: list[str] = dc_field(default_factory=list)
    #: The `image` field to read the thumbnail from. Default `image`.
    image_path: str | None = None


@dataclass
class EntityCardColumn:
    """One field of the grid, resolved."""

    path: str
    #: `path_label` of the resolved path; the raw path when the path does not resolve.
    label: str
    data_type: str
    #: The leaf field's schema, for a status label out of `display_values` (probe 009).
    field: FieldSchema | None = None
    value: Any = None


@dataclass
class EntityCardStatus:
    """The type's status field and the row's code."""

    code: str
    field: FieldSchema


@dataclass
class EntityCardModel:
    entity: EntityRef
    #: The row the model was built from, for a caller's own label or sub-label.
    row: EntityRow
    name: str
    #: The type's display name, from the site's enabled types.
    type_label: str
    thumbnail: str | None = None
    #: The type's status field and the row's code, when the type has one.
    status: EntityCardStatus | None = None
    #: The caller's paths, less the one naming the type's own status field.
    columns: list[EntityCardColumn] = dc_field(default_factory=list)


DEFAULT_IMAGE_PATH = "image"


def entity_card_fields(
    context: SgContext,
    entity_type: str,
    options: EntityCardOptions | None = None,
) -> list[str]:
    """The fields one card read asks for.

    The identity chain the type actually has, its thumbnail, its status field and the
    caller's paths. The chain is intersected with the type's schema because a name
    absent from a type is not an empty column but a 400 on the read: Task has neither
    `code` nor `name` (entity_types/Task).
    """
    settings = options if options is not None else EntityCardOptions()
    schema = context.schema.fields(entity_type)
    image = settings.image_path if settings.image_path is not None else DEFAULT_IMAGE_PATH
    status = status_field_for(entity_type, schema)
    wanted = [
        *(name for name in DISPLAY_NAME_FIELDS if name in schema),
        *([image] if image in schema else []),
        *([] if isinstance(status, str) else [status.name]),
        *settings.fields,
    ]
    return list(dict.fromkeys(wanted))


def describe_entity_card(
    context: SgContext,
    row: EntityRow,
    options: EntityCardOptions | None = None,
) -> EntityCardModel:
    """The card model for a row already read. Resolves the labels and types of the paths."""
    settings = options if options is not None else EntityCardOptions()
    paths = settings.fields
    schema = context.schema.fields(row.type)
    types = context.schema.entity_types()
    columns = [_describe_column(context, row, path) for path in paths]
    status = status_field_for(row.type, schema)
    code = None if isinstance(status, str) else row.values.get(status.name)
    badge = (
        None
        if isinstance(status, str) or not isinstance(code, str)
        else EntityCardStatus(code=code, field=status)
    )
    image = settings.image_path if settings.image_path is not None else DEFAULT_IMAGE_PATH
    thumbnail = row.values.get(image)
    return EntityCardModel(
        entity=EntityRef(type=row.type, id=row.id, name=display_name_of(row.values)),
        row=row,
        name=display_name_of(row.values, f"{row.type} #{row.id}"),
        type_label=next((t.display_name for t in types if t.name == row.type), row.type),
        thumbnail=thumbnail if isinstance(thumbnail, str) else None,
        status=badge,
        # The header draws this row's own status when it has one, so the same field asked
        # for by name is one value with one badge. With no status to draw, the column is
        # where its emptiness shows. A path that ends at a linked row's status is a
        # different row's and stays.
        columns=[c for c in columns if c.path != badge.field.name] if badge else columns,
    )


def load_entity_card(
    context: SgContext,
    entity: EntityRef,
    options: EntityCardOptions | None = None,
) -> EntityCardModel:
    """The card model for a reference: one search for the row, then its description."""
    fields = entity_card_fields(context, entity.type, options)
    found = context.client.search(
        entity.type,
        SearchOptions(
            filters={"logical_operator": "and", "conditions": [["id", "is", entity.id]]},
            fields=fields,
            page={"size": 1},
        ),
    )
    row = found.data[0] if found.data else None
    if row is None:
        raise ValueError(f"{entity.type} {entity.id} is not readable.")
    return describe_entity_card(context, row, options)


def _describe_column(context: SgContext, row: EntityRow, path: str) -> EntityCardColumn:
    """One column.

    A path that names no field is shown under its own text rather than failing the card:
    a projection answers 200 with the key absent for a segment outside the field's
    `valid_types`, so an unresolvable path is an empty value (probe 059).
    """
    value = cell_value(row, path)
    try:
        segments = context.schema.resolve_path(row.type, path)
        leaf = segments[-1] if segments else None
        type_labels = {t.name: t.display_name for t in context.schema.entity_types()}
        return EntityCardColumn(
            path=path,
            label=path_label(segments, PathLabelOptions(type_labels=type_labels)),
            data_type=leaf.data_type if leaf else "text",
            field=leaf.field if leaf else None,
            value=value,
        )
    except Exception:
        return EntityCardColumn(path=path, label=path, data_type="text", field=None, value=value)
