---
title: DateTimeEditor
description: A date_time field as a picker button, shown local and stored UTC.
---

Edits a date_time field in the viewer's wall-clock time and emits the UTC instant the field stores.

The button carries a calendar icon, the stored instant or the placeholder, and the invalid state;
the popover under it holds a typed day, the calendar and the time, in that order.

## Install

```python
from sg_widgets_qt.widgets.date_time_editor import DateTimeEditor
```

::demo{name="date-time-editor" title="DateTimeEditor: three sizes, a second zone, unset, and the three marked states"}

## Input

| typed, in `America/Los_Angeles` | emitted |
|---|---|
| `2026-03-04` and `05:06` | `"2026-03-04T13:06:00Z"` |
| `2026-03-04` and `05:06:07`, with seconds shown | `"2026-03-04T13:06:07Z"` |
| `2026-03-04` and no time | `"2026-03-04T08:00:00Z"` |
| both empty | `null` |
| a time and no date | nothing; a time needs a date |

The zone the typed time is read in is named under the button.

## Props

::props{name="date-time-editor" kind="props"}

## Events

::props{name="date-time-editor" kind="events"}

`onValueChange` fires on commit and on a pick. Input that does not parse emits nothing.

The two are signals here: `committed` carries the value above, and `error_changed` carries the
message or None.

`open_changed` carries True when the calendar opens and False when it closes. `set_open` opens and
closes it, `toggle` is what a press on the trigger does, and `is_open` reads it back.

## Slots

`errorMessage` receives the message and renders it.

## Keyboard

::props{name="date-time-editor" kind="keyboard"}

A picked day leaves the popover open, so the time can follow it.

## API behaviour

The field is stored and read as UTC `YYYY-MM-DDTHH:MM:SSZ` at second resolution. A written offset is
normalised away and a zoneless string is taken as UTC, not as site-local, so a wall-clock time has to
be converted before it is sent (field_types/date_time).

Only `null` clears the field; the empty string is a 400 (field_types/date_time).

Most timestamp fields are server-managed, and the name does not predict it. Read the schema's
`editable` flag before offering this control (field_types/date_time).
