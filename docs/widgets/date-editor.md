---
title: DateEditor
description: A date field as a picker button over a typed day and a calendar.
---

Edits a date field from one button, in every context.

The button carries a calendar icon, the stored day or the placeholder, and the invalid state; the
popover under it holds a typed day and the calendar, in that order.

## Install

```python
from sg_widgets_qt.widgets.date_editor import DateEditor
```

::demo{name="date-editor" title="DateEditor: three sizes, set, unset, and the three marked states"}

## Input

| typed | emitted |
|---|---|
| `2026-09-02` | `"2026-09-02"` |
| a day picked in the calendar | that day, as `YYYY-MM-DD` |
| empty | `null` |
| `2026-02-30` | nothing; no such day |
| `09/02/2026`, `2026-9-8`, a timestamp | nothing; wrong format |

## Props

::props{name="date-editor" kind="props"}

## Events

::props{name="date-editor" kind="events"}

`onValueChange` fires on commit and on a pick. Input that does not parse emits nothing.

The two are signals here: `committed` carries the value above, and `error_changed` carries the
message or None.

`open_changed` carries True when the calendar opens and False when it closes. `set_open` opens and
closes it, `toggle` is what a press on the trigger does, and `is_open` reads it back.

## Slots

`errorMessage` receives the message and renders it.

## Keyboard

::props{name="date-editor" kind="keyboard"}

## API behaviour

A date is exactly `YYYY-MM-DD`, with no time and no zone, and the API validates the day rather than
only parsing it: `2026-02-30` is refused by the same message as `tomorrow`. Any timestamp is a 400,
on write and as a filter value (field_types/date).

Both `null` and the empty string clear the field and read back as null, so there is one empty state
(field_types/date).
