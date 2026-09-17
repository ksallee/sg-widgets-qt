---
title: Entity Grid
description: Flow Production Tracking rows as EntityCard tiles, with selection and a page number, a load-more row or the scroller.
---

Renders rows from an entity source as EntityCard tiles: the thumbnail fills the top of each tile, the
status sits on it, and one metadata line runs under the name.

`paging` says how the set is walked, and the source follows it: `scroll` loads the next page when
the scroller reaches the last loaded tile, `more` puts a load-more row under the tiles, and `pages`
draws the pagination footer. The grid defaults to `scroll`. A wall of pictures is browsed rather
than read, and the tile a reader wants is found by looking, not by page number.

`more` and `scroll` append: the tiles already loaded stay and the new page lands under them. A page
that fails leaves its tiles and puts one error line under them with a retry.

## Install

Installing this pulls EntityCard, and StatusBadge and Thumbnail with it.

```python
from sg_widgets_qt.widgets.entity_grid import EntityGrid
```

::demo{name="entity-grid" title="Entity Grid: Versions at three tile sizes, a selectable grid, one with no picture, one with every third card disabled, and one drawing a card of the caller's own"}

```ts
const context = createSgContext({ client });
const source = createEntitySource({
  client: context.client,
  entityType: 'Version',
  fields: ['code', 'image', 'sg_status_list', 'user'],
  pageSize: 12,
});
const [artist] = await resolveColumns(context.schema, 'Version', ['user']);
```

The source reads the fields the tiles draw. The status badge needs the type's status field in that
list; the metadata line needs whatever `subLabelField` and `secondaryField` name.

## Props

::props{name="entity-grid" kind="props"}

Nothing is on the metadata line by default, and the row's id is never on it.

## Events

::props{name="entity-grid" kind="events"}

## Slots

::props{name="entity-grid" kind="slots"}

## Keyboard

The grid is one tab stop: Tab moves into the tile the cursor is on, and the arrows walk from there.

::props{name="entity-grid" kind="keyboard"}

A disabled row takes no keys and no click: the arrows step over it and the cursor never lands on it.

## Anatomy

The tile follows the thumbnail view of the Flow PT web app and the asset grid of Frame.io: the
picture first and at one aspect, the state on the picture rather than under it, one line of name and
one of metadata, and the controls only while the pointer or the focus is on the tile.

## API behaviour

The value of an image field is a presigned URL re-signed on every read, and it is the only state
marker there is: null means the row never had a thumbnail, and a URL under the transient status path
means one is still transcoding. All three states render (field_types/image). A Version tile carries a
play overlay.

Paging stops on a short page: `links.next` is emitted on every page forever, including empty ones, and
no total is in a read (006_pagination). The "of N" in the footer comes from one `_summarize` call
counting `id`; a site that does not answer that key leaves the range without a total (020_summarize).
