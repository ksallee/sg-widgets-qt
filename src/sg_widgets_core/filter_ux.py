"""Filter vocabulary, in human wording.

`field_types.py` holds what the API accepts; this holds what a filter editor
shows. The two are not one list: `is null` and `is` are the same operator to the
API and two different menu entries to a person, and `in_calendar_week 0` reads as
"this week". An `OperatorPreset` is one menu entry, and it always names the raw
operator it serialises to, so nothing here invents wire behaviour.

Operator legality per type comes from the corpus (`findings/017_filter_operators.md`
and `findings/field_types/*`) through `operators_for`.
"""
from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Callable, Literal, Optional

from .client import EntityRow, SgApiError, SgClient, SummarizeOptions, SummaryGroup, SummaryGrouping
from .field_types import (
    TIME_UNITS,
    VALUE_SHAPE,
    DataType,
    Operator,
    TimeUnit,
    ValueShape,
    is_filterable,
    is_link_type,
    is_numeric_type,
    is_operator,
    is_temporal_type,
    operators_for,
    supports_operator,
)
from .filter import (
    ConditionValue,
    EntityRef,
    FilterCondition,
    FilterGroup,
    FilterNode,
    Scalar,
    WireGroup,
    is_blank_condition,
    to_api3_hash,
)
from .filter import condition as make_condition
from .filter import group as make_group
from .schema import FieldSchema

__all__ = [
    "ConditionArity",
    "ConditionIssue",
    "ConditionIssueCode",
    "ConditionParts",
    "ConditionValues",
    "FacetCondition",
    "FacetCounts",
    "FacetList",
    "FacetReads",
    "FacetShape",
    "FacetValue",
    "FoundCondition",
    "NO_EMPTY_VALUE",
    "NO_SCHEMA",
    "NodePath",
    "OPERATOR_LABELS",
    "OperatorGroup",
    "OperatorPreset",
    "PresetInput",
    "RelativeDate",
    "RelativeWindow",
    "SortKey",
    "TIME_UNIT_LABELS",
    "ValueEditorKind",
    "append_at",
    "apply_preset",
    "condition_arity",
    "condition_list",
    "condition_parts",
    "condition_values",
    "count_active_conditions",
    "count_conditions",
    "default_condition",
    "default_value_for",
    "describe_condition",
    "empty_value_for",
    "facet_counts",
    "facet_lists",
    "facet_presets",
    "facet_scopes",
    "facet_shape",
    "facet_values",
    "facet_values_from_groups",
    "field_operators",
    "filterable_fields",
    "find_condition",
    "find_facet",
    "from_sort_string",
    "is_grouping_refusal",
    "is_hidden_path",
    "is_pinned",
    "is_sortable",
    "move_at",
    "node_at",
    "operator_label",
    "operator_menu",
    "preset_by_id",
    "preset_id_of",
    "presets_for",
    "relative_from",
    "relative_operator",
    "relative_value",
    "relative_window",
    "remove_at",
    "replace_at",
    "set_facet",
    "set_facet_preset",
    "sortable_fields",
    "supports_empty",
    "time_unit_field",
    "time_unit_label",
    "to_sort_string",
    "validate_condition",
    "value_arity",
    "value_editor_for",
    "with_added_list_value",
    "with_list_value",
    "with_relative_window",
    "without_list_value",
    "without_paths",
]

# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------

#: One label per raw operator, for a type that has no wording of its own.
OPERATOR_LABELS: dict[Operator, str] = {
    "is": "is",
    "is_not": "is not",
    "in": "is any of",
    "not_in": "is none of",
    "contains": "contains",
    "not_contains": "does not contain",
    "starts_with": "starts with",
    "ends_with": "ends with",
    "greater_than": "greater than",
    "less_than": "less than",
    "between": "between",
    "in_last": "in the last",
    "not_in_last": "not in the last",
    "in_next": "in the next",
    "not_in_next": "not in the next",
    "in_calendar_day": "in the calendar day",
    "in_calendar_week": "in the calendar week",
    "in_calendar_month": "in the calendar month",
    "in_calendar_year": "in the calendar year",
    "name_is": "name is",
    "name_contains": "name contains",
    "name_not_contains": "name does not contain",
    "type_is": "type is",
    "type_is_not": "type is not",
}

#: Comparison reads as time on a date and as size on a number.
_TEMPORAL_LABELS: dict[Operator, str] = {"greater_than": "after", "less_than": "before"}


def operator_label(operator: Operator, data_type: str | None = None) -> str:
    """The label a data type puts on an operator."""
    if data_type and is_temporal_type(data_type):
        temporal = _TEMPORAL_LABELS.get(operator)
        if temporal:
            return temporal
    return OPERATOR_LABELS.get(operator, operator)


#: Singular and plural wording for a relative-date unit.
TIME_UNIT_LABELS: dict[TimeUnit, tuple[str, str]] = {
    "HOUR": ("hour", "hours"),
    "DAY": ("day", "days"),
    "WEEK": ("week", "weeks"),
    "MONTH": ("month", "months"),
    "YEAR": ("year", "years"),
}


def time_unit_label(unit: TimeUnit, count: float = 1) -> str:
    pair = TIME_UNIT_LABELS.get(unit)
    if not pair:
        return str(unit).lower()
    return pair[0] if count == 1 else pair[1]


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------

PresetInput = Literal[
    "none",  # the preset pins the value; the row shows no editor
    "scalar",
    "list",
    "range",
    "relative",
    "string",
]


@dataclass
class OperatorPreset:
    """One entry of the operator menu.

    `operator` and, for a pinned preset, `value` are what serialisation sends;
    everything else is wording. A preset whose `id` equals its `operator` is the
    plain operator with no UX layer on it.
    """

    id: str
    label: str
    operator: Operator
    input: PresetInput
    #: The value the preset pins. Meaningful only when `input` is `none`.
    value: ConditionValue = None


@dataclass
class OperatorGroup:
    """A named run of the operator menu."""

    label: str
    presets: list[OperatorPreset] = dc_field(default_factory=list)


class _NoEmptyValue:
    """The type has no empty test at all."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_EMPTY_VALUE"


#: What `empty_value_for` answers where the type has no empty test. `None` is a
#: value here, the spelling `is null`, so the two cannot share one answer.
NO_EMPTY_VALUE = _NoEmptyValue()


def empty_value_for(data_type: str) -> str | _NoEmptyValue | None:
    """The value "is empty" sends on a type, or `NO_EMPTY_VALUE` where the type has none.

    `None` is the spelling on every filterable type but two: uuid takes `""` and
    400s on null, and a checkbox is two-state, never null, and 400s on both
    (field_types/uuid, field_types/checkbox).
    """
    if not is_filterable(data_type) or not supports_operator(data_type, "is"):
        return NO_EMPTY_VALUE
    if data_type == "checkbox":
        return NO_EMPTY_VALUE
    return "" if data_type == "uuid" else None


def supports_empty(data_type: str) -> bool:
    return empty_value_for(data_type) is not NO_EMPTY_VALUE


@dataclass(frozen=True)
class _CalendarPreset:
    id: str
    label: str
    operator: Operator
    offset: int


#: The calendar bucket a date sits in, named. The offset is a bare signed integer
#: relative to today: `0` is the bucket today falls in, `-1` the one before it and
#: `+1` the one after (field_types/date).
_CALENDAR_PRESETS: tuple[_CalendarPreset, ...] = (
    _CalendarPreset("today", "today", "in_calendar_day", 0),
    _CalendarPreset("yesterday", "yesterday", "in_calendar_day", -1),
    _CalendarPreset("tomorrow", "tomorrow", "in_calendar_day", 1),
    _CalendarPreset("this_week", "this week", "in_calendar_week", 0),
    _CalendarPreset("last_week", "last week", "in_calendar_week", -1),
    _CalendarPreset("next_week", "next week", "in_calendar_week", 1),
    _CalendarPreset("this_month", "this month", "in_calendar_month", 0),
    _CalendarPreset("last_month", "last month", "in_calendar_month", -1),
    _CalendarPreset("next_month", "next month", "in_calendar_month", 1),
    _CalendarPreset("this_year", "this year", "in_calendar_year", 0),
    _CalendarPreset("last_year", "last year", "in_calendar_year", -1),
    _CalendarPreset("next_year", "next year", "in_calendar_year", 1),
)


def _input_for(shape: ValueShape) -> PresetInput:
    """The editor a value shape needs."""
    if shape == "list":
        return "list"
    if shape == "range":
        return "range"
    if shape == "relative":
        return "relative"
    if shape == "string":
        return "string"
    if shape in ("calendar", "none"):
        return "none"
    return "scalar"


def _plain_preset(operator: Operator, data_type: str) -> OperatorPreset:
    return OperatorPreset(
        id=operator,
        label=operator_label(operator, data_type),
        operator=operator,
        input=_input_for(VALUE_SHAPE[operator]),
    )


def field_operators(field: FieldSchema | None = None) -> list[Operator]:
    """The operators a field takes: its data type's vocabulary, narrowed by the
    field's own `operators` where the API evaluates fewer of them."""
    all_operators = operators_for(field.data_type if field is not None else "")
    only = field.operators if field is not None else None
    if only is None:
        return list(all_operators)
    return [operator for operator in all_operators if operator in only]


def _group_of(operator: Operator) -> str:
    """Which named run an operator belongs in."""
    if operator in ("is", "is_not", "in", "not_in"):
        return "Is"
    if operator in ("contains", "not_contains", "starts_with", "ends_with"):
        return "Text"
    if operator in ("greater_than", "less_than", "between"):
        return "Compare"
    if operator in ("in_last", "not_in_last", "in_next", "not_in_next"):
        return "Relative"
    return "Link"


_GROUP_ORDER = ("Is", "Text", "Compare", "Relative", "Calendar", "Link", "Empty")


def operator_menu(data_type: str, operators: list[Operator] | None = None) -> list[OperatorGroup]:
    """The operator menu for a data type, grouped.

    Every entry names the raw operator it serialises to; an unfilterable type gets
    an empty menu. `operators` narrows the menu to what the field's own site answers.
    """
    by_group: dict[str, list[OperatorPreset]] = {}
    for preset in presets_for(data_type, operators):
        by_group.setdefault(_preset_group(preset), []).append(preset)
    return [OperatorGroup(label=label, presets=by_group[label]) for label in _GROUP_ORDER if label in by_group]


def _preset_group(preset: OperatorPreset) -> str:
    if preset.id in ("is_empty", "is_not_empty"):
        return "Empty"
    if preset.operator.startswith("in_calendar_"):
        return "Calendar"
    return _group_of(preset.operator)


def presets_for(data_type: str, only: list[Operator] | None = None) -> list[OperatorPreset]:
    """Every menu entry for a data type, in menu order.

    Calendar operators are replaced by their named offsets and never offered raw:
    an integer offset with no wording around it is not a control anyone can read.
    """
    operators = only if only is not None else list(operators_for(data_type))
    if len(operators) == 0:
        return []
    empty = empty_value_for(data_type)
    out: list[OperatorPreset] = []
    # An `image` filter takes null and nothing else: a thumbnail is a presigned URL
    # minted per read, so the only question it answers is has-one (field_types/image).
    if data_type != "image":
        for operator in operators:
            if operator.startswith("in_calendar_"):
                continue
            out.append(_plain_preset(operator, data_type))
        for calendar in _CALENDAR_PRESETS:
            if calendar.operator not in operators:
                continue
            out.append(
                OperatorPreset(
                    id=calendar.id, label=calendar.label, operator=calendar.operator,
                    input="none", value=calendar.offset,
                )
            )
    # uuid spells its empty test `is ""`, which the tree reads as an unfilled row and
    # drops, so the menu cannot offer it; every other type spells it `is null`. A field
    # whose own `operators` narrows the type's vocabulary was measured on those operators
    # with values, never on null: `Note.read_by_current_user` evaluates `is` and `is_not`
    # against `read` and `unread` alone (068_note_read_state), so the empty tests follow
    # the narrowing off the menu.
    if empty is None and not _narrowed(data_type, only) and "is" in operators and "is_not" in operators:
        out.append(OperatorPreset(id="is_empty", label="is empty", operator="is", input="none", value=None))
        out.append(OperatorPreset(id="is_not_empty", label="is not empty", operator="is_not", input="none", value=None))
    return out


def _narrowed(data_type: str, only: list[Operator] | None) -> bool:
    """True where `only` leaves out an operator the data type's own vocabulary holds."""
    if only is None:
        return False
    return any(operator not in only for operator in operators_for(data_type))


def preset_by_id(data_type: str, id: str, operators: list[Operator] | None = None) -> OperatorPreset | None:
    return next((p for p in presets_for(data_type, operators) if p.id == id), None)


def preset_id_of(condition: FilterCondition, data_type: str) -> str:
    """The menu entry a condition currently sits on."""
    operator, value = condition.operator, condition.value
    if value is None and operator in ("is", "is_not") and empty_value_for(data_type) is None:
        return "is_empty" if operator == "is" else "is_not_empty"
    if operator.startswith("in_calendar_"):
        found = next((c for c in _CALENDAR_PRESETS if c.operator == operator and c.offset == value), None)
        if found:
            return found.id
        # An offset with no name of its own still belongs to its calendar operator.
        fallback = next((c for c in _CALENDAR_PRESETS if c.operator == operator), None)
        return fallback.id if fallback else operator
    return operator


def apply_preset(condition: FilterCondition, preset: OperatorPreset, data_type: str) -> FilterCondition:
    """Move a condition onto another menu entry.

    The value survives when the two entries edit the same shape and is reset to the
    type's default otherwise, so switching "is" to "is any of" keeps what was typed
    only where it fits.
    """
    if preset.input == "none":
        return dataclasses.replace(condition, operator=preset.operator, value=preset.value)
    before = VALUE_SHAPE[condition.operator]
    after = VALUE_SHAPE[preset.operator]
    keep = before == after and not is_pinned(condition, data_type)
    return dataclasses.replace(
        condition,
        operator=preset.operator,
        value=condition.value if keep else default_value_for(data_type, preset.operator),
    )


def is_pinned(condition: FilterCondition, data_type: str) -> bool:
    """True when the condition sits on a preset that pins its value, so no editor is drawn."""
    id = preset_id_of(condition, data_type)
    return id in ("is_empty", "is_not_empty") or condition.operator.startswith("in_calendar_")


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------


def default_value_for(data_type: str, operator: Operator) -> ConditionValue:
    """The value a row starts on.

    Blank wherever a person has to supply the value, so a half-built row serialises
    to nothing; filled where the type has only one sensible starting point (a
    checkbox is two-state and never null, and a relative window with no length is
    not a window).
    """
    shape = VALUE_SHAPE[operator]
    if shape == "list":
        return []
    if shape == "range":
        return [None, None]
    if shape == "relative":
        # `[count, UNIT]` with a positive integer count and an uppercase unit
        # (field_types/date); the window includes today.
        return [7, "DAY"]
    if shape == "calendar":
        return 0
    if shape == "string":
        return ""
    return True if data_type == "checkbox" else ""


def default_condition(path: str, data_type: str, operators: list[Operator] | None = None) -> FilterCondition:
    """A blank condition on a field, ready for its value."""
    presets = presets_for(data_type, operators)
    preset = presets[0] if presets else None
    operator: Operator = preset.operator if preset else "is"
    value = preset.value if preset is not None and preset.input == "none" else default_value_for(data_type, operator)
    return FilterCondition(path=path, operator=operator, value=value)


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

#: Between the values of a list, wherever one is spelled out.
_VALUE_SEPARATOR = ", "


def _entity_parts(value: Any) -> tuple[Any, Any, Any] | None:
    """`(type, id, name)` of an entity reference, `None` when the value is not one."""
    if isinstance(value, EntityRef):
        return value.type, value.id, value.name
    if isinstance(value, dict):
        return value.get("type"), value.get("id"), value.get("name")
    return None


def _scalar_label(value: Scalar, field: FieldSchema | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    parts = _entity_parts(value)
    if parts is not None:
        type_, id_, name = parts
        return name if name is not None else f"{type_} #{id_}"
    if isinstance(value, str) and field is not None and field.display_values:
        return field.display_values.get(value, value)
    return str(value)


def _number_of(value: Any) -> float:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    try:
        n = float(str(value))
    except (TypeError, ValueError):
        return math.nan
    return int(n) if n.is_integer() else n


def _value_summary(condition: FilterCondition, field: FieldSchema | None = None) -> str:
    operator, value = condition.operator, condition.value
    shape = VALUE_SHAPE[operator]
    if shape == "list":
        return _VALUE_SEPARATOR.join(_scalar_label(v, field) for v in value) if isinstance(value, list) else ""
    if shape == "range":
        if not isinstance(value, list) or len(value) != 2:
            return ""
        return f"{_scalar_label(value[0], field)} and {_scalar_label(value[1], field)}"
    if shape == "relative":
        if not isinstance(value, list) or len(value) != 2:
            return ""
        count = _number_of(value[0])
        return f"{count} {time_unit_label(value[1], count)}"
    if shape in ("calendar", "none"):
        return ""
    return _scalar_label(value, field)


@dataclass
class ConditionParts:
    """A condition read as three segments: what is compared, how, and against what."""

    field: str
    operator: str
    #: Empty when the operator pins its own value, as `is empty` and the calendar presets do.
    value: str


def condition_parts(condition: FilterCondition, field: FieldSchema | None = None) -> ConditionParts:
    """The three segments of a condition's summary. A pill draws them apart and a
    sentence joins them; both read the same words."""
    data_type = field.data_type if field is not None else ""
    preset = preset_by_id(data_type, preset_id_of(condition, data_type))
    return ConditionParts(
        field=field.display_name if field is not None else condition.path,
        operator=preset.label if preset is not None else operator_label(condition.operator, data_type),
        value=_value_summary(condition, field),
    )


@dataclass
class ConditionValues:
    """A condition's values, as much of them as a pill has room to name."""

    #: The values the pill names, in order.
    shown: list[str] = dc_field(default_factory=list)
    #: Values past `shown`, which the pill reads as `+n`.
    overflow: int = 0
    #: Every value, comma-joined, for the tooltip a truncated pill carries.
    title: str = ""
    #: The shown values as one line, for a pill that spells its values rather than drawing them.
    text: str = ""
    #: The scalar behind each shown value, for a pill that draws its values rather than spelling them.
    values: list[Scalar] = dc_field(default_factory=list)


def condition_values(condition: FilterCondition, field: FieldSchema | None = None, max: int = 2) -> ConditionValues:
    """A condition's values as a pill reads them: the first `max`, a count of the rest,
    and the whole list for the tooltip.

    A condition on any other shape than a list has one value and no overflow, so a
    pill draws it whole.
    """
    title = _value_summary(condition, field)
    if VALUE_SHAPE[condition.operator] != "list" or not isinstance(condition.value, list):
        return ConditionValues(shown=[title] if title else [], overflow=0, title=title, text=title, values=[])
    all_values: list[Scalar] = list(condition.value)
    limit = min(max, len(all_values)) if max > 0 else len(all_values)
    shown = [_scalar_label(v, field) for v in all_values[:limit]]
    return ConditionValues(
        shown=shown,
        overflow=len(all_values) - limit,
        title=title,
        text=_VALUE_SEPARATOR.join(shown),
        values=all_values[:limit],
    )


def describe_condition(condition: FilterCondition, field: FieldSchema | None = None) -> str:
    """One line naming what a condition matches, such as `Status is any of Approved, Final`.

    Without a schema the field's dotted path stands in for its label and codes stand
    in for their display values.
    """
    parts = condition_parts(condition, field)
    head = f"{parts.field} {parts.operator}"
    return f"{head} {parts.value}" if parts.value else head


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

ConditionIssueCode = Literal[
    "no-field", "unknown-field", "unfilterable", "unknown-operator", "wrong-shape", "blank-value",
]


@dataclass
class ConditionIssue:
    code: ConditionIssueCode
    message: str


class _NoSchema:
    """No schema is loaded, which suppresses every check that needs one."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_SCHEMA"


#: What `validate_condition` takes where no schema is loaded. `None` means the path
#: resolved to nothing, which is a different answer.
NO_SCHEMA = _NoSchema()


def _shape_holds(shape: ValueShape, value: ConditionValue) -> bool:
    if shape == "list":
        return isinstance(value, list)
    if shape == "range":
        return isinstance(value, list) and len(value) == 2
    if shape == "relative":
        return (
            isinstance(value, list)
            and len(value) == 2
            and isinstance(value[0], (int, float))
            and not isinstance(value[0], bool)
            and isinstance(value[1], str)
        )
    if shape == "calendar":
        return isinstance(value, int) and not isinstance(value, bool)
    if shape == "string":
        return isinstance(value, str)
    if shape == "none":
        return True
    return not isinstance(value, list)


def validate_condition(
    condition: FilterCondition,
    field: FieldSchema | _NoSchema | None = NO_SCHEMA,
) -> list[ConditionIssue]:
    """Everything wrong with one row, in the order a person would fix it. An empty
    list means the row serialises to a filter the API accepts.

    `field` is the schema of the path's last segment. Pass `None` when the path
    resolved to nothing and leave it out when no schema is loaded.
    """
    issues: list[ConditionIssue] = []
    if not condition.path:
        return [ConditionIssue(code="no-field", message="Pick a field.")]
    if field is None:
        return [ConditionIssue(code="unknown-field", message=f"No field at {condition.path}.")]
    schema = field if isinstance(field, FieldSchema) else None
    data_type = schema.data_type if schema is not None else None
    if data_type is not None and not is_filterable(data_type):
        label = schema.display_name if schema is not None else condition.path
        return [ConditionIssue(code="unfilterable", message=f"{label} cannot be filtered on.")]
    if not is_operator(condition.operator):
        issues.append(
            ConditionIssue(code="unknown-operator", message=f"{condition.operator} is not an operator.")
        )
        return issues
    if data_type is not None and not supports_operator(data_type, condition.operator):
        issues.append(
            ConditionIssue(
                code="unknown-operator",
                message=f"{operator_label(condition.operator, data_type)} does not apply to a {data_type} field.",
            )
        )
    shape = VALUE_SHAPE[condition.operator]
    if not _shape_holds(shape, condition.value):
        issues.append(
            ConditionIssue(
                code="wrong-shape",
                message=f"{operator_label(condition.operator, data_type)} needs a {shape} value.",
            )
        )
    elif is_blank_condition(condition):
        issues.append(ConditionIssue(code="blank-value", message="Fill in a value."))
    return issues


# ---------------------------------------------------------------------------
# value editors
# ---------------------------------------------------------------------------

ValueEditorKind = Literal[
    "none", "text", "number", "date", "date_time", "checkbox", "options", "entity", "color", "url",
]


def value_editor_for(data_type: str, operator: Operator) -> ValueEditorKind:
    """Which editor a row draws.

    The operator picks the arity (one value, a list, a range, a relative window) and
    the data type picks the editor inside it.

    A `url` field takes no filter at all, so no field list offers one; the kind is
    here for a tree that carries a path the schema no longer filters on
    (field_types/url).
    """
    shape = VALUE_SHAPE[operator]
    if shape in ("calendar", "none"):
        return "none"
    # `name_*` and `type_*` compare against a plain string whatever the field holds.
    if shape == "string":
        return "text"
    if shape == "relative":
        return "none"
    if data_type == "checkbox":
        return "checkbox"
    if data_type == "date":
        return "date"
    if data_type == "date_time":
        return "date_time"
    if data_type in ("list", "status_list"):
        return "options"
    if is_link_type(data_type):
        return "entity"
    if is_numeric_type(data_type):
        return "number"
    if data_type == "color":
        return "color"
    if data_type == "url":
        return "url"
    return "text"


ConditionArity = Literal["none", "one", "many", "two", "relative"]


def condition_arity(condition: FilterCondition, data_type: str) -> ConditionArity:
    """The arity a row draws: none for a pinned preset, else the operator's own."""
    return "none" if is_pinned(condition, data_type) else value_arity(condition.operator)


def value_arity(operator: Operator) -> ConditionArity:
    """Whether a value editor holds one value or many."""
    shape = VALUE_SHAPE[operator]
    if shape == "list":
        return "many"
    if shape == "range":
        return "two"
    if shape == "relative":
        return "relative"
    if shape in ("calendar", "none"):
        return "none"
    return "one"


# ---------------------------------------------------------------------------
# list values
# ---------------------------------------------------------------------------


def condition_list(value: ConditionValue) -> list[Scalar]:
    """The values a list-shaped condition holds, as a row edits them.

    `in` and `not_in` take a JSON array, so anything else on the condition reads as
    no values yet.
    """
    return list(value) if isinstance(value, list) else []


def with_list_value(value: ConditionValue, index: int, next: Scalar) -> list[Scalar]:
    """The list with one value replaced. An index outside it leaves the list alone."""
    values = condition_list(value)
    if index < 0 or index >= len(values):
        return values
    values[index] = next
    return values


def without_list_value(value: ConditionValue, index: int) -> list[Scalar]:
    """The list with one value dropped."""
    return [v for i, v in enumerate(condition_list(value)) if i != index]


def with_added_list_value(value: ConditionValue) -> list[Scalar]:
    """The list with one more entry on the end, blank.

    A blank entry serialises to nothing: a row whose value is still unfilled is
    dropped rather than sent.
    """
    return [*condition_list(value), ""]


# ---------------------------------------------------------------------------
# relative dates
# ---------------------------------------------------------------------------


@dataclass
class RelativeDate:
    """A relative-date window, as a filter row edits it."""

    count: float
    unit: TimeUnit
    direction: Literal["last", "next"]
    #: Negated windows also match rows where the field is unset (017_filter_operators).
    negated: bool = False


def relative_operator(direction: Literal["last", "next"], negated: bool = False) -> Operator:
    if direction == "next":
        return "not_in_next" if negated else "in_next"
    return "not_in_last" if negated else "in_last"


def relative_value(count: float, unit: TimeUnit) -> list[Any]:
    return [count, unit]


def relative_from(operator: Operator, value: ConditionValue) -> RelativeDate | None:
    """Read a condition back as a relative window, or `None` when it is not one."""
    if VALUE_SHAPE[operator] != "relative":
        return None
    if not isinstance(value, list) or len(value) != 2:
        return None
    return RelativeDate(
        count=_number_of(value[0]),
        unit=value[1],
        direction="next" if operator in ("in_next", "not_in_next") else "last",
        negated=operator in ("not_in_last", "not_in_next"),
    )


@dataclass
class RelativeWindow:
    """The count and the unit a relative row shows."""

    count: float | None
    unit: TimeUnit


def relative_window(value: ConditionValue) -> RelativeWindow:
    """The count and the unit a relative row shows, with the default window for an unfilled one."""
    pair = list(value) if isinstance(value, list) else []
    raw = pair[0] if len(pair) > 0 else None
    count = _number_of(raw) if raw is not None else math.nan
    unit = pair[1] if len(pair) > 1 else None
    return RelativeWindow(
        count=count if not math.isnan(count) and str(raw if raw is not None else "") != "" else None,
        unit=unit if str(unit) in TIME_UNITS else "DAY",
    )


_UNSET: Any = object()


def with_relative_window(value: ConditionValue, count: Any = _UNSET, unit: Any = _UNSET) -> list[Any]:
    """The window with one half replaced. A missing count goes as 1, the smallest the API takes."""
    current = relative_window(value)
    merged_count = current.count if count is _UNSET else count
    merged_unit = current.unit if unit is _UNSET else unit
    return [1 if merged_count is None else merged_count, merged_unit]


def time_unit_field(display_name: str = "Unit") -> FieldSchema:
    """The time units as a field, so a relative row picks its unit with the same list
    control a `list` field uses. Mandatory: a window always has a unit."""
    return FieldSchema(
        name="unit",
        display_name=display_name,
        entity_type="",
        data_type="list",
        editable=True,
        mandatory=True,
        unique=False,
        valid_values=list(TIME_UNITS),
        display_values={unit: time_unit_label(unit, 2) for unit in TIME_UNITS},
    )


# ---------------------------------------------------------------------------
# tree editing
# ---------------------------------------------------------------------------

#: Where a node sits in the tree: the index it holds in each group from the root
#: down. `[]` is the root itself.
NodePath = list


def _child_at(node: FilterNode, index: int) -> FilterNode | None:
    if node.kind != "group" or index < 0 or index >= len(node.conditions):
        return None
    return node.conditions[index]


def node_at(root: FilterNode, path: NodePath) -> FilterNode | None:
    node: FilterNode | None = root
    for index in path:
        if node is None or node.kind != "group":
            return None
        node = _child_at(node, index)
    return node


def _map_child(
    node: FilterNode,
    path: NodePath,
    change: Callable[[list[FilterNode], int], list[FilterNode]],
) -> FilterNode:
    if node.kind != "group" or len(path) == 0:
        return node
    at, rest = path[0], list(path[1:])
    if len(rest) == 0:
        return dataclasses.replace(node, conditions=change(list(node.conditions), at))
    child = _child_at(node, at)
    if child is None:
        return node
    conditions = list(node.conditions)
    conditions[at] = _map_child(child, rest, change)
    return dataclasses.replace(node, conditions=conditions)


def replace_at(root: FilterGroup, path: NodePath, node: FilterNode) -> FilterGroup:
    """A copy of the tree with the node at `path` replaced. The root cannot be replaced this way."""
    if len(path) == 0:
        return node if node.kind == "group" else root

    def change(children: list[FilterNode], index: int) -> list[FilterNode]:
        if 0 <= index < len(children):
            children[index] = node
        return children

    return _map_child(root, path, change)


def remove_at(root: FilterGroup, path: NodePath) -> FilterGroup:
    """A copy of the tree with the node at `path` gone."""
    if len(path) == 0:
        return root

    def change(children: list[FilterNode], index: int) -> list[FilterNode]:
        if 0 <= index < len(children):
            del children[index]
        return children

    return _map_child(root, path, change)


def append_at(root: FilterGroup, path: NodePath, node: FilterNode) -> FilterGroup:
    """A copy of the tree with `node` appended to the group at `path`."""
    target = node_at(root, path)
    if target is None or target.kind != "group":
        return root
    return replace_at(root, path, dataclasses.replace(target, conditions=[*target.conditions, node]))


def move_at(root: FilterGroup, path: NodePath, delta: int) -> FilterGroup:
    """A copy of the tree with the node at `path` moved `delta` places among its siblings."""
    if len(path) == 0:
        return root

    def change(children: list[FilterNode], index: int) -> list[FilterNode]:
        to = index + delta
        if to < 0 or to >= len(children):
            return children
        moved = children.pop(index)
        children.insert(to, moved)
        return children

    return _map_child(root, path, change)


def count_conditions(node: FilterNode) -> int:
    """Conditions in the tree, nested groups included."""
    if node.kind == "condition":
        return 1
    return sum(count_conditions(child) for child in node.conditions)


def count_active_conditions(node: FilterNode) -> int:
    """Conditions that would survive serialisation."""
    if node.kind == "condition":
        return 0 if is_blank_condition(node) else 1
    return sum(count_active_conditions(child) for child in node.conditions)


@dataclass
class FoundCondition:
    at: NodePath
    condition: FilterCondition


def find_condition(root: FilterNode, path: str, at: NodePath | None = None) -> FoundCondition | None:
    """The first condition on a field path, with where it sits."""
    where = list(at) if at is not None else []
    if root.kind == "condition":
        return FoundCondition(at=where, condition=root) if root.path == path else None
    for i, child in enumerate(root.conditions):
        found = find_condition(child, path, [*where, i])
        if found:
            return found
    return None


def without_paths(root: FilterGroup, paths: list[str]) -> FilterGroup:
    """A copy of the tree with every condition on one of `paths` gone.

    A group the pruning emptied goes with it, so the `or` of `is` conditions a facet
    writes leaves nothing behind.
    """
    drop = set(paths)

    def prune(node: FilterNode) -> FilterNode | None:
        if node.kind == "condition":
            return None if node.path in drop else node
        conditions = [c for c in (prune(child) for child in node.conditions) if c is not None]
        if len(node.conditions) > 0 and len(conditions) == 0:
            return None
        return dataclasses.replace(node, conditions=conditions)

    pruned = prune(root)
    return pruned if pruned is not None else dataclasses.replace(root, conditions=[])


@dataclass
class FacetShape:
    """How a facet spells a set of ticked values on a field.

    A field the API evaluates `in` on takes one condition holding the list. A field
    it does not takes one condition per value: `is` joined by `or`, `is_not` joined
    by `and`, which is the same set of rows.
    """

    #: The operator a ticked set writes.
    any: Operator
    #: The operator a negated set writes.
    none: Operator
    #: True where a set of several values is one condition per value.
    spread: bool


def facet_shape(field: FieldSchema | None = None) -> FacetShape:
    operators = field_operators(field)
    if "in" in operators and "not_in" in operators:
        return FacetShape(any="in", none="not_in", spread=False)
    return FacetShape(any="is", none="is_not", spread=True)


@dataclass
class FacetCondition:
    """The node a facet contributes, read back as one checklist."""

    #: Where the node sits in the tree.
    at: NodePath
    #: The condition, or the group of one-value conditions, the facet wrote.
    node: FilterNode
    #: The condition a pill reads. A group of one-value conditions stands in as one
    #: list-shaped condition, so a pill draws every facet the same way. Never serialised.
    summary: FilterCondition
    #: The operator the checklist writes, `in` or `is` and their negations.
    operator: Operator
    #: The values ticked. Empty where the node is not a checklist.
    values: list[Scalar] = dc_field(default_factory=list)
    #: True where the node is a checklist this facet can edit, false where the editor wrote it.
    checklist: bool = False


def _facet_values_of(
    node: FilterNode, path: str, shape: FacetShape, data_type: str, root: bool = False
) -> list[Scalar] | None:
    """The values a node holds as one checklist on `path`, or `None` where it is not one.

    A group qualifies only when every child is a one-value condition on the path; the
    root never does, since a facet writes into the root and never is it.
    """
    if node.kind == "condition":
        if node.path != path or is_pinned(node, data_type):
            return None
        if node.operator in ("in", "not_in"):
            return list(node.value) if isinstance(node.value, list) else None
        if not shape.spread or node.operator not in (shape.any, shape.none):
            return None
        return [node.value]
    if root or not shape.spread or len(node.conditions) == 0:
        return None
    wanted = shape.any if node.logical_operator == "or" else shape.none
    values: list[Scalar] = []
    for child in node.conditions:
        if child.kind != "condition" or child.path != path or child.operator != wanted:
            return None
        if is_pinned(child, data_type):
            return None
        values.append(child.value)
    return values


def _facet_operator_of(node: FilterNode, shape: FacetShape) -> Operator:
    if node.kind == "condition":
        return node.operator
    return shape.any if node.logical_operator == "or" else shape.none


def find_facet(
    root: FilterNode,
    path: str,
    field: FieldSchema | None = None,
    at: NodePath | None = None,
) -> FacetCondition | None:
    """The node a facet contributes on `path`, wherever it sits: the condition it
    wrote, or the group of one-value conditions it wrote on a field the API
    evaluates no `in` on."""
    shape = facet_shape(field)
    data_type = field.data_type if field is not None else ""

    def read(node: FilterNode, where: NodePath) -> FacetCondition | None:
        values = _facet_values_of(node, path, shape, data_type, node is root)
        if values is not None:
            operator = _facet_operator_of(node, shape)
            listed: Operator = "not_in" if operator in (shape.none, "not_in") else "in"
            return FacetCondition(
                at=where, node=node, summary=make_condition(path, listed, values),
                operator=operator, values=values, checklist=True,
            )
        if node.kind == "condition":
            if node.path != path:
                return None
            return FacetCondition(
                at=where, node=node, summary=node, operator=node.operator, values=[], checklist=False
            )
        for i, child in enumerate(node.conditions):
            found = read(child, [*where, i])
            if found:
                return found
        return None

    return read(root, list(at) if at is not None else [])


def set_facet(
    root: FilterGroup,
    path: str,
    values: list[Scalar],
    operator: Operator = "in",
    field: FieldSchema | None = None,
) -> FilterGroup:
    """Set the condition a facet contributes: replaced where one exists, appended to
    the root where none does, removed when nothing is ticked.

    `operator` is the list operator the facet holds, spelled out as one `is` per
    value on a field the API evaluates no `in` on.
    """
    shape = facet_shape(field)
    negated = operator in ("not_in", "is_not")
    op = shape.none if negated else shape.any
    found = find_facet(root, path, field)
    if len(values) == 0:
        return remove_at(root, found.at) if found is not None else root
    if not shape.spread:
        next_node: FilterNode = make_condition(path, op, list(values))
    elif len(values) == 1:
        next_node = make_condition(path, op, values[0])
    else:
        next_node = make_group("and" if negated else "or", [make_condition(path, op, v) for v in values])
    return replace_at(root, found.at, next_node) if found is not None else append_at(root, [], next_node)


def _type_field(data_type: str) -> FieldSchema:
    """A schema that carries nothing but a data type, for a caller that has only that."""
    return FieldSchema(
        name="", display_name="", entity_type="", data_type=data_type,
        editable=True, mandatory=False, unique=False,
    )


def set_facet_preset(
    root: FilterGroup,
    path: str,
    preset: OperatorPreset,
    data_type: str,
    field: FieldSchema | None = None,
) -> FilterGroup:
    """A facet's condition moved onto another of its menu entries."""
    known = field if field is not None else _type_field(data_type)
    found = find_facet(root, path, known)
    # A list preset keeps the values and changes only which way the facet spells them.
    if preset.input == "list" and found is not None and found.checklist:
        return set_facet(root, path, found.values, preset.operator, known)
    current = found.summary if found is not None else FilterCondition(path=path, operator="in", value=[])
    next_node = apply_preset(current, preset, data_type)
    return replace_at(root, found.at, next_node) if found is not None else append_at(root, [], next_node)


# ---------------------------------------------------------------------------
# facets
# ---------------------------------------------------------------------------


@dataclass
class FacetValue:
    """One value a facet offers, with how many rows hold it."""

    #: Stable identity for the UI. An entity is `Type:id`; everything else is its own string.
    key: str
    label: str
    #: The value an `in` condition sends.
    value: Scalar
    count: float


@dataclass
class FacetList:
    """What one facet lists, and where its counts came from."""

    values: list[FacetValue] = dc_field(default_factory=list)
    #: The rows the counts were tallied from, where they came from a page of rows rather
    #: than the site's groups. None where every count is the site's own.
    sampled: int | None = None


#: The groups of a `summarize` call grouped on `field` under `filters`.
FacetCounts = Callable[[str, Optional[WireGroup]], "list[SummaryGroup]"]


@dataclass
class FacetReads:
    """What a facet reads: the site's groups, and one page of rows for a field it cannot group."""

    #: One page of rows carrying `fields`, under `filters`.
    sample: Callable[[list[str], WireGroup | None], list[EntityRow]]
    counts: FacetCounts | None = None
    #: Fields the site refused to group, as `Type.field`, held by the caller across reads
    #: so the site is asked once per field. Filled here.
    refused: set[str] | None = None


def _facet_key(value: Scalar) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    parts = _entity_parts(value)
    if parts is not None:
        return f"{parts[0]}:{parts[1]}"
    return str(value)


def _as_entity_ref(value: Any) -> Scalar:
    parts = _entity_parts(value)
    if parts is None:
        return value
    type_, id_, name = parts
    return EntityRef(type=type_, id=id_, name=name if isinstance(name, str) else None)


def _row_values(row: EntityRow, field: FieldSchema) -> list[Scalar]:
    value = row.values.get(field.name)
    if is_link_type(field.data_type):
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        return [_as_entity_ref(item) for item in items if item is not None]
    return [] if value is None else [value]


def _facet_vocabulary(field: FieldSchema) -> list[Scalar]:
    """The values a facet always offers, at zero: a list's vocabulary and a checkbox's two states."""
    codes: list[Scalar] = list(field.valid_values or [])
    if field.data_type == "checkbox":
        codes.extend((True, False))
    return codes


def _facet_label(value: Scalar, field: FieldSchema) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    parts = _entity_parts(value)
    if parts is not None:
        type_, id_, name = parts
        return name if name is not None else f"{type_} #{id_}"
    text = str(value)
    return field.display_values.get(text, text) if field.display_values else text


class _FacetTally:
    """A tally, most common first."""

    def __init__(self, field: FieldSchema) -> None:
        self._field = field
        self._found: dict[str, FacetValue] = {}
        for code in _facet_vocabulary(field):
            self.add(code, 0)

    def add(self, value: Scalar, count: float, label: str | None = None) -> None:
        key = _facet_key(value)
        if key == "":
            return
        at = self._found.get(key)
        if at is not None:
            at.count += count
        else:
            self._found[key] = FacetValue(
                key=key,
                label=label if label is not None else _facet_label(value, self._field),
                value=value,
                count=count,
            )

    def values(self) -> list[FacetValue]:
        return sorted(self._found.values(), key=lambda v: (-v.count, v.label))


def facet_values(rows: list[EntityRow], field: FieldSchema) -> list[FacetValue]:
    """The values a facet offers, tallied from a page of rows.

    The site vocabulary of a `list` or `status_list` field comes from the schema so a
    value nobody holds still appears at zero; every other type can only be discovered
    from the rows that were read, so its list is as complete as the page size allowed.
    """
    tally = _FacetTally(field)
    for row in rows:
        for value in _row_values(row, field):
            tally.add(value, 1)
    return tally.values()


def facet_values_from_groups(groups: list[SummaryGroup], field: FieldSchema) -> list[FacetValue]:
    """The values a facet offers, from the groups of a `summarize` call grouped on its field.

    A group is keyed on `group_value`, which on an entity field is the reference
    itself, so two people sharing a display name stay two rows, and `group_name` is
    the label. The `''` group, the rows with nothing in the field, is left out: the
    empty tests belong to the dialog (020_summarize). A multi_entity group's value is
    the row's set of links, and it counts towards each of them; the corpus has not
    measured that grouping.
    """
    tally = _FacetTally(field)
    for group_row in groups:
        for value in _group_scalars(group_row.group_value, group_row.group_name):
            tally.add(value, _group_count(group_row))
    return tally.values()


def _group_scalars(value: Any, name: str) -> list[Scalar]:
    """`group_value` as the values a condition sends: an entity as a reference, a code as itself."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[Scalar] = []
        for one in value:
            out.extend(_group_scalars(one, name))
        return out
    parts = _entity_parts(value)
    if parts is not None:
        type_, id_, own = parts
        if not isinstance(type_, str) or not isinstance(id_, int) or isinstance(id_, bool):
            return []
        return [EntityRef(type=type_, id=id_, name=own if isinstance(own, str) else name)]
    if isinstance(value, (str, int, float, bool)):
        return [value]
    return []


def _group_count(group_row: SummaryGroup) -> float:
    """The `id count` of a group, or the first summary the call asked for."""
    summaries = group_row.summaries or {}
    if "id" in summaries:
        count = summaries["id"]
    else:
        count = next(iter(summaries.values()), None)
    return count if isinstance(count, (int, float)) and not isinstance(count, bool) else 0


def facet_counts(client: SgClient, entity_type: str) -> FacetCounts:
    """The `counts` reader over a client: one `summarize` call grouped on the field."""

    def read(field: str, filters: WireGroup | None) -> list[SummaryGroup]:
        options = SummarizeOptions(filters=filters, grouping=[SummaryGrouping(field=field)])
        return client.summarize(entity_type, options).groups

    return read


def facet_scopes(
    value: FilterGroup, base: FilterGroup | None, facets: list[str]
) -> dict[str, WireGroup | None]:
    """The filter each facet counts against: the base filter and the whole tree, less the
    facet's own conditions, so a facet keeps every value it could switch to while the
    others show what remains.

    Keyed by facet name; a facet nobody ticked shares the whole tree with its neighbours.
    """
    out: dict[str, WireGroup | None] = {}
    for name in facets:
        own = without_paths(value, [name])
        if base is None:
            scope: FilterNode = own
        elif len(own.conditions) == 0:
            scope = base
        else:
            scope = make_group("and", [base, own])
        out[name] = to_api3_hash(scope)
    return out


def is_grouping_refusal(error: Any) -> bool:
    """True where the site refused to group the field: a 4xx.

    The measured refusal is 400 `Grouping is not allowed for field <Type>.<field>.`
    (field_types/image, field_types/summary); the status decides, never the wording.
    """
    return isinstance(error, SgApiError) and 400 <= error.status < 500


def facet_lists(
    fields: list[FieldSchema],
    scopes: dict[str, WireGroup | None],
    reads: FacetReads,
) -> dict[str, FacetList]:
    """What every facet lists, each counted under its own scope.

    With `counts`, a field's values come from the site's groups, and a field the site
    refuses to group is tallied from one page of rows instead, with the schema's
    vocabulary at zero and `sampled` saying how many rows; the refusal is kept in
    `refused` so the next read tallies that field without asking. Without `counts`
    every field is tallied that way. Facets sharing a scope share one page. Any other
    failure fails the read.
    """
    out: dict[str, FacetList] = {}
    tallied: list[FieldSchema] = []
    counts = reads.counts
    refused = reads.refused if reads.refused is not None else set()
    if counts is not None:
        for field in fields:
            known = f"{field.entity_type}.{field.name}"
            if known in refused:
                tallied.append(field)
                continue
            try:
                groups = counts(field.name, scopes.get(field.name))
            except Exception as error:
                if not is_grouping_refusal(error):
                    raise
                refused.add(known)
                tallied.append(field)
                continue
            out[field.name] = FacetList(values=facet_values_from_groups(groups, field))
    else:
        tallied.extend(fields)
    pages: dict[str, list[FieldSchema]] = {}
    for field in tallied:
        key = json.dumps(scopes.get(field.name), sort_keys=True, default=str)
        pages.setdefault(key, []).append(field)
    for page in pages.values():
        rows = list(reads.sample([f.name for f in page], scopes.get(page[0].name)))
        for field in page:
            out[field.name] = FacetList(values=facet_values(rows, field), sampled=len(rows))
    return out


def facet_presets(data_type: str, field: FieldSchema | None = None) -> list[OperatorPreset]:
    """The menu a facet pill's operator segment offers: the operators that take the
    checklist's list of values, and the empty tests, which take none.

    A field the API evaluates no `in` on still offers both list entries, since the
    facet spells a list out as one condition per value.
    """
    lists = [p for p in presets_for(data_type) if p.input == "list"]
    empties = [
        p
        for p in presets_for(data_type, field_operators(field) if field is not None else None)
        if p.id in ("is_empty", "is_not_empty")
    ]
    return [*lists, *empties]


# ---------------------------------------------------------------------------
# sort
# ---------------------------------------------------------------------------

#: Types a `sort` may name. Sorting is a silent 200 no-op on `summary`, `url` and
#: `password`, and a 400 on `uuid` and `pivot_column`; `calculated` sorts correctly
#: even though it cannot be filtered (026_result_order, reports/003).
_UNSORTABLE = frozenset(("summary", "url", "password", "serializable", "uuid", "pivot_column"))


def is_sortable(data_type: str) -> bool:
    return data_type not in _UNSORTABLE


def sortable_fields(
    fields: dict[str, FieldSchema], hide_paths: list[str] | None = None
) -> list[FieldSchema]:
    """Fields a sort picker may offer, sorted by display name."""
    kept = [
        f
        for f in fields.values()
        if is_sortable(f.data_type) and not is_hidden_path(f.name, hide_paths)
    ]
    return sorted(kept, key=lambda f: (f.display_name, f.name))


@dataclass
class SortKey:
    #: Field name or dotted path.
    field: str
    direction: Literal["asc", "desc"]


def to_sort_string(keys: list[SortKey]) -> str:
    """The `sort` string a search takes: field names comma-joined, each descending one
    prefixed with `-`.

    A leading `+` and a trailing ` desc` are both 400s, and id ascending is the
    implicit tiebreak (026_result_order).
    """
    return ",".join(f"-{k.field}" if k.direction == "desc" else k.field for k in keys if k.field)


def from_sort_string(sort: str | None) -> list[SortKey]:
    if not sort:
        return []
    parts = [p.strip() for p in sort.split(",")]
    return [
        SortKey(field=p[1:], direction="desc") if p.startswith("-") else SortKey(field=p, direction="asc")
        for p in parts
        if p
    ]


# ---------------------------------------------------------------------------
# fields
# ---------------------------------------------------------------------------


def is_hidden_path(path: str, hide_paths: list[str] | None) -> bool:
    """A path pattern hides the exact path and everything under it."""
    if not hide_paths:
        return False
    return any(path == pattern or path.startswith(f"{pattern}.") for pattern in hide_paths)


def filterable_fields(
    fields: dict[str, FieldSchema],
    hide_paths: list[str] | None = None,
    data_types: list[DataType] | None = None,
) -> list[FieldSchema]:
    """Fields a filter row may choose, sorted by display name."""
    kept = [
        f
        for f in fields.values()
        if is_filterable(f.data_type)
        and not is_hidden_path(f.name, hide_paths)
        and (data_types is None or f.data_type in data_types)
    ]
    return sorted(kept, key=lambda f: (f.display_name, f.name))
