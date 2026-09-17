"""The binding between a collection and the source behind it.

Ported from `packages/react/src/registry/sg/components/collection-source.ts`. The table,
the grid and the grouped list each hold a source, follow its snapshot, load it when it is
idle, keep its mode on the `paging` prop and mirror its sort and its filter out through
`sort_changed` and `filters_changed`. That is one model, so it lives here and each widget
keeps only what it draws.

Core's source is synchronous, so every call it makes runs on a pool of one thread and the
snapshot it publishes crosses back to the GUI thread on a queued signal: a widget only ever
reads `snapshot()` on the thread it draws on. One thread, because two reads writing the same
source would interleave; the source's own ticket (`begin`, `holds`) is what drops the answer a
later read replaced, and `begin_count` is what drops a count whose filter has moved.

    binding = CollectionSource(source, paging="pages")
    binding.changed.connect(redraw)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qtpy import QtCore
from qtpy.QtCore import QObject, Qt, Signal

from sg_widgets_core.collection import (
    EntitySource,
    EntitySourceState,
    SortSpec,
    SourceFilters,
)
from sg_widgets_core.collection_state import same_filters, same_sort
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.paging import PAGING_MODE_VALUES, source_mode_for

from ..workers import JobPool

__all__ = ["COLLECTION_PAGING_VALUES", "CollectionSource"]

#: How a collection walks a set. Core's `PagingMode`.
COLLECTION_PAGING_VALUES: tuple[str, ...] = PAGING_MODE_VALUES


class CollectionSource(QObject):
    """One `EntitySource`, read off the GUI thread, with its sort and its filter two-way."""

    #: The source published a new snapshot.
    changed = Signal()
    #: The source's sort moved. Carries `list[SortSpec]`.
    sort_changed = Signal(object)
    #: The source's filter moved. Carries the wire group, or None.
    filters_changed = Signal(object)
    #: A write, a count or a re-read raised. Carries the exception.
    failed = Signal(object)

    #: Private: the source's listener, emitted from the pool thread and delivered on this one.
    _published = Signal()

    def __init__(
        self,
        source: EntitySource,
        paging: str = "pages",
        sort: Sequence[SortSpec] | None = None,
        filters: SourceFilters = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._paging = paging if paging in COLLECTION_PAGING_VALUES else "pages"
        # One thread, so the source is never mutated by two reads at once.
        self._pool = JobPool(1, self)
        self._sort: list[SortSpec] | None = None if sort is None else list(sort)
        self._filters: SourceFilters = filters
        self._sort_seen = list(source.sort)
        self._filters_seen = source.filters

        self._published.connect(self._on_published, Qt.ConnectionType.QueuedConnection)
        self._unsubscribe = source.subscribe(self._published.emit)
        self._apply_mode()
        if self._sort is not None and not same_sort(self._sort, source.sort):
            self.set_sort(self._sort)
        if self._filters is not None and not same_filters(self._filters, source.filters):
            self.set_filters(self._filters)
        if source.status == "idle":
            self.load()

    # --- props ----------------------------------------------------------------------------

    @property
    def source(self) -> EntitySource:
        """The rows, the filter, the sort and the page behind them."""
        return self._source

    @property
    def paging(self) -> str:
        """`pages`, `more` or `scroll`. The source's mode follows it."""
        return self._paging

    def set_paging(self, value: str) -> None:
        value = value if value in COLLECTION_PAGING_VALUES else "pages"
        if value == self._paging:
            return
        self._paging = value
        self._apply_mode()

    @property
    def sort(self) -> list[SortSpec]:
        """The sort the source holds."""
        return list(self._source.sort)

    def set_sort(self, value: Sequence[SortSpec] | None) -> None:
        """Take a sort from the `sort` prop. A sort the source already holds is a no-op.

        The prop is recorded, so the snapshot that comes back says what the caller already
        knows and nothing is reported: a change travels once, and the two never write to each
        other. A sort the widget itself makes goes through `apply_sort` instead.
        """
        if value is None:
            return
        keys = list(value)
        self._sort = keys
        if same_sort(keys, self._source.sort):
            return
        self._run(self._source.set_sort, keys)

    def apply_sort(self, value: Sequence[SortSpec]) -> None:
        """Sort from the widget's own control: a header click, or a sort picker.

        The prop is not recorded, so the snapshot that comes back is reported through
        `sort_changed` and a `sort` prop follows it.
        """
        keys = list(value)
        if same_sort(keys, self._source.sort):
            return
        self._run(self._source.set_sort, keys)

    @property
    def filters(self) -> SourceFilters:
        """The filter the source holds, as the wire group."""
        return self._source.filters

    def set_filters(self, value: SourceFilters) -> None:
        """Take a filter from the `filters` prop. One the source already holds is a no-op."""
        self._filters = value
        if same_filters(value, self._source.filters):
            return
        self._run(self._source.set_filters, value)

    def apply_filters(self, value: SourceFilters) -> None:
        """Filter from the widget's own control, so the change is reported back out."""
        if same_filters(value, self._source.filters):
            return
        self._run(self._source.set_filters, value)

    # --- what a view reads ----------------------------------------------------------------

    def snapshot(self) -> EntitySourceState:
        """The last state the source published."""
        return self._source.snapshot()

    @property
    def status(self) -> str:
        return self._source.status

    @property
    def busy(self) -> bool:
        """True while a call to the source is in flight."""
        return self._pool.running > 0

    @property
    def pool(self) -> JobPool:
        """The one thread the source is read on.

        A widget reading beside it, a schema lookup for a column or a status field, submits
        here rather than to the shared pool: the answer is then dropped with the rest when the
        widget goes, and the reads stay in the order they were asked for.
        """
        return self._pool

    # --- the calls ------------------------------------------------------------------------

    def load(self) -> None:
        """Read the first page, discarding anything already loaded."""
        self._run(self._source.load)

    def load_more(self) -> None:
        """Append the next page. A no-op in `pages` mode or with nothing more."""
        if self._paging == "pages" or self.busy or not self._source.has_more:
            return
        self._run(self._source.load_more)

    def refresh(self) -> None:
        """Read every page already shown again."""
        self._run(self._source.refresh)

    def retry(self) -> None:
        """Read the page that failed again: the one a pager is on, or the one appended."""
        if self._paging == "pages":
            self._run(self._source.set_page, self._source.page)
        else:
            self._run(self._source.load_more)

    def set_page(self, page: int) -> None:
        """Show one page of the set. `pages` mode only."""
        self._run(self._source.set_page, int(page))

    def set_page_size(self, size: int) -> None:
        self._run(self._source.set_page_size, int(size))

    def count(self) -> None:
        """Count the set through `_summarize`, so a range can read "n to m of N" (020_summarize).

        The ticket is taken here, on the GUI thread, so an answer whose filter has moved is
        dropped rather than written over the filter that replaced it.
        """
        pending = self._source.begin_count()
        self._run(self._source.count, pending)

    def update_row(self, ref: EntityRef, patch: dict[str, Any], on_done: Any = None) -> None:
        """Write one field of one row and put the re-read row back in place.

        The write answers the whole record but resolves no dotted path, so the source reads
        the row again with its own projection (024_read_after_write). `on_done` is called on
        the GUI thread with the fresh row, or with the exception a refused write raised.
        """

        def done(row: object) -> None:
            if on_done is not None:
                on_done(row)

        def failed(error: BaseException) -> None:
            self.failed.emit(error)
            if on_done is not None:
                on_done(error)

        self._pool.submit(
            self._source.update_row, ref, patch, on_result=done, on_error=failed
        )

    def reread_rows(self, ids: Sequence[int]) -> None:
        """Read these rows again with the source's own projection and swap them in place."""
        self._run(self._source.reread_rows, list(ids))

    def wait(self, timeout_ms: int = 5000) -> bool:
        """Block until every call is answered, then deliver what they published.

        For a test and for teardown. Never on a GUI thread that has a reader waiting.
        """
        done = self._pool.wait(timeout_ms)
        QtCore.QCoreApplication.processEvents()
        return done

    # --- internals ------------------------------------------------------------------------

    def _apply_mode(self) -> None:
        mode = source_mode_for(self._paging)
        if self._source.mode != mode:
            self._run(self._source.set_mode, mode)

    def _run(self, fn: Any, *args: Any) -> None:
        self._pool.submit(fn, *args, on_error=self.failed.emit)

    def _on_published(self) -> None:
        """The source moved. Mirror the sort and the filter out, then tell the view."""
        state = self._source.snapshot()
        if not same_sort(state.sort, self._sort_seen):
            self._sort_seen = list(state.sort)
            if self._sort is None or not same_sort(state.sort, self._sort):
                self._sort = list(state.sort)
                self.sort_changed.emit(list(state.sort))
        if not same_filters(state.filters, self._filters_seen):
            self._filters_seen = state.filters
            if self._filters is None or not same_filters(state.filters, self._filters):
                self._filters = state.filters
                self.filters_changed.emit(state.filters)
        self.changed.emit()

    def close(self) -> None:
        """Stop following the source and drop what is in flight."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._pool.cancel_all()
