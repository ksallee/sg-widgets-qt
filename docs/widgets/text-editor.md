---
title: TextEditor
description: A text field as an input, or a textarea when the field is multi-line.
---

Edits a text field and emits the string the API stores.

## Install

```python
from sg_widgets_qt.widgets.text_editor import TextEditor
```

::demo{name="text-editor" title="TextEditor: single line, multi-line, and the three blocked states"}

## Input

| typed | emitted |
|---|---|
| `plate delivered` | `"plate delivered"` |
| `  padded  ` | `"padded"` |
| empty, or spaces only | `null` |
| `line1` newline `line2` | `"line1\nline2"` |

## Props

::props{name="text-editor" kind="props"}

## Events

`onValueChange` fires on commit only, never on a keystroke. `onErrorChange` reports the parse error.

The two are signals here: `committed` carries the value above, and `error_changed` carries the
message or None.

## Slots

`errorMessage` receives the message and renders it. Without it the message is a small line under the
control.

## Keyboard

::props{name="text-editor" kind="keyboard"}

## API behaviour

Both ends of the value are stripped on write, and an empty string is stored as null, so there is no
"set but blank" state to round-trip. A non-string is a 400 (field_types/text).
