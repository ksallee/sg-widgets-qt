---
title: EntityTypeMultiPicker
description: Several entity types of a site, chosen from a searchable list with checkbox rows.
---

Picks any number of entity types of a site, from a searchable list of everything the site has
enabled.

Single and multi: [EntityTypePicker](entity-type-picker.md) takes one type.

## Install

```python
from sg_widgets_qt.widgets.entity_type_multi_picker import EntityTypeMultiPicker
```

::demo{name="entity-type-multi-picker" title="EntityTypeMultiPicker: allow and deny lists, summary modes, codes, sizes and states"}

## Props

::props{name="entity-type-multi-picker" kind="props"}

Every row carries a checkbox and the list stays open across selections. Each selection is a chip in
the control, with its own remove control.

`chips` makes the control a token field: every chip, wrapped, with the caret beside them, and
`+n` after the last chip `max` allows.
`ellipsis` makes it a one-line trigger: as many whole chips as the row fits, never a cut one,
then `+n` inline after the last, the whole list in the tooltip, and the search box at the top of
the popup.
`count` makes it the same trigger reading `3 selected`.
A press on `+n` opens the list, where the hidden rows are.

`allow` is applied first and `deny` second, both to the derived list rather than to the read, so a
caller narrowing the set sees the list change with no second call.

## Events

::props{name="entity-type-multi-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="entity-type-multi-picker" kind="keyboard"}

## API behaviour

`GET /schema` returns every enabled type in about 12KB, custom slots included, and presence in that
listing is the enablement test: a slot absent from it 404s everywhere else. The display name is the
type's `name`, and the key is what a URL and a dotted path take (002_schema).

## Reference

The row, chip and checkbox anatomy follows shadcn's Base UI Combobox, read through shadcn 4.21.0.
The primitive underneath is Base UI Combobox 1.8.0 in React and Bits UI Combobox 2.19.1 in Svelte.
shadcn-svelte ships no combobox item, so each widget composes the headless primitive of its
framework and both draw the same rows, the same classes and the same states.
::qt-note
