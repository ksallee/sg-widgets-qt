---
title: EntityMultiPicker
description: Several Flow Production Tracking entities, chosen by server-side search, with checkbox rows and removable chips.
---

Searches one or more entity types on the server as you type, and binds the rows you tick.

Single and multi: [EntityPicker](entity-picker.md) binds one row.

## Install

```python
from sg_widgets_qt.widgets.entity_multi_picker import EntityMultiPicker
```

::demo{name="entity-multi-picker" title="EntityMultiPicker: secondary column, types, hydration, exclusions, paging, errors, summary modes, sizes, states"}

## Props

::props{name="entity-multi-picker" kind="props"}

The secondary column shows nothing until `secondaryField` or `secondary` asks for something, and
`secondaryField` is drawn by the field's data type: a status is a badge, a date is formatted.

Selected rows are appended to the option list after the search results, so a row stays there to be
unticked whatever the query. Each selection is also a chip in the control, with its own remove
control.

`chips` makes the control a token field: every chip, wrapped, with the caret beside them, and
`+n` after the last chip `max` allows.
`ellipsis` makes it a one-line trigger: as many whole chips as the row fits, never a cut one,
then `+n` inline after the last, the whole list in the tooltip, and the search box at the top of
the popup.
`count` makes it the same trigger reading `3 selected`.
A press on `+n` opens the list, where the hidden rows are.

## Events

::props{name="entity-multi-picker" kind="events"}

## Slots

None. The row is fixed: checkbox, leading thumbnail or avatar, label with the matched words in
bold, sub-label, right-aligned secondary.

## Keyboard

::props{name="entity-multi-picker" kind="keyboard"}

## API behaviour

The same request model as the single picker: one `contains` condition per word, `or`'d across the
display-name fields the type has, one `POST /entity/<type>/_search` per searched type, and
client-side filtering off (017_filter_operators, 030_complex_filters). With nothing typed the name
condition is dropped and the page is sorted `-updated_at` (026_result_order).

Exclusions go into the server filter as `id not_in` per type, so they never eat into the page. The
legacy behaviour of filtering them out after the page cap could empty a dropdown that had matches.

Bare `{ type, id }` members are resolved on mount by one `id in` read per type, batched, with the
page size set to the number of ids. A resolved row is never overwritten by the bare reference it
came from.

## Reference

Here there is no headless primitive to compose. The box and its popup are
`widgets/picker_control.py`, the popup is `primitives/popover.py` and never takes focus, the list is
`primitives/list_view.py`, and every row is drawn by `primitives/row_delegate.py` through
`PickerRowModel`, so PySide6 and PyQt5 draw the same pixels and answer a key the same way.

The checkbox is the row's indicator column, drawn by the same delegate, so a label sits at one x
down the whole list whether or not a row is ticked. A pick keeps the list open, and the measured
chip row hides whole chips into a `+n` pill when the control is too narrow for them.

`tk-framework-qtwidgets/python/search_completer/search_completer.py` runs its completion popup
unfiltered and draws every row through a delegate; this picker does the same. It was read, and
nothing was copied.
