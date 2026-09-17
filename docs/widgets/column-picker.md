---
title: ColumnPicker
description: The columns of a grid as a field picker over the ordered list it fills, each row dragged into place.
---

Chooses the columns of a grid. A field picker sits over the list of chosen paths; picking a field
appends it, and each row is dragged into the order the columns will be drawn in.

A field picker sits over the chosen list, so the popup, its press rule and its keyboard are the
shared picker control's. The picker contract of design rule 7 holds on it, and
`tests/qt/test_picker_contract.py` is the proof.

Single and multi: this picker is the ordered multi of [FieldPicker](field-picker.md), an
array of paths ordered by drag, where the field picker takes one path.

## Install

```python
from sg_widgets_qt.widgets.column_picker import ColumnPicker
```

::demo{name="column-picker" title="ColumnPicker: the default list, a picker restricted to dates, the dual layout, disabled and read-only"}

## Props

::props{name="column-picker" kind="props"}

Every prop is a keyword argument, a property of the same name and a `set_<name>` method, so a
value handed in at construction can be changed afterwards.

Picking a field appends its path to the end of the list and clears the picker, which takes focus
back for the next one. A path already chosen is off the list, so a column is never added twice.

Each row carries a grip, the friendly path with the raw path in its tooltip, and a remove control.
A read-only list is the labels alone: no grip, none of its inset, and no cross. A disabled one
keeps both, drawn inert.

A row is reordered by dragging its grip, which moves the row under the pointer as it crosses each
neighbour's midpoint, or from the keyboard: Space on the list picks the row under the cursor up,
the arrow keys move it, and Space drops it. Alt with an arrow key moves the row without picking it
up, and Delete removes it. Every step is written to the list's accessible description, which is
this port's live region.

`value_changed` carries the new order once per gesture: a keyboard move emits on every arrow, a
drag emits on the release alone and never while the rows are giving way, and a drag cancelled with
`Escape` emits nothing at all.

A link field carries a chevron that descends into the type it points at, and the breadcrumb above
the search box goes back one level or all the way to the root. A link declaring several target
types asks which one first. `data_types` and `valid_types` bind what may be chosen, not what may be
walked through, so a picker restricted to dates still reaches a date behind a link.

`layout='dual'` puts the fields of the type in a checked list beside the chosen paths. Checking a
row appends its path; unchecking removes it. A row there is one line — a checkbox, the field's
glyph, its display name and its programmatic name where the two differ — rather than the field
picker's two. The two lists sit side by side from a width of 512
pixels and stack under it, measured on the widget rather than on the window, so a column picker in
a narrow panel stacks on a wide page.

## Events

::props{name="column-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="column-picker" kind="keyboard"}

Dragging a grip moves the row under the pointer once it has travelled four pixels; the list scrolls
when the pointer nears an edge, and `Escape` cancels the drag. The chosen list takes the keyboard,
so `Tab` reaches it once and the arrows walk its rows rather than the grip of each one.

## API behaviour

`GET /schema/<Type>/fields` is 48KB and about 330ms per type, so the schema service caches it: a hop
back to a type already visited costs nothing, and a list of ten paths over three types costs three
reads (002_schema).

Only single entity fields are descended into. A dotted path through a multi-entity field reads back
nothing, 200 with the key absent from `attributes` (probe 016). A type already on the path is never
offered again, so a path cannot loop.

Every path is resolved for display through the schema of each type it travels, and a path the schema
no longer holds stays readable as itself rather than disappearing.

## Reference

Reordering follows ReUI's Sortable 2.5.2 for the grip and the lifted row, and Dice UI's Sortable,
its shadcn registry item, for the live-region copy and the keyboard model. Neither is installed. The
pointer behaviour, a four-pixel activation distance with midpoint hit-testing and edge auto-scroll,
follows dnd-kit 6.3.1.

The measurements and the announced lines are `sg_widgets_core.sortable`, which both packages share;
the gesture itself runs on a `QListView` with this package's row delegate, so the grip, the label
and the remove control are painted rather than three widgets in a row.

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
