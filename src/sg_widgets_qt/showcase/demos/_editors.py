"""What the eight editor demos share: the row a case stands in and the readout under it.

The upstream demos draw a table whose first column names the case and whose second holds the editor
over the value it holds, printed as JSON. This is that table, as a column of rows.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from qtpy import QtCore, QtGui, QtWidgets

from ...primitives.base import ThemedWidget
from ...primitives.label import Separator

__all__ = ["CASE_WIDTH", "Case", "Mono", "Readout", "bind", "json_text", "rows"]

#: The width the case name takes, `w-28` of the upstream table.
CASE_WIDTH = 112

#: `px-3 py-2` of a table cell, and the 16 between stacked form fields.
ROW_GAP = 16
CELL_GAP = 8


def json_text(value: Any) -> str:
    """A value the way the upstream demo prints it, which is `JSON.stringify`."""
    return json.dumps(_plain(value), separators=(",", ":"), ensure_ascii=False)


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: item for key, item in asdict(value).items() if item is not None}
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


class Mono(ThemedWidget):
    """One 12px line in the monospace family, muted, elided at the end, rule 6."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.setToolTip(value)
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(12, mono=True, tabular=True)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, QtGui.QFontMetrics(self._font()).height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self._font())
        painter.setPen(self.theme.color("muted_foreground"))
        metrics = QtGui.QFontMetrics(painter.font())
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(self._text, QtCore.Qt.TextElideMode.ElideRight, self.width()),
        )
        painter.end()


class Readout(Mono):
    """The value the editor holds, printed the way the upstream demo prints it."""

    def show_value(self, value: Any) -> None:
        self.set_text(json_text(value))


class Case:
    """One row: the name, the editor and the readout under it."""

    def __init__(self, name: str, editor: QtWidgets.QWidget, readout: bool = True) -> None:
        self.name = name
        self.editor = editor
        self.readout = Readout("") if readout else None


def rows(parent: QtWidgets.QWidget, cases: list[Case]) -> QtWidgets.QWidget:
    """The table the upstream demos draw, as a column of `[name] [editor over its value]` rows."""
    holder = QtWidgets.QWidget(parent)
    column = QtWidgets.QVBoxLayout(holder)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(ROW_GAP)
    for index, case in enumerate(cases):
        row = QtWidgets.QWidget(holder)
        row.setObjectName("demo-case")
        row.setProperty("data_case", case.name)
        line = QtWidgets.QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(CELL_GAP)

        label = Mono(case.name, row)
        label.setFixedWidth(CASE_WIDTH)
        line.addWidget(label, 0, QtCore.Qt.AlignmentFlag.AlignTop)

        cell = QtWidgets.QWidget(row)
        stack = QtWidgets.QVBoxLayout(cell)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(CELL_GAP)
        case.editor.setParent(cell)
        stack.addWidget(case.editor)
        if case.readout is not None:
            case.readout.setParent(cell)
            stack.addWidget(case.readout)
        line.addWidget(cell, 1)
        column.addWidget(row)
        if index < len(cases) - 1:
            column.addWidget(Separator(parent=holder))
    return holder


def bind(case: Case, initial: Any, on_commit: Callable[[Any], None] | None = None) -> None:
    """Print the value the editor holds, and print it again on every commit."""
    if case.readout is None:
        return
    case.readout.show_value(initial)
    editor = case.editor

    def answered(value: Any) -> None:
        case.readout.show_value(value)
        if on_commit is not None:
            on_commit(value)

    editor.committed.connect(answered)
