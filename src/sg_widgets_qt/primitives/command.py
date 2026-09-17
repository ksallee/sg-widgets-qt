"""The Command surface: a search row over a list.

`command.tsx`: a popover-coloured panel holding the search row on its `bg-input/30` frame and a
`ListSurface` under it, with the empty line, the group headings and the separators the rows
carry. The input holds the caret and hands Up, Down, Enter and Escape to the list, which is
where the highlight lives.

`should_filter` on keeps the client-side substring match over the labels; off leaves the rows to
the caller, which is what a server list wants.
"""
from __future__ import annotations

from typing import Callable

from qtpy.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from qtpy.QtGui import QFont, QFontMetrics, QKeyEvent, QPainter
from qtpy.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from sg_widgets_core.list_chrome import ListStatusState, list_status
from sg_widgets_core.picker_keys import SearchKeyState, search_key_intent
from sg_widgets_core.state import NO_MATCH_LABEL, NO_ROWS_LABEL, StateLabels

from ..theme import theme_of, with_alpha
from .base import ThemedWidget, fill_round_rect
from .input_group import InputGroup, InputGroupInput
from .list_view import MAX_HEIGHT, ListSurface
from .roles import Roles

__all__ = [
    "COMMAND_PAD",
    "EMPTY_PAD",
    "Command",
    "CommandEmpty",
    "command_shortcut",
]

#: `p-1` around the search row and the list.
COMMAND_PAD = 4

#: `py-6`: the room above and below the empty line.
EMPTY_PAD = 24

#: The kinds a query never matches on.
_CHROME = ("heading", "separator")


class _Filter(QSortFilterProxyModel):
    """The client-side match: a substring of the label, case ignored.

    A heading and a separator are the list's own chrome, so a query drops them rather than
    matching their text.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._query = ""

    def set_query(self, value: str) -> None:
        self._query = value
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:  # noqa: N802
        if not self._query:
            return True
        source = self.sourceModel()
        if source is None:
            return True
        index = source.index(row, 0, parent)
        kind = index.data(Roles.KIND)
        if isinstance(kind, str) and kind in _CHROME:
            return False
        label = index.data(Roles.LABEL)
        if label is None:
            label = index.data(Qt.ItemDataRole.DisplayRole)
        return self._query.lower() in str(label or "").lower()


class CommandEmpty(ThemedWidget):
    """The centred line a list with no rows shows instead of them."""

    def __init__(self, parent: QWidget | None = None, text: str = NO_ROWS_LABEL) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, QFontMetrics(self.theme.font(14)).height() + 2 * EMPTY_PAD)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self.theme.font(14))
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self._text)
        painter.end()


def command_shortcut(text: str) -> Callable[[QPainter, QRect, object], None]:
    """A painter for `Roles.PAINTER` drawing a keystroke in the kbd look, right-aligned."""

    def paint(painter: QPainter, rect: QRect, option: object) -> None:
        widget = getattr(option, "widget", None)
        theme = theme_of(widget) if widget is not None else theme_of(painter.device())
        font = theme.font(12, QFont.Weight.Medium)
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance(text) + 12
        height = metrics.height() + 4
        box = QRect(rect.right() + 1 - width, rect.top() + (rect.height() - height) // 2, width, height)
        fill_round_rect(
            painter,
            box,
            float(theme.radius_px("sm")),
            with_alpha(theme.muted, 1.0),
            with_alpha(theme.border, 1.0),
        )
        painter.setFont(font)
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)

    return paint


class _CommandInput(InputGroupInput):
    """The search box. Every key the list wants goes to the list; the rest types."""

    def __init__(self, owner: Command) -> None:
        super().__init__(owner)
        self._owner = owner

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._owner.handle_key(event):
            return
        super().keyPressEvent(event)


class Command(ThemedWidget):
    """The shadcn Command: a search row over a list of rows.

    `set_model` takes the rows, as a `QAbstractItemModel` answering the roles in `roles.py`.
    `activated` carries the row in that model, whatever the filter is showing.
    """

    query_changed = Signal(str)
    activated = Signal(int)
    highlighted_changed = Signal(int)
    load_more_requested = Signal()
    dismissed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        placeholder: str = "Search",
        should_filter: bool = True,
        max_height: int = MAX_HEIGHT,
        size: str = "md",
        labels: StateLabels | None = None,
    ) -> None:
        super().__init__(parent, size_step=size)
        self._should_filter = bool(should_filter)
        self._labels = labels if labels is not None else StateLabels()
        self._filter = _Filter(self)
        self._model: QAbstractItemModel | None = None

        self._input = _CommandInput(self)
        self._input.setPlaceholderText(placeholder)
        self._group = InputGroup(self, size="sm", surface="muted")
        self._group.add_icon("search", "start")
        self._group.set_control(self._input)

        self._list = ListSurface(self, max_height=max_height, size=size)
        self._empty = CommandEmpty(self)
        self._empty.hide()

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        head = QVBoxLayout()
        head.setContentsMargins(COMMAND_PAD, COMMAND_PAD, COMMAND_PAD, COMMAND_PAD)
        head.setSpacing(0)
        head.addWidget(self._group)
        column.addLayout(head)
        column.addWidget(self._empty)
        column.addWidget(self._list, 1)

        self._input.textChanged.connect(self._on_query)
        self._list.activated.connect(self._on_activated)
        self._list.highlighted_changed.connect(self.highlighted_changed.emit)
        self._list.load_more_requested.connect(self.load_more_requested.emit)
        self.setFocusProxy(self._input)

    # --- the rows ------------------------------------------------------------------------

    def set_model(self, model: QAbstractItemModel) -> None:
        """Put the rows in the list, through the client-side filter when one is on."""
        self._model = model
        if self._should_filter:
            self._filter.setSourceModel(model)
            self._list.setModel(self._filter)
        else:
            self._list.setModel(model)
        model.modelReset.connect(self._on_rows)
        model.rowsInserted.connect(self._on_rows)
        model.rowsRemoved.connect(self._on_rows)
        self._on_rows()

    def model(self) -> QAbstractItemModel | None:
        """The rows the caller set."""
        return self._model

    @property
    def should_filter(self) -> bool:
        """Whether the query filters the rows here or is left to the caller."""
        return self._should_filter

    def set_should_filter(self, value: bool) -> None:
        self._should_filter = bool(value)
        if self._model is not None:
            self.set_model(self._model)

    def list_surface(self) -> ListSurface:
        """The list under the search row."""
        return self._list

    def input(self) -> InputGroupInput:
        """The search box, which holds the caret."""
        return self._input

    def set_load_more(self, visible: bool, label: str = "Load more") -> None:
        """Show or hide the row that asks for the next page."""
        self._list.set_load_more(visible, label)
        self._on_rows()

    # --- the query -----------------------------------------------------------------------

    @property
    def query(self) -> str:
        """What the search box holds."""
        return self._input.text()

    def set_query(self, value: str) -> None:
        """Write the query into the box, which filters the rows and emits `query_changed`."""
        self._input.setText(value)

    def _on_query(self, text: str) -> None:
        if self._should_filter:
            self._filter.set_query(text)
        self._on_rows()
        self._list.highlight_first()
        self.query_changed.emit(text)

    def _on_rows(self, *_: object) -> None:
        rows = self._list.row_count()
        self._empty.set_text(self._empty_line())
        self._empty.setVisible(rows == 0)
        self._list.setVisible(rows > 0)
        self._list.updateGeometry()
        self.updateGeometry()
        if rows > 0 and self._list.highlighted() < 0:
            self._list.highlight_first()

    def _empty_line(self) -> str:
        if self._labels.empty_label is not None:
            return self._labels.empty_label
        return NO_MATCH_LABEL if self.query else NO_ROWS_LABEL

    def status_line(self, loading: bool = False, error: str | None = None) -> str:
        """The one line the list's live region carries, from core's `list_status`."""
        state = ListStatusState(loading=loading, count=self._list.row_count(), error=error, asked=True)
        return list_status(state, self._labels)

    # --- keys ----------------------------------------------------------------------------

    def handle_key(self, event: QKeyEvent) -> bool:
        """Take one key from the search box. True when the Command used it."""
        if event.key() == Qt.Key.Key_Escape:
            intent = search_key_intent("Escape", SearchKeyState(query=self.query))
            if intent.kind == "clear":
                self.set_query("")
            else:
                self.dismissed.emit()
            return True
        return self._list.handle_key(event)

    def _on_activated(self, row: int) -> None:
        if self._should_filter:
            source = self._filter.mapToSource(self._filter.index(row, 0))
            row = source.row() if source.isValid() else row
        self.activated.emit(row)

    # --- the surface ---------------------------------------------------------------------

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fill_round_rect(painter, self.rect(), float(theme.radius_px("xl")), theme.color("popover"))
        painter.end()
