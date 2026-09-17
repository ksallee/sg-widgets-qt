# Design rules

These rules bind every widget. A change that breaks one is not mergeable. The goal is one system:
a panel mixing ten of our widgets reads as one hand, and none of it reads as stock Qt.

The upstream rules are `~/dev/sg-widgets/docs/design-rules.md`. This file is that document with
Tailwind classes turned into pixels and Qt mechanisms. Where the two disagree, this one wins here.

## 0. Custom, not stock

Every visible control is drawn by this repo: `paintEvent` on a `QWidget` subclass, or a
`QStyledItemDelegate` inside a view, with the theme's tokens. A `QComboBox`, `QPushButton`,
`QCheckBox`, `QLineEdit` or `QScrollBar` drawn by the host style is a defect, so is a QSS rule that
leaves one of them looking native. Views (`QListView`, `QTableView`, `QTreeView`) are kept for
their models, virtualisation and keyboard handling, and every row they draw is a delegate of ours.
Scrollbars are the thin overlay kind, drawn by `primitives/scrollbar.py`.

Ideas are taken from the upstream shadcn primitives first, then from Qt widget libraries with a
modern look (qfluentwidgets, qt-material, QDarkStyle, tk-framework-qtwidgets), read and never
copied. The docs page names what was read.

## 1. Tokens only

- Colours, radius, fonts and shadows come from the `Theme` tokens (`background`, `foreground`,
  `card`, `popover`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `success`, `warning`,
  `info`, `border`, `input`, `ring`, each with its `_foreground` where shadcn has one, and `radius`).
  Never a literal `QColor("#...")` in a widget. The exceptions are colour that is data: status
  colour from the site through `parse_bg_color`, and the name-derived hue behind initials, both
  applied at paint time.
- A theme applies to a root widget through `apply_theme(root, theme)`, which sets the generated
  QSS on that root and a `Theme` the widgets under it read through `theme_of(widget)`. Never
  `QApplication.setStyleSheet`. A host's own stylesheet survives.
- `host_theme()` derives tokens from the host `QPalette`, so a widget dropped into Maya, Houdini or
  Nuke wears the host's greys and its accent.
- Light and dark, and the palettes the showcase offers, are values of the same tokens, read from
  `theme/palettes.json`, which `tools/export_palettes.py` writes from the upstream `themes.css`.

## 2. Spacing

- Parents own the gap. A layout sets its spacing; children never carry a margin to space
  themselves from siblings. If you reach for `setContentsMargins` on a child to make room, you are
  missing a layout.
- A parent owns a zero gap too. A list of rows has spacing 0, as every popup list does, so hover,
  drop-target and dragging fills run edge to edge. 8px is for items in a row, never for rows in a
  list.
- Padding belongs to the surface that has a border or background, not to its content. A row's
  padding is the inset of its own surface, never spacing between rows.
- Skeletons stand in for rows: same inset, same height, same zero gap.
- One scale, used everywhere:

  | role | value |
  |---|---|
  | between inline glyph and its text | 6 |
  | between items in a row or list | 8 |
  | between sections inside a card or popover | 12 |
  | between stacked form fields | 16 |
  | popover / card / dialog padding | 12 (compact), 16 (default) |
  | list row padding | 8 horizontal, 6 vertical |
  | list row holding an icon button | 8 horizontal, 2 vertical, so the button ladder sets the row at 28, 32 and 36 |
  | table cell padding | 12 horizontal, 8 vertical |

- Density is a keyword on collections (`density='compact' | 'default'`), never global. Compact
  halves the vertical padding only.
- Alignment: every row is a horizontal layout, vertically centred, with a fixed-size leading slot
  (thumbnail, avatar, checkbox) so text always starts at the same x. A picker option with a
  sub-label stays centred and takes 4px vertical padding, so its two lines stand as tall as a
  one-line option with a picture; a tree row with a sub-label aligns to the top. A multi picker's
  checkbox centres on the picture beside it; a single picker's tick trails the row.
- Truncation: single-line text is elided at the end with the full value as the tooltip. Never let a
  widget grow past its container horizontally; the horizontal size policy is Expanding with a
  minimum width of 0.

## 3. Sizes

- Controls come in `sm`, `md` (default), `lg`: heights 28, 32, 36. Icons inside controls are 16 for
  sm and md, 20 for lg. Thumbnails in list rows are 24 (sm), 32 (md), 40 (lg); cards and detail
  panes use 64 and 96. Avatars follow the first three.
- A chip or a badge sits one step under the control it is in: 20 high in sm, 24 in md, 32 in lg,
  medium weight, with a 12, 14 or 16 glyph. The edge beside a glyph takes a step less inset than a
  bare text edge (20: 6 bare, 4 beside a glyph), and the edge beside a cross matches the room above
  the cross. The glyph sits 4 from the label at the two small steps and 6 above; the cross a step
  closer. The cross grows with the chip, 12 at the smallest to 18 at the largest.
- A picker control insets its leading edge to match the room above and below the chip it holds. An
  empty control gives that inset back (md: 8 left, 0 vertical) so it reads as a plain input. The
  minimum height never changes; the trailing inset is reserve for the clear and open controls.
- An icon control (clear, open, remove) is drawn at the glyph's own size with a hit box of at least
  24 and, on a touch screen, 44.
- Width is the caller's business: widgets expand by default and never set a fixed width.

## 4. Motion

Motion explains a change; it never decorates.

- Durations: 100ms for a popover, a menu or a dialog entering or leaving, 150 for hover, press and
  focus feedback, 200 for chips and rows entering or leaving, 300 only for a large expanding panel.
  Nothing over 300.
- Easing: `QEasingCurve.OutCubic` to enter, `InCubic` to exit, `Linear` never.
- Animate only opacity, a translate of a few pixels, scale and height. Never width, margins or
  positions of siblings.
- Popovers: fade in plus a 4px slide from the anchor side and a scale from 0.95 to 1, on a
  frameless translucent top-level window with a painted shadow.
- Lists: an item appearing fades in over 150; an item removed fades and collapses over 200.
- Loading: never a spinner for the first 150ms. Skeletons shaped like the content they replace,
  with a shimmer; a spinner only inside a control that is busy.
- Hover and press: background change over 150; press scales to 0.98 on buttons and chips only.
- Reduced motion is a flag on the theme (`theme.reduced_motion`): all transitions collapse to
  opacity only, at the same durations. Test it once per widget.

## 5. States, in this order of precedence

`disabled` > `readonly` > `invalid` > `focus` > `hover` > `selected`.

- Focus: a 2px ring in `ring` at a 2px offset in `background`, painted around the control's
  rounded rect, only for keyboard focus (`Qt.TabFocusReason`, `BacktabFocusReason`, a shortcut).
  Never the host's focus rectangle.
- `ring` reads at least 3:1 against the surface it sits on in every palette; `tests/qt/test_palettes.py`
  measures it.
- Disabled: the widget at 50% opacity and inert. A tile that is mostly a picture also greys it.
  Readonly keeps full contrast and removes affordances (no chevron, no clear control).
- Invalid: the border and the ring in `destructive`, plus room for a message the caller renders.
- Selected rows: `accent` behind `accent_foreground`. The keyboard cursor uses the same, never a
  second colour.
- A remove control inside a chip or a badge hovers with a wash of its own foreground at 8%, never
  the destructive tint.
- Empty, loading and error states are part of every data widget and are visually consistent: a
  centred 14px line in `muted_foreground` with a 16px icon, 24px of vertical padding inside
  popovers, 40 in tables.

## 6. Typography

- Body 14px. Sub-labels and metadata 12px in `muted_foreground`. Ids and codes in the monospace
  family at 12px with tabular figures.
- Numbers right-aligned with tabular figures. Dates left-aligned.
- One weight step for emphasis (`QFont.Weight.Medium`). Matched search runs are `DemiBold`, not
  colour.
- The family is the theme's `font_sans`, which the host theme takes from the host and the showcase
  palettes name. Never a hardcoded family in a widget.

## 7. Composition and reuse

- Before building a control, look for its primitive in `primitives/`. Compose it. A widget exposes
  hooks for the parts callers will want to change: option row, selected item, empty state.
  Everything else is fixed.
- Keyboard first: every widget is operable without a mouse, and the keyboard model is documented on
  its docs page in one short table.

A picker is built on `picker_control`, one module: the control box with its states, the press
rule (a press anywhere on the control toggles the list, the caret included), the dismissal guard,
where the caret lands on open, the keyboard model of core's `picker_key_intent`, the inline token
field against the summary trigger with its chip row, and the popup shell: the search row, the
list, the empty, loading and error block, and the load-more row. A picker supplies its query and
rows, its row renderer and its chip.

The picker contract, every clause, is the upstream one:

1. A press on the control toggles the list, the caret included, and typing opens it.
2. The caret lands in the control's own input on open, or in the popup's search box on a summary
   control.
3. Escape closes the list and clears the query. On a closed picker it does nothing.
4. Backspace and Left in an empty query take the caret to the last chip of a multi picker, and
   Backspace clears the value of a single one. On a chip, the arrows walk the row, Backspace and
   Delete remove it and leave the caret on its neighbour, Enter, Space and a printable key give the
   caret back to the input, and Down opens the list.
5. Up and Down keep the highlighted row in view, across a load-more page.
6. A pick keeps a multi picker open and closes a single one.
7. An outside press closes the list.
8. The clear control follows `clearable` and is off on a mandatory field.
9. Readonly keeps full contrast and drops the affordances.
10. Disabled is inert.

`tests/qt/test_picker_contract.py` checks every clause that applies to a picker's shape, on every
picker.

A search widget is built on `search_control`: the query lifecycle (the pause before a query is
asked for, the ticket that drops an answer the next query replaced, the page and its load-more
row, and the highlight across that page) and the list it feeds: the error line, the skeletons, the
empty line, and the rows.

## 8. Checklist

1. No margins on layout children.
2. Only the spacing scale above.
3. Tokens only, no literal colours.
4. Motion on opacity, transform and height only, 100/150/200/300, reduced motion tested.
5. Nothing looks stock.
6. Empty, loading, error states present and consistent.
7. Focus rings painted, keyboard documented.
8. Expanding width, elision with a tooltip.
9. Runs on PySide6 and PyQt5.

## 9. Row anatomy and its props

Every widget that lists entity rows draws the same row (`picker_row`) and takes the same keywords:

| keyword | meaning | default |
|---|---|---|
| `thumbnail` | `False`, or the image field name (`'image'`) | `'image'` in pickers and search, `False` in dense lists |
| `label_field` | the field shown as the main label | the display-name chain in core |
| `sub_label_field` / `sub_label` | the muted line under the label | none |
| `secondary_field` / `secondary` | the right-aligned column, rendered by data type through `field_value` | the entity type when several types are shown, else none |
| `show_code` | show programmatic names beside display names where the row is a field or a type | `False` |
| `fields` | extra fields to request | `[]` |

A status offered as an option is the status glyph as its leading mark and the name as plain text,
matched runs bold, the code or the count right-aligned. The badge is what a status is where it is
a value: the selected value in a control, a list row's status column, a card, a table cell. The
stock sprite was drawn for a light page, so the glyph inverts and keeps its hue in dark.

A popup list fades at whichever edge has more content past it, holds a gutter for its scrollbar,
and sets an accessible description saying what it is doing: the read in flight, the count it
answered, the empty line, or what a failed read said.
