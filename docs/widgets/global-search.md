---
title: GlobalSearch
description: A command palette that searches Flow Production Tracking by name across several entity types.
---

Searches several entity types at once by name and emits the row you pick. It is a wrapper over
[`search-control`](search-control.md), which owns the debounce, the paging and the list.

## Install

```python
from sg_widgets_qt.widgets.global_search import GlobalSearch
```

::demo{name="global-search" title="GlobalSearch: palette with a hotkey, the inline variant scoped to a project, and the three sizes beside a button"}

## Props

::props{name="global-search" kind="props"}

Every prop is a keyword of the constructor and a `set_<name>` after it. The events are Qt signals:
`selected`, `recents_changed` and `open_changed`.

Recents live in the caller. The widget hands back the new list and never writes anywhere, so where
they are kept between sessions is the app's decision.

A row is the shared picker row: a thumbnail, or an avatar for a person, the name with the matched
words in bold, a muted sub-label and a right-aligned secondary drawn by its data type. With no
`sub_label_field` and no `sub_label`, the sub-label is the row's project; a row with no project shows
the row it links to instead.

Results are grouped by entity type, in the order the types were given, under the type's display name
from the site schema. A heading is a row of the list that the highlight steps over, so the arrows
walk the results and never land on a heading.

The trigger is the control the palette hangs off: a search glyph, the label, and the shortcut in a
small pill at the trailing edge. `hotkey` puts that shortcut on the application, so the palette
opens from anywhere in the window; Qt spells it `Ctrl` and macOS draws it as Command.

## Events

::props{name="global-search" kind="events"}

## Slots

::props{name="global-search" kind="slots"}

## Keyboard

::props{name="global-search" kind="keyboard"}

## API behaviour

Every word of the query has to match, each as a case-insensitive substring, and a row matches on its
own name or on the name of the row it links to. So a Version whose code holds none of the words comes
back because its linked Shot does (053_text_search_matching).

The page size is 1 to 25, and 25 is also the default. The answer carries no paging links, so "load
more" asks for the next page and stops when a page comes back short (053_text_search_matching,
006_pagination).

Search results carry a name, the linked row and a status code, and nothing else: the endpoint has no
`fields` parameter. The thumbnail, the project and whatever the row props name are a second read of
the page just returned (post_entity_text_search).

`project_id` adds a project condition only to types that have a `project` field. Project has none and
neither does Step, and the condition would be a 400 rather than an empty result
(entity_types/Project, entity_types/Step).

## Reference

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
