"""Field schema, normalised.

`GET /schema/<Type>/fields` wraps every property in `{value, editable}` where the
outer `editable` says whether you may change the property, not the field.
`data[field].editable.value` is the one that answers "can I write this".
With `project_id`, status and list fields gain `hidden_values`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, TypedDict

from .field_types import Operator

__all__ = [
    "DISPLAY_NAME_FIELDS",
    "FIELD_SCHEMA_OVERRIDES",
    "FieldSchema",
    "RawFieldSchema",
    "RawFieldsResponse",
    "RawProperty",
    "display_name_of",
    "field_schema_override",
    "normalize_field",
    "normalize_fields",
    "status_field_for",
    "status_field_name_for",
    "undeclared_field",
]


class RawProperty(TypedDict):
    """One property as the API returns it."""

    value: Any
    editable: bool


class RawFieldSchema(TypedDict):
    name: RawProperty
    entity_type: RawProperty
    data_type: RawProperty
    editable: RawProperty
    mandatory: RawProperty
    unique: RawProperty
    properties: dict[str, RawProperty]


class RawFieldsResponse(TypedDict):
    data: dict[str, RawFieldSchema]


@dataclass
class FieldSchema:
    #: Programmatic name, e.g. `sg_status_list`.
    name: str
    #: Human label, e.g. `Status`.
    display_name: str
    entity_type: str
    data_type: str
    editable: bool
    mandatory: bool
    unique: bool
    #: For `entity` and `multi_entity`: the types the field may link to. Advisory on most fields.
    valid_types: list[str] | None = None
    #: For `list` and `status_list`: the site-wide vocabulary of codes.
    valid_values: list[str] | None = None
    #: For `status_list`: code to label map. Absent when labels equal codes.
    display_values: dict[str, str] | None = None
    #: For `list` and `status_list`, only when read with `project_id`. May contain codes outside `valid_values`.
    hidden_values: list[str] | None = None
    #: The operators the API evaluates on this field, where they are fewer than the
    #: vocabulary it advertises. None means the whole vocabulary.
    operators: list[Operator] | None = None
    #: A default of null and no default at all read the same here.
    default_value: Any = None
    description: str | None = None


FIELD_SCHEMA_OVERRIDES: dict[str, dict[str, Any]] = {
    "Note.read_by_current_user": {
        "display_name": "Read by Current User",
        "data_type": "list",
        "valid_values": ["unread", "read"],
        "operators": ["is", "is_not"],
        "editable": True,
        "mandatory": False,
        "unique": False,
    },
}
"""Fields the schema types one way and the API answers another, keyed
`<Type>.<field>`. `Note.read_by_current_user` holds the codes `unread` and
`read`, never a boolean, so every control derived from it is a list and not a
checkbox (067_notes_in_the_stream, entity_types/Note).

An entry carries the whole field, because a site may leave it out of the schema
and still answer it on the row: `GET /schema/Note/fields` answers 33 fields and
no `read_by_current_user` among them, while `GET /schema/Note/fields/read_by_current_user`
answers 200 with `data: null`, which is what an undeclared field reads as and a
name that is nothing at all answers 404 (068_note_read_state). `normalize_fields`
adds what the schema left out. A site that declares the field keeps its own
display name and editability and is corrected on the data type, the values and
the operators alone.

`operators` is the set the API evaluates, which is not always the set it
advertises. `read_by_current_user` names `is`, `is_not`, `in` and `not_in` in its
own `Valid relations`, and evaluates only the first two: `in`, `not_in` and an
`is` value outside the vocabulary all answer 200 with the caller's unread rows
whatever the list holds, in `_search` and in `_summarize`, under both body shapes
(068_note_read_state).

The value is per person: a person's `PUT` answers 200 and the re-read follows it,
so the field is editable. A script has no read state, and its own write answers
200 and stores nothing (068_note_read_state)."""

#: The part of an override that corrects a declaring site.
_PATCHED_KEYS = ("data_type", "valid_values", "operators")


def field_schema_override(entity_type: str, name: str) -> dict[str, Any] | None:
    """What a declared field's schema has to be corrected to, when it is one of those."""
    whole = FIELD_SCHEMA_OVERRIDES.get(f"{entity_type}.{name}")
    if not whole:
        return None
    patch: dict[str, Any] = {}
    for key in _PATCHED_KEYS:
        if whole.get(key) is not None:
            patch[key] = whole[key]
    return patch


def undeclared_field(entity_type: str, name: str) -> FieldSchema | None:
    """The whole field, for a site whose schema does not declare it; None when it is not one of those."""
    whole = FIELD_SCHEMA_OVERRIDES.get(f"{entity_type}.{name}")
    return FieldSchema(name=name, entity_type=entity_type, **whole) if whole else None


def _prop(props: dict[str, RawProperty] | None, key: str) -> Any:
    p = (props or {}).get(key)
    return p["value"] if p else None


def normalize_field(name: str, raw: RawFieldSchema) -> FieldSchema:
    props = raw["properties"]
    field = FieldSchema(
        name=name,
        display_name=raw["name"]["value"],
        entity_type=raw["entity_type"]["value"],
        data_type=raw["data_type"]["value"],
        editable=raw["editable"]["value"],
        mandatory=raw["mandatory"]["value"],
        unique=raw["unique"]["value"],
    )
    valid_types = _prop(props, "valid_types")
    if valid_types:
        field.valid_types = valid_types
    valid_values = _prop(props, "valid_values")
    if valid_values:
        field.valid_values = valid_values
    display_values = _prop(props, "display_values")
    if display_values:
        field.display_values = display_values
    hidden_values = _prop(props, "hidden_values")
    if hidden_values:
        field.hidden_values = hidden_values
    default_value = _prop(props, "default_value")
    if default_value is not None:
        field.default_value = default_value
    description = _prop(props, "description")
    if description:
        field.description = description
    return dataclasses.replace(field, **(field_schema_override(field.entity_type, name) or {}))


def normalize_fields(response: RawFieldsResponse, entity_type: str | None = None) -> dict[str, FieldSchema]:
    """Every field of a type, with the fields an override declares and the schema omitted.

    `entity_type` is only needed for a response with no fields at all; otherwise the
    fields name their own type.
    """
    out: dict[str, FieldSchema] = {}
    for name, raw in response["data"].items():
        out[name] = normalize_field(name, raw)
    type_ = entity_type if entity_type is not None else next((f.entity_type for f in out.values()), None)
    if not type_:
        return out
    for key in FIELD_SCHEMA_OVERRIDES:
        at = key.index(".")
        name = key[at + 1:]
        if key[:at] != type_ or name in out:
            continue
        whole = undeclared_field(type_, name)
        if whole:
            out[name] = whole
    return out


def status_field_name_for(entity_type: str) -> str:
    """The field name a type's own status lives under. Project's is a plain `list`."""
    return "sg_status" if entity_type == "Project" else "sg_status_list"


def status_field_for(entity_type: str, fields: dict[str, FieldSchema] | None = None) -> FieldSchema | str:
    """The status field of an entity type.

    Every type but Project uses `sg_status_list` (data type `status_list`); Project's
    is `sg_status`, a plain `list`. Prefer the schema when you have it; the name guess
    is the fallback.

    The conventional name wins over any other `status_list` field on the type. A site
    is free to add its own, a client status, a delivery status, and a schema read
    answers them in no order the caller controls, so picking the first one found makes
    a type's status whichever field the response happened to list first.
    """
    name = status_field_name_for(entity_type)
    if fields is not None:
        own = fields.get(name)
        if own:
            return own
        status = next((f for f in fields.values() if f.data_type == "status_list"), None)
        if status:
            return status
    return name


DISPLAY_NAME_FIELDS: tuple[str, ...] = ("cached_display_name", "code", "name", "title", "content", "subject")
"""The fields Flow PT conventionally uses as a row's human label, in order.
`cached_display_name` is the server's own copy and wins when present."""


def display_name_of(values: dict[str, Any] | None, fallback: str = "") -> str:
    if not values:
        return fallback
    for key in DISPLAY_NAME_FIELDS:
        v = values.get(key)
        if isinstance(v, str) and len(v) > 0:
            return v
    return fallback
