"""The table look of `table.tsx`.

No grid: one 1px line in `border` under the header and one under each row. Header cells are 12px
in `muted_foreground` at medium weight on a 40px row, body cells are 14px, and both take
12 horizontal and 8 vertical, which `density` of `compact` halves. A row lights under the
pointer in `muted` at 50% and stands chosen in `muted`.

A cell draws its text unless the model hands back a painter under `Roles.PAINTER`, which is how
a typed value, a status or a thumbnail reaches the same cell.
"""
from __future__ import annotations

from qtpy.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, Signal
from qtpy.QtGui import QFont, QFontMetrics, QPainter
from qtpy.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from .. import icons
from ..theme import Theme, theme_of, watch_theme, with_alpha
from .base import elide
from .roles import Roles
from .scrollbar import install_overlay_scrollbars

__all__ = [
    "CELL_PAD_X",
    "CELL_PAD_Y",
    "HEADER_HEIGHT",
    "HEADER_TEXT",
    "CellDelegate",
    "HeaderDelegate",
    "TableSurface",
]

#: `px-3 py-2` on both the header and the body.
CELL_PAD_X = 12
CELL_PAD_Y = 8

#: `h-10` on the header, and the type steps of the two rows.
HEADER_HEIGHT = 40
HEADER_TEXT = 12
CELL_TEXT = 14

#: The sort arrow beside a header label.
SORT_GLYPH = 12

#: How near the pointer must come to a divider for it to light.
HANDLE_REACH = 4


def _pad_y(density: str) -> int:
    return max(2, CELL_PAD_Y // 2) if density == "compact" else CELL_PAD_Y


class HeaderDelegate(QHeaderView):
    """The header row: its labels, its sort arrow, its rule and its resize handles."""

    sort_requested = Signal(int, int)

    def __init__(self, parent: QWidget | None = None, density: str = "default") -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._density = density
        self._handle = -1
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setStretchLastSection(True)
        self.setMouseTracking(True)
        self.setSortIndicatorShown(False)
        self.sectionClicked.connect(self._on_clicked)
        watch_theme(self, lambda _theme: self.viewport().update())

    def set_density(self, value: str) -> None:
        self._density = value
        self.updateGeometry()

    def _theme(self) -> Theme:
        return theme_of(self)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(super().sizeHint().width(), HEADER_HEIGHT - 2 * (CELL_PAD_Y - _pad_y(self._density)))

    def sortable(self, column: int) -> bool:
        """True when the model says this column sorts."""
        model = self.model()
        if model is None:
            return False
        return bool(model.headerData(column, Qt.Orientation.Horizontal, Roles.SORTABLE))

    def _on_clicked(self, column: int) -> None:
        if not self.sortable(column):
            return
        order = Qt.SortOrder.AscendingOrder
        if self.sortIndicatorSection() == column and self.sortIndicatorOrder() == order:
            order = Qt.SortOrder.DescendingOrder
        self.setSortIndicator(column, order)
        self.sort_requested.emit(column, int(order))

    def paintSection(self, painter: QPainter, rect: QRect, column: int) -> None:  # noqa: N802
        theme = self._theme()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(rect, theme.color("background"))

        model = self.model()
        label = "" if model is None else str(
            model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) or ""
        )
        box = rect.adjusted(CELL_PAD_X, 0, -CELL_PAD_X, 0)
        room = box.width()
        if self.sortable(column) and self.sortIndicatorSection() == column:
            room -= SORT_GLYPH + 6
        painter.setFont(theme.font(HEADER_TEXT, QFont.Weight.Medium))
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            QRect(box.left(), box.top(), max(0, room), box.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(painter, label, max(0, room)),
        )

        if self.sortable(column) and self.sortIndicatorSection() == column:
            name = (
                "arrow-up"
                if self.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
                else "arrow-down"
            )
            glyph = QRect(
                box.left() + max(0, room) + 6,
                box.top() + (box.height() - SORT_GLYPH) // 2,
                SORT_GLYPH,
                SORT_GLYPH,
            )
            icons.paint_icon(painter, glyph, name, theme.color("muted_foreground"))

        painter.fillRect(
            QRect(rect.left(), rect.bottom(), rect.width(), 1), theme.color("border")
        )
        if column < self.count() - 1:
            lit = column == self._handle
            painter.fillRect(
                QRect(rect.right(), rect.top() + 6, 1, rect.height() - 12),
                theme.color("ring") if lit else theme.color("border"),
            )
        painter.restore()

    def mouseMoveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        point = _point(event)
        found = -1
        for column in range(self.count() - 1):
            edge = self.sectionViewportPosition(column) + self.sectionSize(column)
            if abs(point.x() - edge) <= HANDLE_REACH:
                found = column
                break
        if found != self._handle:
            self._handle = found
            self.viewport().update()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._handle = -1
        self.viewport().update()


class CellDelegate(QStyledItemDelegate):
    """One body cell: its text or the painter the model hands back, and the rule under it."""

    def __init__(self, parent: QWidget | None = None, density: str = "default") -> None:
        super().__init__(parent)
        self._density = density

    def set_density(self, value: str) -> None:
        self._density = value

    def _theme(self, option: QStyleOptionViewItem) -> Theme:
        widget = getattr(option, "widget", None)
        return theme_of(widget if widget is not None else self.parent())

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        theme = self._theme(option)
        height = QFontMetrics(theme.font(CELL_TEXT)).height() + 2 * _pad_y(self._density)
        return QSize(option.rect.width(), height)

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        theme = self._theme(option)
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        view = getattr(option, "widget", None)
        hovered = isinstance(view, TableSurface) and view.hovered_row() == index.row()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, theme.color("muted"))
        elif hovered:
            painter.fillRect(rect, with_alpha(theme.muted, 0.5))

        painter.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), theme.color("border"))

        box = rect.adjusted(CELL_PAD_X, 0, -CELL_PAD_X, -1)
        paint_role = index.data(Roles.PAINTER)
        if callable(paint_role):
            paint_role(painter, box, option)
            painter.restore()
            return

        if bool(index.data(Roles.DISABLED)):
            painter.setOpacity(0.5)
        value = index.data(Qt.ItemDataRole.DisplayRole)
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        flags = int(alignment) if alignment is not None else int(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        painter.setFont(theme.font(CELL_TEXT))
        painter.setPen(theme.color("foreground"))
        painter.drawText(box, flags, elide(painter, "" if value is None else str(value), box.width()))
        painter.restore()


class TableSurface(QTableView):
    """A table wearing the shadcn look: no grid, a rule per row, and our overlay scrollbars."""

    sort_requested = Signal(int, int)

    def __init__(self, parent: QWidget | None = None, density: str = "default") -> None:
        super().__init__(parent)
        self._density = density
        self._hovered = -1

        self.setFrameShape(QTableView.Shape.NoFrame)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(
            CELL_TEXT + 2 * _pad_y(density) + 8
        )

        self._header = HeaderDelegate(self, density=density)
        self.setHorizontalHeader(self._header)
        self._header.sort_requested.connect(self.sort_requested.emit)
        self._cells = CellDelegate(self, density=density)
        self.setItemDelegate(self._cells)
        install_overlay_scrollbars(self)
        watch_theme(self, lambda _theme: self._apply_theme())
        self._apply_theme()

    # --- the keywords --------------------------------------------------------------------

    @property
    def density(self) -> str:
        """`default` or `compact`, which halves the vertical padding."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value
        self._header.set_density(value)
        self._cells.set_density(value)
        self.verticalHeader().setDefaultSectionSize(CELL_TEXT + 2 * _pad_y(value) + 8)
        self.viewport().update()

    def header(self) -> HeaderDelegate:
        """The header row."""
        return self._header

    def cell_delegate(self) -> CellDelegate:
        """The delegate drawing the body cells."""
        return self._cells

    def hovered_row(self) -> int:
        """The row under the pointer, or -1."""
        return self._hovered

    # --- events --------------------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = theme_of(self)
        self.setStyleSheet(
            f"QTableView {{ background: {theme.background}; color: {theme.foreground}; "
            "border: none; outline: none; }"
        )
        self.viewport().update()

    def mouseMoveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        index = self.indexAt(_point(event))
        row = index.row() if index.isValid() else -1
        if row != self._hovered:
            self._hovered = row
            self.viewport().update()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._hovered = -1
        self.viewport().update()


def _point(event: QEvent) -> QPoint:
    """A mouse event's position, on either binding."""
    return event.position().toPoint() if hasattr(event, "position") else event.pos()
