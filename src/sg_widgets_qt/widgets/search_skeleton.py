"""The rows a search draws while its read is in flight.

The port of `search-skeleton.tsx`. Skeletons stand in for rows, so the block takes a row's
inset, a row's height and the zero gap of rule 2: a list holds its place when the page lands
rather than jumping under the reader. The leading slot is the row's own picture slot, and the
two bars sit in the line boxes of the label and the sub-label they replace.

    SearchSkeleton(label="Loading…", lines=3, size="md")

The block carries the loading line as its accessible name, so a reader hears what is happening
rather than nothing.
"""
from __future__ import annotations

from typing import Any

from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from sg_widgets_core.state import LOADING_LABEL

from ..primitives.base import THUMB_SIZE
from ..primitives.row_delegate import GAP, ROW_PAD_X, ROW_PAD_Y
from ..primitives.skeleton import Skeleton

__all__ = ["LABEL_BAR", "SUB_BAR", "SearchSkeleton"]

#: The line boxes the two bars sit in, and the bar inside each.
LABEL_LINE = 20
SUB_LINE = 16
LABEL_BAR = 12
SUB_BAR = 10

#: How wide each bar stands, as a share of the text column.
LABEL_WIDTH = 0.5
SUB_WIDTH = 0.25

#: Rows the block stands in for when the caller names none.
DEFAULT_LINES = 3


class SearchSkeleton(QWidget):
    """A column of skeleton rows, shaped like the rows they stand in for.

    `lead` is the leading slot's shape, a `QSize` or a `(width, height)` pair; with none it is
    the square of the thumbnail ladder at `size`, which is what a picker row draws there.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = LOADING_LABEL,
        lines: int = DEFAULT_LINES,
        lead: QSize | tuple[int, int] | None = None,
        slot_name: str = "search-loading",
        size: str = "md",
        animated: bool = True,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._lines = max(0, int(lines))
        self._lead = lead
        self._size = size
        self._animated = bool(animated)
        self.setObjectName(slot_name)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        # Rows in a list take no gap, so the skeletons take none either.
        self._column.setSpacing(0)
        self._rebuild()

    # --- the props ------------------------------------------------------------------------

    @property
    def label(self) -> str:
        """The accessible name of the block."""
        return self._label

    def set_label(self, value: str) -> None:
        self._label = value
        self.setAccessibleName(value)
        self.setAccessibleDescription(value)

    @property
    def lines(self) -> int:
        """Rows the read stands in for."""
        return self._lines

    def set_lines(self, value: int) -> None:
        value = max(0, int(value))
        if value != self._lines:
            self._lines = value
            self._rebuild()

    @property
    def lead(self) -> QSize:
        """The leading slot's shape."""
        if isinstance(self._lead, QSize):
            return QSize(self._lead)
        if isinstance(self._lead, (tuple, list)) and len(self._lead) == 2:
            return QSize(int(self._lead[0]), int(self._lead[1]))
        side = THUMB_SIZE.get(self._size, THUMB_SIZE["md"])
        return QSize(side, side)

    def set_lead(self, value: QSize | tuple[int, int] | None) -> None:
        self._lead = value
        self._rebuild()

    @property
    def slot_name(self) -> str:
        """The object name the block carries, the upstream `data-slot`."""
        return self.objectName()

    def set_slot_name(self, value: str) -> None:
        self.setObjectName(value)

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the rung the leading slot stands on."""
        return self._size

    def set_size(self, value: str) -> None:
        if value != self._size:
            self._size = value
            self._rebuild()

    @property
    def animated(self) -> bool:
        """Whether the shimmer runs."""
        return self._animated

    def set_animated(self, value: bool) -> None:
        self._animated = bool(value)
        for block in self.findChildren(Skeleton):
            block.set_animated(self._animated)

    # --- building it ----------------------------------------------------------------------

    def _rebuild(self) -> None:
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.set_label(self._label)
        for _ in range(self._lines):
            self._column.addWidget(self._row())
        self.updateGeometry()

    def _row(self) -> QWidget:
        lead = self.lead
        row = QWidget(self)
        row.setObjectName("search-skeleton-row")
        line = QHBoxLayout(row)
        # `px-2 py-1.5`: a skeleton row keeps the full inset whatever the row it stands in
        # for holds, so the block is as tall as the page that replaces it.
        line.setContentsMargins(ROW_PAD_X, ROW_PAD_Y, ROW_PAD_X, ROW_PAD_Y)
        line.setSpacing(GAP)

        picture = Skeleton(lead.width(), lead.height(), parent=row)
        picture.set_animated(self._animated)
        line.addWidget(picture)

        text = QWidget(row)
        column = QVBoxLayout(text)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._bar(text, LABEL_LINE, LABEL_BAR, LABEL_WIDTH))
        column.addWidget(self._bar(text, SUB_LINE, SUB_BAR, SUB_WIDTH))
        line.addWidget(text, 1)
        return row

    def _bar(self, parent: QWidget, line_height: int, bar: int, share: float) -> QWidget:
        """One bar in the line box of the text it stands in for."""
        box = _ShareBox(share, parent)
        box.setFixedHeight(line_height)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, (line_height - bar) // 2, 0, (line_height - bar) // 2)
        layout.setSpacing(0)
        block = Skeleton(None, bar, parent=box)
        block.set_animated(self._animated)
        layout.addWidget(block)
        layout.addStretch(1)
        box.set_block(block)
        return box

    def sizeHint(self) -> QSize:  # noqa: N802
        row = max(self.lead.height(), LABEL_LINE + SUB_LINE) + 2 * ROW_PAD_Y
        return QSize(0, row * self._lines)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


class _ShareBox(QWidget):
    """A line box holding a bar of a share of its own width, the upstream `w-1/2`."""

    def __init__(self, share: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._share = share
        self._block: QWidget | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_block(self, block: QWidget) -> None:
        self._block = block
        self._resize_block()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize_block()

    def _resize_block(self) -> None:
        if self._block is None:
            return
        self._block.setFixedWidth(max(24, int(self.width() * self._share)))
