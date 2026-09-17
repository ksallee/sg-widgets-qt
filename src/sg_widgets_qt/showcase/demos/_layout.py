"""The shapes the demos are laid out in.

A demo upstream is sections of a heading, an optional caption under it, and a wrapping row
(`flex-wrap`), which Qt has no layout for, so `FlowLayout` is the one written here. The heading is
upstream's `text-muted-foreground text-xs font-medium tracking-wide uppercase` and the caption its
`text-muted-foreground text-xs`. The spacings are `docs/design-rules.md` rule 2: 12 between
stacked sections, 6 between a heading and its caption, 8 from there to the example and between
items in a row.

    body = column(self)
    body.addWidget(section("Sizes", flow(a, b, c), caption="Small, medium and large", parent=self))
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from ...theme import theme_of, watch_theme
from .. import chrome

__all__ = [
    "CAPTION_SIZE",
    "HEADING_SIZE",
    "HEADING_TRACKING",
    "FlowLayout",
    "alive",
    "caption",
    "column",
    "field",
    "flow",
    "heading",
    "row",
    "section",
]

#: Between stacked sections, between a heading and its caption, and from there to the example.
#: Rule 2's scale: 12 between sections, 6 between an inline label and what it names, 8 in a row.
SECTION_GAP = 12
HEADING_GAP = 6
INNER_GAP = 8
ROW_GAP = 8

#: The heading over a section and the caption under it: the metadata step of rule 6, muted.
HEADING_SIZE = 12
CAPTION_SIZE = 12

#: `tracking-wide`, the 0.025em the heading is set at upstream, as Qt's percentage spacing.
HEADING_TRACKING = 102.5


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
    """The demo's own column: no margins of its own, sections a rule 2 gap apart."""
    layout = QtWidgets.QVBoxLayout(parent)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(SECTION_GAP)
    return layout


class _Heading(QtWidgets.QWidget):
    """The line over a section: capitals at the metadata step, medium, tracked wide, muted."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text.upper()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        watch_theme(self, lambda _theme: self.updateGeometry())

    def text(self) -> str:
        return self._text

    def _font(self) -> QtGui.QFont:
        font = theme_of(self).font(HEADING_SIZE, QtGui.QFont.Weight.Medium)
        font.setLetterSpacing(QtGui.QFont.SpacingType.PercentageSpacing, HEADING_TRACKING)
        return font

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(metrics.horizontalAdvance(self._text), metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setFont(self._font())
        painter.setPen(theme_of(self).color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()


def heading(text: str, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The line over a section, in capitals."""
    return _Heading(text, parent)


def caption(text: str, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The line under a heading saying what the example below it shows."""
    return chrome.TextLine(text, size=CAPTION_SIZE, parent=parent)


#: `section` takes a `caption` keyword, which shadows the function above inside it.
_caption_line = caption


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


def field(
    text: str, widget: QtWidgets.QWidget, parent: QtWidgets.QWidget | None = None
) -> QtWidgets.QWidget:
    """One caption over the example it names, which is upstream's `field` stack."""
    holder = QtWidgets.QWidget(parent)
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(INNER_GAP)
    layout.addWidget(caption(text, holder))
    widget.setParent(holder)
    layout.addWidget(widget)
    return holder


def section(
    title: str,
    *bodies: QtWidgets.QWidget,
    caption: str = "",
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QWidget:
    """One heading, the caption it carries, and the examples under them.

    The gaps are the ones rule 2 gives: 6 from the heading to its caption, 8 from there to the
    example, so the pair reads as one label however many examples follow it.
    """
    holder = QtWidgets.QWidget(parent)
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(heading(title, holder))
    if caption:
        layout.addSpacing(HEADING_GAP)
        layout.addWidget(_caption_line(caption, holder))
    for body in bodies:
        layout.addSpacing(INNER_GAP)
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
