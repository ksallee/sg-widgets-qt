---
title: EntityChip
description: A linked Flow Production Tracking row as a compact chip.
---

Renders one linked row as a chip, an inline link or bare text, with a type glyph or thumbnail, its
name, an optional remove control and an optional hover card.

## Install

Installing this pulls EntityCard with it, for the hover card.

```python
from sg_widgets_qt.widgets.entity_chip import EntityChip
```

::demo{name="entity-chip" title="EntityChip: variants, links, hover card, sizes, thumbnails, removal"}

## Props

::props{name="entity-chip" kind="props"}

With no `href` and a site to work from, the chip addresses the row's own page,
`<site>/detail/<Type>/<id>`, and a press opens it in the desktop browser through
`QDesktopServices`. A url you pass yourself belongs to your own app, so hand it to `on_click`
instead and do the routing there. The `text` variant never links.

A `preview` list gives the chip a hover card. What the card holds is `set_preview_builder`, called
as `builder(entity, preview, context)`: EntityCard fills it once that widget lands, and until then
the card names the row and the paths that were asked for. The card is built on the hover card
primitive, which opens 200ms after the pointer lands and stays while the pointer is on either it or
the chip.

A chip with no name shows the type and id instead, in the mono treatment with tabular figures that
ids get elsewhere.

Nine entity types have their own glyph: Shot, Asset, Sequence, Version, Task, HumanUser, Project,
Note and PublishedFile. Every other type, including a site's custom entities, gets a tag.

Here the chip is one painted `QWidget` whose object name is `entity-chip`, so `entity`, `variant`,
`url`, `label` and `named` are properties rather than data attributes. A thumbnail is read through
`sg_widgets_qt.images` on a worker.

## Events

::props{name="entity-chip" kind="events"}

## Slots

None.

## Keyboard

::props{name="entity-chip" kind="keyboard"}

An inert chip takes no focus. The chip is one widget rather than a link with a button beside it, so
Tab reaches the chip itself: Enter and Space follow the link or run `on_click`, and Delete and
Backspace remove. On a chip that is removable and points nowhere, Enter and Space remove.

## API behaviour

The name in an entity hash is the target's cached display name, and it is filled on every entity
type measured, single links and multi links alike, so a chip needs no second call
(060_entity_dict_name).

A thumbnail URL is presigned and re-minted on every read, so pass a fresh one rather than a stored
string (field_types/image).

The web app addresses a row at `/detail/<Type>/<id>`. The API hands that path out for one type only,
as `Project.landing_page_url`, site-relative and with the site url left to the caller
(entity_types/Project). On the test site the same shape answers for every type: the route resolves
before authentication decides, redirecting an anonymous visitor to the login page with itself as the
return path. Site measurement, pending a corpus card.

## Reference

The hover card is shadcn's own, installed unmodified: Base UI's Preview Card (`@base-ui/react`
1.8.0) in React, Bits UI's Link Preview (`bits-ui` 2.19.1) in Svelte.

Here it is `primitives/hover_card.py` over `primitives/popover.py`, a frameless translucent window
with a painted shadow, so nothing of the host style shows through. The demo's wrapping rows are
Qt's own Flow Layout example (`examples/widgets/layouts/flowlayout`), read and not copied.

## EntityGlyphs

The glyph a chip shows for a type with no thumbnail. A stock site has 114 entity types and any
number of custom ones, so the map covers the types a widget meets constantly — Shot, Asset,
Sequence, Version, Task, HumanUser, Project, Note, PublishedFile — and everything else falls back to
a tag. It is a plain map from type name to icon: a caller with a custom type adds an entry.
