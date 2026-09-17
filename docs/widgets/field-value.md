---
title: FieldValue
description: Any Flow Production Tracking attribute value, rendered by its data type.
---

Renders a raw attribute value the way its data type should look, delegating to the other atoms where
one exists.

## Install

Installing this pulls EntityChip, StatusBadge and Thumbnail with it.

```python
from sg_widgets_qt.widgets.field_value import FieldValue
```

::demo{name="field-value" title="FieldValue: every data type, including the empty and sentinel cases"}

## Props

::props{name="field-value" kind="props"}

Each data type renders as follows.

The entity props are passed straight to EntityChip: a variant, the site each row is addressed on, and
the field paths its hover card shows.

A chip and a badge sit one step under the row around them: a collection passes its density, and a
compact one draws them a step smaller.

An unset value renders a muted marker rather than a dash, because a dash is a character a field can
hold. Zero, false and the string zero are values and render as themselves.

The root fills its container, carries the data type as an attribute, and puts the full value in a
tooltip for every single-line rendering.

## Events

None.

## Slots

None.

## Keyboard

::props{name="field-value" kind="keyboard"}

Nothing else in the widget takes focus.

## API behaviour

A checkbox is two-state and never null, so it is the one type whose empty-looking value is a real
one (field_types/checkbox).

A float is returned as a quoted string rounded to six decimals, never a JSON number
(field_types/float).

A url field is an object whose keys depend on its link type, and one of the three shapes carries no
URL at all, only local paths (field_types/url).

A colour field can hold a pipeline-step token instead of a colour, meaning the value should be taken
from the linked step (field_types/color).

A pivot column has no REST implementation and reads null on every row (field_types/pivot_column).
