---
title: CheckboxEditor
description: A checkbox field as an editable switch.
---

Edits a checkbox field with the shadcn switch.

The switch is the painted primitive of this package, so the control wears the theme's tokens and
never the host style.

## Install

```python
from sg_widgets_qt.widgets.checkbox_editor import CheckboxEditor
```

::demo{name="checkbox-editor" title="CheckboxEditor: two states, and the two blocked ones"}

## Input

| done | emitted |
|---|---|
| switch on | `true` |
| switch off | `false` |

There is no third state, and no way to clear the field.

## Props

::props{name="checkbox-editor" kind="props"}

## Events

::props{name="checkbox-editor" kind="events"}

`onValueChange` fires as soon as the switch moves. There is nothing to commit. `onErrorChange` fires
with `null` on that same change, so a message the caller set clears when the field is answered.

The two are signals here: `committed` carries the value above, and `error_changed` carries the
message or None.

## Slots

`errorMessage` receives the message and renders it.

## Keyboard

::props{name="checkbox-editor" kind="keyboard"}

## API behaviour

A checkbox is two-state and never null: a row that was never touched already reads false, a written
null is a 400, and `false` is the only off state (field_types/checkbox).
