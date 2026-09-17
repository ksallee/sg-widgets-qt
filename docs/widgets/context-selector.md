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

Every other attribute is spread onto the root: `id`, `aria-*`, `data-*`, key handlers and a
`ref` to the root element.

A `WorkContext` is a project, an entity and a task, each of them a row reference or null.

The popover holds three sections in this order: the recents the caller passed, the tasks assigned to
`currentUser` grouped by project with their step and status, and a drill-down over the navigation
tree scoped to the current project.

Picking an assigned task sets all three parts at once: the task, the row it hangs off and its
project. Picking from the tree reads the same three out of the path.

An assigned task is the shared picker row, and the row props shape it. With no `subLabelField` and no
`subLabel`, the sub-label is the row the task hangs off and its step. The row props reach the tree
section too, so both lists read the same.

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
