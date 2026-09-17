"""A queue of shots drawn straight off the base.

The port of `apps/site/src/demos/collection-control/Demo.tsx`. The demo is a collection of its
own, not one of the three widgets: it holds a source of shots, draws one row per shot with a
checkbox, and puts the footer under them. The three paging modes change what walks the set;
nothing else in the demo changes with them.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, Qt

from sg_widgets_core.collection import (
    EntitySourceOptions,
    cell_value,
    create_entity_source,
)
from sg_widgets_core.filter import condition

from ...primitives.checkbox import Checkbox
from ...primitives.list_view import GUTTER
from ...primitives.roles import Roles
from ...primitives.row_delegate import ROW_PAD_X, ROW_PAD_Y, RowDelegate
from ...primitives.scrollbar import install_overlay_scrollbars
from ...primitives.skeleton import Skeleton
from ...theme import theme_of, with_alpha
from ...widgets.collection_control import COLLECTION_GAP, CollectionControl, CollectionModel
from ...widgets.collection_footer import CollectionFooter
from ...widgets.entity_table import EMPTY_ICON, ERROR_ICON, _BottomBlock
from ...widgets.state_line import StateLine
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: The rows the demo reads, and the sizes its footer offers.
FIELDS = ("code", "sg_status_list")
PAGE_SIZE = 8
PAGE_SIZES = (8, 16, 32)

#: The three ways a set is walked, as the toggle row offers them.
PAGING = (("pages", "Pages"), ("more", "Load more"), ("scroll", "Scroll"))

#: The demo's own box: the head over the rows, and the body under it.
BOX_HEIGHT = 288
SKELETON_ROWS = 5


class _QueueModel(CollectionModel):
    """The shared model with the two strings this queue's rows draw."""

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        line = self.line_at(index.row())
        if line is None or line.row is None:
            return super().data(index, role)
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return str(cell_value(line.row, "code") or "")
        if role == Roles.SECONDARY:
            return str(cell_value(line.row, "sg_status_list") or "")
        return super().data(index, role)


class _Head(QtWidgets.QWidget):
    """The head over the rows: the select-all box, the column names, and the rule under it."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-queue-head")
        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(ROW_PAD_X, ROW_PAD_Y, ROW_PAD_X + GUTTER, ROW_PAD_Y)
        line.setSpacing(COLLECTION_GAP)
        self.box = Checkbox(parent=self)
        self.box.setAccessibleName("Select all loaded rows")
        self.box.set_tri_state(True)
        line.addWidget(self.box)
        line.addWidget(chrome.TextLine("Shot", size=12, parent=self))
        line.addStretch(1)
        line.addWidget(chrome.TextLine("Status", size=12, parent=self))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), with_alpha(theme.muted, 0.5))
        painter.fillRect(
            QtCore.QRect(0, self.height() - 1, self.width(), 1), theme.color("border")
        )
        painter.end()


class _Rows(QtWidgets.QListView):
    """The rows: our delegate, our overlay scrollbars, the demo's own keys."""

    def __init__(self, demo: CollectionControlDemo) -> None:
        self._demo = demo
        super().__init__(demo)
        self.setObjectName("review-queue-rows")
        self.setFrameShape(QtWidgets.QListView.Shape.NoFrame)
        self.setSpacing(0)
        self.setUniformItemSizes(False)
        self.setResizeMode(QtWidgets.QListView.ResizeMode.Adjust)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setViewportMargins(0, 0, GUTTER, 0)
        install_overlay_scrollbars(self)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        index = self.indexAt(
            event.position().toPoint() if hasattr(event, "position") else event.pos()
        )
        if index.isValid():
            self.setCurrentIndex(index)
            self._demo.toggle_at(index.row())
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._demo.on_key(event):
            return
        super().keyPressEvent(event)


class CollectionControlDemo(QtWidgets.QWidget):
    """The queue: the paging toggles, the rows, the bottom block and the footer."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collection-control-demo")
        self._context = context
        # The mock's rows are one project's already; a real site's are not.
        filters = (
            condition("project", "is", {"type": "Project", "id": context.project_id})
            if context.live
            else None
        )
        source = create_entity_source(
            EntitySourceOptions(
                client=context.client,
                entity_type="Shot",
                fields=list(FIELDS),
                filters=filters,
                mode="pages",
                page_size=PAGE_SIZE,
            )
        )
        self.control = CollectionControl(source, paging="pages", model=_QueueModel(), parent=self)

        body = lay.column(self)
        self._toggles: dict[str, QtWidgets.QWidget] = {}
        row = QtWidgets.QWidget(self)
        toggles = lay.FlowLayout(row)
        for value, label in PAGING:
            made = chrome.toggle(label, size="sm", parent=row)
            made.setObjectName(f"paging-{value}")
            made.toggled.connect(lambda on, mode=value: self._on_paging(mode, on))
            self._toggles[value] = made
            toggles.addWidget(made)
        self._count = chrome.TextLine("0 selected", size=12, parent=row)
        self._count.setObjectName("selection-count")
        toggles.addWidget(self._count)
        body.addWidget(lay.section("How the set is walked", row, parent=self))

        queue = QtWidgets.QWidget(self)
        queue.setObjectName("review-queue")
        column = QtWidgets.QVBoxLayout(queue)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(COLLECTION_GAP)

        box = QtWidgets.QWidget(queue)
        box.setObjectName("review-queue-box")
        inner = QtWidgets.QVBoxLayout(box)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        self._head = _Head(box)
        self._head.box.toggled.connect(self.control.toggle_all)
        inner.addWidget(self._head)
        self.view = _Rows(self)
        self.view.setModel(self.control.model)
        self._delegate = RowDelegate(self.view, size="md", thumbnail=False, indicator="checkbox")
        self.view.setItemDelegate(self._delegate)
        self.view.setMaximumHeight(BOX_HEIGHT)
        inner.addWidget(self.view)
        self._state = StateLine(pad="table", slot_name="review-queue-state", parent=box)
        self._state.hide()
        inner.addWidget(self._state)
        self._skeleton = _Skeletons(box)
        self._skeleton.hide()
        inner.addWidget(self._skeleton)
        self._bottom = _BottomBlock(box)
        self._bottom.setObjectName("review-queue-bottom")
        self._bottom.retry_requested.connect(self.control.retry)
        self._bottom.more_requested.connect(self.control.load_more)
        self._bottom.hide()
        inner.addWidget(self._bottom)
        column.addWidget(box)

        self.footer = CollectionFooter(
            self.control.binding,
            page_sizes=PAGE_SIZES,
            slot_name="review-queue",
            parent=queue,
        )
        column.addWidget(self.footer)
        body.addWidget(queue)

        self.control.changed.connect(self._sync)
        self.control.selection_changed.connect(self._on_selection)
        bar = self.view.verticalScrollBar()
        if bar is not None:
            bar.valueChanged.connect(self._on_scrolled)
        self.control.count()
        self.set_paging("pages")
        self._sync()

    @property
    def demo_ready(self) -> bool:
        """True once the first read has settled, which is what the stage waits for."""
        return self.control.snapshot().status in ("ready", "error")

    def _on_paging(self, mode: str, on: bool) -> None:
        """One toggle reports going down and coming up; only the first is a pick.

        Reading every report as a pick sets the others down, is reported for each of them,
        and never returns.
        """
        if not on:
            if not any(made.checked for made in self._toggles.values()):
                made = self._toggles[mode]
                made.blockSignals(True)
                made.set_checked(True)
                made.blockSignals(False)
            return
        self.set_paging(mode)

    def set_paging(self, mode: str) -> None:
        self.control.set_paging(mode)
        for value, made in self._toggles.items():
            if value != mode:
                made.set_checked(False)
        self._toggles[mode].set_checked(True)
        self._sync()

    def toggle_at(self, line: int) -> None:
        found = self.control.model.line_at(line)
        if found is not None and found.row is not None:
            self.control.set_cursor(found.index)
            self.control.toggle(found.row)
            self.view.viewport().update()

    def on_key(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        index = self.view.currentIndex()
        at = index.row() if index.isValid() else -1
        if key == Qt.Key.Key_Space and at >= 0:
            self.toggle_at(at)
            return True
        if key not in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            return False
        step = 1 if key == Qt.Key.Key_Down else -1
        if step > 0 and self.control.ask_for_page(at + 1):
            return True
        wanted = self.control.step_cursor(step, max(0, at))
        if wanted >= 0:
            self.view.setCurrentIndex(self.control.model.index(wanted, 0))
        return True

    def _on_selection(self, rows: object) -> None:
        self._count.set_text(f"{len(rows or [])} selected")  # type: ignore[arg-type]

    def _on_scrolled(self, _value: int) -> None:
        last = self.view.indexAt(self.view.viewport().rect().bottomLeft())
        line = last.row() if last.isValid() else self.control.model.rowCount() - 1
        self.control.on_last_visible(self.control.model.last_row_of_line(line))

    def _sync(self) -> None:
        if not lay.alive(self):
            return
        state = self.control.snapshot()
        view = self.control.view(len(self.control.model.lines))
        self.view.setVisible(view == "rows")
        self._skeleton.setVisible(view == "loading")
        self._state.setVisible(view in ("empty", "error"))
        if view == "empty":
            self._state.set_icon(EMPTY_ICON)
            self._state.set_state("empty")
            self._state.set_label("No shots")
        elif view == "error":
            self._state.set_icon(ERROR_ICON)
            self._state.apply_state(
                "error", self.control.labels, None if state.error is None else str(state.error)
            )
        from sg_widgets_core.state import state_line

        self._bottom.apply(
            self.control.bottom(),
            state_line("error", self.control.labels, None if state.error is None else str(state.error)),
            self.control.loading_text,
        )
        chosen = self.control.all_selected
        # The box carries the numbers `Qt.CheckState` does: 0 off, 1 partial, 2 on.
        self._head.box.set_check_state(2 if chosen.all else 1 if chosen.some else 0)
        self.footer.set_pager(self.control.pager)
        self.footer.set_loading(state.status == "loading")
        waiting = self.control.take_pending_cursor()
        if waiting >= 0:
            self.view.setCurrentIndex(self.control.model.index(waiting, 0))
        self.view.viewport().update()


class _Skeletons(QtWidgets.QWidget):
    """Rows a first read stands behind: the same inset, the same height, the same zero gap."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("review-queue-loading")
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(ROW_PAD_X, ROW_PAD_Y, ROW_PAD_X, ROW_PAD_Y)
        column.setSpacing(0)
        for _ in range(SKELETON_ROWS):
            column.addWidget(Skeleton(height=20, parent=self))


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return CollectionControlDemo(context, parent)
