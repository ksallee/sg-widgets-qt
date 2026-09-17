---
title: NumberEditor
description: 'The numeric family as one input: number, float, percent, currency, duration and timecode.'
---

Edits any numeric field as a number field, with the parse, the format and the step chosen by the
data type.

## Install

```python
from sg_widgets_qt.widgets.number_editor import NumberEditor
```

::demo{name="number-editor" title="NumberEditor: one control over six data types"}

## Input

| data type | typed | emitted |
|---|---|---|
| `number`, `percent` | `42` | `42` |
| `number`, `percent` | `3.7` | nothing; whole numbers only |
| `float` | `1.23456789` | `"1.234568"` |
| `float` | `2` | `"2.0"` |
| `currency` | `12500.5` | `12500.5` |
| `duration` | `90` | `90` |
| `duration` | `1h 30m`, `1.5h`, `1:30` | `90` |
| `duration` | `2d`, with an eight-hour day | `960` |
| `timecode` | `3600000` | `3600000` |
| `timecode` | `01:00:00` | `3600000` |
| `timecode` | `00:00:01:00`, at 23.976 | `1000` |
| any | empty | `null` |

A duration shows the minutes it will store under the input while you type.

The value is written in the locale's own marks, so a currency reads `12,500.50` and a number reads
`1,001`. What is emitted keeps the API's shape. A typed unit form is parsed before it is formatted,
so `1h 30m` becomes `1:30` on commit.

## Stepping

The two buttons flanking the input, the arrow keys and the scrub area all move the value by one
step. The step is the unit the data type reads in:

| data type | step | bounds |
|---|---|---|
| `number`, `currency` | `1` | the 32-bit bounds |
| `float` | `0.1` | none |
| `percent` | `1` | `0` to `100` |
| `duration` | `15` minutes | the 32-bit bounds |
| `timecode` | one frame at `frameRate`, one second without one | the 32-bit bounds |

A step runs on the parsed value, so `1h 30m` in the input steps to `1:45`. A stepper goes disabled
at the bound it would cross. An empty field lands on zero on its first step.

## Props

::props{name="number-editor" kind="props"}

## Events

`onValueChange` fires on commit only. Input that does not parse emits nothing; it sets the invalid
state and reports the message through `onErrorChange`.

## Slots

`errorMessage` receives the message and renders it.

## Keyboard

::props{name="number-editor" kind="keyboard"}

The steppers are out of the tab order: the input reaches every value they do. Holding one down
repeats after 400ms, then every 60ms.

## API behaviour

A `number`, a `percent` and a `timecode` take whole numbers and reject a decimal outright, while a
`duration` truncates one toward zero at 200; all four sit in a signed 32-bit column
(field_types/number, percent, timecode, duration).

A `float` is returned as a quoted string rounded to six decimals, and rejects an integer on write and
inside a filter, so a whole value is emitted with a decimal point (field_types/float).

A duration is a whole number of minutes and the field names no unit. The site does:
`GET /preferences` carries `hours_per_day` and `duration_units` (field_types/duration).

A timecode is milliseconds. No schema or preference names the frame rate; a `_summarize` grouping is
the one place the server renders one, and the rate solves out of that (field_types/timecode).

The corpus has no card for `currency`. It is parsed as a decimal here, and its write shape is not
verified.

## Reference

The React half composes Base UI's NumberField 1.8.0 for the group, the steppers and the scrub area.
Bits UI has no number field, so the Svelte half is written here against the same parts, classes and
attributes; its state model — the step and its Shift and Page multipliers, the bounds, the hold that
repeats, the pixel-per-step scrub — follows Zag's number-input 1.43.3, which is not installed.
::qt-note
