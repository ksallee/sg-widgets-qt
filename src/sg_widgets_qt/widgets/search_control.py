"""The query lifecycle and the list every search widget is built on.

The port of `search-control.tsx`. The pause before a query is asked for, the ticket that
drops an answer the next query replaced, the page and its load-more row, the highlight across
that page, and the list itself: the error line, the skeletons, the empty line and the rows.
A wrapper supplies the read behind it and the model its rows are drawn from.

    control = SearchControl(load=find, model=PickerRowModel(context=context), paging=True)
    control.activated.connect(pick)

`load` runs on the `JobPool` and its answer lands on the GUI thread, so no read ever blocks
the caret. React draws the rows through a render prop; here a wrapper hands over a model,
which is what a Qt list draws through.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from qtpy.QtCore import QAbstractItemModel, QEvent, QSize, Qt, Signal
from qtpy.QtGui import QKeyEvent, QPainter
from qtpy.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from sg_widgets_core.list_chrome import ListStatusState, list_status
from sg_widgets_core.picker_keys import SearchKeyState, search_key_intent
from sg_widgets_core.search import (
    SEARCH_DEBOUNCE_MS,
    SearchViewState,
    query_plan,
    search_view,
)
from sg_widgets_core.state import (
    LOADING_LABEL,
    NO_MATCH_LABEL,
    StateLabels,
    error_text,
    state_line,
)

from ..primitives.base import ThemedWidget, fill_round_rect
from ..primitives.dialog import Dialog
from ..primitives.input_group import InputGroup, InputGroupInput
from ..primitives.list_view import MAX_HEIGHT, ListSurface
from ..workers import JobPool, QueryRunner, default_pool
from .picker_row import PickerRowModel
from .search_skeleton import SearchSkeleton
from .state_line import StateLine

__all__ = [
    "SEARCH_SHELLS",
    "SearchAnswer",
    "SearchControl",
    "SearchRequest",
    "SearchShell",
]

SearchShell = str
"""What is drawn around the list: `command`, `dialog` or `bare`."""

SEARCH_SHELLS: tuple[str, ...] = ("command", "dialog", "bare")

#: `p-1` around the search row and the list, as the Command surface takes.
BOX_PAD = 4

#: The load-more row's two labels.
LOAD_MORE_LABEL = "Load more"


@dataclass
class SearchRequest:
    """What a read is asked for: the query as it stands and the page wanted, one-based."""

    query: str
    page: int = 1


@dataclass
class SearchAnswer:
    """What a read answers: the rows it found and whether a further page may be there."""

    items: list = dc_field(default_factory=list)
    has_more: bool = False


LoadFn = Callable[[SearchRequest], Any]


def _answer_of(value: Any) -> SearchAnswer:
    """A read's answer, whether it named a page or handed back a bare list of rows."""
    if isinstance(value, SearchAnswer):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return SearchAnswer(items=list(value), has_more=False)
    items = getattr(value, "items", None)
    return SearchAnswer(
        items=list(items) if items is not None else [],
        has_more=bool(getattr(value, "has_more", False)),
    )


class _SearchInput(InputGroupInput):
    """The caret, which holds the keyboard while the list under it takes the arrows."""

    def __init__(self, owner: SearchControl, size: str = "md") -> None:
        super().__init__(owner, size=size)
        self._owner = owner

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._owner.handle_key(event):
            event.accept()
            return
        super().keyPressEvent(event)


class SearchControl(ThemedWidget):
    """The debounce, the ticket, the page and the list a search widget wears.

    `shell` is `command` for a box with a search row over the list, `dialog` for the same box
    inside a modal panel, and `bare` for the list alone, which is what a section of a larger
    surface takes.
    """

    #: The caret changed.
    query_changed = Signal(str)
    #: A row was taken. The payload is its index in the model.
    activated = Signal(int)
    #: A further page was asked for.
    load_more_requested = Signal()
    #: The read failed, with what it said.
    error = Signal(str)
    #: A dialog shell opened or closed.
    open_changed = Signal(bool)
    #: Escape on an empty query: the shell's own key.
    dismissed = Signal()
    #: A page landed, or the list emptied.
    rows_changed = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        load: LoadFn | None = None,
        model: QAbstractItemModel | None = None,
        query: str = "",
        request: str = "",
        enabled: bool = True,
        reads_empty: bool = False,
        paging: bool = False,
        debounce_ms: int = SEARCH_DEBOUNCE_MS,
        shell: SearchShell = "command",
        open: bool = False,
        title: str = "Search",
        description: str = "",
        placeholder: str = "Search…",
        empty_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        error_slot: str | None = "search-error",
        loading_slot: str | None = "search-loading",
        empty_slot: str | None = "search-empty",
        skeleton_lines: int = 3,
        skeleton_lead: QSize | tuple[int, int] | None = None,
        size: str = "md",
        max_height: int = MAX_HEIGHT,
        row_mapper: Callable[[list], list] | None = None,
        on_key_down: Callable[[Any, list], bool] | None = None,
        pool: JobPool | None = None,
    ) -> None:
        super().__init__(parent, size_step=size)
        self.setObjectName("search-control")
        self._load = load
        self._query = query
        self._request = request
        self._read_enabled = bool(enabled)
        self._reads_empty = bool(reads_empty)
        self._paging = bool(paging)
        self._shell = shell if shell in SEARCH_SHELLS else "command"
        self._open = bool(open)
        self._title = title
        self._description = description
        self._empty_label = empty_label
        self._loading_label = loading_label
        self._error_label = error_label
        self._error_slot = error_slot
        self._empty_slot = empty_slot
        self._size = size
        self._row_mapper = row_mapper
        self._on_key_down = on_key_down

        self._items: list = []
        self._page = 1
        self._has_more = False
        self._failure: str | None = None
        self._loading = bool(enabled) and query_plan(query, self._reads_empty) != "clear"
        self._dialog: Dialog | None = None
        self._rows_signal: Any = None

        self._runner = QueryRunner(
            pool if pool is not None else default_pool(), delay_ms=debounce_ms, parent=self
        )

        self._model = model if model is not None else PickerRowModel([], self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(0)

        self._input: _SearchInput | None = None
        self._group: InputGroup | None = None
        if self._shell != "bare":
            self._group = InputGroup(self, size="sm", surface="muted")
            self._group.add_icon("search", "start")
            self._input = _SearchInput(self, size=size)
            self._input.setObjectName("command-input")
            self._input.setPlaceholderText(placeholder)
            self._input.setText(query)
            self._group.set_control(self._input)
            head = QVBoxLayout()
            head.setContentsMargins(BOX_PAD, BOX_PAD, BOX_PAD, BOX_PAD)
            head.setSpacing(0)
            head.addWidget(self._group)
            self._column.addLayout(head)
            self._input.textChanged.connect(self._on_typed)
            self.setFocusProxy(self._input)

        self._list = ListSurface(self, max_height=max_height, size=size)
        self._list.setObjectName("search-list")
        self._list.setModel(self._model)
        self._sync_delegate()
        self._sync_query()
        self._list.activated.connect(self._on_activated)
        self._list.load_more_requested.connect(self.load_more)

        self._skeleton = SearchSkeleton(
            self,
            label=state_line("loading", self._labels()),
            lines=skeleton_lines,
            lead=skeleton_lead,
            slot_name=loading_slot or "",
            size=size,
        )
        self._empty = StateLine(
            state="empty",
            label=empty_label,
            icon="search",
            slot_name=empty_slot or "search-empty",
            size=size,
            parent=self,
        )
        self._error = StateLine(
            state="error",
            label=state_line("error", self._labels(), None),
            icon="triangle-alert",
            slot_name=error_slot or "search-error",
            size=size,
            parent=self,
        )

        body = QVBoxLayout()
        body.setContentsMargins(BOX_PAD, 0, BOX_PAD, BOX_PAD)
        body.setSpacing(0)
        for block in (self._error, self._skeleton, self._empty, self._list):
            body.addWidget(block)
        self._column.addLayout(body)

        if self._shell == "dialog":
            self._build_dialog()
        self._apply_view()
        self._restart()

    # --- the keywords ----------------------------------------------------------------------

    @property
    def load(self) -> LoadFn | None:
        """The read behind the list. It takes a request and answers the rows and `has_more`."""
        return self._load

    def set_load(self, value: LoadFn | None) -> None:
        self._load = value
        self._restart()

    @property
    def row_mapper(self) -> Callable[[list], list] | None:
        """The rows the model is given, from the items the read answered.

        A wrapper that groups its results, or puts a heading row among them, supplies one.
        """
        return self._row_mapper

    def set_row_mapper(self, value: Callable[[list], list] | None) -> None:
        self._row_mapper = value
        self._write_rows(self._items)

    @property
    def on_key_down(self) -> Callable[[Any, list], bool] | None:
        """Keys the wrapper owns, with the rows they act on. True when the wrapper used one."""
        return self._on_key_down

    def set_on_key_down(self, value: Callable[[Any, list], bool] | None) -> None:
        self._on_key_down = value

    @property
    def model(self) -> QAbstractItemModel:
        """The model the rows are drawn from. A wrapper hands over its own."""
        return self._model

    def set_model(self, value: QAbstractItemModel) -> None:
        self._model = value
        self._list.setModel(value)
        self._sync_delegate()
        self._sync_query()
        self._write_rows(self._items)

    def _sync_query(self) -> None:
        """Hand the query to the model, which is what makes the matched runs bold.

        Matching is the server's alone, so the query is only ever a mark: a model that takes
        none draws its labels whole.
        """
        setter = getattr(self._model, "set_query", None)
        if callable(setter):
            setter(self._query)

    def _sync_delegate(self) -> None:
        """The row keywords the delegate owns come off the model, which is where a caller sets them."""
        delegate = self._list.row_delegate()
        thumbnail = getattr(self._model, "thumbnail", True)
        delegate.set_thumbnail(thumbnail is not False)
        delegate.set_round_thumbnail(bool(getattr(self._model, "round_thumbnail", False)))
        delegate.set_bare_glyph(bool(getattr(self._model, "bare_glyph", False)))
        held, self._rows_signal = self._rows_signal, None
        if held is not None:
            try:
                held.disconnect(self._on_model_rows)
            except (RuntimeError, TypeError):
                pass
        changed = getattr(self._model, "rows_changed", None)
        if changed is not None:
            changed.connect(self._on_model_rows)
            self._rows_signal = changed

    def _on_model_rows(self) -> None:
        delegate = self._list.row_delegate()
        thumbnail = getattr(self._model, "thumbnail", True)
        bare = bool(getattr(self._model, "bare_glyph", False))
        if delegate.bare_glyph != bare:
            delegate.set_bare_glyph(bare)
        if delegate.thumbnail != (thumbnail is not False):
            delegate.set_thumbnail(thumbnail is not False)
            self._list.updateGeometry()

    @property
    def query(self) -> str:
        """What the caret holds."""
        return self._query

    def set_query(self, value: str) -> None:
        value = value or ""
        if value == self._query:
            return
        self._query = value
        if self._input is not None and self._input.text() != value:
            self._input.setText(value)
        self._sync_query()
        self.query_changed.emit(value)
        self._restart()

    @property
    def request(self) -> str:
        """What the read depends on besides the query. A change reads again at once."""
        return self._request

    def set_request(self, value: str) -> None:
        if value == self._request:
            return
        self._request = value
        self._restart()

    @property
    def read_enabled(self) -> bool:
        """Nothing is read while this is off. `enabled` at construction."""
        return self._read_enabled

    def set_enabled(self, value: bool) -> None:
        """Hold every read back, for a list that has nothing to read yet."""
        value = bool(value)
        if value == self._read_enabled:
            return
        self._read_enabled = value
        self._restart()

    @property
    def reads_empty(self) -> bool:
        """An empty query reads too, rather than emptying the list."""
        return self._reads_empty

    def set_reads_empty(self, value: bool) -> None:
        self._reads_empty = bool(value)
        self._restart()

    @property
    def paging(self) -> bool:
        """A further page is asked for on a load-more row under the rows."""
        return self._paging

    def set_paging(self, value: bool) -> None:
        self._paging = bool(value)
        self._apply_view()

    @property
    def debounce_ms(self) -> int:
        """The pause before a typed query is asked for."""
        return self._runner.delay_ms

    def set_debounce_ms(self, value: int) -> None:
        self._runner.set_delay_ms(int(value))

    @property
    def shell(self) -> SearchShell:
        """`command`, `dialog` or `bare`."""
        return self._shell

    def set_shell(self, value: SearchShell) -> None:
        """The shell is the widget's own shape and is fixed once it is built."""
        if value != self._shell:
            raise ValueError("the shell is settled at construction")

    @property
    def open(self) -> bool:
        """Whether the dialog shell is showing."""
        return self._open

    def set_open(self, value: bool) -> None:
        value = bool(value)
        if value == self._open:
            return
        self._open = value
        if self._dialog is not None:
            if value:
                self._dialog.open()
                if self._input is not None:
                    self._input.setFocus(Qt.FocusReason.OtherFocusReason)
            else:
                self._dialog.close()
        self.open_changed.emit(value)

    @property
    def title(self) -> str:
        """The dialog's accessible name."""
        return self._title

    def set_title(self, value: str) -> None:
        self._title = value
        if self._dialog is not None:
            self._dialog.setAccessibleName(value)

    @property
    def description(self) -> str:
        """The dialog's accessible description. Like the title, it is heard and not drawn."""
        return self._description

    def set_description(self, value: str) -> None:
        self._description = value
        if self._dialog is not None:
            self._dialog.setAccessibleDescription(value)

    @property
    def placeholder(self) -> str:
        """Text in the search box."""
        return self._input.placeholderText() if self._input is not None else ""

    def set_placeholder(self, value: str) -> None:
        if self._input is not None:
            self._input.setPlaceholderText(value)

    @property
    def empty_label(self) -> str:
        """Shown when the read answered nothing."""
        return self._empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = value
        self._empty.set_label(value)
        self._apply_view()

    @property
    def loading_label(self) -> str | None:
        """The accessible name of the skeletons."""
        return self._loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._loading_label = value
        self._skeleton.set_label(state_line("loading", self._labels()))
        self._apply_view()

    @property
    def error_label(self) -> str | None:
        """Shown in place of what the failed read said."""
        return self._error_label

    def set_error_label(self, value: str | None) -> None:
        self._error_label = value
        self._apply_view()

    @property
    def error_slot(self) -> str | None:
        """The object name the error line carries."""
        return self._error_slot

    def set_error_slot(self, value: str | None) -> None:
        self._error_slot = value
        self._error.set_slot_name(value or "search-error")

    @property
    def loading_slot(self) -> str | None:
        """The object name the skeleton block carries."""
        return self._skeleton.slot_name or None

    def set_loading_slot(self, value: str | None) -> None:
        self._skeleton.set_slot_name(value or "")

    @property
    def empty_slot(self) -> str | None:
        """The object name the empty line carries."""
        return self._empty_slot

    def set_empty_slot(self, value: str | None) -> None:
        self._empty_slot = value
        self._empty.set_slot_name(value or "search-empty")

    @property
    def skeleton_lines(self) -> int:
        """How many rows the skeletons stand in for."""
        return self._skeleton.lines

    def set_skeleton_lines(self, value: int) -> None:
        self._skeleton.set_lines(value)

    @property
    def skeleton_lead(self) -> QSize:
        """The leading slot of a skeleton row."""
        return self._skeleton.lead

    def set_skeleton_lead(self, value: QSize | tuple[int, int] | None) -> None:
        self._skeleton.set_lead(value)

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value
        self.set_size_step(value)
        self._skeleton.set_size(value)
        self._empty.set_size(value)
        self._error.set_size(value)
        self._list.row_delegate().set_size(value)
        setter = getattr(self._model, "set_size", None)
        if callable(setter):
            setter(value)
        self._list.updateGeometry()
        self.updateGeometry()
        self.update()

    def set_density(self, value: str) -> None:
        """`default` or `compact`, which halves a row's vertical inset."""
        self._list.row_delegate().set_density(value)
        self._list.updateGeometry()

    # --- what a wrapper reads ---------------------------------------------------------------

    @property
    def items(self) -> list:
        """The rows the read answered, every page of them."""
        return list(self._items)

    @property
    def loading(self) -> bool:
        """True while a read is in flight."""
        return self._loading

    @property
    def failure(self) -> str | None:
        """What the failed read said, or None."""
        return self._failure

    @property
    def has_more(self) -> bool:
        """True while a further page may be there."""
        return self._has_more

    @property
    def page(self) -> int:
        """The last page that landed."""
        return self._page

    @property
    def view(self) -> str:
        """Which of `error`, `loading`, `empty` and `rows` the list is drawing."""
        return search_view(
            SearchViewState(
                error=self._failure,
                loading=self._loading,
                count=len(self._items),
                asked=self._asked(),
            )
        )

    @property
    def status(self) -> str:
        """The one line the list's live region carries."""
        return list_status(
            ListStatusState(
                loading=self._loading,
                count=len(self._items),
                error=self._failure,
                asked=self._asked(),
            ),
            self._labels(),
        )

    def list_surface(self) -> ListSurface:
        """The list the rows are drawn in."""
        return self._list

    def input(self) -> InputGroupInput | None:
        """The search box, or None under the bare shell."""
        return self._input

    def dialog(self) -> Dialog | None:
        """The modal panel under the dialog shell, or None."""
        return self._dialog

    # --- the lifecycle ----------------------------------------------------------------------

    def _labels(self) -> StateLabels:
        return StateLabels(
            empty_label=self._empty_label,
            loading_label=self._loading_label,
            error_label=self._error_label,
        )

    def _asked(self) -> bool:
        return self._reads_empty or len(self._query.strip()) > 0

    def _on_typed(self, text: str) -> None:
        if text == self._query:
            return
        self._query = text
        self._sync_query()
        self.query_changed.emit(text)
        self._restart()

    def _restart(self) -> None:
        """Empty the list and ask again, at once or once the pause has elapsed.

        Taking the next ticket is the cancellation: a read already in flight for what has
        just been replaced can no longer write its answer.
        """
        self._runner.cancel()
        self._items = []
        self._page = 1
        self._has_more = False
        self._failure = None
        self._write_rows([])
        if not self._read_enabled or self._load is None:
            self._loading = False
            self._apply_view()
            return
        plan = query_plan(self._query, self._reads_empty)
        if plan == "clear":
            self._loading = False
            self._apply_view()
            return
        self._loading = True
        self._apply_view()
        self._ask(self._query, 1, delay_ms=0 if plan == "now" else None)

    def _ask(self, text: str, page: int, delay_ms: int | None = None) -> None:
        if self._load is None:
            return
        request = SearchRequest(query=text, page=page)
        self._runner.start(
            self._load,
            request,
            on_result=lambda answer, page=page: self._landed(answer, page),
            on_error=lambda failed: self._failed(failed),
            delay_ms=delay_ms,
        )

    def flush(self) -> None:
        """Ask now for the query that is waiting out its pause. For a test, and for Enter."""
        self._runner.flush()

    def load_more(self) -> None:
        """Ask for the next page, which lands under the rows already there."""
        if not self._paging or not self._has_more or self._loading or self._load is None:
            return
        self.load_more_requested.emit()
        self._loading = True
        self._apply_view()
        self._ask(self._query, self._page + 1, delay_ms=0)

    def _landed(self, answer: Any, page: int) -> None:
        found = _answer_of(answer)
        # The highlight survives a load-more page, per the picker contract's clause 5.
        held = self._list.highlighted() if page > 1 else -1
        self._items = list(found.items) if page == 1 else [*self._items, *found.items]
        self._page = page
        self._has_more = bool(found.has_more)
        self._failure = None
        self._loading = False
        self._write_rows(self._items, append=page > 1, page_items=list(found.items))
        self._apply_view()
        if held >= 0:
            self._list.set_highlight(held)
        self.rows_changed.emit()

    def _failed(self, failed: BaseException) -> None:
        self._failure = error_text(failed)
        self._items = []
        self._has_more = False
        self._loading = False
        self._write_rows([])
        self._apply_view()
        self.error.emit(self._failure)

    def _write_rows(
        self, items: Sequence[Any], append: bool = False, page_items: Sequence[Any] = ()
    ) -> None:
        """Put the rows in the model, a page at a time where the wrapper maps nothing."""
        adder = getattr(self._model, "append_rows", None)
        setter = getattr(self._model, "set_rows", None)
        if append and self._row_mapper is None and callable(adder):
            adder(page_items)
        elif callable(setter):
            setter(self._row_mapper(list(items)) if self._row_mapper is not None else list(items))

    # --- the view ----------------------------------------------------------------------------

    def _apply_view(self) -> None:
        view = self.view
        self._error.setVisible(view == "error")
        self._skeleton.setVisible(view == "loading")
        self._empty.setVisible(view == "empty")
        self._list.setVisible(view == "rows")
        if view == "error":
            self._error.apply_state("error", self._labels(), self._failure)
        if view == "empty":
            self._empty.set_label(self._empty_label)
        self._list.set_load_more(
            view == "rows" and self._paging and self._has_more,
            LOADING_LABEL if self._loading else LOAD_MORE_LABEL,
        )
        if view == "rows" and self._list.highlighted() < 0:
            self._list.highlight_first()
        self._list.setAccessibleDescription(self.status)
        self._list.updateGeometry()
        self.updateGeometry()

    # --- the shell ---------------------------------------------------------------------------

    def _build_dialog(self) -> None:
        """The modal panel the box sits in. The dialog owns the box from here on.

        The host window is the parent's, never this widget's own: the box moves into the
        dialog, so asking it for its window once it is there answers the dialog itself.
        """
        parent = self.parentWidget()
        host = parent.window() if parent is not None else None
        # Upstream's command dialog draws no header and no close control: the title and the
        # description are `sr-only`, so the panel is the search box and its list and nothing
        # else. Here they are the panel's accessible name and description.
        self._dialog = Dialog(host, show_close=False)
        self._dialog.setAccessibleName(self._title)
        self._dialog.setAccessibleDescription(self._description)
        self._dialog.set_content(self)
        self._dialog.dismissed.connect(self._on_dialog_closed)
        self._dialog.rejected.connect(self._on_dialog_closed)

    def _on_dialog_closed(self) -> None:
        if self._open:
            self._open = False
            self.open_changed.emit(False)

    # --- keys ----------------------------------------------------------------------------------

    def handle_key(self, event: QKeyEvent) -> bool:
        """Take one key from the search box. True when the search used it.

        Escape is the box's business only while the query has text: it clears the query and
        the rows and leaves the caret where it is. An empty one is the shell's key.
        """
        if self._on_key_down is not None and self._on_key_down(event, list(self._items)):
            return True
        if event.key() == Qt.Key.Key_Escape:
            intent = search_key_intent("Escape", SearchKeyState(query=self._query))
            if intent.kind == "clear":
                self.set_query("")
                return True
            self.dismissed.emit()
            if self._shell == "dialog":
                self.set_open(False)
            return True
        return self._list.handle_key(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self.handle_key(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_activated(self, row: int) -> None:
        self.activated.emit(row)

    # --- the surface ----------------------------------------------------------------------------

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        if self._shell == "bare":
            return
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fill_round_rect(
            painter,
            self.rect(),
            float(theme.radius_px("lg")),
            brush=theme.color("popover"),
            border=theme.color("border"),
        )
        painter.end()
