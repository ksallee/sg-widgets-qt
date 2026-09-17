"""The value-editor demo: a frame range editor of the caller's own, on the base.

The port of `apps/site/src/demos/value-editor/Demo.tsx`. The editor is one the base knows nothing
about: a frame range is typed as two numbers and stored as a pair, so it supplies a format and a
parse of its own and draws one input. Everything else on show is the base.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from qtpy import QtWidgets

from sg_widgets_core.edit import ParseError, ParseResult, ParseValue

from ...primitives.input import Input
from ...widgets.value_editor import VALUE_EDITOR_GAP, ValueEditor, ValueSession
from ..context import DemoContext
from . import _editors

__all__ = ["RangeEditor", "build"]

_RANGE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


@dataclass
class Range:
    """What this editor stores: the first and the last frame of a range."""

    first: int
    last: int


def format_range(value: Range | None) -> str:
    """The pair as the two numbers a person types."""
    return "" if value is None else f"{value.first}-{value.last}"


def parse_range(draft: str) -> ParseResult:
    """The two numbers back as a pair, or the reason they were refused."""
    raw = draft.strip()
    if not raw:
        return ParseValue(None)
    found = _RANGE.match(raw)
    if not found:
        return ParseError("A range reads as two frames, 1001-1120.")
    first, last = int(found.group(1)), int(found.group(2))
    if last < first:
        return ParseError("The last frame comes before the first.")
    return ParseValue(Range(first=first, last=last))


def same_range(next_value: Range | None, current: Range | None) -> bool:
    """A pair is a new object every parse, so identity is not what says it changed."""
    if next_value is None or current is None:
        return next_value is current
    return next_value.first == current.first and next_value.last == current.last


class RangeEditor(ValueEditor):
    """A frame range, on the base every leaf editor runs on."""

    def __init__(
        self,
        value: Range | None = None,
        size: str = "md",
        inline: bool = False,
        error: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__("range-editor", size=size, inline=inline, parent=parent)
        self.use_session(
            ValueSession(
                value,
                format=format_range,
                parse=parse_range,
                same=same_range,
                error=error,
                parent=self,
            )
        )
        self._input = Input(placeholder="1001-1120", size=size, parent=self)
        self._input.setObjectName("range-editor-input")
        self._session.bind(self._input)
        self.add_control(self._input)
        self._apply_state()

    @property
    def value(self) -> Range | None:
        """The stored pair."""
        return self._session.value

    def set_value(self, value: Range | None) -> None:
        self._session.set_value(value)

    @property
    def input(self) -> Input:
        """The caret the draft lives in."""
        return self._input

    def _apply_size(self, size: str) -> None:
        self._input.set_size(size)

    def _apply_state(self) -> None:
        control = getattr(self, "_input", None)
        if control is None:
            return
        control.setReadOnly(self.readonly)
        control.set_invalid(self.reads_invalid)


class ValueEditorDemo(QtWidgets.QWidget):
    """Two range editors: the default form, and the row form with a message the caller named."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("value-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.editors = [
            RangeEditor(value=Range(first=1001, last=1120), size="md"),
            RangeEditor(
                value=Range(first=1001, last=1064),
                size="sm",
                inline=True,
                error="The site refused this range.",
            ),
        ]
        captions = (
            "Cut range: commits on Enter and on leaving, restores on Escape",
            "Delivery range: the row form, small, with a message the caller named",
        )

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(VALUE_EDITOR_GAP * 2)
        for caption, editor in zip(captions, self.editors):
            column.addWidget(self._case(caption, editor))

    def _case(self, caption: str, editor: RangeEditor) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("demo-case")
        stack = QtWidgets.QVBoxLayout(holder)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(VALUE_EDITOR_GAP)
        stack.addWidget(_editors.Caption(caption, holder))
        editor.setParent(holder)
        stack.addWidget(editor)
        readout = _editors.Readout("", holder)
        readout.show_value(editor.value)
        editor.committed.connect(readout.show_value)
        stack.addWidget(readout)
        return holder

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The row form names its own."""
        self.editors[0].set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ValueEditorDemo(context, parent)
