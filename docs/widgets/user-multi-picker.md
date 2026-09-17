---
title: UserMultiPicker
description: Several people and script accounts, chosen by server-side search across name, login and email.
---

Searches people, and optionally script accounts, on the server, and binds the rows you tick.

Single and multi: [UserPicker](user-picker.md) takes one person.

## Install

```python
from sg_widgets_qt.widgets.user_multi_picker import UserMultiPicker
```

::demo{name="user-multi-picker" title="UserMultiPicker: chips, scripts, inactive people, hydration, summary modes, sizes, states"}

## Props

::props{name="user-multi-picker" kind="props"}

`placeholder` defaults to `Search for people`. `summary` and `max` set what the control shows for
the selection, as on every other multi picker.

The query is matched against the display-name chain and the email, and against `login` while the
query holds no whitespace. Both fields are requested so the row can show them. A person's sub-label
is their email; a script account's is `API user`. A person's picture is an avatar, so
`round_thumbnail` starts True here and the rows draw circles. `subLabelField="login"` puts the login there
instead.

Every row carries a checkbox and the list stays open across selections. Selected rows are appended
to the option list after the search results, so a person stays there to be unticked whatever the
query. Each selection is also a chip in the control, with its own remove control.

## Events

::props{name="user-multi-picker" kind="events"}

## Slots

None.

## Keyboard

::props{name="user-multi-picker" kind="keyboard"}

## API behaviour

`login` is the only unique field on HumanUser and is what impersonation matches; `email` is not
unique, and `code` does not exist at all, so a filter on it is a 400
(entity_types/HumanUser).

Everyone on a site shares an email domain, so the address is matched with `starts_with` until the
query holds an `@`, and with `contains` after that. `contains` on the whole address would match the
domain and with it every person on the site (017_filter_operators).

`sg_status_list` on HumanUser is two codes, `act` and `dis`, with `act` the default
(entity_types/HumanUser). Active-only is that condition, and it is dropped on ApiUser, which has no
status field: the same name in a filter on a type that lacks it would be a 400
(017_filter_operators).

HumanUser is site-wide and has no `project` field; a person's membership is the `projects`
multi-entity on the row, so `projectId` scopes through that instead (entity_types/HumanUser).

## Reference

The row, chip and checkbox anatomy follows shadcn's Base UI Combobox, read through shadcn 4.21.0.
The primitive underneath is Base UI Combobox 1.8.0 in React and Bits UI Combobox 2.19.1 in Svelte.
shadcn-svelte ships no combobox item, so each widget composes the headless primitive of its
framework and both draw the same rows, the same classes and the same states.

Here there is no headless primitive to compose. The widget is the entity picker with the person
preset on it: the box and its popup are `widgets/picker_control.py`, the popup is
`primitives/popover.py` and never takes focus, the list is `primitives/list_view.py`, and every row
is drawn by `primitives/row_delegate.py` through `PickerRowModel`, so PySide6 and PyQt5 draw the
same pixels and answer a key the same way. The read runs on `sg_widgets_qt.workers`.

`tk-framework-qtwidgets/python/shotgun_fields/entity_widget.py` edits an entity field through a
completer over a background task manager, and reads the field's schema before it offers anything;
this picker splits the same work between core and `sg_widgets_qt.workers` and leaves the site as
the only authority on what matches. It was read, and nothing was copied.
