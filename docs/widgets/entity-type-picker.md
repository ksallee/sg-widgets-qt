---
title: EntityTypePicker
description: One entity type of a site, chosen from a searchable list.
---

Picks one entity type of a site, from a searchable list of everything the site has enabled.

Single and multi: [EntityTypeMultiPicker](entity-type-multi-picker.md) takes several types.
This picker takes `multiple` no more; a caller passing it moves to the multi picker.

## Install

```python
from sg_widgets_qt.widgets.entity_type_picker import EntityTypePicker
```

::demo{name="entity-type-picker" title="EntityTypePicker: allow and deny lists, codes, sizes and states"}

## Props

::props{name="entity-type-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

Each row shows the display name, with the code beneath it in mono when the two differ, unless
`showCode` is off. The control is a token field: the value is one chip, with the caret beside it.
A pick closes the list.

`allow` is applied first and `deny` second, both to the derived list rather than to the read, so a
caller narrowing the set sees the list change with no second call.

## Events

::props{name="entity-type-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="entity-type-picker" kind="keyboard"}

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
