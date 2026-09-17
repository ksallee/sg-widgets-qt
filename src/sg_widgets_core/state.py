"""The empty, loading and error states of `docs/design-rules.md` rule 5.

Every data widget takes the same three labels and draws the same block. The
defaults are here so the registries cannot drift and a studio that wants its
own wording sets one prop per widget. A translation seam belongs at this
boundary; until a non-English studio asks for one, these are the strings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "ERROR_LABEL",
    "LOADING_LABEL",
    "NOTHING_CHOSEN_LABEL",
    "NO_MATCH_LABEL",
    "NO_ROWS_LABEL",
    "StateLabels",
    "WIDGET_STATE_VALUES",
    "WidgetState",
    "error_text",
    "state_line",
]

#: The three states a data widget draws instead of its rows.
WidgetState = Literal["empty", "loading", "error"]
WIDGET_STATE_VALUES: tuple[WidgetState, ...] = ("empty", "loading", "error")


@dataclass
class StateLabels:
    """What a data widget calls its empty, loading and error states."""

    #: Shown when the read or the query returned nothing.
    empty_label: str | None = None
    #: The accessible name of the skeletons a read stands behind.
    loading_label: str | None = None
    #: Shown in place of what the failed read said.
    error_label: str | None = None


#: A query matched nothing.
NO_MATCH_LABEL = "No match"

#: A read returned nothing.
NO_ROWS_LABEL = "No rows"

#: A list of what the caller has picked holds nothing.
NOTHING_CHOSEN_LABEL = "Nothing chosen"

#: A read is in flight.
LOADING_LABEL = "Loading…"

#: A read failed and said nothing a reader can use.
ERROR_LABEL = "Something went wrong"


def state_line(state: WidgetState, labels: StateLabels, message: str | None = None) -> str:
    """The line a state block shows.

    An error falls back to what the read said and then to a fixed line, so a
    failure is never a blank block; a caller's `error_label` replaces both.
    """
    if state == "loading":
        return labels.loading_label if labels.loading_label is not None else LOADING_LABEL
    if state == "error":
        if labels.error_label is not None:
            return labels.error_label
        said = message.strip() if message is not None else ""
        return said if said else ERROR_LABEL
    return labels.empty_label if labels.empty_label is not None else NO_ROWS_LABEL


def error_text(error: object) -> str:
    """What a failed read said, as a line.

    An exception gives its message; anything else a read raised is rendered as itself, so a
    raised string still reads.
    """
    return str(error)
