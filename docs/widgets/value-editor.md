---
title: ValueEditor
description: The box and the session every leaf value editor runs on.
---

The box a value editor stands in and the session its control runs on. Text, number, url, colour,
date and date-time are built on it.

## Install

```python
from sg_widgets_qt.widgets.value_editor import ValueEditor
```

::demo{name="value-editor" title="ValueEditor: a frame range editor of the caller's own, on the base"}

The demo is an editor the base knows nothing about. A frame range is typed as two numbers and stored
as a pair, so the editor supplies a format and a parse of its own and draws one input. Everything
else on show is the base: the draft the input holds, the commit on leaving and on Enter, the Escape
that restores, the refusal as a line under the control, and the invalid ring the control wears while
that line is there. The second one is the row form at the small height, with a message the caller
named rather than one the parse made.

## The box

The box is a column: the control and whatever sits beside it, then the error line. It carries the
editor's `data-slot` name, its size and, on the row form, `data-inline`, where the box takes the
width of its value instead of the width it is given.

`render` draws the root with the attributes and classes the box carries, for an editor whose root is
a primitive of its own. The number editor uses it, since the primitive it stands on owns the pointer
over the whole field.

## The draft and the value

The value is what the caller holds; the draft is what the control shows. `format` turns one into the
other and `parse` turns it back, or names the reason it was refused.

While the control has focus the draft belongs to the control, so an incoming value never fights
typing. A value that changed elsewhere lands as soon as the control is left.

A commit parses the draft. It happens when the control loses focus and when Enter is pressed, and
`commitOnEnter` turns the second off where a newline is what Enter means. Losing focus because the
control was taken off the page is not a commit. A parsed value is emitted only when it differs from
the stored one; `same` says what differs means for a value that is not a scalar.

Escape restores the stored value and drops whatever the last parse said.

A value that needs no parse goes through `apply`: a picked day, a picked colour, a step on a number.
It writes the draft and emits in one act.

A refused parse becomes the message under the control, and the control reads invalid for as long as
that message is there. A message from the caller is shown in its place, and `invalid` sets the
reading on its own, for a field the site refused.

The checkbox editor is not built on this. It has no draft to hold, so it writes on the toggle, and
there is nothing between the two states for a parse to refuse.

## Props

::props{name="value-editor" kind="props"}

## The session

`useValueSession` in React and `createValueSession` in Svelte. Svelte takes a getter for every
option that changes — `value`, `error`, `invalid` and `commitOnEnter` — and React takes the value
itself.
::qt-note

| option | type | meaning |
|---|---|---|
| `value` | `TValue` | The stored value. |
| `format` | `(value: TValue) => TDraft` | The stored value as the draft the control shows. |
| `parse` | `(draft: TDraft) => ParseResult<TValue>` | The draft as a stored value, or the reason it was refused. |
| `onValueChange` | `(value: TValue) => void` | Called with a committed value that differs from the stored one. |
| `onErrorChange` | `(error: string \| null) => void` | Called when the parse error appears or clears. |
| `error` | `string \| null` | A message from the caller, shown in place of the parse error. |
| `invalid` | `boolean` | Forced invalid state. A failed parse sets it on its own. |
| `same` | `(next: TValue, current: TValue) => boolean` | Whether a value is the stored one. Default is `Object.is`. |
| `commitOnEnter` | `boolean` | Enter commits. False where a newline is what Enter means. |
| `stopKeys` | `boolean` | Enter and Escape stop where they are answered, for a control drawn in a portal. |
| `onEnter` | `(committed: boolean) => void` | After Enter, with whether the parse held. |
| `onEscape` | `() => void` | After Escape. |

| holds | type | meaning |
|---|---|---|
| `draft` | `TDraft` | What the control shows. Svelte writes it back; React has `setDraft`. |
| `editing` | `boolean` | Whether the control has focus. A blur that follows a teardown reads it. |
| `message` | `string \| null` | The caller's message, the parse error, or nothing. |
| `invalid` | `boolean` | The reading the control wears. |
| `apply` | `(value: TValue) => void` | Takes a value that needs no parse. |
| `commit` | `(draft?: TDraft) => boolean` | Parses the draft and takes it. Answers whether it parsed. |
| `reset` | `() => void` | Back to the stored value, with nothing left to report. |
| `onFocus` / `onBlur` / `onKeyDown` | handlers | The control's own. Svelte spells them `onfocus`, `onblur` and `onkeydown`. |
::qt-note

## FieldError

The line a value editor shows under its control when a parse fails or the caller names an error. The
box draws it, so an editor gets it without asking; an editor that puts the message somewhere else
draws it itself. `errorMessage` replaces the line; without it the message is a small destructive line
under the control.

::props{name="field-error" kind="props"}

## EditorCalendar

The two date editors hand a day to a calendar primitive, and the shape that primitive takes is not
the shape the API stores. `editor-calendar` is the pair of functions between them: one reads
`YYYY-MM-DD` as the calendar's day, one reads a picked day back out as `YYYY-MM-DD`, and a string
that is not a day reads as nothing picked (field_types/date).

The split of a day into its parts and the padding on the way back are core's. Only the shape the
primitive takes lives here, which is why each framework holds its own file: react-day-picker takes a
`Date`, Bits UI takes a `CalendarDate`.
::qt-note

## Composing an editor

An editor is a format, a parse and a control. It holds the value the caller passes, hands the session
those two functions for its own type, draws its control from the session's draft and handlers, and
stands the result in the box under its own slot name.

```tsx
const session = useValueSession<string | null, string>({
  value,
  format: (stored) => stored ?? '',
  parse: parseTextInput,
  onValueChange,
  onErrorChange,
  error,
  invalid,
});

return (
  <ValueEditor slotName="text-editor" size={size} message={session.message} errorMessage={errorMessage}>
    <Input
      value={session.draft}
      aria-invalid={session.invalid}
      onChange={(event) => session.setDraft(event.target.value)}
      onFocus={session.onFocus}
      onBlur={session.onBlur}
      onKeyDown={session.onKeyDown}
    />
  </ValueEditor>
);
```

```svelte
<ValueEditor slotName="text-editor" {size} message={session.message} {errorMessage}>
	<Input
		bind:value={session.draft}
		aria-invalid={session.invalid}
		onfocus={session.onfocus}
		onblur={session.onblur}
		onkeydown={session.onkeydown}
	/>
</ValueEditor>
```

What the six editors add on top of that is small: the number editor takes the root through `render`,
the two date editors put a calendar beside the input and pick through `apply`, and the url editor
commits two inputs into one value. `size`, `inline` and `errorMessage` reach every one of them from
here.
