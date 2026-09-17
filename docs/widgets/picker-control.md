---
title: PickerControl
description: The control box and popup shell every picker is built on.
---

The box a picker's value sits in, and the popup its rows come from. A picker built on it supplies its
query, its rows, its row renderer and its chip.

## Install

```python
from sg_widgets_qt.widgets.picker_control import PickerControl
```

::demo{name="picker-control" title="PickerControl: every shape a picker comes in, over one static list of departments"}

The demo draws every shape a picker comes in from one static list of departments: single and several,
inline and summary, a measured row that ends in `+n`, a fixed set with no search row, the three
heights, disabled, read-only and invalid, and a row and a chip of the caller's own. The chip is a
plain text chip; a picker that draws an entity chip or a status badge passes that instead.

## The control

The control is a bordered field at one of three heights, `sm`, `md` and `lg`. It carries `data-empty`
while nothing is chosen, which gives it the reading inset of a plain input; a filled control insets
its leading edge to the room above and below its chip, so a value sits evenly inside the border. The
height holds across both states, and the trailing inset is reserve for the clear control and the
chevron.

The states are attributes on the box: `aria-disabled` for a disabled or inert control, `data-readonly`,
`data-invalid`, `data-empty` while nothing is chosen, `data-multiple` on a control that takes several
keys, and the ring the field takes from whatever inside it has focus. A readonly control
keeps full contrast and loses the clear control and the chevron. The clear control appears once
something is chosen, and stays through a load.

A press anywhere on the control toggles the popup, its own caret included. A press on a button inside
the control — a chip's remove control, the clear control, the chevron — is that button's own. Typing
opens the popup, so a press that closed it a moment ago does not swallow the next keystroke, and a
press on the control is never read as a dismissal.

The caret that takes focus on open is the control's own when the control is inline, and the popup's
search box when it is a summary trigger. Every focus call passes `preventScroll`, so opening a picker
far down a page leaves the page where it is.

## Inline and summary

An inline control holds the caret beside its value: a token field, with the chips and the query on one
line. A summary control holds no input at all, so the search box sits at the top of the popup instead,
and the control shows the selection alone.

`summary` says what the control shows. `chips` draws every chip and wraps. `ellipsis` measures the row
against the room it has, draws whole chips only, hides the rest and follows the last one drawn with a
`+n` pill; a press on the pill opens the popup, where the hidden ones are. `count` replaces the row
with one line reading how many are selected. `max` caps the chips whatever the room allows.

## The popup

The popup is portalled, positioned with a fixed strategy and anchored on the whole control. It holds,
in order: the search row when the control is a summary trigger, then the list, then the load-more row.

The list draws one of four things. An error is the error line, a read in flight is three skeleton rows,
a query that matched nothing is the empty line, and otherwise it is the rows the picker supplied. A
further page adds a load-more row under them; a press on it pages rather than selects, so the popup
stays open and the value is untouched.

Above the list sits a live region, which says what the list is doing: the read in flight, the number
of rows it offered, the empty line, or what a failed read said. It is what a reader hears; the state
line inside the list is what a reader sees.

The list fades at whichever edge has more content past it and holds a gutter for its scrollbar, so
rows never shift as a page lands. The pattern is coss.com/ui at e937bec, whose scroll area reads the
same variables; it is read as a reference and not installed.

## Props

::props{name="picker-control" kind="props"}

## Slots

::props{name="picker-control" kind="slots"}

A chip carries `data-chip` so the measured row can weigh it, and `data-armed` while it holds the
caret, so every picker's chip says the same thing. The base takes every chip out of the tab order
and moves the caret between them itself, so a chip needs nothing of the caller for that.

## The contract

Every picker behaves the same, whether it is built on this base or keeps a primitive of its own.
The clauses are design rule 7; `tools/drives/picker-contract.js` checks the ones that apply to a
picker's shape, on every picker page, in both frameworks.

One picker, walked from the keyboard:

1. A press on the control toggles the list, its own caret included. Typing opens it again.
2. On open the caret takes focus: the control's input when the control is inline, the popup's
   search box when it is a summary trigger. A fixed set has no search row and holds one caret out
   of sight, so the keys still land somewhere. Every focus call passes `preventScroll`.
3. `ArrowDown` and `ArrowUp` move the highlight and the list scrolls it into view, through a
   load-more page and back to the top.
4. `Enter` takes the highlighted row. A multi picker stays open for the next one; a single picker
   closes.
5. `Backspace` and `ArrowLeft` in an empty query belong to the value: on a multi picker they take
   the caret to the last chip, and on a single picker `Backspace` clears the value in one press.
6. On a chip, `ArrowLeft` and `ArrowRight` walk the row and step off the last one back into the
   input, `Backspace` and `Delete` remove the chip and leave the caret on its neighbour, `Enter`
   and `Space` give the caret back, a printable key gives it back and writes that character into
   the query, and `ArrowDown` opens the list.
7. `Escape` closes the list and clears the query. The selection survives it, and on a closed picker
   the key belongs to whatever encloses the picker.
8. A press outside the control and the popup closes the list.
9. `Tab` leaves the control. The chips are walked with the arrows, not with `Tab`.

The chip model is Base UI's, which coss.com/ui at e937bec takes wholesale; here it lives in core so
both frameworks answer a key the same way, and it is read as a reference and not installed.
::qt-note

A readonly control keeps full contrast and loses the clear control and the chevron. A disabled one
takes no press and no key.

The clear control follows `clearable`, and a widget bound to a named field takes that answer from
the field: a field the site flags mandatory is never clearable, since clearing it writes a value the
site refuses. `clearableForField` in core is the one reading of that rule.

## Keyboard

::props{name="picker-control" kind="keyboard"}

## Composing a wrapper

A wrapper owns its value and its rows. It holds the chosen keys, maps each one to a label, answers the
query with rows — from a vocabulary it already has, or from a query layer — and hands the base `keys`,
`labels`, its rows and its chip. `slot` names every part of the result, so `entity-type-picker` gives
a control at `entity-type-picker-control` and rows the wrapper marks itself.

What the wrapper still spells out is its own: the slot prefix, the query source, the row and the chip.
The entity type picker is the smallest of them at around 250 lines per framework.

One thing an inline single picker owns: the primitive writes the chosen item into the caret, over the
chip that already says it. React passes `itemToStringLabel` to write nothing; Svelte mirrors the label
into the query, so the base's clear on close is a change the caret sees.
::qt-note

## PickerRow

The row every picker, search and tree draws, and the other half of a picker's list. It draws a row's
contents, not its box: the caller owns the list item and its selection state.

The row opens on an indicator column, which is a fixed width whether or not the row is ticked, so a
label sits at one x down the whole list. A multi picker puts its checkbox there and a single picker a
tick on the row it holds.

::props{name="picker-row" kind="props"}

Two slots, `glyph` and `indicator` in both frameworks. `glyph` is drawn in the leading slot when the
row carries no picture; a row whose type is a person draws an avatar there instead. `indicator` is
the tick or the checkbox in the indicator column, and the column is drawn only where a widget
passes it.

Here the row is a model rather than a component, because a Qt list draws its rows through a
delegate and a model is what the delegate reads. `PickerRowModel` takes the rows and the same row
keywords, resolves every part of the anatomy into the roles `RowDelegate` paints, loads each
picture on a worker and redraws the row it lands on. `glyph` and `indicator` are not slots: the
glyph is `set_glyph_of`, a callable of the row answering a lucide name, and the indicator is the
delegate's own column, which `indicator` turns into a leading checkbox or a trailing tick.
`PickerRowWidget` paints one row on its own, for a card or a chip preview.
