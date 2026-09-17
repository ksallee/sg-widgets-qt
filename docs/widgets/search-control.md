---
title: SearchControl
description: The query lifecycle and the list every search widget is built on.
---

The pause before a query is asked for, the answer that arrives too late to count, the page under the
rows, and the list itself. A search built on it supplies the read and draws its own rows.

## Install

```python
from sg_widgets_qt.widgets.search_control import SearchControl
```

::demo{name="search-control" title="SearchControl: a query, a page, a list with no query, and a read that failed"}

The demo reads a static crew list behind a 300ms pause, at four rows a page. The first case takes a
query, debounces it, pages it and emits the row picked. The second takes no query at all: one read,
drawn straight into the page with no command box around it. The third fails, so the list shows the
error line instead.

## The lifecycle

`load` is the read. It is handed the query as it stands and the page wanted, and answers the rows it
found plus whether a further page may be there. Everything around it belongs to the base.

A query is asked for once the pause has elapsed, so a typist does not fire a request a letter. A
query that arrives while a read is in flight takes the next ticket, which is what makes the earlier
answer stale: it is dropped rather than landing over the query that replaced it. The same ticket is
taken when the list is emptied, so a cancelled read never writes.

An empty query empties the list and reads nothing. A search that browses rather than matching sets
`reads_empty`, and then an empty query reads too — at once, because no one is typing.

`request` is what the read depends on besides the query: the level of a tree, the person whose rows
are listed. A change to it empties the list and reads again at once. `enabled` holds every read back,
for a list that has nothing to read yet.

## The list

The list draws one of four things. An error is the error line. A first page in flight is skeleton
rows, shaped like the rows they stand in for; a page arriving under rows already on screen leaves
those rows where they are. A read that answered nothing is the empty line, and otherwise it is the
rows the wrapper drew. With `paging` on, a further page adds a load-more row under them.

The blocks carry `search-error`, `search-loading` and `search-empty` as their object name, and the
list itself `search-list`. A wrapper renames any of them.

## The shell

`command` is a command box with a search row at the top of it, `dialog` the same box inside a
dialog, and `bare` the list alone, for a section of a larger surface that draws its own heading and
takes no query. The shell is settled when the widget is built.

The highlight is the base's: it lands on the first row whenever the list changes. Matching is the
server's alone — the command box never filters what came back.

The list carries a live line saying what it is doing: the read in flight, the number of rows it
answered, the empty line, or what a failed read said. It is the list's accessible description, so a
reader hears it; the state line inside the list is what a reader sees.

The list fades at whichever edge has more content past it and holds a gutter for its scrollbar, so
rows never shift as pages land. The pattern is coss.com/ui at e937bec, whose scroll area reads the
same variables.

## Props

::props{name="search-control" kind="props"}

## Slots

::props{name="search-control" kind="slots"}

## Keyboard

::props{name="search-control" kind="keyboard"}

The list never takes focus: the search box holds the caret and hands the arrows over, so a press
inside the list cannot move the caret and nothing has to put it back.

Anything else a wrapper needs reaches it through `on_key_down`, which is handed the event and the
rows on show: the hierarchical search walks the tree with Left and Right that way.

## Composing a wrapper

A wrapper owns its read and its rows. It writes one `load`, draws one row, and says which shell it
wants. The three search widgets in this registry are that and little else: the global search adds
the trigger, the hotkey and the recents above the results; the hierarchical search adds the level it
is browsing and the keys that walk it; the context selector uses the bare shell for the tasks
assigned to one person, beside its recents and its tree.

Here a wrapper hands over a model instead of drawing the rows itself: `model` is any
`QAbstractItemModel` answering the roles the row delegate reads, and `PickerRowModel` is the one
every wrapper in this package uses. A wrapper that groups its results, or puts a heading among
them, passes `row_mapper`, which turns the items the read answered into the rows the model holds.
Anything else a wrapper needs off the keyboard reaches it through `on_key_down`, which is handed
the event and the rows on show.

## API behaviour

Nothing here is API behaviour of its own. A search that pages a text search reads a full page as the
only sign of another one, since a read carries no total and `links.next` is emitted forever
(`006_pagination`); `has_more_page` in core answers that, and the wrapper passes the result as
`has_more`.

## SearchSkeleton

The rows a search draws while its read is in flight. Skeletons are shaped like the rows they stand
in for, so a list holds its place when the page lands: the same inset, the same height and the same
zero gap. `lead` is the leading slot's shape, a `QSize` or a width and a height, which is a
thumbnail in one widget and a glyph in another; with none it is the square of the thumbnail ladder
at `size`. The block carries the accessible name the state line gives it, so a reader hears what is
happening rather than nothing.

::props{name="search-skeleton" kind="props"}

## Reference

`tk-framework-qtwidgets`, `python/search_completer/search_completer.py`: the loading row and the
row that asks for more live in the list's own model rather than in a layer over it, so the arrows
walk them like any other row. Read as a reference, nothing copied.
