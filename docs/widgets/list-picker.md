---
title: ListPicker
description: One value of a list field, picked from the set its schema declares.
---

Edits a list field, offering the vocabulary its schema declares.

It is the shared picker control with rows from the field's valid values. The set is fixed and read
once, so there is no search row unless a caller asks for one, and the control is the summary
trigger: the value reads as plain text, the way a select does.

Single and multi: [ListMultiPicker](list-multi-picker.md) takes several values.

## Install

```python
from sg_widgets_qt.widgets.list_picker import ListPicker
```

::demo{name="list-picker" title="ListPicker: valid values, labels, a project's hidden values removed, a search box, and a mandatory field"}

## Input

| chosen | emitted |
|---|---|
| a row | that row's value, byte for byte |
| the clear control | `null` |

The offered set is the field's valid values, minus its hidden values when a project id is given. A
row already holding a value outside that set keeps a row of its own, labelled with the value.

The list opens with the cursor on the row the picker holds, so a reader sees where the value sits;
one holding nothing opens with nothing highlighted, and the first <kbd>↓</kbd> takes the first row.

## Props

::props{name="list-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a `ref`
to the root element.

A row is the row anatomy of the design rules: the label as the main text and, with `showCode`, the
stored string right-aligned. A value has no picture and no fields of its own, so the row's leading
slot is empty unless a caller fills it and its secondary is a function rather than a field name.

The clear control follows the field. Left unset, `clearable` reads the field's schema, and a field
the site flags mandatory offers no clear, since clearing it writes a value the site refuses.

## Events

::props{name="list-picker" kind="events"}

`onValueChange` fires as soon as a row is chosen, and with `null` when the value is cleared.
`onErrorChange` fires with `null` on that same change, so a message the caller set clears when the
field is answered.

`onOpenChange` fires when the popup opens or closes. Svelte also binds it with `bind:open`.

`value_changed` carries the chosen string, or None once the value is cleared. `error_changed`
carries None on that same change, so a message the caller set clears when the field is answered.
`open_changed` carries True or False. All three are Qt signals; `on_value_change`,
`on_error_change` and `on_open_change` take a plain callable instead.

## Slots

::props{name="list-picker" kind="slots"}

## Keyboard

::props{name="list-picker" kind="keyboard"}

## API behaviour

Despite the name a list field holds one bare string. A write outside `valid_values` is a 400 and
case-sensitive, down to a trailing space, so the schema's vocabulary is the whole set a picker may
offer (field_types/list).

A filter is case-insensitive where a write is not, so a value read out of a filter is never safe to
write back (field_types/list).

Hidden values reach the schema only when it is read with a project id, and REST does not enforce them
on write, so the subtraction is the client's (probe 009).

## Reference

The box and its popup are `widgets/picker_control.py`, the popup is `primitives/popover.py`, the
list is `primitives/list_view.py`, and every row is drawn by `primitives/row_delegate.py`, so
PySide6 and PyQt5 draw the same pixels and answer a key the same way. The slots are callables:
`mark` answers a glyph name per row, `value_chip` answers the widget the control shows for the
value, and `error_message` answers the widget under it.

`tk-framework-qtwidgets/python/shotgun_fields/list_widget.py` edits a list field as a `QComboBox`
filled straight from `valid_values`, with the stored string as the item text and an empty first
item for "no value". The vocabulary is the same one here; the empty item is a clear control
instead, so a mandatory field can withhold it, and the control is drawn by this repo. It was
read, and nothing was copied.
