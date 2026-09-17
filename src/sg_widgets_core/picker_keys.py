"""The keyboard model every picker shares.

A picker is a token field: chips, a caret and a list. The chips take the caret one at
a time, and Backspace, the arrows and Escape mean the same thing in all of them, so
the rules live here and the frameworks cannot drift.

The upstream `focusChip`, `scrollHighlightedIntoView` and `watchHighlight` hold no decision
and are not ported. The Qt layer gives the caret to the chip widget an intent names and
keeps its view scrolled to the highlighted row.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "PickerKeyIntent",
    "PickerKeyIntentKind",
    "PickerKeyState",
    "SearchKeyIntent",
    "SearchKeyIntentKind",
    "SearchKeyState",
    "picker_key_intent",
    "search_key_intent",
]

PickerKeyIntentKind = Literal["nothing", "dismiss", "focus", "remove", "type", "open", "follow"]


@dataclass(frozen=True)
class PickerKeyIntent:
    """What a keydown asks the control to do.

    `nothing` leaves the key to whatever encloses the control. `dismiss` closes the popup,
    clears the query and gives the caret back to the input. `focus` puts the caret on the
    chip at `index`, or back in the input when `index` is None. `remove` takes the chip at
    `index` and leaves the caret on `then`: a chip, or the input when None. `type` gives the
    caret back to the input and writes `key` into the query. `open` gives the caret back to
    the input and shows the list. `follow` keeps the list's highlighted row in view.
    """

    kind: PickerKeyIntentKind
    index: int | None = None
    then: int | None = None
    key: str | None = None


@dataclass
class PickerKeyState:
    """What the control looks like when the key arrives."""

    #: The popup is showing.
    open: bool
    #: Text in the search box.
    query: str
    #: Chips in the control. A single picker counts its value as one.
    count: int
    #: Index of the chip holding the caret, or None while the input holds it.
    focused: int | None
    #: The control takes edits. A disabled or readonly one takes none.
    editable: bool
    #: Several keys may be chosen at once.
    multiple: bool


def _printable(key: str) -> bool:
    """A key that writes one character, as against a named key like `Enter` or `Tab`."""
    return len(key) == 1 and key != " "


def picker_key_intent(key: str, state: PickerKeyState) -> PickerKeyIntent:
    """What a keydown means to a picker.

    From the input, Backspace and `ArrowLeft` in an empty query reach the chips of a multi
    picker rather than the text, and a single picker clears its one value in a press. From
    a chip, the arrows walk the row, Backspace and Delete take the chip and leave the caret
    on its neighbour, `ArrowDown` shows the list, and anything a person would type gives
    the caret back to the input. Escape is the control's business only while the popup
    shows; a closed picker leaves the key to whatever encloses it.
    """
    open_, query, count = state.open, state.query, state.count
    editable, multiple = state.editable, state.multiple
    focused = state.focused if state.focused is not None and 0 <= state.focused < count else None

    if key == "Escape":
        return PickerKeyIntent("dismiss") if open_ else PickerKeyIntent("nothing")

    if focused is not None:
        if not editable:
            return PickerKeyIntent("nothing")
        if key == "ArrowLeft":
            return PickerKeyIntent("focus", index=max(0, focused - 1))
        if key == "ArrowRight":
            return PickerKeyIntent("focus", index=focused + 1 if focused + 1 < count else None)
        if key in ("Backspace", "Delete"):
            then = min(focused, count - 2) if count > 1 else None
            return PickerKeyIntent("remove", index=focused, then=then)
        if key == "ArrowDown":
            return PickerKeyIntent("open")
        if _printable(key):
            return PickerKeyIntent("type", key=key)
        if key in ("Enter", " "):
            return PickerKeyIntent("focus", index=None)
        return PickerKeyIntent("nothing")

    if key in ("ArrowUp", "ArrowDown"):
        return PickerKeyIntent("follow") if open_ else PickerKeyIntent("nothing")
    if not editable or query != "" or count == 0:
        return PickerKeyIntent("nothing")
    if not multiple:
        if key == "Backspace":
            return PickerKeyIntent("remove", index=count - 1, then=None)
        return PickerKeyIntent("nothing")
    if key in ("Backspace", "ArrowLeft"):
        return PickerKeyIntent("focus", index=count - 1)
    return PickerKeyIntent("nothing")


SearchKeyIntentKind = Literal["nothing", "clear"]


@dataclass(frozen=True)
class SearchKeyIntent:
    """What a keydown asks a search box to do.

    `nothing` leaves the key to the shell. `clear` clears the query and the rows it
    answered, and keeps the caret where it is.
    """

    kind: SearchKeyIntentKind


@dataclass
class SearchKeyState:
    """What the search box looks like when the key arrives."""

    #: Text in the search box.
    query: str


def search_key_intent(key: str, state: SearchKeyState) -> SearchKeyIntent:
    """What a keydown means to a search box.

    Escape is the search box's business only while the query has text; an empty one leaves
    the key to the shell, as a closed picker does.
    """
    if key != "Escape":
        return SearchKeyIntent("nothing")
    return SearchKeyIntent("clear") if len(state.query) > 0 else SearchKeyIntent("nothing")
