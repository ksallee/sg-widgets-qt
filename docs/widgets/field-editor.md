---
title: FieldEditor
description: One field, displayed or edited, with the editor chosen by the data type.
---

Shows a field value and turns it into the right editor for its data type.

## Install

Installing this pulls FieldValue, the eight typed editors and the three pickers with it.

```python
from sg_widgets_qt.widgets.field_editor import FieldEditor
```

::demo{name="field-editor" title="FieldEditor: every data type, with a display and edit toggle"}

## Editors

| data type | editor |
|---|---|
| `text`, `entity_type`, `uuid` | TextEditor |
| `number`, `float`, `percent`, `currency`, `duration`, `timecode` | NumberEditor |
| `checkbox` | CheckboxEditor |
| `date` | DateEditor |
| `date_time` | DateTimeEditor |
| `list` | ListPicker |
| `url` | UrlEditor |
| `color` | ColorEditor |
| `status_list` | StatusPicker |
| `entity` | EntityPicker |
| `multi_entity` | EntityMultiPicker |
| `image`, `calculated`, `summary`, `pivot_column`, everything else | none; display only |

A field whose type has no editor stays on the display half whatever the mode says.

The last three read the API, so they need `context`. A status field also needs its schema's
`entity_type` and a link field its `valid_types`; without either the field stays on the display
half. `projectId` scopes a status picker to the codes the project allows and an entity picker's
search to that project.

## Props

::props{name="field-editor" kind="props"}

## Events

`onValueChange` fires when the editor commits. `onModeChange` fires on every toggle.

## Slots

`errorMessage` receives the message and renders it, in whichever editor is showing.

## Keyboard

::props{name="field-editor" kind="keyboard"}

Enter keeps the textarea of a multi-line text field open; leave it with `Tab`.

With `editorPlacement="popover"` the value stays where it is and the editor opens under it: the
field's name, the control, then Cancel and Save. The popover is `w-72`, or `w-96` for a multi-entity
field. Focus lands in the control and returns to the value when the popover closes.

On a field whose editor is a button over a popup — a date, a date-time, a list, a status — Enter
opens the popup. On an entity field Enter chooses the highlighted row. Either way the value commits
inside the popup and the edit half stays until the press or the focus move that leaves it.

The commit is on Enter or on the press that lands outside, never on the blur itself: the control is
blurred first so what it holds is emitted, then the editor closes.

## API behaviour

The write shapes each editor emits are the ones its own page documents. The dispatch itself follows
the data types the corpus names, and the types with no editor here are the ones REST cannot write
(field_types/calculated, summary, pivot_column).

A status value is the raw code, never the display label (field_types/status_list). An entity value is
one `{type, id}` hash and a multi-entity value a list of them (field_types/entity).
