---
title: ColorEditor
description: A color field as a picker swatch and a text input.
---

Edits a color field and emits the decimal triple it stores.

## Install

```python
from sg_widgets_qt.widgets.color_editor import ColorEditor
```

::demo{name="color-editor" title="ColorEditor: a triple, a hex code, the pipeline-step token"}

## Input

| typed | emitted |
|---|---|
| `255,128,0` | `"255,128,0"` |
| `255, 128, 0` | `"255,128,0"`; the spaces are dropped |
| `#ff8000`, `ff8000` | `"255,128,0"` |
| `#f80` | `"255,136,0"` |
| `pipeline_step` | `"pipeline_step"` |
| empty | `null` |
| `300,0,0` | nothing; each channel runs 0 to 255 |
| `255,128` | nothing |

The swatch opens the browser's colour picker and follows what is typed, so a hex code shows its colour before it is committed.

There is no browser picker in Qt and the host's colour dialog is not ours to draw, so the swatch
opens a popover this package paints: a saturation and value square over a hue strip. Both are
dragged, and the arrows and Page Up and Page Down walk them.

## Props

::props{name="color-editor" kind="props"}

## Events

`onValueChange` fires on commit only. Input that does not parse emits nothing.

The two are signals here: `committed` carries the value above, and `error_changed` carries the
message or None.

## Slots

`errorMessage` receives the message and renders it.

## Keyboard

::props{name="color-editor" kind="keyboard"}

## API behaviour

The stored form is decimal `r,g,b`, no spaces and no `#`. Hex is rejected on write and inside a
filter, `255, 128, 0` with spaces is rejected, and a channel over 255 is rejected
(field_types/color).

The token `pipeline_step` means "use the colour of my pipeline step" and is the only way to un-set
`Task.color`: a written null is a 400 and the empty string is a 400 (field_types/color).

The legacy colour names are accepted on write but stored expanded, so `Red` never reads back as `Red`
(field_types/color). They are not offered here.
