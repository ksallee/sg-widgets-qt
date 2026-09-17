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

Each row shows the display name, with the code beside it in mono when the two differ, unless
`show_code` is off. The control is a token field: the value is one chip, with the caret beside it.
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

Here there is no headless primitive to compose. The box and its popup are
`widgets/picker_control.py`, the list is `primitives/list_view.py`, and every row is drawn by
`primitives/row_delegate.py`, so PySide6 and PyQt5 draw the same pixels.

Three things the row does that the upstream row does not, all of them `docs/design-rules.md`:

- The type's glyph from `widgets/entity_glyphs.py` is the row's leading mark (rule 9). A type has
  no picture, so the glyph stands alone rather than on the plate a row draws where a picture was
  expected and has not landed.
- The chosen row carries the indicator every picker here draws: a trailing tick on the single
  picker, the leading checkbox on the multi one (rule 2). Upstream the single picker's rows carry
  no mark at all.
- The runs a query matched are drawn in DemiBold (rule 6). Upstream draws the label plain here,
  while its other pickers highlight; the shared row highlights everywhere.

The code sits beside the display name in the mono family, which is where rule 9 puts a code, and
not under it as upstream does. The one schema read runs on `sg_widgets_qt.workers`.
