---
title: FieldValue
description: Any Flow Production Tracking attribute value, rendered by its data type.
---

Renders a raw attribute value the way its data type should look, delegating to the other atoms where
one exists.

## Install

The module brings EntityChip, StatusBadge and Thumbnail with it, which are what a linked row, a
status and an image draw as.

```python
from sg_widgets_qt.widgets.field_value import FieldValue
```

::demo{name="field-value" title="FieldValue: every data type, including the empty and sentinel cases"}

## Props

::props{name="field-value" kind="props"}

Each data type renders as follows. A number carries tabular figures and reads left to right like
the rest; right-aligning a column is a collection's decision, handed down through the `align`
option. A colour draws its swatch beside its value, a checkbox is the switch of its two states,
inert and at full contrast, and a url is an underlined label that opens through the desktop, a
local one carrying its own path in the tooltip.

Dates and numbers are formatted for the locales `en-US`, `en-GB`, `fr-FR`, `de-DE` and `ja-JP`.
Any other locale formats as `en-US`.

The entity props are passed straight to EntityChip: a variant, the site each row is addressed on, and
the field paths its hover card shows.

A chip and a badge sit one step under the row around them: a collection passes its density, and a
compact one draws them a step smaller. A multi-entity value wraps its chips across the room it has,
so none of them is hidden and none of them is counted.

An unset value renders a muted marker rather than a dash, because a dash is a character a field can
hold. Zero, false and the string zero are values and render as themselves.

Here the value is one painted `QWidget` whose object name is `field-value`, so `value`,
`data_type`, `kind` and `plan` are properties rather than data attributes. It fills the width it is
given and never more, every single-line rendering is elided at the end with the full value as its
tooltip, and free text keeps its newlines and wraps. The tooltip is the value the row holds rather
than the words it is drawn as, so a colour sentinel shows its `pipeline_step` token; a linked value
leaves the tooltip to the chips it is made of, and a picture and a checkbox carry none.

A value is also a painter, for a collection that draws a cell rather than holding one widget a row:

```python
paint_field_value(painter, rect, value, column, options)
field_value_size_hint(value, column, options)
```

The column is a resolved collection column or a bare data type, and the options carry the theme,
the status table, the site url, the density and the site preferences. Both faces settle what to
draw through one call, so a cell and a widget never disagree about a value: given the same value
and the same room the two land on the same pixels, which `tests/qt/test_field_value.py` measures
for every data type in both themes and both densities. A cell one line high shows the first line of
a value that wraps, which is what a table cell does with anything that runs past it.

## Events

None.

## Slots

None.

## Keyboard

::props{name="field-value" kind="keyboard"}

Nothing else in the widget takes focus. A value that opens nowhere is never in the tab order.

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
