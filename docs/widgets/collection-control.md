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
survives a page that redrew the rows. `getRowId` keys a row in the DOM and in the selection, and
defaults to the type and the id. `isRowDisabled` marks a row the selection refuses and the cursor
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

## The virtualiser

A body longer than `virtualizeAfter` draws only the lines the viewport reaches, with the space above
and below them held open, so the scrollbar reads the whole set. Below that threshold every line is
drawn and the virtualiser idles.

The scroller is the element the base watches, both for the virtualiser's own range and for the
sentinel that pages on scroll. A layout hands the base that element and the base does the rest.

## What a layout tells the base

The base never knows what a line holds. A layout says how many lines it draws, what those lines are
measured against, how tall a line is before it is drawn, which line a row sits on, which row the
viewport ends on given the last line it drew, and which element takes the cursor.

A table's line is a row. A grid's line is a row of tiles, so several rows sit on one line and the
threshold is still measured in rows. A grouped list's lines are its headers and its rows as one
stream, so a header on screen only makes the scroller ask for the next page later.

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

`slotName` prefixes every `data-slot` in the footer, so a table's footer is at `entity-table-footer`
and its range at `entity-table-range`.

::props{name="collection-footer" kind="props"}

## Composing a collection

A collection is two calls, because a layout's lines are derived from the rows. The first answers the
source and hands back the rows, the paging model, the selection and what to draw in place of the rows.
The widget shapes its own lines out of those rows. The second wires the virtualiser, the cursor and
the scroll trigger over them.

What the widget still owns is its markup: the box, the row, the header, the empty and error lines, and
the keys its shape implies. The root box and the regions beside it come from the base as two class
strings, so the table, the grid and the grouped list sit the same way on a page.
