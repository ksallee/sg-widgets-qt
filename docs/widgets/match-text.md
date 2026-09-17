---
title: MatchText
description: A label with the words of a search query at the weight a match takes.
---

Draws one label with the words of a query marked, which is the treatment the picker row, the tree
and the searches give a result.

## Install

```python
from sg_widgets_qt.widgets.match_text import MatchText
```

::demo{name="match-text" title="MatchText: a query marked across names, paths and an address"}

## Props

::props{name="match-text" kind="props"}

Here the label is one painted `QWidget` whose object name is `match-text`. Two keywords replace
what CSS gave the span: `size` picks the type step (12, 14 and 16), and `muted` draws the line in
`muted_foreground`, which is the muted-line case the demo shows. The label is elided at the end and
carries the whole value as its tooltip.

A match is weight and never colour, so a label already carrying a colour of its own still reads. The
runs rebuild the label exactly, so a label the query does not touch draws as itself and an empty
query marks nothing.

The splitting is `match_runs` in core, which answers the label as segments with a matched flag. Draw
the segments yourself when the treatment has to be something else; nothing here draws markup from a
row.

```python
from sg_widgets_core.search import match_runs

match_runs("Ada Lovelace", "ad ve")
# [MatchRun(text='Ad', match=True), MatchRun(text='a Lo', match=False),
#  MatchRun(text='ve', match=True), MatchRun(text='lace', match=False)]
```

The widget answers the same list as `runs`, so a caller drawing its own treatment reads it there.

## Events

None.

## Slots

None.

## Keyboard

Not focusable.

## API behaviour

`POST /entity/_text_search` matches a row when every whitespace-separated word of the query appears
in it, so "pub ad" finds "Published Ada" (053_text_search_matching). Every word is therefore marked
wherever it occurs, and overlapping words merge into one run.

The endpoint answers a thin row and has no `fields` parameter, so a label beyond the name, the
linked row and the status code is a second read (post_entity_text_search).

## Reference

Nothing: the runs are drawn run by run with `QPainter` in the theme's own family, the matched ones
at `QFont.Weight.DemiBold`.
