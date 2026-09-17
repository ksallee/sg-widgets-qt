---
title: Entity Table
description: A page of Flow Production Tracking rows as a sortable, selectable, editable table with server pagination.
---

Renders rows from an entity source as a table whose columns come from the schema, with server-side
sorting and paging, a toolbar, a pagination footer, row selection, column sizing, resizing, ordering,
pinning and grouping, and inline edit.

## Install

```python
from sg_widgets_qt.widgets.entity_table import EntityTable
```

::demo{name="entity-table" title="Entity Table: 320 Versions in pages of 25, with a filter bar, a column picker and a sort picker in the toolbar. Pages, Load more and Scroll switch how the set is walked. An editable cell lights up under the pointer; a double-click or Enter opens its editor in a popover; Popover editor and Inline editor switch where every editor opens."}

Build the source and the columns once, then hand both to the table.

```python
context = create_sg_context(client)
source = create_entity_source(EntitySourceOptions(
    client=context.client,
    entity_type="Version",
    fields=["code", "entity", "sg_status_list", "image", "description", "user"],
    page_size=25,
))
columns = resolve_columns(context.schema, "Version", ["code", "entity", "sg_status_list"])
table = EntityTable(source=source, columns=columns, context=context)
```

`resolve_columns` reads the schema, so it runs on a worker and the answer reaches the table
through `set_columns`. The table draws its skeletons until it does.

## Paging

`paging` says how the set is walked, and the source follows it, so a caller sets one prop rather
than two.

| value | the table draws |
|---|---|
| `pages` | The footer's pager: rows per page, a page number, and `n to m of N` once the set is counted. |
| `more` | A load-more row under the last row. The footer counts what is loaded. |
| `scroll` | The next page arrives when the scroller reaches the last loaded row. A skeleton row sits at the bottom while it does, and the footer counts what is loaded. |

`max_height` is pixels here, and a `rem` string is read at 16 pixels to the rem, so the upstream
value still says the same thing.

The table defaults to `pages`. A table is read as a spreadsheet, where a row's place in the set is
part of what it means, and a caller who walks to page 12 wants to come back to it.

`more` and `scroll` append: the rows already loaded stay and the new page lands under them, so a
group that spans a page boundary stays one group and its count grows. A page that fails leaves its
rows and puts one error line under them with a retry.

::demo{name="entity-table-infinite" title="Entity Table: the same rows walked with a load-more row, with the programmatic path beside each header"}

## Props

::props{name="entity-table" kind="props"}

## Events

::props{name="entity-table" kind="events"}

## Slots

::props{name="entity-table" kind="slots"}

The four render props are Qt slots instead. `set_toolbar_start` and `set_toolbar_end` take the
widgets either end of the toolbar; `row`, `cell` and `group_header` are the delegate, so a caller
that wants its own drawing subclasses the one the table installs, or sets another on `table.view`.
`editor_for` stays a callable keyword and takes a data type.

`sort` and `filters` mirror the source, so a SortPicker, a FilterBar and a ColumnPicker drop into
the toolbar and none of them reaches into `source`.

```python
table = EntityTable(source=source, columns=columns, context=context, selectable=True)
table.set_toolbar_start(FilterBar(entity_type="Version", context=context))
table.set_toolbar_end(SortPicker(entity_type="Version", context=context))
table.sort_changed.connect(store_sort)
table.selection_changed.connect(store_selection)
```

Bind a ColumnPicker to the same list the table holds and the two drive each other: hiding a column
from its header menu removes it from the picker, and adding one there puts it back.

```python
picker = ColumnPicker(context=context, entity_type="Version", value=[c.path for c in columns])
picker.value_changed.connect(pick_columns)
table.columns_changed.connect(lambda kept: picker.set_value([c.path for c in kept]))
table.set_toolbar_start(picker)
```

An editor is handed `value`, `data_type`, `field`, `commit` and `cancel`, and owns its own keys.
Without `editor_for`, an editable cell opens the type's own control from the field-editor item: a
status cell opens StatusPicker, an entity cell EntityPicker and a multi-entity cell
EntityMultiPicker, each reading through `context`. The cell editor takes `project_id`, `precision`,
`symbol` and the context's site preferences.

The editor opens in a popover anchored to the cell, carrying the field's name, the control and
Cancel and Save, so a cell's width never squeezes it. A checkbox is one press and stays in the cell.
`editor_placement` on the table forces one or the other everywhere, and `editor_placement` on a
column spec forces it for that column.

## Column menu

With `column_menu`, every header carries a menu: sort ascending, sort descending, clear sort and
hide column. It is off by default: a header sorts on a press, and the column picker in the toolbar
is where columns are shown and hidden.
The sort entries are inert on a column the schema says cannot be sorted. Hiding writes the shorter
column list back through `columns_changed`. Pin left is not here: a frozen column needs a second
view over the same model, and no caller has asked for one.

## Keyboard

::props{name="entity-table" kind="keyboard"}

An editable cell says so: it washes to `accent` at half strength under the pointer and under the
keyboard cursor, and its tooltip reads "Double-click or press Enter to edit". A double-click opens
the editor too. A press inside a popup the editor opened, a calendar, a status list or a picker's
results, leaves the cell open. A header's right edge drags to resize. A header does not drag to
reorder here: the column picker in the toolbar is what orders the columns.

A disabled row takes no keys, no click and no checkbox, and none of its cells opens an editor.

## API behaviour

Sorting is the server's. A header click sets the source's sort and reads the page again, because a
sort applied to one loaded page orders the page and not the set. Sorts also fail silently where
filters fail loudly: a field that cannot be sorted, and a name that does not exist, both return 200
with the rows in default order, so a sortable path is verified against the schema first
(026_result_order).

The cursor in the body is the focused checkbox or editable cell: a row with neither is not a place
a cursor can be.

Paging is the server's too. No total is in a read: a paged GET answers `data` and `links` alone, and
five spellings of a count option are accepted at 200 and change nothing, so `pages` mode walks the
set with an explicit page number and stops on a short page rather than on a missing `links.next`,
which is emitted on every page forever (006_pagination). The "of N" in the range comes from one
`_summarize` call counting `id`, taken once per filter; a site that does not answer that key leaves
the range reading "n to m" (020_summarize).

Grouping collapses the loaded rows under headers, and the group path leads the source's sort so a
group is not split across pages. A count is the rows loaded under that header, and a page that
opens on the value the last header carries grows that group rather than opening a second one.

`collapsed` is a mode with exceptions rather than a list of ids, so Collapse all covers the headers
the next page brings as well as the ones already loaded. A bare id list still works and reads as the
open mode with those ids shut. `collapseAll`, `expandAll`, `isCollapsed` and `toggleCollapsed` in
core are the readings over it, and a host holding the same state for a list of its own imports them.

An edit writes one field with `PUT /entity/<type>/<id>`, which changes only the keys it is given and
leaves the rest alone (put_entity_type_id). The write answers the whole record but resolves no dotted
path, so the row is read again afterwards (024_read_after_write). A dotted path is never editable: a
write names one field of one row.

## Reference

Column sizing, resizing, ordering and grouping are TanStack Table's (`@tanstack/table-core` 9.2.4).
The markup, the classes and the anatomy of the toolbar, the pagination footer and the column menu
follow ReUI's Base UI data grid (ReUI 2.5.2).

Here none of that is a library. The rows, the columns and the group headings are one
`QAbstractTableModel`, `CollectionModel`, which the grid and the grouped list share; the view is a
`QTableView` with `TableSurface`'s header and a cell delegate that draws every value through
`paint_field_value`. Sizing and resizing are the header's own, and only the rows on screen are ever
drawn, so `virtualize_after` is kept for parity and changes nothing.
