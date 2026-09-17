---
title: UrlEditor
description: 'A url field as a web link: address and name.'
---

Edits a url field as a web link. Uploads are not in scope.

## Install

```python
from sg_widgets_qt.widgets.url_editor import UrlEditor
```

::demo{name="url-editor" title="UrlEditor: a web link, an unset field, and a local path it will not edit"}

## Input

| typed | emitted |
|---|---|
| an address and a name | `{ url, name }` |
| an address, no name | `{ url }`; the field reads back the address as its name |
| both empty | `null` |
| an address holding a raw space | nothing; percent-encode it |
| a name and no address | nothing |

## Props

::props{name="url-editor" kind="props"}

A value whose link type is local carries paths and no address. The control shows a line saying so and
takes no input.

## Events

`onValueChange` fires on commit only. Input that does not parse emits nothing.

The two are signals here: `committed` carries the value above, and `error_changed` carries the
message or None.

## Slots

`errorMessage` receives the message and renders it.

## Keyboard

::props{name="url-editor" kind="keyboard"}

## API behaviour

The only accepted write is an object holding `url`. A bare string is a 400, and so is `{}` and an
object carrying only a type and an id (field_types/url).

The address itself is validated. A raw space is the one character measured to fail; the same address
with the space percent-encoded is accepted (field_types/url).

Each accepted write mints a new Attachment row and the value reads back as `link_type: web`. Only
`null` clears the field, and each derived field has to be cleared by name (field_types/url).
