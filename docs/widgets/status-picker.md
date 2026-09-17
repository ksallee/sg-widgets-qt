---
title: StatusPicker
description: One Flow Production Tracking status, picked from the codes a project offers.
---

Picks one status code for an entity type, offering only the codes the project it is scoped to allows.

It is the [list picker](list-picker.md) configured with a status row and a badge for its
value: the same control, popup, press rule and keyboard as every other picker.

Single and multi: [StatusMultiPicker](status-multi-picker.md) takes several codes.

## Install

```python
from sg_widgets_qt.widgets.status_picker import StatusPicker
```

::demo{name="status-picker" title="StatusPicker: per-project options, unknown codes, states and sizes"}

## Props

::props{name="status-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

A row is the row anatomy of the design rules: the status icon as the leading mark, the display name as
the row's text, and the code right-aligned. It is what the [filter bar](filter-bar.md) draws
for a status facet, so a page listing statuses twice lists them the same way. A status has one display
name and one icon, so the row's `labelField` and `thumbnail` are fixed, and it has no fields of its
own, so its secondary is a function rather than a field name. The control keeps the badge, where a
status is a value rather than an option.

Without a project the options are the site vocabulary, which hides nothing. `projectIds` offers the
intersection of what each project allows, in the first project's order.

The clear control follows the field. Left unset, `clearable` reads the field's schema, and a field
the site flags mandatory offers no clear, since clearing it writes a value the site refuses. Set it
and your answer stands, except that a mandatory field is never clearable.

The root carries the size and, while the options load, `data-loading`.

## Events

::props{name="status-picker" kind="events"}

`onValueChange` fires with the code, or with `undefined` when the selection is cleared. It also fires
once with `undefined` when a new option set drops the selected code, which is what a project change
does.

`onOpenChange` fires when the popup opens or closes. Svelte also binds it with `bind:open`.
::qt-note

## Slots

None. The rows are the shared picker row; the closed state is a status badge.

## Keyboard

::props{name="status-picker" kind="keyboard"}

## API behaviour

A project's usable statuses are `valid_values` minus `hidden_values`, read with `project_id`.
`valid_values` is the site's whole vocabulary and is byte-identical at every scope, so reading it
alone tells you nothing about a project (probe 009).

REST does not enforce `hidden_values` on write: a hidden status writes and reads back. Subtracting is
right for offering a choice and wrong for testing a row, so a code outside the option set still
renders here, as itself, and stays removable (field_types/status_list).

Labels come from `display_values`, and a missing key falls back to the raw code rather than dropping
the option (probe 009).

Status lists are per entity type: Version and Task overlap on five codes only, so the options are
read per type and per field (probe 009).

Project's status field is `sg_status`, a plain `list` rather than a `status_list`. There is no Status
row behind a `list`, so those options carry no icon and no colour (entity_types/Project).
