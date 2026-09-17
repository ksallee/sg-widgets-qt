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

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*` and a `ref` to the root
element.

A match is weight and never colour, so a label already carrying a colour of its own still reads. The
runs rebuild the label exactly, so a label the query does not touch draws as itself and an empty
query marks nothing.

The splitting is `matchRuns` in core, which answers the label as segments with a matched flag. Draw
the segments yourself when the treatment has to be something else; nothing here sets HTML from a row.

```ts
import { matchRuns } from '@sg-widgets/core';

matchRuns('Ada Lovelace', 'ad ve');
// [{ text: 'Ad', match: true }, { text: 'a Lo', match: false },
//  { text: 've', match: true }, { text: 'lace', match: false }]
```

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
