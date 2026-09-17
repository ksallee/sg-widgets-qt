---
title: StateLine
description: The empty and error line a data widget draws in place of its rows.
---

One centred line with a glyph in front of it, drawn wherever a data widget has no rows to show.

## Install

```python
from sg_widgets_qt.widgets.state_line import StateLine
```

::demo{name="state-line" title="StateLine: empty and error, in a popup list, in a table body, and under rows already drawn"}

## The three states

A data widget shows one of three things in place of its rows.

A read that returned nothing is the empty line, muted. A read that failed is the error line, in the
destructive tone. A read in flight is neither: it is skeletons shaped like the rows they stand in
for, so a list holds its place when the data lands. That shape belongs to the widget that knows it,
so this line covers the other two.

The label is the caller's. Core settles the defaults, and an error falls back to what the read said
and then to a fixed line, so a failure is never a blank block. The line truncates and carries the
whole label as its title.

Anything passed after the line sits beside it, which is where a failed page puts its retry control.

The root carries the state as a data attribute, and the `data-slot` name the widget gives it, so one
widget's empty line is addressable on its own.

## Padding

`pad` is the room the line takes.

`popover` is the inset of a popup list, `table` the inset of a table or a grid body, and `none` is
for a line under rows already drawn, where the block around it owns the inset. The three match
design rule 5, so every widget on a page leaves the same room around the same line.

## The live region beside it

A popup list carries a live region of its own, saying what the list is doing: the read in flight,
the count it answered, the empty line, or what a failed read said. That is what a reader hears, and
this line is what a reader sees. The two are never the same element (design rule 9), so a screen
reader is told about a list that answered as well as one that did not.

## Props

::props{name="state-line" kind="props"}

## Where it is drawn

Every widget in this registry that reads rows draws this line: the popup of a picker and of a
search, the body of a table and of a grid, a tree, a grouped list, a card, and the field and column
pickers. A widget passes its own label, its own glyph and the padding its surface asks for, and
nothing else changes between them.

Here the line is one painted `QWidget`, so there is no data attribute: `state` and `pad` are
keywords, `icon` is a lucide glyph name rather than a component, and `slot_name` is the widget's
object name, which is what a driver finds it by. `apply_state(state, labels, message)` takes the
line core settles for a state, so a widget that already holds a `StateLabels` passes it straight
through.

## Reference

Nothing: the line is a `paintEvent` over the theme's tokens. The demo's wrapping rows are Qt's own
Flow Layout example (`examples/widgets/layouts/flowlayout`), read and not copied.
