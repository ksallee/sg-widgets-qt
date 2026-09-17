---
title: FieldEditor
description: One field, displayed or edited, with the editor chosen by the data type.
---

Shows a field value and turns it into the right editor for its data type.

## Install

Importing this pulls the eight typed editors and the three pickers with it. The display half is
drawn here from core's `field_text`, with a status badge, an entity chip and a row of chips where a
value is not one line of text.

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
half. `project_id` scopes a status picker to the codes the project allows and an entity picker's
search to that project, and it is what subtracts a list field's hidden values.

A field the schema calls read-only is read-only here whatever `editable` says, so a computed or
locked field never opens.

Given an `entity`, the commit is written through `context.client.update` on a worker and the row is
read back on the field that was written, and a failed write puts what the site said under the
control. Without one the editor only emits `value_changed` and the caller writes.

## Props

::props{name="field-editor" kind="props"}

## Events

`value_changed` carries a committed value, in the shape the API takes. `mode_changed` carries
`display` or `edit` on every toggle. `error_changed` carries the editor's parse error, or what a
failed write said, and `None` when it clears.

## Slots

`error_message` takes the message and answers a widget, drawn in whichever editor is showing.

## Keyboard

::props{name="field-editor" kind="keyboard"}

Enter keeps the textarea of a multi-line text field open; leave it with `Tab`.

With `editor_placement='popover'` the value stays where it is and the editor opens under it: the
field's name, the control, then Cancel and Save. The popover is 288 pixels wide, or 384 for a
multi-entity field. Focus lands in the control and returns to the value when the popover closes.
`editor_placement=None` takes the placement core's `editor_placement_for` gives the data type.

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

A write answers the whole record but never resolves a dotted path, so the row is read again on the
field that was written (024_read_after_write).

## Reference

The pair of a display half and an editor half behind one toggle, with the display half asking to
edit and the editor half saying it is done, is the shape of
`tk-framework-qtwidgets/python/shotgun_fields/shotgun_field_editable.py`, and the map from a data
type to the widget that edits it is the shape of `shotgun_field_manager.py`. Both were read as a
reference and nothing was copied: the dispatch here is core's `editor_kind_for` and the halves are
this package's own widgets.
