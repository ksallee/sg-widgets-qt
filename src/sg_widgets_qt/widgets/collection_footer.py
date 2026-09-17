"""The footer of every collection that pages.

Ported from `packages/react/src/registry/sg/components/collection-footer.tsx`. In `pages`
it draws the page size, the range and the arrows around a page number; in `more` and
`scroll` it draws the loaded count. The numbers are core's `describe_paging`, so the three
collections cannot report the set differently.

A read carries no total, so a range reads "of N" only once `_summarize` has counted the set
(006_pagination, 020_summarize).

    footer = CollectionFooter(binding, slot_name="entity-table")
    footer.set_pager(describe_paging(state))
"""
from __future__ import annotations

from collections.abc import Sequence

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.collection import PagingModel

from ..primitives.base import ThemedWidget, painter_for, text_width
from ..primitives.button import Button
from ..primitives.input import Input
from ..primitives.select import Select
from .collection_source import CollectionSource

__all__ = ["COLLECTION_FOOTER_TEXT", "DEFAULT_PAGE_SIZES", "CollectionFooter"]

#: The footer is metadata, so it stands on the metadata step (rule 6).
COLLECTION_FOOTER_TEXT = 12

#: The rows per page a collection offers when its caller names none.
DEFAULT_PAGE_SIZES: tuple[int, ...] = (25, 50, 100)

#: Between the footer's items, rule 2.
FOOTER_GAP = 8

#: The page number box: wide enough for four digits and no wider.
PAGE_BOX_WIDTH = 56


class _FooterText(ThemedWidget):
    """One line of the footer: 12px, muted, with tabular figures where it counts."""

    def __init__(
        self, text: str = "", tabular: bool = True, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._tabular = bool(tabular)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        if value == self._text:
            return
        self._text = value
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        font = self.theme.font(COLLECTION_FOOTER_TEXT)
        if self._tabular:
            font.setStyleHint(QtGui.QFont.StyleHint.SansSerif)
        return font

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(text_width(metrics, self._text), metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        painter.setFont(self._font())
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()


class CollectionFooter(ThemedWidget):
    """The page size, the range and the arrows in `pages`; the loaded count otherwise."""

    #: A page was asked for. The source is driven directly; this is for a caller that watches.
    page_changed = QtCore.Signal(int)
    #: The rows per page changed.
    page_size_changed = QtCore.Signal(int)

    def __init__(
        self,
        source: CollectionSource | None = None,
        pager: PagingModel | None = None,
        page_sizes: Sequence[int] = DEFAULT_PAGE_SIZES,
        loading: bool = False,
        slot_name: str = "collection",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._pager = pager
        self._page_sizes = list(page_sizes)
        self._loading = bool(loading)
        self._slot_name = slot_name or "collection"
        self.setObjectName(f"{self._slot_name}-footer")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(FOOTER_GAP)

        self._size_box = QtWidgets.QWidget(self)
        self._size_box.setObjectName(f"{self._slot_name}-page-size")
        sizes = QtWidgets.QHBoxLayout(self._size_box)
        sizes.setContentsMargins(0, 0, 0, 0)
        sizes.setSpacing(FOOTER_GAP)
        sizes.addWidget(_FooterText("Rows per page", tabular=False, parent=self._size_box))
        # The footer's own type is `text-xs`, but its controls keep the default step of the
        # control ladder — upstream's `SelectTrigger`, `Input` and `size="icon"` buttons are all
        # 32 here — so the pager does not read as a row of small buttons.
        self._size_select = Select(
            [(size, str(size)) for size in self._page_sizes], parent=self._size_box
        )
        self._size_select.setAccessibleName("Rows per page")
        self._size_select.setFixedWidth(72)
        self._size_select.value_changed.connect(self._on_page_size)
        sizes.addWidget(self._size_select)
        line.addWidget(self._size_box)

        # `more` and `scroll` draw the loaded count alone in a `justify-between` row, so it
        # sits at the start of the line, not at its end: it goes in before the stretch.
        self._loaded = _FooterText("", parent=self)
        self._loaded.setObjectName(f"{self._slot_name}-loaded")
        line.addWidget(self._loaded)
        line.addStretch(1)

        self._pager_box = QtWidgets.QWidget(self)
        self._pager_box.setObjectName(f"{self._slot_name}-pager")
        pages = QtWidgets.QHBoxLayout(self._pager_box)
        pages.setContentsMargins(0, 0, 0, 0)
        pages.setSpacing(FOOTER_GAP)
        self._range = _FooterText("", parent=self._pager_box)
        self._range.setObjectName(f"{self._slot_name}-range")
        pages.addWidget(self._range)
        self._previous = Button(
            icon="chevron-left", variant="outline", size="icon", parent=self._pager_box
        )
        self._previous.setAccessibleName("Previous page")
        self._previous.clicked.connect(self._go_previous)
        pages.addWidget(self._previous)
        self._page = Input(parent=self._pager_box)
        self._page.setObjectName(f"{self._slot_name}-page-number")
        self._page.setAccessibleName("Page number")
        self._page.setFixedWidth(PAGE_BOX_WIDTH)
        self._page.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._page.returnPressed.connect(self._go_typed)
        self._page.editingFinished.connect(self._go_typed)
        pages.addWidget(self._page)
        self._of = _FooterText("", parent=self._pager_box)
        pages.addWidget(self._of)
        self._next = Button(
            icon="chevron-right", variant="outline", size="icon", parent=self._pager_box
        )
        self._next.setAccessibleName("Next page")
        self._next.clicked.connect(self._go_next)
        pages.addWidget(self._next)
        line.addWidget(self._pager_box)

        self._apply()

    # --- props ----------------------------------------------------------------------------

    @property
    def source(self) -> CollectionSource | None:
        """The binding the page size, the arrows and the page number drive."""
        return self._source

    def set_source(self, value: CollectionSource | None) -> None:
        self._source = value

    @property
    def pager(self) -> PagingModel | None:
        """The numbers to draw, from core's `describe_paging`."""
        return self._pager

    def set_pager(self, value: PagingModel | None) -> None:
        self._pager = value
        self._apply()

    @property
    def page_sizes(self) -> list[int]:
        """The page sizes offered in `pages` mode."""
        return list(self._page_sizes)

    def set_page_sizes(self, value: Sequence[int]) -> None:
        self._page_sizes = list(value)
        self._size_select.set_items([(size, str(size)) for size in self._page_sizes])
        self._apply()

    @property
    def loading(self) -> bool:
        """True while the set is being read: the arrows wait for it."""
        return self._loading

    def set_loading(self, value: bool) -> None:
        self._loading = bool(value)
        self._apply()

    @property
    def slot_name(self) -> str:
        """The widget's own name, which prefixes every object name here."""
        return self._slot_name

    def set_slot_name(self, value: str) -> None:
        self._slot_name = value or "collection"
        self.setObjectName(f"{self._slot_name}-footer")
        self._size_box.setObjectName(f"{self._slot_name}-page-size")
        self._pager_box.setObjectName(f"{self._slot_name}-pager")
        self._range.setObjectName(f"{self._slot_name}-range")
        self._loaded.setObjectName(f"{self._slot_name}-loaded")
        self._page.setObjectName(f"{self._slot_name}-page-number")

    # --- drawing --------------------------------------------------------------------------

    def _apply(self) -> None:
        pager = self._pager
        if pager is None:
            self._size_box.setVisible(False)
            self._pager_box.setVisible(False)
            self._loaded.setVisible(False)
            return
        pages = pager.mode == "pages"
        self._size_box.setVisible(pages)
        self._pager_box.setVisible(pages)
        self._loaded.setVisible(not pages)
        if not pages:
            self._loaded.set_text(pager.loaded_label)
            return
        self._size_select.set_value(pager.page_size)
        self._range.set_text(pager.range_label)
        if not self._page.hasFocus():
            self._page.setText(str(pager.page))
        self._of.set_text("" if pager.page_count is None else f"of {pager.page_count}")
        self._of.setVisible(pager.page_count is not None)
        self._previous.setEnabled(pager.has_previous and not self._loading)
        self._next.setEnabled(pager.has_next and not self._loading)

    # --- the controls ---------------------------------------------------------------------

    def _on_page_size(self, value: object) -> None:
        try:
            size = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        self.page_size_changed.emit(size)
        if self._source is not None:
            self._source.set_page_size(size)

    def _go(self, page: int) -> None:
        pager = self._pager
        if pager is not None and pager.page_count is not None:
            page = min(page, pager.page_count)
        page = max(1, page)
        self.page_changed.emit(page)
        if self._source is not None:
            self._source.set_page(page)

    def _go_previous(self) -> None:
        if self._pager is not None:
            self._go(self._pager.page - 1)

    def _go_next(self) -> None:
        if self._pager is not None:
            self._go(self._pager.page + 1)

    def _go_typed(self) -> None:
        text = self._page.text().strip()
        pager = self._pager
        if pager is None:
            return
        try:
            wanted = int(text)
        except ValueError:
            self._page.setText(str(pager.page))
            return
        if wanted < 1:
            self._page.setText(str(pager.page))
            return
        if wanted != pager.page:
            self._go(wanted)
