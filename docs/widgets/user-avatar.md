---
title: UserAvatar
description: A person as a round avatar, with an initials fallback.
---

Renders one person as a round avatar, falling back to initials whenever there is no picture.

## Install

```python
from sg_widgets_qt.widgets.user_avatar import UserAvatar
```

::demo{name="user-avatar" title="UserAvatar: sizes, initials, inactive users, API users"}

## Props

::props{name="user-avatar" kind="props"}

Initials are the first letter of the first and last word, so Ada Lovelace gives AL and Anna van der
Meer gives AM. A single word gives one letter, and a login is split on its punctuation. They come
from the core package, so both frameworks derive them identically.

The avatar never renders blank. An image that fails to load falls back to the initials, and with no
name at all it is still a muted circle. The name is always in the accessible tree.

An API user is a script account rather than a person, so it has neither a picture nor initials: the
circle holds a bot glyph on the secondary token pair, and the tooltip says what it is.

The root carries data attributes for a dimmed user and for an API user.

## Events

None.

## Slots

None.

## Keyboard

Not focusable.

## API behaviour

A person's image field is presigned and short-lived, like every other image on the site
(field_types/image).

A disabled person is a real row that still owns work: the status field holds a discarded code rather
than the row being removed, which is why the widget dims instead of hiding (entity_types/HumanUser).
