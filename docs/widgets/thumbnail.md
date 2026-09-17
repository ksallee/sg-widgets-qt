---
title: Thumbnail
description: A row's thumbnail, with an explicit placeholder and a play overlay.
---

Renders the value of an image field at a fixed aspect ratio, with the row's own glyph standing in
whenever there is no picture to show.

## Install

```python
from sg_widgets_qt.widgets.thumbnail import Thumbnail
```

::demo{name="thumbnail" title="Thumbnail: sizes, aspects, play overlay, missing and failed images"}

## Props

::props{name="thumbnail" kind="props"}

The height comes from the size and the width from the aspect, so the widget never sets a fixed
width.

Three states render, and the root carries the resolved one as a data attribute: no image, still
transcoding, and ready. Most rows on a site never have a picture, so the no-image state is the
ordinary one and reads as one: the glyph of the entity type named by `entityType`, on the muted box.
Without a type a plain picture glyph stands there. A URL that fails to load draws the same, since a
presigned value expires.

The play badge does not take pointer events. Wrap the widget to make it clickable.

## Events

None.

## Slots

None.

## Keyboard

Not focusable.

## API behaviour

The value of an image field is a presigned URL that is re-signed on every read, so two reads of the
same row return different strings and a stored one expires. Cache the row id and re-read
(field_types/image).

That value is also the only state marker there is. Null means the row never had a thumbnail, and a
URL under the transient status path means one is still transcoding, so it is never tested for
truthiness (field_types/image).
