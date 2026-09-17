"""The popup list every picker and search draws.

Upstream's `PICKER_LIST`: 288 pixels tall at most, a 4px inset, no gap between rows, the thin
overlay scrollbar in a gutter of its own, and a 24px fade over whichever edge has content past
it, sized by core's `overflow_edges`.

The list never takes focus. The anchor input holds it and hands the keys over through
`handle_key`, so a picker's caret stays where a person is typing while the highlight walks the
rows. `ArrowDown` past the last row holds, as the upstream Command does with `loop` off.
"""
from __future__ import annotations

from qtpy.QtCore import (
    QAbstractItemModel,
    QAbstractProxyModel,
    QEvent,
    QModelIndex,
    QPoint,
    QSize,
    Qt,
    Signal,
)
from qtpy.QtGui import QKeyEvent, QLinearGradient, QPainter
from qtpy.QtWidgets import QAbstractItemView, QListView, QWidget

from sg_widgets_core.list_chrome import OverflowEdges, overflow_edges

from ..theme import theme_of, watch_theme, with_alpha
from .roles import Roles
from .row_delegate import RowDelegate
from .scrollbar import WIDTH as SCROLLBAR_WIDTH
from .scrollbar import install_overlay_scrollbars

__all__ = [
    "FADE_SIZE",
    "LIST_PAD",
    "MAX_HEIGHT",
    "ListSurface",
]

#: `max-h-72`: the tallest a popup list stands before it scrolls.
MAX_HEIGHT = 288

#: `p-1`: the inset between the surface and its rows.
LIST_PAD = 4

#: `--fade-size: 1.5rem`: how far an edge with content past it is faded.
FADE_SIZE = 24

#: The gutter the scrollbar sits in, held whether or not the list scrolls.
GUTTER = SCROLLBAR_WIDTH + 2

#: The kinds the highlight walks over.
_SKIPPED = ("heading", "separator")

#: The root of a list model, held once so it is not built in a default argument.
_ROOT = QModelIndex()


class _LoadMoreProxy(QAbstractProxyModel):
    """The caller's rows, with one `load_more` row appended when the list asks for it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._visible = False
        self._label = "Load more"
        # The proxy holds the caller's model, which Qt's own `setSourceModel` does not own.
        self._source: QAbstractItemModel | None = None

    # --- the extra row ---

    def set_load_more(self, visible: bool, label: str = "Load more") -> None:
        visible = bool(visible)
        self._label = label
        if visible == self._visible:
            if visible:
                row = self.rowCount() - 1
                self.dataChanged.emit(self.index(row, 0), self.index(row, 0))
            return
        rows = self._source_rows()
        if visible:
            self.beginInsertRows(QModelIndex(), rows, rows)
            self._visible = True
            self.endInsertRows()
        else:
            self.beginRemoveRows(QModelIndex(), rows, rows)
            self._visible = False
            self.endRemoveRows()

    @property
    def load_more_visible(self) -> bool:
        return self._visible

    def is_load_more(self, row: int) -> bool:
        return self._visible and row == self._source_rows()

    def _source_rows(self) -> int:
        source = self.sourceModel()
        return 0 if source is None else source.rowCount()

    # --- the model ---

    def setSourceModel(self, model: QAbstractItemModel) -> None:  # noqa: N802
        old = self.sourceModel()
        self.beginResetModel()
        if old is not None:
            for signal, handler in self._wiring(old):
                try:
                    signal.disconnect(handler)
                except (RuntimeError, TypeError):
                    pass
        self._source = model
        super().setSourceModel(model)
        if model is not None:
            for signal, handler in self._wiring(model):
                signal.connect(handler)
        self.endResetModel()

    def _wiring(self, model: QAbstractItemModel) -> list[tuple[object, object]]:
        return [
            (model.rowsAboutToBeInserted, self._before_insert),
            (model.rowsInserted, self._after_insert),
            (model.rowsAboutToBeRemoved, self._before_remove),
            (model.rowsRemoved, self._after_remove),
            (model.modelAboutToBeReset, self.beginResetModel),
            (model.modelReset, self.endResetModel),
            (model.dataChanged, self._on_data),
            (model.layoutAboutToBeChanged, self.layoutAboutToBeChanged),
            (model.layoutChanged, self.layoutChanged),
        ]

    def _before_insert(self, _parent: QModelIndex, first: int, last: int) -> None:
        self.beginInsertRows(QModelIndex(), first, last)

    def _before_remove(self, _parent: QModelIndex, first: int, last: int) -> None:
        self.beginRemoveRows(QModelIndex(), first, last)

    def _after_insert(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.endInsertRows()

    def _after_remove(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.endRemoveRows()

    def _on_data(self, top_left: QModelIndex, bottom_right: QModelIndex, *_: object) -> None:
        self.dataChanged.emit(self.mapFromSource(top_left), self.mapFromSource(bottom_right))

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return self._source_rows() + (1 if self._visible else 0)

    def columnCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else 1

    def index(self, row: int, column: int, parent: QModelIndex = _ROOT) -> QModelIndex:
        if parent.isValid() or column != 0 or not 0 <= row < self.rowCount():
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, _child: QModelIndex = _ROOT) -> QModelIndex:
        return QModelIndex()

    def mapToSource(self, proxy: QModelIndex) -> QModelIndex:  # noqa: N802
        source = self.sourceModel()
        if source is None or not proxy.isValid() or self.is_load_more(proxy.row()):
            return QModelIndex()
        return source.index(proxy.row(), proxy.column())

    def mapFromSource(self, source: QModelIndex) -> QModelIndex:  # noqa: N802
        if not source.isValid():
            return QModelIndex()
        return self.index(source.row(), source.column())

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        if self.is_load_more(index.row()):
            if role == Roles.KIND:
                return "load_more"
            if role in (Roles.LABEL, Qt.ItemDataRole.DisplayRole):
                return self._label
            return None
        return super().data(index, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if self.is_load_more(index.row()):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return super().flags(index)


class ListSurface(QListView):
    """The scrolling list of rows a popup holds.

    `highlighted_changed` carries the row the keyboard cursor is on, `activated` the row a
    person chose with Enter or a click, and `load_more_requested` the press on the last row
    when one is on show.
    """

    highlighted_changed = Signal(int)
    activated = Signal(int)
    load_more_requested = Signal()
    #: A press landed on a row's drill control rather than on the row.
    drill_requested = Signal(int)

    def __init__(
        self,
        parent: QWidget | None = None,
        max_height: int = MAX_HEIGHT,
        size: str = "md",
        loop: bool = False,
        density: str = "default",
        delegate: RowDelegate | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_height = int(max_height)
        self._loop = bool(loop)
        self._proxy = _LoadMoreProxy(self)
        #: Where the cursor goes when the page the load-more row asked for lands.
        self._awaited_row: int | None = None

        self.setFrameShape(QListView.Shape.NoFrame)
        self.setViewportMargins(LIST_PAD, LIST_PAD, LIST_PAD + GUTTER, LIST_PAD)
        self.setSpacing(0)
        self.setUniformItemSizes(False)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

        self._delegate = delegate if delegate is not None else RowDelegate(self, size=size, density=density)
        self.setItemDelegate(self._delegate)
        # The list is as tall as its rows up to `max_height`, so a page landing under the
        # rows already there has to reach the layout that holds it and the overlay bar's range.
        for signal in (self._proxy.rowsInserted, self._proxy.rowsRemoved):
            signal.connect(self._on_rows_changed)
        self._proxy.modelReset.connect(self._on_model_reset)
        install_overlay_scrollbars(self)
        watch_theme(self, lambda _theme: self._apply_theme())
        self._apply_theme()

    # --- the model -----------------------------------------------------------------------

    def setModel(self, model: QAbstractItemModel) -> None:  # noqa: N802
        self._proxy.setSourceModel(model)
        if self.model() is not self._proxy:
            super().setModel(self._proxy)
            selection = self.selectionModel()
            if selection is not None:
                selection.currentRowChanged.connect(self._on_current)
        self.updateGeometry()

    def source_model(self) -> QAbstractItemModel | None:
        """The model the caller set, under the load-more row."""
        return self._proxy.sourceModel()

    def row_delegate(self) -> RowDelegate:
        """The delegate drawing the rows."""
        return self._delegate

    def set_load_more(self, visible: bool, label: str = "Load more") -> None:
        """Show or hide the last row that asks for the next page.

        The row taking the cursor is the row a reader is standing on, and the last page of a
        list takes the load-more row away under it, so the cursor moves to the last real row
        rather than being dropped and found again at the top.
        """
        held = self._proxy.load_more_visible and self._proxy.is_load_more(self.highlighted())
        self._proxy.set_load_more(visible, label)
        if held and not visible:
            self.highlight_last()
        self.updateGeometry()

    def is_load_more(self, row: int) -> bool:
        """True when `row` is the load-more row."""
        return self._proxy.is_load_more(row)

    def row_count(self) -> int:
        """Rows on show, the load-more row counted."""
        return self._proxy.rowCount()

    def load_more_visible(self) -> bool:
        """True while the last row is the one that asks for the next page."""
        return self._proxy.load_more_visible

    def _on_rows_changed(self, *_: object) -> None:
        awaited = self._awaited_row
        if awaited is not None and not self._proxy.is_load_more(awaited):
            self._awaited_row = None
            self.set_highlight(awaited)
        self.updateGeometry()

    def _on_model_reset(self) -> None:
        """A new query answers rows of its own: nothing of the last page is waited for."""
        self._awaited_row = None
        self.updateGeometry()

    # --- the highlight -------------------------------------------------------------------

    def highlighted(self) -> int:
        """The row the keyboard cursor is on, or -1."""
        index = self.currentIndex()
        return index.row() if index.isValid() else -1

    def set_highlight(self, row: int) -> bool:
        """Put the cursor on `row` and keep it in view. False when the row takes no cursor."""
        if not self._selectable(row):
            return False
        index = self._proxy.index(row, 0)
        if not index.isValid():
            return False
        if index.row() != self.highlighted():
            self.setCurrentIndex(index)
        self.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)
        return True

    def highlight_first(self) -> bool:
        """The first row that takes the cursor, with the list back at its top.

        A group heading sits above that row, so scrolling the cursor into view alone would
        push the heading out and the list would open on rows with nothing naming them.
        """
        moved = self._step_from(-1, 1)
        self.scrollToTop()
        return moved

    def highlight_last(self) -> bool:
        """The last row that takes the cursor."""
        return self._step_from(self.row_count(), -1)

    def highlight_next(self) -> bool:
        """The next row down. At the last row it holds, unless the list loops."""
        return self._move(1)

    def highlight_prev(self) -> bool:
        """The next row up. At the first row it holds, unless the list loops."""
        return self._move(-1)

    def highlight_page(self, forward: bool = True) -> bool:
        """A viewport of rows down or up."""
        step = max(1, self._rows_per_page())
        current = self.highlighted()
        if current < 0:
            return self.highlight_first() if forward else self.highlight_last()
        target = current + (step if forward else -step)
        target = max(0, min(self.row_count() - 1, target))
        direction = 1 if forward else -1
        if self._selectable(target):
            return self.set_highlight(target)
        return self._step_from(target - direction, direction)

    def _move(self, direction: int) -> bool:
        current = self.highlighted()
        if current < 0:
            return self.highlight_first() if direction > 0 else self.highlight_last()
        if self._step_from(current, direction):
            return True
        if not self._loop:
            return False
        return self.highlight_first() if direction > 0 else self.highlight_last()

    def _step_from(self, start: int, direction: int) -> bool:
        row = start + direction
        while 0 <= row < self.row_count():
            if self._selectable(row):
                return self.set_highlight(row)
            row += direction
        return False

    def _selectable(self, row: int) -> bool:
        index = self._proxy.index(row, 0)
        if not index.isValid():
            return False
        kind = index.data(Roles.KIND)
        if isinstance(kind, str) and kind in _SKIPPED:
            return False
        return not bool(index.data(Roles.DISABLED))

    def _rows_per_page(self) -> int:
        height = max(1, self.viewport().height())
        row = max(1, self.sizeHintForRow(0)) if self.row_count() else 1
        return max(1, height // row)

    def _on_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self.highlighted_changed.emit(current.row() if current.isValid() else -1)

    # --- choosing ------------------------------------------------------------------------

    def activate(self, row: int) -> bool:
        """Choose `row`: the load-more row asks for a page, any other row is the answer."""
        if not self._selectable(row):
            return False
        if self._proxy.is_load_more(row):
            # The page lands under the load-more row, so the cursor takes the seat the row
            # was in: the first of the new page, where Down carries on from.
            self._awaited_row = row
            self.load_more_requested.emit()
            return True
        self.activated.emit(row)
        return True

    def handle_key(self, event: QKeyEvent) -> bool:
        """Take one key from the widget holding the focus. True when the list used it."""
        key = event.key()
        modifiers = event.modifiers()
        if key == Qt.Key.Key_Down:
            self.highlight_next()
            return True
        if key == Qt.Key.Key_Up:
            self.highlight_prev()
            return True
        if key == Qt.Key.Key_PageDown:
            self.highlight_page(True)
            return True
        if key == Qt.Key.Key_PageUp:
            self.highlight_page(False)
            return True
        if key == Qt.Key.Key_Home and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.highlight_first()
            return True
        if key == Qt.Key.Key_End and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.highlight_last()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self.activate(self.highlighted())
        return False

    # --- the pointer ---------------------------------------------------------------------

    def mouseMoveEvent(self, event: QEvent) -> None:  # noqa: N802
        index = self.indexAt(_point(event))
        if index.isValid():
            self.set_highlight(index.row())
        super().mouseMoveEvent(event)

    def _on_drill(self, index: QModelIndex, point: QPoint) -> bool:
        """True when a press landed on the row's drill control rather than on the row.

        Upstream's drill is a button inside the row that stops the press reaching it, so a
        press on the chevron opens the level and a press anywhere else takes the row.
        """
        if not index.isValid():
            return False
        rect = self._delegate.drill_rect(self.visualRect(index), index)
        return not rect.isNull() and rect.contains(point)

    def mousePressEvent(self, event: QEvent) -> None:  # noqa: N802
        point = _point(event)
        index = self.indexAt(point)
        if event.button() == Qt.MouseButton.LeftButton and self._on_drill(index, point):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        point = _point(event)
        index = self.indexAt(point)
        if event.button() == Qt.MouseButton.LeftButton and self._on_drill(index, point):
            event.accept()
            self.drill_requested.emit(index.row())
            return
        super().mouseReleaseEvent(event)
        if index.isValid() and event.button() == Qt.MouseButton.LeftButton:
            self.activate(index.row())

    # --- the surface ---------------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = theme_of(self)
        self.setStyleSheet(
            f"QListView {{ background: {theme.popover}; color: {theme.popover_foreground}; border: none; outline: none; }}"
        )
        self.viewport().update()

    def fade_edges(self) -> OverflowEdges:
        """How far the list has content past each edge, in pixels."""
        bar = self.verticalScrollBar()
        height = self.viewport().height()
        return overflow_edges(bar.value(), bar.maximum() + height, height)

    def fade_sizes(self) -> tuple[int, int]:
        """The height of the fade drawn over the top and the bottom edge."""
        edges = self.fade_edges()
        return min(FADE_SIZE, edges.start), min(FADE_SIZE, edges.end)

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        top, bottom = self.fade_sizes()
        if top <= 0 and bottom <= 0:
            return
        theme = theme_of(self)
        surface = theme.color("popover")
        box = self.viewport().rect()
        painter = QPainter(self.viewport())
        if top > 0:
            gradient = QLinearGradient(0, box.top(), 0, box.top() + top)
            gradient.setColorAt(0.0, surface)
            gradient.setColorAt(1.0, with_alpha(surface, 0.0))
            painter.fillRect(box.left(), box.top(), box.width(), top, gradient)
        if bottom > 0:
            gradient = QLinearGradient(0, box.bottom() + 1 - bottom, 0, box.bottom() + 1)
            gradient.setColorAt(0.0, with_alpha(surface, 0.0))
            gradient.setColorAt(1.0, surface)
            painter.fillRect(box.left(), box.bottom() + 1 - bottom, box.width(), bottom, gradient)
        painter.end()

    # --- geometry ------------------------------------------------------------------------

    @property
    def max_height(self) -> int:
        """The tallest the list stands before it scrolls."""
        return self._max_height

    def set_max_height(self, value: int) -> None:
        self._max_height = int(value)
        self.updateGeometry()

    def content_height(self) -> int:
        """How tall the rows stand, the inset counted."""
        rows = self.row_count()
        if rows == 0:
            return 2 * LIST_PAD
        total = sum(self.sizeHintForRow(row) for row in range(rows))
        return total + 2 * LIST_PAD

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(super().sizeHint().width(), min(self._max_height, self.content_height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, min(self._max_height, self.content_height()))


def _point(event: QEvent) -> object:
    """A mouse event's position, on either binding."""
    return event.position().toPoint() if hasattr(event, "position") else event.pos()
