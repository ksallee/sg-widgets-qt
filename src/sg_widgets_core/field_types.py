"""Field data types and their filter vocabularies.

Every list here is what a live Flow Production Tracking site answered when a
probe sent it an unknown operator: the 400 names the legal set. Source:
sg-groundtruth corpus, `findings/field_types/*.md` and `findings/017_filter_operators.md`.
"""
from __future__ import annotations

from typing import Literal

__all__ = [
    "DATA_TYPES",
    "DataType",
    "NEGATING_OPERATORS",
    "OPERATORS",
    "OPERATORS_BY_TYPE",
    "TIME_UNITS",
    "TimeUnit",
    "Operator",
    "VALUE_SHAPE",
    "VALUE_SHAPES",
    "ValueShape",
    "is_data_type",
    "is_filterable",
    "is_link_type",
    "is_numeric_type",
    "is_operator",
    "is_temporal_type",
    "operators_for",
    "supports_operator",
]

DataType = Literal[
    "text", "number", "float", "percent", "duration", "timecode", "currency",
    "checkbox", "date", "date_time", "list", "status_list", "entity", "multi_entity",
    "entity_type", "color", "image", "url", "jsonb", "serializable", "uuid",
    "calculated", "summary", "password", "pivot_column", "footage", "tag_list",
]

DATA_TYPES: tuple[DataType, ...] = (
    "text", "number", "float", "percent", "duration", "timecode", "currency",
    "checkbox", "date", "date_time", "list", "status_list", "entity", "multi_entity",
    "entity_type", "color", "image", "url", "jsonb", "serializable", "uuid",
    "calculated", "summary", "password", "pivot_column", "footage", "tag_list",
)

Operator = Literal[
    "is", "is_not", "in", "not_in",
    "contains", "not_contains", "starts_with", "ends_with",
    "greater_than", "less_than", "between",
    "in_last", "not_in_last", "in_next", "not_in_next",
    "in_calendar_day", "in_calendar_week", "in_calendar_month", "in_calendar_year",
    "name_is", "name_contains", "name_not_contains", "type_is", "type_is_not",
]

OPERATORS: tuple[Operator, ...] = (
    "is", "is_not", "in", "not_in",
    "contains", "not_contains", "starts_with", "ends_with",
    "greater_than", "less_than", "between",
    "in_last", "not_in_last", "in_next", "not_in_next",
    "in_calendar_day", "in_calendar_week", "in_calendar_month", "in_calendar_year",
    "name_is", "name_contains", "name_not_contains", "type_is", "type_is_not",
)

TimeUnit = Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
TIME_UNITS: tuple[TimeUnit, ...] = ("HOUR", "DAY", "WEEK", "MONTH", "YEAR")

_EQUALITY: tuple[Operator, ...] = ("is", "is_not", "in", "not_in")
_TEXT: tuple[Operator, ...] = ("contains", "not_contains", "is", "is_not", "starts_with", "ends_with", "in", "not_in")
_NUMERIC: tuple[Operator, ...] = ("is", "is_not", "greater_than", "less_than", "between", "in", "not_in")
_TEMPORAL: tuple[Operator, ...] = (
    "is", "is_not", "greater_than", "less_than", "in_last", "not_in_last", "in_next", "not_in_next",
    "in_calendar_week", "in_calendar_month", "in_calendar_day", "in_calendar_year", "between", "in", "not_in",
)
_LINK: tuple[Operator, ...] = (
    "is", "is_not", "name_contains", "name_not_contains", "name_is", "type_is", "type_is_not", "in", "not_in",
)
_NONE: tuple[Operator, ...] = ()

OPERATORS_BY_TYPE: dict[DataType, tuple[Operator, ...]] = {
    "text": _TEXT,
    "number": _NUMERIC,
    "float": _NUMERIC,
    "percent": _NUMERIC,
    "duration": _NUMERIC,
    "timecode": _NUMERIC,
    "currency": _NUMERIC,
    "footage": _NUMERIC,
    "checkbox": ("is", "is_not"),
    "date": _TEMPORAL,
    "date_time": _TEMPORAL,
    "list": _EQUALITY,
    "status_list": _EQUALITY,
    "entity_type": _EQUALITY,
    "color": _EQUALITY,
    "uuid": _EQUALITY,
    "entity": _LINK,
    "multi_entity": _LINK,
    "tag_list": _LINK,
    "image": ("is", "is_not"),
    "jsonb": ("is", "is_not", "contains", "not_contains"),
    "url": _NONE,
    "serializable": _NONE,
    "calculated": _NONE,
    "summary": _NONE,
    "password": _NONE,
    "pivot_column": _NONE,
}
"""Operators each data type accepts in a `_search` filter. An empty list means the
type "cannot be used in a filter" and the API 400s on every operator."""

ValueShape = Literal[
    "scalar",      # one value of the field's kind, or null
    "list",        # a JSON array of scalars (or entity hashes)
    "range",       # exactly two scalars, inclusive, order-insensitive
    "relative",    # [count, TimeUnit], count positive
    "calendar",    # an integer offset: 0 = current, -1 = previous, +1 = next
    "string",      # a plain string regardless of field kind (name_*, type_*)
    "none",        # e.g. in_calendar_* take an int but no field-typed value
]
"""Shape of the value an operator expects on the wire."""

VALUE_SHAPES: tuple[ValueShape, ...] = ("scalar", "list", "range", "relative", "calendar", "string", "none")

VALUE_SHAPE: dict[Operator, ValueShape] = {
    "is": "scalar", "is_not": "scalar",
    "in": "list", "not_in": "list",
    "contains": "scalar", "not_contains": "scalar", "starts_with": "scalar", "ends_with": "scalar",
    "greater_than": "scalar", "less_than": "scalar",
    "between": "range",
    "in_last": "relative", "not_in_last": "relative", "in_next": "relative", "not_in_next": "relative",
    "in_calendar_day": "calendar", "in_calendar_week": "calendar",
    "in_calendar_month": "calendar", "in_calendar_year": "calendar",
    "name_is": "string", "name_contains": "string", "name_not_contains": "string",
    "type_is": "string", "type_is_not": "string",
}

NEGATING_OPERATORS: frozenset[Operator] = frozenset(
    ("is_not", "not_in", "not_contains", "not_in_last", "not_in_next", "name_not_contains", "type_is_not")
)
"""Operators whose result set includes rows where the field is null.

`is_not X` is not the complement of `is X` on Flow PT: every negating operator
matches unset rows, while comparisons exclude them."""


def is_data_type(value: str) -> bool:
    return value in DATA_TYPES


def is_operator(value: str) -> bool:
    return value in OPERATORS


def operators_for(data_type: str) -> tuple[Operator, ...]:
    """Operators legal for a data type. Unknown types get the equality set, the smallest one the API prints."""
    return OPERATORS_BY_TYPE[data_type] if is_data_type(data_type) else _EQUALITY


def is_filterable(data_type: str) -> bool:
    return len(operators_for(data_type)) > 0


def supports_operator(data_type: str, operator: Operator) -> bool:
    return operator in operators_for(data_type)


def is_link_type(data_type: str) -> bool:
    """Types whose scalar value is a `{type, id}` entity hash."""
    return data_type in ("entity", "multi_entity", "tag_list")


def is_numeric_type(data_type: str) -> bool:
    """Types whose scalar value is a number (integer unless noted)."""
    return data_type in ("number", "float", "percent", "duration", "timecode", "currency", "footage")


def is_temporal_type(data_type: str) -> bool:
    return data_type in ("date", "date_time")
