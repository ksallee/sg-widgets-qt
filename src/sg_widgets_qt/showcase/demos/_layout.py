"""The shapes the demos are laid out in.

A demo upstream is sections of a heading over a wrapping row (`flex-wrap`), which Qt has no layout
for, so `FlowLayout` is the one written here. The spacings are `docs/design-rules.md` rule 2: 16
between stacked sections, 8 inside one and between items in a row.

    body = column(self)
    body.addWidget(section("Sizes", flow(a, b, c), parent=self))
"""
from __future__ import annotations

from qtpy import QtCore, QtWidgets

from .. import chrome

__all__ = ["FlowLayout", "alive", "column", "flow", "heading", "row", "section"]

#: Between stacked sections, inside one, and between items in a row (rule 2).
SECTION_GAP = 16
INNER_GAP = 8
ROW_GAP = 8

#: The heading over a section: the metadata step, muted, in capitals.
HEADING_SIZE = 12


class FlowLayout(QtWidgets.QLayout):
    """A row that wraps, which is what every demo lays its examples out in."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, spacing: int = ROW_GAP) -> None:
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._lay(QtCore.QRect(0, 0, width, 0), measure=True)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._lay(rect, measure=False)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:  # noqa: N802
        size = QtCore.QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _lay(self, rect: QtCore.QRect, measure: bool) -> int:
        """Place the items line by line, each line's items centred on it, as `items-center` is."""
        space = self.spacing()
        x, y, line = rect.x(), rect.y(), 0
        pending: list[tuple[QtWidgets.QLayoutItem, int]] = []

        def flush() -> None:
            if measure:
                return
            for item, left in pending:
                hint = item.sizeHint()
                top = y + (line - hint.height()) // 2
                item.setGeometry(QtCore.QRect(QtCore.QPoint(left, top), hint))

        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line > 0:
                flush()
                pending = []
                x = rect.x()
                y += line + space
                line = 0
            pending.append((item, x))
            x += hint.width() + space
            line = max(line, hint.height())
        flush()
        return y + line - rect.y()


def column(parent: QtWidgets.QWidget) -> QtWidgets.QVBoxLayout:
    """The demo's own column: no margins of its own, sections 16 apart."""
    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SECTION_GAP)
    return layout


def heading(text: str, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The line over a section."""
    return chrome.TextLine(text.upper(), size=HEADING_SIZE, parent=parent)


def flow(
    *widgets: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None
) -> QtWidgets.QWidget:
    """A row of examples that wraps at the width it is given."""
    holder = QtWidgets.QWidget(parent)
    layout = FlowLayout(holder)
    for widget in widgets:
        layout.addWidget(widget)
    policy = QtWidgets.QSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
    )
    policy.setHeightForWidth(True)
    holder.setSizePolicy(policy)
    return holder


def row(*widgets: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """A row that does not wrap, for examples that stand on one line."""
    holder = QtWidgets.QWidget(parent)
    layout = QtWidgets.QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(ROW_GAP)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return holder


def section(
    title: str, *bodies: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None
) -> QtWidgets.QWidget:
    """One heading over the examples under it."""
    holder = QtWidgets.QWidget(parent)
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(INNER_GAP)
    layout.addWidget(heading(title, holder))
    for body in bodies:
        body.setParent(holder)
        layout.addWidget(body)
    return holder


def alive(widget: QtWidgets.QWidget) -> bool:
    """False once Qt has deleted the widget under the Python wrapper a callback still holds.

    A demo's read answers on the GUI thread, and the page it was built on may have gone by then.
    """
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True
