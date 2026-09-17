---
title: EntityCard
description: One Flow Production Tracking row as a card, or as a thumbnail-first tile.
---

Renders one row as a card: its thumbnail, name, type, status and a grid of the field paths you name.
Give the card a row you hold, or a reference and it reads the row itself. The tile variant reads the
same row picture first, and is what EntityGrid lays out.

## Install

Installing this pulls StatusBadge and Thumbnail with it.

```python
from sg_widgets_qt.widgets.entity_card import EntityCard
```

::demo{name="entity-card" title="EntityCard: three sizes from a row, one card reading a picked reference, and the tile variant"}

## Props

::props{name="entity-card" kind="props"}

A card reads through a context. Given a client instead, it builds one and shares it with every
other widget on that client.

These shape the tile and are ignored by the card:

Nothing is on the metadata line by default, and the row's id is never on it. The tile takes its
selected state rather than holding one, and it spreads whatever attributes and handlers it is given
onto its root, so a collection can make it an option of a listbox and drive it.

Given a reference, the card reads the row itself: one search asking for the type's identity chain,
its thumbnail, its status field and your paths at once. The read goes through the context's cache,
so a second card on the same row costs nothing.

Every path is labelled through the schema. A hop names the type it travels through only when its
field accepts several, so `sg_task.Task.sg_status_list` reads

```
Task › Status
```

and `entity.Shot.sg_sequence` reads

```
Link › Shot › Sequence
```

A card is a compact surface, so a value is one line: a status is a badge, an image a thumbnail, a
linked row a link to its own page, and everything else the text core's formatters give it. A path
that names no field is shown under its own text with an empty value. A badge sits one step under
the card's own size.

The header names the row's own status, so a path naming that same field is not drawn a second time
in the grid. A path that ends at a linked row's status is a different row's status and stays.
The field is the type's conventional one, `sg_status_list` or `sg_status` on a Project, whatever
other status fields the site has added to the type.

A card with no row yet shows a skeleton shaped like the card; a read that fails shows the message
inline.

The root fills its container and carries the size as a data attribute.

## Events

::props{name="entity-card" kind="events"}

## Slots

::props{name="entity-card" kind="slots"}

## Keyboard

::props{name="entity-card" kind="keyboard"}

Nothing else in the card takes focus. A tile is focusable only once whoever lays it out gives it a
tab index; EntityGrid does, and owns the arrow keys.

## Anatomy

The tile follows the thumbnail view of the Flow PT web app and the asset grid of Frame.io: the
picture first and at one aspect, the state on the picture rather than under it, one line of name and
one of metadata, and the controls only while the pointer or the focus is on the tile.

## API behaviour

A dotted path is projected against the middle segment's `valid_types`: a segment outside that list
answers 200 with the key simply absent, so an unresolvable path is an empty value and not an error
(059_dotted_path_type_check).

A path through a multi-entity field reads back nothing at all, in a single read and in a search
alike, while the same path filters correctly (016_dotted_multi_entity).

The identity chain is intersected with the type's own schema before the read, because a field a type
does not have is a 400 and not an empty column: a Task has neither `code` nor `name`
(entity_types/Task).

Every type but Project holds its status in `sg_status_list`; Project's is `sg_status`, a plain list
with no Status row behind it (entity_types/Project). A site may add status fields of its own to a
type, and a schema read answers them in no fixed order, so the conventional name is what a row's
status is read from and never whichever status field the response listed first.

The web app addresses a row at `/detail/<Type>/<id>`. The API hands that path out for one type only,
as `Project.landing_page_url`, site-relative and with the site url left to the caller
(entity_types/Project). On the test site the same shape answers for every type: the route resolves
before authentication decides, redirecting an anonymous visitor to the login page with itself as the
return path. Site measurement, pending a corpus card.
