---
title: EntityCard
description: One Flow Production Tracking row as a card, or as a thumbnail-first tile.
---

Renders one row as a card: its thumbnail, name, type, status and a grid of the field paths you name.
Give the card a row you hold, or a reference and it reads the row itself. The tile variant reads the
same row picture first, and lands with EntityGrid.

## Install

The module brings StatusBadge and Thumbnail with it, which are what a status and a picture draw as.

```python
from sg_widgets_qt.widgets.entity_card import EntityCard
```

::demo{name="entity-card" title="EntityCard: three sizes from a row, one card reading a picked reference, and the three states"}

## Props

::props{name="entity-card" kind="props"}

A card reads through a context. Given a client instead, it builds one and shares it with every
other widget on that client.

These shape the tile and are ignored by the card: `label_field`, `sub_label_field`, `sub_label`,
`secondary_field`, `secondary`, `show_code`, `selectable`, `selected` and `actions`. The tile takes
its selected state rather than holding one, and reports a change on `selected_changed`, so a
collection can make it an option of a list and drive it. Nothing is on the metadata line by
default, and the row's id is never on it. The tile itself is drawn by EntityGrid, which owns the
picture that fills a cell's width; until then `variant` draws the card whichever value it holds.

Given a reference, the card reads the row itself: one search asking for the type's identity chain,
its thumbnail, its status field and your paths at once. The read goes through the context's cache,
so a second card on the same row costs nothing. It runs on a worker and never on the GUI thread,
and a card handed a second reference drops the answer to the first.

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

A card with no row yet shows a skeleton shaped like the card: the picture, two lines of the header
— three quarters of its width for the name and half for the line under it — and a pair of blocks
per path. A read that fails shows what it said on one line, or `error_label`
in its place.

Here the card is a `QWidget` whose object name is `entity-card`, so `size`, `model`, `name`, `url`,
`loading` and `error` are properties rather than data attributes. It fills the width it is given
and never more. A field's label sits on the baseline of the value beside it rather than on the top
of a row that stretched. A press on the name opens the row's page and emits `clicked`.

A value that points somewhere — a linked row, a url — reads as text until the pointer is on it,
which is when it underlines, so a stack of values does not read as a stack of rules. The name
underlines the same way. A url that leaves the application also carries the external mark the field
value draws, which the web widget does not.

## Events

::props{name="entity-card" kind="events"}

The card also emits `clicked` when its name is activated, and `loaded` carrying whether the read it
settled gave it a row.

## Slots

::props{name="entity-card" kind="slots"}

## Keyboard

::props{name="entity-card" kind="keyboard"}

Nothing else in the card takes focus. A value holding several links walks them with the arrows and
opens the one it is on. A tile is focusable only once whoever lays it out gives it a tab index;
EntityGrid does, and owns the arrow keys.

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
