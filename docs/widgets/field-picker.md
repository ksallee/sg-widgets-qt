---
title: FieldPicker
description: One field of an entity type, chosen through a searchable list that descends into linked types.
---

Picks one field of an entity type and emits its dotted path, descending through linked types on the
way.

It sits on the Popover over a Command list rather than the shared picker control: its list is a
stack of levels a row descends into, not one flat list of values, and its press, its keyboard
and its dismissal already match the pickers.

Single and multi: this picker takes one path, and [ColumnPicker](column-picker.md) is its
ordered multi, an array of paths ordered by drag.

## Install

```python
from sg_widgets_qt.widgets.field_picker import FieldPicker
```

::demo{name="field-picker" title="FieldPicker: drill-down, restrictions, computed columns and states"}

## Props

::props{name="field-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

The value is a dotted path. A root field is its own code; every hop names the field followed and the
type it landed on, which is the syntax a projection and a filter both take.

```
sg_status_list
entity.Shot.code
project.Project.sg_start_date
```

`dataTypes` and `validTypes` bind what may be chosen, not what may be walked through. A picker
restricted to dates still lists the link fields, so a date behind a link stays reachable. Everything
else — `exclude`, `hidePaths`, `filterableOnly` and `filter` — hides the row outright and is measured
against the full dotted path, so excluding a root field leaves a field of the same name behind a hop
alone.

A link that declares one target type descends at once. One declaring several replaces the list with
one row per type and asks which. A type already on the path is not offered again, and the path stops
at `maxDepth`.

The closed control shows the friendly path, the display names joined with a chevron, never the raw
one.

## Events

::props{name="field-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="field-picker" kind="keyboard"}

The search box clears on every hop, on every selection and on every close, and the control is never
remounted, so focus stays where you are typing.

The control is the Popover and the Command list rather than the picker base: a field list walks a
path through links, so its popup carries a breadcrumb and its rows descend, which the base's flat
list does not. It keeps the picker contract of design rule 7 all the same, and
`tools/drives/picker-contract.js` is the proof.

## API behaviour

A dotted path through a `multi_entity` field reads back nothing: HTTP 200 with the key absent from
`attributes`, indistinguishable from no data. Only single `entity` fields are descended into
(016_dotted_multi_entity).

A dotted path names the type it travels through, and a projection checks that middle segment against
the field's `valid_types` (field_types/entity).

`GET /schema/<Type>/fields` is 48KB and about 330ms per type, so the schema service caches it and a
hop back to a type already visited costs nothing (002_schema).

Five data types take no filter operator at all — `url`, `calculated`, `password`, `serializable` and
`summary` — and the API answers `data type cannot be used in a filter` for each. `filterableOnly`
drops them (017_filter_operators).

## Reference

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
