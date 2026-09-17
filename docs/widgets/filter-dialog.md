---
title: FilterDialog
description: The launcher that opens the filter editor and applies its result in one step.
---

A button that opens the filter editor in a dialog. Edits are staged: only Apply emits.

## Install

```python
from sg_widgets_qt.widgets.filter_dialog import FilterDialog
```

::demo{name="filter-dialog" title="FilterDialog: empty, two filters applied, a Note read-state row, and sizes"}

With no filters it is one Add filters button. With filters applied it becomes Edit filters, carries
the count of conditions that would be sent, and gains a control that clears them without opening
anything.

## Props

::props{name="filter-dialog" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

## Events

::props{name="filter-dialog" kind="events"}

## Slots

The three the editor takes, forwarded unchanged.

::props{name="filter-dialog" kind="slots"}

## Keyboard

::props{name="filter-dialog" kind="keyboard"}

## API behaviour

Apply sends the tree through the same serialiser the editor shows: a tree whose rows are all blank
applies as no filter, because a group with no conditions matches every row (030_complex_filters).
