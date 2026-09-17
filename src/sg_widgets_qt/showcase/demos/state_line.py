"""The empty and error line at each of its paddings.

The port of `apps/site/src/demos/state-line/Demo.tsx`: inside a popup-sized box, in a table body,
and under rows already drawn. Each case carries an object name of its own, so a drive reads it
without knowing what surrounds it. Nothing here is read from a site.
"""
from __future__ import annotations

from qtpy import QtWidgets

from ...widgets.state_line import StateLine
from ..context import DemoContext
from ..stage import Surface
from . import _layout as lay

__all__ = ["build"]

#: The rows the last case draws its line under.
DEPARTMENTS = ("Layout", "Animation", "Lighting")

#: `w-72` of the upstream popup box.
POPOVER_WIDTH = 288

#: A popup list's own inset around its rows.
POPOVER_PAD = 4

#: A row of a plain list: 8 horizontal, 6 vertical (rule 2).
LIST_ROW_PAD_X = 8
LIST_ROW_PAD_Y = 6

#: The inset the last case's block gives the line it holds.
UNDER_ROWS_PAD = 8


def _boxed(
    inner: QtWidgets.QWidget, parent: QtWidgets.QWidget, pad: int = POPOVER_PAD, width: int = 0
) -> Surface:
    """One bordered surface holding a line, which is the box a popup or a body draws."""
    box = Surface(parent, token="background", border=True, radius="md")
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(pad, pad, pad, pad)
    layout.setSpacing(0)
    inner.setParent(box)
    layout.addWidget(inner)
    if width:
        box.setFixedWidth(width)
    return box


class StateLineDemo(QtWidgets.QWidget):
    """The line in a popup list, in a table body, and under rows already drawn."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("state-line-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.lines: list[StateLine] = []
        body = lay.column(self)
        body.addWidget(self._popover_case())
        body.addWidget(self._table_case())
        body.addWidget(self._under_rows_case())

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for line in self.lines:
            line.set_size(size)

    def _line(self, state: str, label: str, icon: str, pad: str = "popover") -> StateLine:
        line = StateLine(state=state, label=label, icon=icon, pad=pad, parent=self)
        self.lines.append(line)
        return line

    def _popover_case(self) -> QtWidgets.QWidget:
        case = lay.section(
            "In a popup list",
            lay.flow(
                _boxed(
                    self._line("empty", "No department matches", "search-x"),
                    self,
                    width=POPOVER_WIDTH,
                ),
                _boxed(
                    self._line("error", "The read was refused", "triangle-alert"),
                    self,
                    width=POPOVER_WIDTH,
                ),
            ),
            parent=self,
        )
        case.setObjectName("case-popover")
        return case

    def _table_case(self) -> QtWidgets.QWidget:
        case = lay.section(
            "In a table body",
            _boxed(self._line("empty", "No shot in this window", "inbox", pad="table"), self, 0),
            _boxed(self._line("error", "The read timed out", "circle-alert", pad="table"), self, 0),
            parent=self,
        )
        case.setObjectName("case-table")
        return case

    def _under_rows_case(self) -> QtWidgets.QWidget:
        box = Surface(self, token="background", border=True, radius="md")
        rows = QtWidgets.QVBoxLayout(box)
        rows.setContentsMargins(0, 0, 0, 0)
        # A list of rows has a zero gap, so a hover fill runs edge to edge (rule 2).
        rows.setSpacing(0)
        for department in DEPARTMENTS:
            label = QtWidgets.QWidget(box)
            inner = QtWidgets.QHBoxLayout(label)
            inner.setContentsMargins(LIST_ROW_PAD_X, LIST_ROW_PAD_Y, LIST_ROW_PAD_X, LIST_ROW_PAD_Y)
            inner.setSpacing(0)
            inner.addWidget(_row_label(department, label))
            rows.addWidget(label)

        line = StateLine(
            state="error",
            label="The next page did not arrive",
            icon="circle-alert",
            pad="none",
            slot_name="state-line-page-error",
            parent=box,
        )
        self.lines.append(line)
        holder = QtWidgets.QWidget(box)
        inset = QtWidgets.QHBoxLayout(holder)
        inset.setContentsMargins(UNDER_ROWS_PAD, UNDER_ROWS_PAD, UNDER_ROWS_PAD, UNDER_ROWS_PAD)
        inset.setSpacing(0)
        inset.addWidget(line)
        rows.addWidget(holder)

        case = lay.section("Under rows already drawn", box, parent=self)
        case.setObjectName("case-under-rows")
        return case


def _row_label(text: str, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
    from ...primitives.label import Label

    label = Label(text, parent=parent)
    return label


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return StateLineDemo(context, parent)
