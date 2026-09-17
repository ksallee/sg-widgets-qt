---
title: CollectionControl
description: The source, the selection and the cursor every collection is built on.
---

The model under the entity table, the entity grid and the grouped list: a source and its paging, a
selection, a keyboard cursor, and a virtualiser over whatever lines a layout draws. A collection built
on it supplies its layout and its markup.

## Install

```python
from sg_widgets_qt.widgets.collection_control import CollectionControl
```

::demo{name="collection-control" title="CollectionControl: a queue of shots drawn straight off the base"}

The demo is a collection of its own, not one of the three widgets. It holds a source of shots, draws
one row per shot with a checkbox, and puts the footer under them. The three paging modes change what
walks the set; nothing else in the demo changes with them.

## The source

A collection holds a source and follows the snapshot it publishes: the rows, the read's status, the
error a failed read carried, whether another page exists, and the total the last count answered. The
base loads an idle source, keeps the source's mode on `paging`, and mirrors `sort` and `filters` both
ways, so a sort picker and a filter bar drive the same rows the collection draws.

`source` and `paging` are the two options a collection has to pass. Each of the three carries its own
default for `paging`.

## Paging

`paging` says how the set is walked, and the source follows it rather than the other way round.
`pages` reads one page at a time and the footer gets its size, its range and its arrows. `more` appends
a page under the rows behind a load-more control. `scroll` appends the next page as the body nears its
end, watched by a sentinel under the last row.

Under the rows sits one block at a time: the failed page with its retry, the skeleton of a page on the
way, the load-more control, or the scroller's sentinel. In place of the rows sits one of four things:
the error line, skeletons, the empty line, or the rows themselves. A read that failed with rows already
loaded keeps those rows and puts the error under them.

## The selection

The selection is a list of references, two-way. A row is added or dropped by reference, so a selection
survives a page that redrew the rows. `get_row_id` keys a row in the model and in the selection, and
defaults to the type and the id. `is_row_disabled` marks a row the selection refuses and the cursor
steps over.

A header control reads the selection over the loaded rows as a tri-state — all, some, or none — and
takes or drops every row that is not disabled. A page of nothing but disabled rows is neither all nor
some.

## The cursor

A collection is one tab stop. The cursor is the row that holds it, and it never lands on a disabled
row. Moving the cursor focuses the row with `preventScroll` and brings it into view.

The arrow that steps past the last loaded row asks for the next page in `more` and `scroll`. The
cursor stays where it is until those rows arrive, then lands on the first of them. A read that failed
gives the cursor back where it was.

## The shared model

Qt has models, so the lines the three layouts draw are one `QAbstractTableModel`. `CollectionModel`
holds the rows the source published, the resolved columns, and the group headings a `group_by` puts
between them; it answers the roles `RowDelegate` and the table's cell delegate read, and it says
which line a row sits on and which row the viewport ends on given the last line it drew.

A view draws only the lines on screen at any length, so `virtualize_after` is kept for parity and
changes nothing. The scroller is the view's own vertical bar: the last line it reaches becomes the
last row, and the base decides from there whether to ask for the next page.

A table's line is a row, or a group heading spanning the table. A grid's line is a tile, and the
flow says how many sit across, so the threshold is still measured in rows. A grouped list's lines
are its headings and its rows as one stream, so a heading on screen only makes the scroller ask for
the next page later.

## Props

::props{name="collection-control" kind="props"}

## Events

::props{name="collection-control" kind="events"}

## CollectionSource

The binding between a collection and its source, and the half of the base a widget can take on its
own. It follows the snapshot, loads an idle source, keeps the mode on `paging`, and carries `sort` and
`filters` in both directions. Each pair is one change out of the source and one into it, so a change
travels once and the two sides never write to each other. It also answers the retry a failed page
needs: the page a pager is on, or the page that was being appended.

::props{name="collection-source" kind="props"}

## CollectionFooter

The footer every collection that pages draws. In `pages` it holds the page size, the range and the
arrows, with a page number that goes to that page on Enter. In `more` and `scroll` it holds the loaded
count. The numbers come from one place, so the three collections cannot report the set differently.

`slot_name` prefixes every object name in the footer, so a table's footer is `entity-table-footer`
and its range `entity-table-range`.

::props{name="collection-footer" kind="props"}

## Composing a collection

A collection is one object here rather than two calls. `CollectionControl` holds the binding, the
shared model, the selection, the cursor and the paging triggers; a widget builds one, draws a view
over `control.model`, and connects `changed` to its own redraw. Every read runs on a pool of one
thread and the snapshot crosses back on a queued signal, so a widget only ever reads on the thread
it draws on.

A sort or a filter has two doors. `set_sort` and `set_filters` take what the caller already knows
and report nothing; `apply_sort` and `apply_filters` are the widget's own controls, a header click
or a sort picker, and those are reported back out. That is how a change travels once and the two
sides never write to each other.

What the widget still owns is its markup: the box, the row, the header, the empty and error lines, and
the keys its shape implies. The root box and the regions beside it come from the base as two class
strings, so the table, the grid and the grouped list sit the same way on a page.
