---
title: Widgets
description: Every widget, with a live demo of the Svelte and React implementations.
---

Each widget page shows the Svelte and React implementations side by side. The toolbar on an example
sets the framework, reduced motion and the corner radius; the palette select in the header picks one
of seven palettes for the demo stages, and light or dark follows the theme select next to it. Every one
of those choices carries to the other examples on the page and to the next page.
::qt-note

Demos run on fixtures until you open Connect in the header, switch it to Live, give it your site and
log in through your site's own approval page. Your session stays in this browser, this site keeps
nothing of it on a server, and the project you pick there is the one the demos that take a project
read.

Widgets install from a registry into your project, one command per framework:
::qt-note

```sh
pnpm dlx shadcn@latest add https://sg-widgets.dev/r/react/status-badge.json
pnpm dlx shadcn-svelte@latest add https://sg-widgets.dev/r/svelte/status-badge.json
```

Name `sg-widgets.json` in place of a widget to install every widget and every shared part at once.

Every widget that reads takes the context, built once over your client. It is what makes one page
cost one schema read and one status table. Wire your own client, or the shipped REST one.

::demo{name="hello"}

## Shared parts

A widget is built from parts the registry also holds. They install with the widgets that need
them; a picker pulls in its base, its row and its classes the way a table pulls in its source
binding and its footer. The same names exist in both registries.
::qt-note

| part | what it is | used by |
|---|---|---|
| [`picker-control`](picker-control.md) | The control box and popup shell every picker is built on: the press rule, the caret, the keyboard model, inline and summary modes, the search row, the list, the state line and the load-more row. | every picker: entity, entity multi, status, status multi, list, list multi and entity type |
| [`search-control`](search-control.md) | The query lifecycle and the list every search widget is built on: the debounce, the ticket that drops a stale answer, the page and its load-more row, and the error, loading and empty blocks. | global search, hierarchical search, context selector |
| [`picker-row`](picker-control.md#pickerrow) | The row every picker, search and tree draws: a picture, a highlighted label, a sub-label and a typed secondary. | the pickers, global search, hierarchical search, context selector |
| `picker-classes` | The control, popup, list and row classes every picker wears. | the pickers, picker-control |
| `control-classes` | The height, inset and glyph ladder every non-picker control wears. | the editors, filter bar, filter dialog, global search, context selector |
| `leaf-classes` | The ladder and the remove control every badge, chip and avatar wears. | status badge, entity chip, user avatar |
| [`state-line`](state-line.md) | The centred empty and error line every data widget draws. | the collections, the pickers, the search widgets, filter editor, entity card |
| [`status-glyph`](status-badge.md#statusglyph) | One status icon, from the site's own image or a cell of the stock sprite. | status badge, and the badge's `glyph` variant |
| [`entity-glyphs`](entity-chip.md#entityglyphs) | A glyph per entity type, with the tag every unlisted type takes. | entity chip, entity card, hierarchical search |
| [`value-editor`](value-editor.md) | The session every leaf editor runs on: the draft, the commit on blur and on Enter, the Escape that restores, the error, and the box the control stands in. | text, number, url, colour, date and date-time editors |
| [`field-error`](value-editor.md#fielderror) | The line a field editor shows under its control when a parse fails. | value-editor, checkbox editor |
| [`editor-calendar`](value-editor.md#editorcalendar) | The calendar day the date editors hand the Calendar primitive. | date editor, date-time editor |
| [`search-skeleton`](search-control.md#searchskeleton) | The rows a search widget draws while its read is in flight. | search-control |
| [`collection-control`](collection-control.md) | The state and behaviour every collection shares: the source, the selection and its tri-state, the keyboard cursor, the virtualiser and the paging triggers. The table, the grid and the grouped list are layouts over it. | entity table, entity grid, grouped list |
| [`collection-source`](collection-control.md#collectionsource) | The binding between a collection and its source: the snapshot, the paging mode and the two-way sort and filter. | collection-control, entity tree |
| [`collection-footer`](collection-control.md#collectionfooter) | The pager under a collection: page size, range and arrows in pages, the loaded count otherwise. | entity table, entity grid, grouped list |
| [`entity-fields`](filter-editor.md#entityfields) | One entity type's fields, read through the context and kept. | filter bar, filter editor |
