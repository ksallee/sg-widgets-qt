---
title: ColumnPicker
description: The columns of a grid as a field picker over the ordered list it fills, each row dragged into place.
---

Chooses the columns of a grid. A field picker sits over the list of chosen paths; picking a field
appends it, and each row is dragged into the order the columns will be drawn in.

It sits on the Popover rather than the shared picker control, for the same reason the sort picker
does: its popup is an editor over an ordered list. It keeps the picker contract of design rule 7 all
the same, and `tools/drives/picker-contract.js` is the proof.

Single and multi: this picker is the ordered multi of [FieldPicker](field-picker.md), an
array of paths ordered by drag, where the field picker takes one path.

## Install

```python
from sg_widgets_qt.widgets.column_picker import ColumnPicker
```

::demo{name="column-picker" title="ColumnPicker: the default list, a picker restricted to dates, the dual layout, disabled and read-only"}

## Props

::props{name="column-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

Picking a field appends its path to the end of the list and clears the picker, which takes focus
back for the next one. A path already chosen is off the list, so a column is never added twice.

Each row carries a grip, the friendly path with the raw path in its tooltip, and a remove button.
A row is reordered by dragging its grip, which lifts the row and opens a gap where it will land,
or from the keyboard: Space on the grip picks the row up, the arrow keys move it, and Space drops
it. Alt with an arrow key moves the row holding focus one place. Every step is announced in a live
region. Reduced motion keeps the reordering and drops the movement.

A link field carries a chevron that descends into the type it points at, and the breadcrumb above
the search box goes back one level or all the way to the root. A link declaring several target
types asks which one first. `dataTypes` and `validTypes` bind what may be chosen, not what may be
walked through, so a picker restricted to dates still reaches a date behind a link.

`layout="dual"` puts the fields of the type in a checked list beside the chosen paths. Checking a
row appends its path; unchecking removes it. The two lists sit side by side from a width of 32rem
and stack under it, measured on the widget rather than on the window, so a column picker in a
narrow panel stacks on a wide page.

## Events

::props{name="column-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="column-picker" kind="keyboard"}

Dragging a grip moves the row under the pointer once it has travelled four pixels; the list scrolls
when the pointer nears an edge, and `Escape` cancels the drag.

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
::qt-note

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
