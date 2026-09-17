---
title: StatusMultiPicker
description: Several Flow Production Tracking statuses, picked from the codes a project offers.
---

Picks any number of status codes for an entity type, offering only the codes the project it is scoped
to allows.

Single and multi: [StatusPicker](status-picker.md) takes one code.

## Install

```python
from sg_widgets_qt.widgets.status_multi_picker import StatusMultiPicker
```

::demo{name="status-multi-picker" title="StatusMultiPicker: per-project options, a mandatory field, trigger summaries, unknown codes, states and sizes"}

## Props

::props{name="status-multi-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

`summary` and `badge` are two axes. `summary` says how many of the selection the control shows:
`chips` makes it a token field with every badge, wrapped, each with its own remove control inside the
badge, the caret beside them, and `+n` after the last badge `max` allows; `ellipsis` makes it a one-line trigger with
as many whole badges as the row fits, never a cut one, then `+n` inline after the last, and the
search box at the top of the popup; `count` is the same trigger reading `3 selected`.

`badge` says what one status is drawn as: `both` is the icon and the label, `icon` drops the label
and the per-badge remove, so removal happens in the list and twice as many fit, and `text` is the
label alone.
A row is the row anatomy of the design rules, after its checkbox: the status icon as the leading mark,
the display name with the matched runs bold, and the code right-aligned. It is what the
[filter bar](filter-bar.md) draws for a status facet, so a page listing statuses twice lists
them the same way. A status has one display name and one icon, so the row's `labelField` and
`thumbnail` are fixed, and it has no fields of its own, so its secondary is a function rather than a
field name. The control keeps the badges, where a status is a value rather than an option.

A press on `+n` opens the list, where the hidden codes are. Without a project the options are the site
vocabulary, which hides nothing. `projectIds` offers the intersection of what each project allows,
in the first project's order.

The root carries the size and, while the options load, `data-loading`.

## Events

::props{name="status-multi-picker" kind="events"}

`onValueChange` fires with the whole array on every change, including the empty array from the clear
control. A selected code the option set does not carry is kept, never dropped.

`onOpenChange` fires when the popup opens or closes. Svelte also binds it with `bind:open`.

`value_changed` carries the whole list on every change, including the empty list from the clear
control, and a selected code the option set does not carry is kept rather than dropped.
`open_changed` carries True or False. Both are Qt signals; `on_value_change` and `on_open_change`
take a plain callable instead.

## Slots

None. The rows are the shared picker row; the closed state is status badges.

## Keyboard

::props{name="status-multi-picker" kind="keyboard"}

## API behaviour

A project's usable statuses are `valid_values` minus `hidden_values`, read with `project_id`.
`valid_values` is the site's whole vocabulary and is byte-identical at every scope, so reading it
alone tells you nothing about a project (probe 009).

REST does not enforce `hidden_values` on write: a hidden status writes and reads back. Subtracting is
right for offering a choice and wrong for testing a row, so a selected code outside the option set
keeps a row of its own here, labelled with the code (field_types/status_list).

A status list has no substring operator, so there is no server-side type-ahead over it. The
vocabulary is read once and the query input narrows it in the browser (field_types/status_list).

Labels come from `display_values`, and a missing key falls back to the raw code rather than dropping
the option (probe 009).

Project's status field is `sg_status`, a plain `list` rather than a `status_list`. There is no Status
row behind a `list`, so those options carry no icon and no colour (entity_types/Project).

## Reference

The row, chip and checkbox anatomy follows shadcn's Base UI Combobox, read through shadcn 4.21.0.
The primitive underneath is Base UI Combobox 1.8.0 in React and Bits UI Combobox 2.19.1 in Svelte.
shadcn-svelte ships no combobox item, so each widget composes the headless primitive of its
framework and both draw the same rows, the same classes and the same states.

Here there is no headless primitive to compose. The box and its popup are
`widgets/picker_control.py`, the popup is `primitives/popover.py` and never takes focus, the list
is `primitives/list_view.py`, and every row is drawn by `primitives/row_delegate.py`, so PySide6
and PyQt5 draw the same pixels. The glyph in a row's leading slot is `widgets/status_glyph.py`
and the value in the control is `widgets/status_badge.py`. The options, the field and the Status
table are read on `sg_widgets_qt.workers`, through the context's own caches.

`tk-framework-qtwidgets/python/shotgun_fields/status_list_widget.py` edits a status field as a
`QComboBox` carrying the display name as the item text and the code as the item data, and draws
the value as a coloured block before the name. The split between the code and its label is the
same here; the control is drawn by this repo rather than by the host style, and the mark is the
status's own icon. It was read, and nothing was copied.
