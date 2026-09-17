---
title: EntityPicker
description: One Flow Production Tracking entity, chosen by server-side search across one or more types.
---

Searches one or more entity types on the server as you type, and binds the row you choose.

Single and multi: [EntityMultiPicker](entity-multi-picker.md) binds several rows.

## Install

```python
from sg_widgets_qt.widgets.entity_picker import EntityPicker
```

::demo{name="entity-picker" title="EntityPicker: secondary column, types, project scope, hydration, paging, errors, row anatomy, sizes, states"}

## Props

::props{name="entity-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

The secondary column shows nothing until `secondaryField` or `secondary` asks for something.
`secondaryField` is drawn by the field's data type, so a status is a badge, an entity is the name it
links to, a date is formatted and a number is right-aligned in tabular figures; `secondaryField="id"`
puts the id back, in mono. The field is requested with the row.

A query shorter than `minQueryLength`, or none at all, still lists the first page, sorted by the last
update, so an open picker is never empty.

A row is `{ type, id, name, values }`, where `values` holds the attributes and the relationships in
one map. A dotted field is a literal key with dots in it, so `project.Project.name` reads straight
out of it.

The picker is `w-full`; wrap it in a sized container.

## Events

::props{name="entity-picker" kind="events"}

## Slots

None. The row is fixed: leading thumbnail or avatar, label with the matched words in bold and the
code beside it, sub-label, right-aligned secondary.

## Keyboard

::props{name="entity-picker" kind="keyboard"}

## API behaviour

A query is split on whitespace and every word must match, each as its own `contains` condition,
`or`'d across the fields the type has out of `cached_display_name`, `code`, `name`, `title`,
`content` and `subject`. `contains` works on text fields and through dotted paths, and an operator
the field does not accept is a 400, never a silent pass (017_filter_operators). Client-side
filtering is off: the server decides what matches.

Each searched type gets its own `POST /entity/<type>/_search` with `api3_hash`, the only content
type that expresses a nested `and` and `or` group (030_complex_filters).
`POST /entity/_text_search` is not used: it takes no `fields`, so every row comes back as name,
links and status whatever the type, and a picker needs a thumbnail and a sub-label
(post_entity_text_search).

With no name condition the rows are sorted `-updated_at`. Unsorted, a read comes back id ascending,
which is the oldest work on the site; an unsortable or unknown sort field is a silent 200 no-op
(026_result_order).

Another page exists when the page came back full. `links.next` is emitted on every page forever,
including empty ones, so it is never the stop signal (006_pagination).

A pre-filter naming a field the type does not have is dropped on that type. The same name in a
filter would be a 400 while an unknown name in `fields` is a silent 200 (003_query,
017_filter_operators), so a picker across several types applies each condition only where it
resolves. `projectId` follows the same rule: it becomes `project` on a type that links one and
`projects` on a site-wide type such as HumanUser, and nothing on Project itself.

A bare `{ type, id }` is resolved on mount by one `id in` read per type, with the same field list.
A row that cannot be resolved keeps the label `Type id`.

A thumbnail URL is presigned and re-minted on every read, so the picker holds the row and re-reads
rather than storing the string (field_types/image).

The control is `PickerControl` with the chosen row's `EntityChip` inline, and the list is a
`ListSurface` inside a popover that never takes focus, so the caret stays in the control while the
list is showing. The loading state is three `Skeleton` rows at the inset and the height of a row.

The read runs on `sg_widgets_qt.workers`: the pause a typist leaves, then `fetch_page` on a worker,
then `deliver` back on the GUI thread with the ticket `begin` handed out, so an answer to a query
that was replaced is dropped. Pictures are read on a pool of their own, so a page of thumbnails
never queues a query behind it.

## Reference

Here there is no headless primitive to compose. The box and its popup are
`widgets/picker_control.py`, the popup is `primitives/popover.py` and never takes focus, the list is
`primitives/list_view.py`, and every row is drawn by `primitives/row_delegate.py` through
`PickerRowModel`, so PySide6 and PyQt5 draw the same pixels and answer a key the same way.

`tk-framework-qtwidgets/python/search_completer/search_completer.py` runs its completion popup
unfiltered and draws every row through a delegate; this picker does the same, and the site is the
only authority on what matches. It was read, and nothing was copied.
