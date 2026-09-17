---
title: FieldPicker
description: One field of an entity type, chosen through a searchable list that descends into linked types.
---

Picks one field of an entity type and emits its dotted path, descending through linked types on the
way.

It is built on the shared picker control, so the press rule, the caret, the dismissal guard and
the states are the ones every picker in this package wears. What it adds is the breadcrumb over
the search row, the field glyph per data type, and the friendly path the closed control reads.

Single and multi: this picker takes one path, and [ColumnPicker](column-picker.md) is its
ordered multi, an array of paths ordered by drag.

## Install

```python
from sg_widgets_qt.widgets.field_picker import FieldPicker
```

::demo{name="field-picker" title="FieldPicker: drill-down, restrictions, computed columns, a fixed list and states"}

## Props

::props{name="field-picker" kind="props"}

Every prop is a keyword argument, a property of the same name and a `set_<name>` method, so a
value handed in at construction can be changed afterwards.

The value is a dotted path. A root field is its own code; every hop names the field followed and the
type it landed on, which is the syntax a projection and a filter both take.

```
sg_status_list
entity.Shot.code
project.Project.sg_start_date
```

`data_types` and `valid_types` bind what may be chosen, not what may be walked through. A picker
restricted to dates still lists the link fields, so a date behind a link stays reachable. Everything
else, `exclude`, `hide_paths`, `filterable_only` and `filter`, hides the row outright and is measured
against the full dotted path, so excluding a root field leaves a field of the same name behind a hop
alone.

A link that declares one target type descends at once. One declaring several replaces the list with
one row per type and asks which, and the search box asks `Which type?` while they are on show. A
type already on the path is not offered again, and the path stops at `max_depth`.

`options` fills the list a second way: the paths you name, flat, in the order you give them, each
labelled by its resolved path with its data-type glyph and, under `show_code`, its code. A path the
schema cannot resolve keeps its place, shown as it was written and marked in its sub-label. With
`options` set the list does not nest, so `deep_links`, `max_depth`, `hide_paths`, `exclude`,
`data_types`, `valid_types`, `filterable_only`, `extra_fields` and `filter` do not apply and the
breadcrumb never shows. The search box narrows the flat list on the label and on the path.

The Qt picker reads `options` back as the prop, so the schema rows the nested list derives are
`picker.derived`, which is the name upstream gives that same list inside the component.

The closed control shows the friendly path, the display names joined with a chevron, never the raw
one.

## Events

::props{name="field-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="field-picker" kind="keyboard"}

The search box clears on every hop, on every selection and on every close — from the `Left` key
and from the bar's own Back and Reset alike — and the control is never remounted, so focus stays
where you are typing. The first row of the list is the cursor the moment the list opens, so `Right`
or `Enter` on it acts without a `Down` first.

A row is its display name, the data type under it and the field's glyph drawn on its own, with
no picture box behind it; where the list stands is the breadcrumb bar's to say, so a row behind a
hop never repeats the trail above it. `Down` past the last row comes back to the first, and a
schema read stands behind three skeletons shaped like those two-line rows.

A field list walks a path through links, so the popup carries a breadcrumb above the search row
and a row that descends carries a chevron at its trailing edge, drawn in the row's own drill column
and pressed there. `Left`, `Right` and `Enter` on a link belong to the
levels rather than to the flat list, which is why a descend never closes the popup. The picker
contract of design rule 7 holds all the same, and `tests/qt/test_picker_contract.py` is the proof.

## API behaviour

A dotted path through a `multi_entity` field reads back nothing: HTTP 200 with the key absent from
`attributes`, indistinguishable from no data. Only single `entity` fields are descended into
(016_dotted_multi_entity).

A dotted path names the type it travels through, and a projection checks that middle segment against
the field's `valid_types` (field_types/entity).

`GET /schema/<Type>/fields` is 48KB and about 330ms per type, so the schema service caches it and a
hop back to a type already visited costs nothing (002_schema).

Five data types take no filter operator at all — `url`, `calculated`, `password`, `serializable` and
`summary` — and the API answers `data type cannot be used in a filter` for each. `filterable_only`
drops them (017_filter_operators).

## Reference

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
