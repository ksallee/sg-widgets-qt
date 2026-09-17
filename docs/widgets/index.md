---
title: Widgets
description: Every widget, with a live demo.
---

Each widget page shows the Qt widget in a demo stage. The toolbar in the header sets the palette,
light or dark, the size step, the corner radius, reduced motion, and whether the demos read the mock
or a live site; the toolbar under a stage sets the size, the density, the radius and reduced motion.
Every one of those choices carries to the other examples on the page and to the next page, and
`QSettings` carries them to the next run.

Demos run on `MockClient` until the source select is set to Live. Live is offered when `.env.local`
sits beside the checkout and holds the three keys the [install page](../start/install.md) names. Live
mode reads the site and writes nothing.

A widget is imported from its own module:

```python
from sg_widgets_qt.widgets.status_badge import StatusBadge
```

Every widget that reads takes the context, built once over your client. It is what makes one page
cost one schema read and one status table. Wire your own client, or `ShotgunClient`.

::demo{name="hello"}

## Shared parts

A widget is built from parts the other widgets share. They are modules of the same package rather
than separate installs, and a picker pulls in its base, its row and its ladders the way a table pulls
in its source binding and its footer.

| part | module | what it is | used by |
|---|---|---|---|
| [`picker-control`](picker-control.md) | `sg_widgets_qt.widgets.picker_control` | The control box and popup shell every picker is built on: the press rule, the caret, the keyboard model, inline and summary modes, the search row, the list, the state line and the load-more row. | every picker: entity, entity multi, status, status multi, list, list multi and entity type |
| [`search-control`](search-control.md) | `sg_widgets_qt.widgets.search_control` | The query lifecycle and the list every search widget is built on: the debounce, the ticket that drops a stale answer, the page and its load-more row, and the error, loading and empty blocks. | global search, hierarchical search, context selector |
| [`picker-row`](picker-control.md#pickerrow) | `sg_widgets_qt.widgets.picker_row` | The row every picker, search and tree draws: a picture, a highlighted label, a sub-label and a typed secondary. | the pickers, global search, hierarchical search, context selector |
| `picker-classes` | `sg_widgets_qt.primitives.base` | The control, popup, list and row ladders every picker wears. | the pickers, picker-control |
| `control-classes` | `sg_widgets_qt.primitives.base` | The height, inset and glyph ladder every non-picker control wears. | the editors, filter bar, filter dialog, global search, context selector |
| `leaf-classes` | `sg_widgets_qt.primitives.base` | The ladder and the remove control every badge, chip and avatar wears. | status badge, entity chip, user avatar |
| [`state-line`](state-line.md) | `sg_widgets_qt.widgets.state_line` | The centred empty and error line every data widget draws. | the collections, the pickers, the search widgets, filter editor, entity card |
| [`status-glyph`](status-badge.md#statusglyph) | `sg_widgets_qt.widgets.status_glyph` | One status icon, from the site's own image or a cell of the stock sprite. | status badge, and the badge's `glyph` variant |
| [`entity-glyphs`](entity-chip.md#entityglyphs) | `sg_widgets_qt.widgets.entity_glyphs` | A glyph per entity type, with the tag every unlisted type takes. | entity chip, entity card, hierarchical search |
| [`value-editor`](value-editor.md) | `sg_widgets_qt.widgets.value_editor` | The session every leaf editor runs on: the draft, the commit on blur and on Enter, the Escape that restores, the error, and the box the control stands in. | text, number, url, colour, date and date-time editors |
| [`field-error`](value-editor.md#fielderror) | `sg_widgets_qt.widgets.field_error` | The line a field editor shows under its control when a parse fails. | value-editor, checkbox editor |
| [`editor-calendar`](value-editor.md#editorcalendar) | `sg_widgets_qt.widgets.editor_calendar` | The calendar day the date editors hand the Calendar primitive. | date editor, date-time editor |
| [`search-skeleton`](search-control.md#searchskeleton) | `sg_widgets_qt.widgets.search_skeleton` | The rows a search widget draws while its read is in flight. | search-control |
| [`collection-control`](collection-control.md) | `sg_widgets_qt.widgets.collection_control` | The state and behaviour every collection shares: the source, the selection and its tri-state, the keyboard cursor, the virtualiser and the paging triggers. The table, the grid and the grouped list are layouts over it. | entity table, entity grid, grouped list |
| [`collection-source`](collection-control.md#collectionsource) | `sg_widgets_core.collection` | The binding between a collection and its source: the snapshot, the paging mode and the two-way sort and filter. | collection-control, entity tree |
| [`collection-footer`](collection-control.md#collectionfooter) | `sg_widgets_qt.widgets.collection_footer` | The pager under a collection: page size, range and arrows in pages, the loaded count otherwise. | entity table, entity grid, grouped list |
| [`entity-fields`](filter-editor.md#entityfields) | `sg_widgets_core.schema_service` | One entity type's fields, read through the context and kept. | filter bar, filter editor |
