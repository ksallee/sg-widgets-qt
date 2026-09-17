---
title: SortPicker
description: The ordered sort keys of a query, and the sort string they serialise to.
---

An ordered list of sort keys. Each is a field and a direction; the list serialises to the `sort`
string `_search` takes. Fields are chosen with FieldPicker, which descends through links, so a key
may be a dotted path.

It sits on the Popover rather than the shared picker control: its popup is an editor over an
ordered list, not a list of values to pick from. It keeps the picker contract of design rule 7 all
the same, and `tools/drives/picker-contract.js` is the proof.

## Install

```python
from sg_widgets_qt.widgets.sort_picker import SortPicker
```

::demo{name="sort-picker" title="SortPicker: two keys over Shot, with the rows they order, and the three sizes beside a button"}

## Props

::props{name="sort-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

## Events

::props{name="sort-picker" kind="events"}

`changed` carries the keys and the string together. `sort_changed` carries the keys alone, for a
page wiring several query widgets to one handler, and `announced` carries the line a live region
reads.

## Slots

None.

## Keyboard

::props{name="sort-picker" kind="keyboard"}

A key is also reordered by dragging its grip: a drop mark shows where it would land, and the move is
announced. Holding `Alt` with `Up` or `Down` on a grip moves the key one place without a drag.

## API behaviour

`sort` is one string: field names comma-joined, a leading `-` marking a descending key, as
`sort=sg_status_list,-id` (026_result_order). The array-of-objects spelling, a leading `+` and a
trailing ` desc` are each a 400. With no sort, rows come back id ascending, and id ascending is the
implicit tiebreak whether or not it is in the list. A dotted path sorts: `entity.Shot.code` reorders
Versions by the shot they link, and `project.Project.name` reverses under `-` (026_result_order).

A sort naming a field that does not exist is a silent 200 in default order, where the same name in a
filter is a 400, so the field list is built from the schema. Sorting a `uuid` or a `pivot_column`
field is a 400 and sorting a `summary`, `url`, `password` or `serializable` field is a silent no-op;
none of them appear in the list. A `calculated` field sorts correctly even though it cannot be
filtered.

`in` does not preserve the order of the ids it was given: rows come back id ascending regardless, so
an explicit id order has to be restored on the client.

## Reference

Reordering follows ReUI's Sortable 2.5.2 for the grip and the lifted row, and Dice UI's Sortable,
its shadcn registry item, for the live-region copy and the keyboard model. Neither is installed. The
pointer behaviour, a four-pixel activation distance with midpoint hit-testing and edge auto-scroll,
follows dnd-kit 6.3.1.

In Qt the grip, the drag and the arrow keys run on `sg_widgets_core.sortable`, which answers where a
drop lands and what the live region is told. The count past one key is a chip beside the trigger
rather than inside it, because the button primitive draws one label.
