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
`<site>/detail/<Type>/<id>`, and opens it in a new tab. A url you pass yourself belongs to your own
app and opens in the same tab. The `text` variant never links.

A `preview` list turns the chip into a hover card holding an EntityCard at its small size. The card
is read when the card opens, through the context's cache, so hovering the same row twice costs one
read.

A chip with no name shows the type and id instead, in the mono treatment ids get elsewhere.

Nine entity types have their own glyph: Shot, Asset, Sequence, Version, Task, HumanUser, Project,
Note and PublishedFile. Every other type, including a site's custom entities, gets a tag.

The root carries the entity type, id and variant as data attributes.

## Events

::props{name="entity-chip" kind="events"}

## Slots

None.

## Keyboard

::props{name="entity-chip" kind="keyboard"}

An inert chip takes no focus.

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
::qt-note

## EntityGlyphs

The glyph a chip shows for a type with no thumbnail. A stock site has 114 entity types and any
number of custom ones, so the map covers the types a widget meets constantly — Shot, Asset,
Sequence, Version, Task, HumanUser, Project, Note, PublishedFile — and everything else falls back to
a tag. It is a plain map from type name to icon: a caller with a custom type adds an entry.
