---
title: ListMultiPicker
description: Several values of a list field, picked from the set its schema declares.
---

Chooses several values of a list field, offering the vocabulary its schema declares.

It is the shared picker control with rows from the field's valid values. The set is fixed and read
once, so there is no search row unless a caller asks for one, and a chosen value is a plain chip.

Single and multi: [ListPicker](list-picker.md) takes one value.

## Install

```python
from sg_widgets_qt.widgets.list_multi_picker import ListMultiPicker
```

::demo{name="list-multi-picker" title="ListMultiPicker: valid values, labels, a project's hidden values removed, a search box, and a mandatory field"}

## Input

| chosen | emitted |
|---|---|
| an unchecked row | the list with that value added at the end |
| a checked row | the list with that value removed |
| the clear control | an empty list |

The offered set is the field's valid values, minus its hidden values when a project id is given. A
value already held that is outside that set keeps a row of its own, labelled with the value.

The control draws a chip per chosen value. What does not fit on the line becomes a `+n` pill, and a
press on it opens the list.

## Props

::props{name="list-multi-picker" kind="props"}

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a `ref`
to the root element.

A row is the row anatomy of the design rules, after its checkbox: the label as the main text and,
with `showCode`, the stored string right-aligned.

## Events

::props{name="list-multi-picker" kind="events"}

`onValueChange` fires as soon as a row is checked or unchecked, and with an empty list when the
selection is cleared. `onErrorChange` fires with `null` on that same change, so a message the caller
set clears when the field is answered.

`onOpenChange` fires when the popup opens or closes. Svelte also binds it with `bind:open`.
::qt-note

## Slots

::props{name="list-multi-picker" kind="slots"}

## Keyboard

::props{name="list-multi-picker" kind="keyboard"}

## API behaviour

A list field holds one bare string, so several values only appear in a filter, under `in` and
`not_in`. A value outside `valid_values` is a 400 on write and the comparison is case-sensitive,
down to a trailing space, so the schema's vocabulary is the whole set a picker may offer
(field_types/list).

Hidden values reach the schema only when it is read with a project id, and REST does not enforce
them on write, so the subtraction is the client's (probe 009).
