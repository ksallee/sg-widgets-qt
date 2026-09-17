---
title: FilterBar
description: Quick facet pills over one entity type, bound to a filter tree.
---

A row of facet pills. Each lists one field's values with a count and ticking them adds a condition to
the bound tree. A More filters pill opens the same tree in the full editor.

## Install

```python
from sg_widgets_qt.widgets.filter_bar import FilterBar
```

::demo{name="filter-bar" title="FilterBar: status, sequence and shot type over Shot, seeded pills, read state over Note, and sizes"}

An untouched facet is a quiet dashed pill naming its field. Ticking a value turns it into a pill
reading the field and the values ticked, and opening the pill again reopens the checklist. A control
at the end of the pill removes it, and once any pill is active a Clear all control drops every
condition the pills contribute, leaving anything built in the dialog alone. Other operators on a
facet field, is none of and is empty among them, are set in the dialog; a pill holding one reads its
condition as text.

A pill names `maxValues` of what is ticked, comma-joined, and reads the rest as `+n`. Its value is
capped and truncated with the whole list in its `title`, so a facet with everything ticked never
stretches the bar past the width it was given.

A facet over a status field draws the site's own icon before each value in the checklist, with the
matched runs of the search box bold, the way a picker lists its options. The pill draws its values as
badges, where a value is what the filter holds rather than what is on offer.

A pill is named from the field's schema. `labels` names one differently, keyed by field name, for a
field whose schema label is written for an admin rather than for the page.

## Props

::props{name="filter-bar" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

## Events

::props{name="filter-bar" kind="events"}

## Slots

None. The dialog behind More filters takes the editor's slots.

## Keyboard

::props{name="filter-bar" kind="keyboard"}

## API behaviour

`POST /entity/<type>/_summarize` answers one group per distinct value with a count, and its
`group_value` is the raw value while `group_name` is the server's rendering, which is not unique on
an entity field (020_summarize). `counts` takes that call's groups for one field, and the reader to
pass is one line:

```ts
counts={facetCounts(context.client, 'Note')}
```

With it an entity facet lists the entities the rows carry, by name and keyed by id, and a list or
status facet lists its codes, each with the site's own count. A field the site refuses to group
answers 400 `Grouping is not allowed for field <Type>.<field>.` (field_types/image,
field_types/summary), and the bar tallies that facet from one page of `sampleSize` rows instead,
with the schema's vocabulary at zero and a line under the list saying how many rows it read. Without
`counts` every facet is tallied that way, so a value outside the page is missing and the numbers are
counts of what was read.

Each facet is counted against the whole filter, the base filter, the dialog's conditions and every
other facet, less its own condition. Ticking two statuses narrows the other pills to the rows under
them, while the status pill keeps every status it could switch to.

A status or list value is the raw code, never the display label, and a code outside `valid_values`
matches nothing rather than erroring (field_types/status_list). An entity value is a `{type, id}`
hash (field_types/entity).

A badge's colour and icon come from the `Status` rows, which are one read per site and are keyed by
code (probe 010). A code with no row of its own still draws, as itself.

Every negating operator, `not_in` included, also matches rows where the field is unset
(017_filter_operators), so is none of on a facet returns the blanks as well.

A field the API evaluates fewer operators on than it advertises carries the evaluated set in its
schema, and both the facet and the dialog read it. `Note.read_by_current_user` is one: `is` and
`is_not` answer the caller's rows in that state, while `in`, `not_in` and an `is` value outside the
vocabulary answer 200 with the caller's unread rows whatever the list holds, in `_search` and in
`_summarize` alike (068_note_read_state). Its facet writes one `is` per ticked value joined by `or`,
which is the same set of rows, and the dialog offers it neither is any of nor is none of. The field is
also per person: a script's own read state is always unread, and its own write to the field is a 200
that stores nothing.

## Reference

The dashed add-a-filter pill and the value checklist follow ReUI's Filters 2.5.2, and the counts beside each value follow shadcn's data table faceted filter. Neither is installed.

In Qt the pill is painted from the theme's tokens and its checklist is the Command primitive in a
popover: the tick sits in the row's indicator column, the count is right-aligned, and a status value
carries its own colour as the row's leading mark. The field read and the tally both run on a worker,
so the bar never blocks the GUI thread, and a stale tally is dropped by its ticket.

The list is one engine in both frameworks: it is always open, always in place and always holds a highlight. It fades at whichever edge has more content past it, holds a gutter for its scrollbar, and carries a live region saying what it is doing. The pattern is coss.com/ui at e937bec, read as a reference and not installed.
