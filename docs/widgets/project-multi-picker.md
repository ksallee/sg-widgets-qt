---
title: ProjectMultiPicker
description: Several projects, chosen by server-side search, with the project thumbnail and its status.
---

Searches projects on the server, showing each one's thumbnail and status, and binds the ones you
tick.

Single and multi: [ProjectPicker](project-picker.md) takes one project.

## Install

```python
from sg_widgets_qt.widgets.project_multi_picker import ProjectMultiPicker
```

::demo{name="project-multi-picker" title="ProjectMultiPicker: chips, archived projects, hydration, summary modes, sizes, states"}

## Props

::props{name="project-multi-picker" kind="props"}

`placeholder` defaults to `Search for projects`. `summary` and `max` set what the control shows for
the selection, as on every other multi picker.

The sub-label is the project's status, so an active project can be told from a bidding one.

Every row carries a checkbox and the list stays open across selections. Selected rows are appended
to the option list after the search results, so a project stays there to be unticked whatever the
query. Each selection is also a chip in the control, with its own remove control.

## Events

::props{name="project-multi-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="project-multi-picker" kind="keyboard"}

## API behaviour

Project's status field is `sg_status`, a plain list with no Status row behind it, where every other
type uses `sg_status_list` (entity_types/Project).

`sg_status` is not a liveness filter and is null on most projects; `archived`, `is_template` and
`is_demo` are the discriminators, which is why hiding archived projects filters on `archived`
(018_project_listing).

Project is site-wide and has no `project` field, so `projectId` adds nothing on this picker.

## Reference

The row, chip and checkbox anatomy follows shadcn's Base UI Combobox, read through shadcn 4.21.0.
The primitive underneath is Base UI Combobox 1.8.0 in React and Bits UI Combobox 2.19.1 in Svelte.
shadcn-svelte ships no combobox item, so each widget composes the headless primitive of its
framework and both draw the same rows, the same classes and the same states.

Here there is no headless primitive to compose. The widget is the entity picker with the project
preset on it: the box and its popup are `widgets/picker_control.py`, the popup is
`primitives/popover.py` and never takes focus, the list is `primitives/list_view.py`, and every row
is drawn by `primitives/row_delegate.py` through `PickerRowModel`, so PySide6 and PyQt5 draw the
same pixels and answer a key the same way. The read runs on `sg_widgets_qt.workers`.

`tk-framework-qtwidgets/python/shotgun_fields/entity_widget.py` edits an entity field through a
completer over a background task manager, and reads the field's schema before it offers anything;
this picker splits the same work between core and `sg_widgets_qt.workers` and leaves the site as
the only authority on what matches. It was read, and nothing was copied.
