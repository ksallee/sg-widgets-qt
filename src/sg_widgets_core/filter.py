"""Filter model.

The editor works on a tree of groups and conditions. The wire format is the
`api3_hash` body of `POST /entity/<type>/_search`: a group is
`{logical_operator, conditions}` and a condition is `[path, relation, value]`.
`api3_hash` also expresses a plain `and`, so it is the only content type the
client needs. Nesting is safe to 265 levels (probe 030); no one will get there.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict, Union

from .field_types import VALUE_SHAPE, Operator

__all__ = [
    "LOGICAL_OPERATORS",
    "ConditionValue",
    "EntityRef",
    "FilterCondition",
    "FilterGroup",
    "FilterNode",
    "LogicalOperator",
    "Scalar",
    "TextSearchFilter",
    "WireCondition",
    "WireGroup",
    "condition",
    "empty_filter",
    "from_wire",
    "group",
    "is_blank_condition",
    "is_empty_filter",
    "referenced_paths",
    "to_api3_hash",
    "to_filter_array",
    "walk",
]

LogicalOperator = Literal["and", "or"]
LOGICAL_OPERATORS: tuple[LogicalOperator, ...] = ("and", "or")


@dataclass
class EntityRef:
    type: str
    id: int
    #: `cached_display_name` of the target when known. Never sent to the API.
    name: str | None = None


Scalar = Union[str, int, float, bool, None, EntityRef]

ConditionValue = Union[Scalar, list[Scalar], tuple[Any, ...]]


@dataclass
class FilterCondition:
    #: Dotted path such as `entity.Shot.code`.
    path: str
    operator: Operator
    value: ConditionValue = None
    kind: Literal["condition"] = "condition"


@dataclass
class FilterGroup:
    logical_operator: LogicalOperator = "and"
    conditions: list[FilterNode] = field(default_factory=list)
    kind: Literal["group"] = "group"


FilterNode = Union[FilterGroup, FilterCondition]

#: A condition on the wire: `[path, relation, value]`, and nothing else.
WireCondition = list[Any]


class WireGroup(TypedDict):
    """A group on the wire, which is the filter dict `_search` and `find` take."""

    logical_operator: LogicalOperator
    conditions: list[Any]


TextSearchFilter = Optional[Union[WireGroup, list[WireCondition]]]
"""What one type's entry in `_text_search`'s `entity_types` map accepts: a filter
array, or a group this converts to one."""


def to_filter_array(filter: TextSearchFilter) -> list[WireCondition]:
    """The filter array `entity_types` wants, `[]` for no filter.

    The array form is `and` only and cannot express a nested group, so one is
    refused here rather than sent and guessed at (post_entity_text_search).
    """
    if not filter:
        return []
    if isinstance(filter, list):
        return filter
    if filter["logical_operator"] != "and":
        raise ValueError("A '_text_search' filter is an array of conditions, which is 'and' only.")
    out: list[WireCondition] = []
    for c in filter["conditions"]:
        if not isinstance(c, list):
            raise ValueError("A '_text_search' filter is an array of conditions and cannot nest a group.")
        out.append(c)
    return out


def group(logical_operator: LogicalOperator, conditions: list[FilterNode] | None = None) -> FilterGroup:
    return FilterGroup(logical_operator=logical_operator, conditions=list(conditions or []))


def condition(path: str, operator: Operator, value: ConditionValue) -> FilterCondition:
    return FilterCondition(path=path, operator=operator, value=value)


def empty_filter() -> FilterGroup:
    return group("and")


def is_blank_condition(c: FilterCondition) -> bool:
    """A condition is blank when it has no path, or when its operator needs a value and none was given.

    Blank conditions are dropped on serialisation rather than sent as a degenerate filter.
    """
    if not c.path:
        return True
    shape = VALUE_SHAPE[c.operator]
    v = c.value
    if shape in ("scalar", "string"):
        # `is null` and `is_not null` are meaningful on every type but checkbox and uuid.
        return v == ""
    if shape == "list":
        return not isinstance(v, (list, tuple)) or len(v) == 0
    if shape == "range":
        return not isinstance(v, (list, tuple)) or len(v) != 2 or v[0] is None or v[1] is None
    if shape == "relative":
        return (
            not isinstance(v, (list, tuple))
            or len(v) != 2
            or not _is_number(v[0])
            or v[0] <= 0
            or not v[1]
        )
    if shape == "calendar":
        return not _is_number(v)
    return False


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_empty_filter(node: FilterNode) -> bool:
    """True when serialisation would produce no conditions at all."""
    if node.kind == "condition":
        return is_blank_condition(node)
    return all(is_empty_filter(child) for child in node.conditions)


def _strip_name(v: Scalar) -> Any:
    if isinstance(v, EntityRef):
        return {"type": v.type, "id": v.id}
    if isinstance(v, dict):
        return {"type": v.get("type"), "id": v.get("id")}
    return v


def _serialize_value(c: FilterCondition) -> Any:
    shape = VALUE_SHAPE[c.operator]
    v = c.value
    if shape in ("list", "range"):
        return [_strip_name(item) for item in v]
    if shape in ("relative", "calendar", "none"):
        return v
    return _strip_name(v)


def to_api3_hash(node: FilterNode) -> WireGroup | None:
    """Serialise a tree to the `api3_hash` `filters` value.

    Blank conditions and groups that end up empty are dropped. Returns `None` when
    nothing remains, so callers can omit `filters` rather than send `[]` (which
    matches every row on the site).
    """
    out = _serialize_node(node)
    if out is None:
        return None
    if isinstance(out, list):
        return {"logical_operator": "and", "conditions": [out]}
    return out


def _serialize_node(node: FilterNode) -> WireGroup | WireCondition | None:
    if node.kind == "condition":
        if is_blank_condition(node):
            return None
        return [node.path, node.operator, _serialize_value(node)]
    conditions = [c for c in (_serialize_node(child) for child in node.conditions) if c is not None]
    if len(conditions) == 0:
        return None
    return {"logical_operator": node.logical_operator, "conditions": conditions}


def from_wire(wire: WireGroup | list[WireCondition]) -> FilterGroup:
    """Parse a wire group (or a flat `api3_array` list) back into the editor tree."""
    if isinstance(wire, list):
        return group("and", [_from_wire_condition(c) for c in wire])
    return group(
        wire["logical_operator"],
        [_from_wire_condition(c) if isinstance(c, list) else from_wire(c) for c in wire["conditions"]],
    )


def _from_wire_condition(wire: WireCondition) -> FilterCondition:
    path, operator, value = wire
    return condition(path, operator, value)


def walk(node: FilterNode) -> Iterator[FilterNode]:
    """Depth-first walk, useful for collecting referenced paths or validating against a schema."""
    yield node
    if node.kind == "group":
        for child in node.conditions:
            yield from walk(child)


def referenced_paths(node: FilterNode) -> list[str]:
    paths: list[str] = []
    for n in walk(node):
        if n.kind == "condition" and n.path and n.path not in paths:
            paths.append(n.path)
    return paths
