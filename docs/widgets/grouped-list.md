---
title: Grouped List
description: Dense Flow Production Tracking rows under collapsible group headers with counts.
---

Renders rows from an entity source as one line each, under collapsible headers of a shared value.

`paging` says how the set is walked, and the source follows it: `more` puts a load-more row under
the rows, `scroll` loads the next page when the scroller reaches the last loaded row, and `pages`
draws the pagination footer. The list defaults to `more`. A group's count is the rows loaded under
it, so a boundary a reader can see is worth more here than one that passes under them while they
read.

A header's count follows its label in the same line, a gap away, so the two read as one heading.
A page whose first rows carry the value the last header carries grows that group rather than opening
a second one, and a group shut before the page arrived is still shut after it. A page that fails
leaves its rows and puts one error line under them with a retry.

`collapsed` is a mode with exceptions rather than a list of keys, so Collapse all covers the groups
the next page brings as well as the ones already loaded. A bare key list still works and reads as the
open mode with those keys shut.

```python
from sg_widgets_core.collection_state import collapse_all, expand_all, is_collapsed, toggle_collapsed

collapse_all()                                # CollapseState(all=True, except_=[])
toggle_collapsed(collapse_all(), "group:2")   # every group shut but that one
is_collapsed(collapse_all(), "a group nothing has loaded yet")  # True
```

One of `group_by` and `group_key` is required; a list given neither is refused. `group_key` groups on a
value derived from the row instead of read from a column: the record a note is about, which is a
multi-entity field no site sorts on, or a value that comes from one field on one type and another on
another. The list then leaves the source's sort as the caller set it, so the caller orders the rows
so each run comes out whole. Two rows share a run when the JSON text of their keys is the same, so a
key answers a stable shape: the same keys in the same order, or a string. `group_label` draws the
header's text for a derived key, since there is no column to render the value by; with `group_by` it
is not read.

```python
listing = GroupedList(
    source=source,
    group_key=lambda row: cell_value(row, "entity"),
    group_label=lambda record: display_name_of(record),
)
```

The rows are drawn by `picker_row`'s delegate over the shared collection model, so a grouped row
and a picker row cannot drift. Three props change shape for that: `leading` answers a lucide glyph
name or a `#rrggbb` colour for the row's leading slot rather than a widget, `details` are drawn on
the sub-label line behind their own headers, and `row` and `group_header` are the delegate, which a
caller subclasses. Only the lines on screen are drawn at any length, so `virtualize_after` is kept
for parity and changes nothing, and `max_height` is pixels, with a `rem` string read at 16 pixels
to the rem.

## Install

```python
from sg_widgets_qt.widgets.grouped_list import GroupedList
```

::demo{name="grouped-list" title="Grouped List: Tasks by pipeline step, then Versions under the record each is of, from a derived key"}

```python
context = create_sg_context(client)
source = create_entity_source(EntitySourceOptions(
    client=context.client,
    entity_type="Task",
    fields=["content", "sg_status_list", "step.Step.code", "sg_description", "due_date"],
    mode="pages",
    page_size=25,
))
group, sub, secondary = resolve_columns(
    context.schema, "Task", ["step.Step.code", "sg_description", "due_date"]
)
listing = GroupedList(source=source, group_by=group, label_field="content")
```

## Props

::props{name="grouped-list" kind="props"}

## Events

::props{name="grouped-list" kind="events"}

## Slots

::props{name="grouped-list" kind="slots"}

## Keyboard

::props{name="grouped-list" kind="keyboard"}

A disabled row is skipped by Tab: its checkbox and its own control take no keys and no click.

## API behaviour

Grouping a paged read is only honest over an order the server produced, so the widget sets the group
path as the source's first sort key and walks the contiguous runs. A group's count is therefore the
rows loaded so far. A derived key has no path to sort on, so the sort stays the caller's and a value
that returns after an interruption opens a second group under the same name.

Sorts fail silently where filters fail loudly: a field that cannot be sorted returns 200 with the
rows in default order, so a group path is verified against the schema first (026_result_order).

No total is in a read, so `pages` mode walks the set with an explicit page number and stops on a short
page rather than on a missing `links.next`, which is emitted forever (006_pagination). The "of N" in
the range comes from one `_summarize` call counting `id` (020_summarize).
