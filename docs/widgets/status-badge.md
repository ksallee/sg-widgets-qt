---
title: StatusBadge
description: One Flow Production Tracking status as a badge.
---

Renders one status code as a badge carrying the site's own label and icon.

## Install

```python
from sg_widgets_qt.widgets.status_badge import StatusBadge
```

::demo{name="status-badge" title="StatusBadge: neutral and coloured, the bare glyph on the muted ground and on its colour, removable, labels, stock icons, unknown codes"}

## Props

::props{name="status-badge" kind="props"}

The name resolves in one order: the Status row's name, then the field's display value, then the raw
code. A code unknown to both renders as itself in the label and in the tooltip.

`glyph` is the icon alone, in its own colour, with no pill around it: no border, no background and no
inset, at the size a list row draws a glyph (4 at sm and md, 5 at lg). It is the leading mark of a row
whose label is a name, where a bordered pill reads as a second surface. The label stays as the
accessible name and the tooltip, `color` has nothing to paint, and a status with no icon to draw takes
a neutral dot.

The stock sprite was drawn as dark strokes for a light page, so a cell of it is inverted and its hue
rotated back on a dark page: the mark reads against the page in both schemes and a green tick stays
green. A site's own icon is sent ready for both and is left as it is, and so is a glyph sitting on the
status colour.

The root carries the status code, the variant and whether it was resolved, as data attributes. An
image-map icon carries its key on the glyph, as a data attribute. A removable badge draws its cross inside the pill
after the label, in the badge's own foreground, and carries a data slot of its own.

## Events

`onRemove` fires with the code. Without `removable` the badge is presentational and not
interactive.

## Slots

None.

## Keyboard

::props{name="status-badge" kind="keyboard"}

## API behaviour

A status_list value is a bare code with no entity behind it, so a dotted read through it returns
nothing and the label has to come from elsewhere (field_types/status_list, 009_status_lists).

Background colour arrives as comma-separated decimal RGB, never hex. Under `color` the foreground is
chosen by relative luminance, so the badge stays readable in both themes (010_status_icons). The
remove control's cross takes that same foreground, so it keeps its contrast on every status colour.

An icon's display type picks one of three renderings. An uploaded icon is a self-contained data URI.
An HTML icon is a short text label. An image-map icon names a cell of one sprite the web app serves
unauthenticated, positioned by a rule in the site's own stylesheet; neither the sprite nor the rule
is in the REST API (010_status_icons). Every icon the status picker offers, 94 cells, is bundled in
the core package and draws with no site access; the shipped statuses, the rows with no `created_by`,
all use one of them (probe 061). A key outside that set draws from the site's own copy of the sprite,
so it needs `siteUrl`; without one it falls back to a neutral dot.

## StatusGlyph

One status icon, at whatever size the caller draws it. The badge draws it, and so does every row
that shows a status. An uploaded icon is a self-contained data URI. A sprite icon names a cell of
the stock sprite: the 94 cells of the shipped statuses are bundled in core and draw with no site
access, any other cell draws from the site's own copy and so needs `siteUrl`, and a key with neither
resolves to a neutral dot. An HTML icon is the label itself, so it draws no picture; `fallback`
gives it the dot instead, which is what a list row wants.

::props{name="status-glyph" kind="props"}
