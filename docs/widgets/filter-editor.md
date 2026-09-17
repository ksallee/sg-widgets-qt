---
title: FilterEditor
description: A Flow Production Tracking filter tree, edited as rows and nested groups.
---

Edits a filter tree. A row is a field, an operator and a value; groups nest under All or Any. The
field is chosen with FieldPicker, so a row may filter through a link on a dotted path, and the value
control comes from the field's data type. The value is a `FilterGroup`, which `toApi3Hash` serialises
to the body `_search` takes.

## Install

```python
from sg_widgets_qt.widgets.filter_editor import FilterEditor
```

::demo{name="filter-editor" title="FilterEditor: a nested tree on Version with its serialised filter, a Note read-state row, and sizes"}

A row is one 36px line: the field, the operator, the value and, on its own axis at the end, the
remove control. A group is a header, its rows and a foot. The header carries the All and Any toggle
and, on a nested group, the control that removes it; the rows hang off one rail, so a level of
nesting reads as one indent; the foot carries the add-condition and add-group controls.

## Props

::props{name="filter-editor" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

## Events

::props{name="filter-editor" kind="events"}

## Value editors

The operator picks the arity and the field's data type picks the control inside it.

| data type | editor |
|---|---|
| `number`, `float`, `percent`, `duration`, `timecode`, `currency` | NumberEditor |
| `date` | DateEditor |
| `date_time` | DateTimeEditor |
| `list` | ListPicker on one value, ListMultiPicker on is any of and is none of |
| `status_list` | StatusPicker on one value, StatusMultiPicker on is any of and is none of |
| `checkbox` | CheckboxEditor |
| `color` | ColorEditor |
| `url` | UrlEditor |
| `text`, and any field under name is, name contains, type is | TextEditor |
| `entity`, `multi_entity` | EntityPicker on one value, EntityMultiPicker on is any of and is none of |

Inside a row the date, date-time, number and colour editors take their inline form: the width the
data type needs, and no zone line under a date-time. A date and a date-time are the same picker
button here as anywhere else, with the calendar in its popover. Between draws both ends on one line.

Arity comes first. An operator that carries its own value — is empty, is not empty, today, this week,
last month — draws no editor. In the last and in the next draw a count in a NumberEditor and a unit
in a ListPicker. Between draws two of the data type's editor. Is any of and is none of on a date, a
number or a text field draw one value to a line, each in the data type's own editor, with a control
that removes it and one that adds another; a blank value is dropped on serialisation rather than
sent.

A duration is typed as `1h 30m`, `1:30` or `90` and stored as the 90 minutes all three mean.

## Slots

::props{name="filter-editor" kind="slots"}

The field chooser is FieldPicker unless the slot replaces it. The value editor slot replaces every
control in the table above; the entity slot replaces only the two entity pickers, for a caller that
wants its own row or its own search.

## Keyboard

::props{name="filter-editor" kind="keyboard"}

## Operators

The menu shows wording, not wire names. Every entry names one raw operator.

| menu entry | operator | value sent |
|---|---|---|
| is | `is` | one value of the field's kind |
| is not | `is_not` | one value |
| is any of | `in` | a list |
| is none of | `not_in` | a list |
| contains, does not contain, starts with, ends with | `contains`, `not_contains`, `starts_with`, `ends_with` | one string |
| greater than / after | `greater_than` | one value, strict |
| less than / before | `less_than` | one value, strict |
| between | `between` | two values, inclusive both ends |
| in the last, not in the last | `in_last`, `not_in_last` | `[count, UNIT]`, count positive |
| in the next, not in the next | `in_next`, `not_in_next` | `[count, UNIT]` |
| today, yesterday, tomorrow | `in_calendar_day` | `0`, `-1`, `1` |
| this week, last week, next week | `in_calendar_week` | `0`, `-1`, `1` |
| this month, last month, next month | `in_calendar_month` | `0`, `-1`, `1` |
| this year, last year, next year | `in_calendar_year` | `0`, `-1`, `1` |
| is empty | `is` | `null` |
| is not empty | `is_not` | `null` |
| name is, name contains, name does not contain | `name_is`, `name_contains`, `name_not_contains` | one string |
| type is, type is not | `type_is`, `type_is_not` | a type name |

Which entries appear is decided by the field's `data_type`.

## API behaviour

The operator vocabulary is per data type, and a wrong operator is a 400 naming the legal set
(017_filter_operators). Six data types take no filter at all — `url`, `serializable`, `calculated`,
`summary`, `password` and `pivot_column` — and are left out of the field list; `pivot_column`
advertises `is` and `is_not` and then rejects both.

Groups serialise to `{logical_operator, conditions}` with both keys required, `and` and `or` in
lowercase and nothing else, and no negation operator; nesting is safe to 265 levels
(030_complex_filters). A group with no conditions matches every row, so an empty tree serialises to
`null` rather than to an empty filter.

`in_calendar_day`, `_week`, `_month` and `_year` take a signed offset from the current bucket, `0`
being this one, not a count (field_types/date). `in_last` and `in_next` take `[count, UNIT]` with a
positive integer and an uppercase unit out of `HOUR`, `DAY`, `WEEK`, `MONTH`, `YEAR`; a window with
no count sends `1`, the smallest the API takes. `between` is inclusive at both ends and
order-insensitive.

A colour is the decimal `r,g,b` the field stores, with no spaces and no `#`; hex is rejected inside a
filter as it is on write (field_types/color).

An entity value is a `{type, id}` hash under `is` and a list of them under `in`; a list under `is` is
a 400 (field_types/entity). A status or list value is the raw code, never the display label
(field_types/status_list).

Every negating operator — `is_not`, `not_in`, `not_contains`, `not_in_last`, `not_in_next`,
`name_not_contains`, `type_is_not` — also matches rows where the field is unset, while `greater_than`
and `less_than` exclude them. To mean "has a value and is not X", add a second `is not empty` row.

A checkbox is two-state and never null, so it has no empty test: `is null` on one is a 400
(field_types/checkbox). An `image` field takes `null` and nothing else, so its only entries are the
empty pair (field_types/image). A `uuid` field spells its empty test `is ""`, which this editor reads
as an unfilled row, so it offers no empty entry there (field_types/uuid).

Dates are `YYYY-MM-DD` and date-times `YYYY-MM-DDTHH:MM:SSZ`, always UTC; an epoch integer and a
slashed date are both 400s (field_types/date, field_types/date_time).

A dotted path filters through a link, and the middle segment names the type it travels through:
`entity.Shot.sg_sequence` reads Shot from Version's Link field. Only a single `entity` field is
descended into; a path through a `multi_entity` field reads back nothing, 200 with the key absent
(probe 016).

## Reference

The row and group anatomy follows ReUI's Filters 2.5.2: the field, operator and value cells on one
band and the row's trailing control on a second, so the trailing controls of every row share an axis
whatever the depth. The chip wording follows bazza/ui's data-table-filter 2025.04.12. The named
buckets around today come from Dice UI's data table config, its `isRelativeToToday` date operator
(`docs/config/data-table.ts`, commit `6e0ab98`), mapped onto the calendar operators this API
documents. None of the three is installed.

## EntityFields

One entity type's fields, read through the context and kept. Every row of the editor asks it what a
path is, so the chooser, the operator list and the value control all read one answer. The schema
service caches, so this reaches the network once per type however often the editor redraws
(probe 002).
