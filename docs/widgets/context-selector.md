---
title: ContextSelector
description: The project, row and task a user is working on, changed from recents, assigned tasks or the tree.
---

Shows the project, the linked row and the task the user is working on, and changes them from one
popover. The assigned tasks are a [`search-control`](search-control.md) with no query of its
own.

## Install

```python
from sg_widgets_qt.widgets.context_selector import ContextSelector
```

::demo{name="context-selector" title="ContextSelector: recents, assigned tasks and the tree in one popover, and the three sizes beside a button"}

## Props

::props{name="context-selector" kind="props"}

Every prop is a keyword of the constructor and a `set_<name>` after it. The events are Qt signals:
`work_context_changed`, `recents_changed` and `open_changed`.

A `WorkContext` is a dataclass of a project, an entity and a task, each of them an `EntityRef` or
None. `context_from_path` reads the three out of a path, which is what a pick from the tree gives.

The popover holds three sections in this order: the recents the caller passed, the tasks assigned to
`current_user` grouped by project with their step and status, and a drill-down over the navigation
tree scoped to the current project.

Picking an assigned task sets all three parts at once: the task, the row it hangs off and its
project. Picking from the tree reads the same three out of the path.

An assigned task is the shared picker row, and the row props shape it. With no `sub_label_field` and
no `sub_label`, the sub-label is the row the task hangs off and its step. The row props reach the
tree section too, so both lists read the same.

The three sections sit in one popover hanging off the trigger. The trigger carries the context as
entity chips and a chevron, on the control ladder; an empty one gives its leading inset back and
says so in `muted_foreground`. The first two sections scroll at their own height with the thin
overlay scrollbar.

## Events

::props{name="context-selector" kind="events"}

## Slots

None.

## Keyboard

::props{name="context-selector" kind="keyboard"}

## API behaviour

Assigned tasks are one search on Task filtered by `task_assignees`, a multi-entity field of Group and
HumanUser (entity_types/Task).

A Task is named by `content`. It has no `code` and no `name` field, and asking for one is a 400
rather than an empty result (entity_types/Task).

A task's status is a bare code with no row behind it, so its label comes from the field's display
values and its colour from the site's Status table (field_types/status_list, 010_status_icons).

## Reference

`tk-framework-qtwidgets`, `python/context_selector/context_widget.py`: a recent is the whole
context, keyed on the project, the link and the task together, rather than on the task alone, so
two tasks of one name under different shots are two entries. Read as a reference, nothing copied.
