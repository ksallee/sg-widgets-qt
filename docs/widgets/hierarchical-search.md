---
title: HierarchicalSearch
description: A drill-down over the Flow Production Tracking navigation tree, with breadcrumb results.
---

Walks the navigation tree level by level, or searches it, and emits the row you pick with the path
that reaches it. It is a wrapper over [`search-control`](search-control.md), which owns the
debounce and the list.

## Install

```python
from sg_widgets_qt.widgets.hierarchical_search import HierarchicalSearch
```

::demo{name="hierarchical-search" title="HierarchicalSearch: browse a project, or search it and read the path"}

## Props

::props{name="hierarchical-search" kind="props"}

Every prop is a keyword of the constructor and a `set_<name>` after it. `selected` is the signal a
pick emits, carrying the row and the path that reaches it.

With no query the list is one level of the tree. With a query it is the rows that match, each shown
as the breadcrumb that reaches it, the row itself last and in bold.

A row is the shared picker row, drawn by the one row delegate: a picture, the crumbs before the
label in `muted_foreground`, the label with the matched words in DemiBold, a muted sub-label and a
right-aligned secondary drawn by its data type. A level of the tree carries no picture, so those
rows show their type glyph; a searched row shows the thumbnail the second read answered. With no
`sub_label_field` and no `sub_label`, the sub-label is the row's type, or `Group` on a level.

`entity_types` limits what a search returns. Browsing reaches every level whatever it says; a row that
is not one of these types opens instead of being picked.

## Events

::props{name="hierarchical-search" kind="events"}

## Slots

None. `sub_label` and `secondary` are callables of the row, which is where a caller writes a line of
its own.

## Keyboard

::props{name="hierarchical-search" kind="keyboard"}

`Backspace` goes up only when the query is empty; otherwise it edits the query.

## API behaviour

The tree is read one level per call: the answer names the paths of its children and says which of
them are worth opening (post_hierarchy_expand).

A path runs through field names, such as `sg_sequence` between a project's shots and a sequence, so
the shape of the tree is the site's own navigation configuration rather than a fixed hierarchy
(post_hierarchy_search).

Searching does not go through the hierarchy endpoints. `hierarchy/_search` takes an entity and
answers where it sits; its criteria accepts the single key `entity` and any other key answers
`search_criteria size must be 1`, which counts the keys it recognises rather than the ones sent
(post_hierarchy_search). So the words are matched by `_text_search` and each hit is then asked for
its path. That endpoint has no `fields` parameter either, so the picture and whatever the row props
name are a second read of the hits (post_entity_text_search).

On the Python API a term is three characters or more: `shotgun_api3.text_search` refuses a
shorter one outright rather than answering nothing, and the widget draws that refusal as its
error line (053_text_search_matching).

The hierarchy endpoints take `application/json` and refuse the vendor content types every other POST
on this API demands (046_search_without_a_path).

## Reference

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
