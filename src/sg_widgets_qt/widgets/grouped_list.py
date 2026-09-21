"""Rows under collapsible group headings.

Ported from `packages/react/src/registry/sg/components/grouped-list.tsx`.

Grouping a paged read is only honest over an order the server produced, so the source is sorted
on the group path and the contiguous runs are the groups; a count is the rows loaded so far and
grows as later pages arrive. Every row is the row of rule 9, drawn by `picker_row`'s delegate: a
fixed-size leading slot, a label, an optional sub-label under it, and an optional right-aligned
secondary rendered by its data type, so text always starts at the same x.

`paging` says how the set is walked and the source follows it. In `more` a row at the bottom
appends the next page and in `scroll` the scroller does; either way a page whose first rows
continue the last group grows that group (006_pagination).

    listing = GroupedList(source=source, group_by=step_column, label_field="content")
    listing.selected.connect(open_it)
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, QRect, QSize, Qt, Signal

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import (
    CollectionColumn,
    EntitySource,
    GroupBy,
    SortSpec,
    SourceFilters,
    cell_value,
    group_key_text,
    to_column,
)
from sg_widgets_core.collection_state import (
    CollapseState,
    RowDisabledFn,
    RowIdFn,
    as_collapse_state,
    collapse_state_from,
    is_collapsed,
    same_collapse,
    toggle_collapsed,
)
from sg_widgets_core.context import SgContext, preferences_of
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.render import field_text, is_empty_value
from sg_widgets_core.row import FieldSpec, path_of
from sg_widgets_core.schema import display_name_of
from sg_widgets_core.state import NO_ROWS_LABEL, StateLabels, state_line
from sg_widgets_core.status import StatusRecord

from .. import icons
from ..images import ImageLoader, image_loader
from ..primitives.base import THUMB_SIZE, elide, event_point
from ..primitives.list_view import GUTTER
from ..primitives.roles import Roles
from ..primitives.row_delegate import CODE_TEXT, ROW_PAD_X, ROW_PAD_Y, ROW_TEXT, RowDelegate
from ..primitives.scroll_latch import WheelLatch
from ..primitives.scrollbar import install_overlay_scrollbars
from ..primitives.skeleton import Skeleton
from ..theme import theme_of, with_alpha
from .collection_control import COLLECTION_GAP, CollectionControl, CollectionModel
from .collection_footer import DEFAULT_PAGE_SIZES, CollectionFooter
from .entity_table import EMPTY_ICON, ERROR_ICON, SkeletonBlock, _BottomBlock, _px, fit_body, rows_height
from .field_value import FieldValueOptions, field_value_size_hint, paint_field_value
from .state_line import StateLine

__all__ = [
    "GROUPED_LIST_DENSITY_VALUES",
    "GROUPED_LIST_SIZE_VALUES",
    "GROUPED_LIST_THUMB",
    "GroupedList",
]

GROUPED_LIST_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")
GROUPED_LIST_DENSITY_VALUES: tuple[str, ...] = ("compact", "default")

#: The thumbnail step a row takes, which is a rung lower under `compact` (rule 3).
GROUPED_LIST_THUMB: dict[str, dict[str, str]] = {
    "sm": {"compact": "sm", "default": "sm"},
    "md": {"compact": "sm", "default": "md"},
    "lg": {"compact": "md", "default": "lg"},
}

#: The heading's chevron and the gap after it, rule 2's inline gap.
CHEVRON = 16
CHEVRON_GAP = 6

#: Height of the scrolling body, upstream's `28rem` in pixels.
DEFAULT_MAX_HEIGHT = 448

#: Rows a first read stands behind, and the block one costs.
SKELETON_ROWS = 8
SKELETON_HEIGHT = 20
#: The row height a first read's skeletons stand at, before any row has been measured.
SKELETON_ROW_HEIGHT = 44

#: A list given nothing to group on says so rather than drawing one group of everything.
GROUPING_REQUIRED = "GroupedList needs group_by or group_key."

#: Between a detail's own label and its value, and between two details on the line.
DETAIL_GAP = " "
DETAIL_SEPARATOR = " · "


class GroupedListModel(CollectionModel):
    """The shared model with the row-anatomy roles `RowDelegate` paints (rule 9)."""

    def __init__(self, listing: GroupedList) -> None:
        super().__init__(listing)
        self._listing = listing
        self._pixmaps: dict[str, QtGui.QPixmap] = {}
        self._asked: set[str] = set()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        line = self.line_at(index.row())
        if line is None or line.kind == "heading" or line.row is None:
            return super().data(index, role)
        row = line.row
        listing = self._listing
        if role == Roles.LABEL or role == Qt.ItemDataRole.DisplayRole:
            return listing.label_of(row)
        if role == Roles.CODE:
            return listing.code_of(row)
        if role == Roles.SUB_LABEL:
            return listing.sub_of(row)
        if role == Roles.SECONDARY:
            return listing.secondary_of(row)
        if role == Roles.GLYPH:
            return listing.leading_of(row)
        if role == Roles.PIXMAP:
            return self._picture(row)
        return super().data(index, role)

    def _picture(self, row: EntityRow) -> QtGui.QPixmap | None:
        """The row's thumbnail, read once on a worker and kept by url (field_types/image)."""
        url = self._listing.thumbnail_of(row)
        if not url:
            return None
        held = self._pixmaps.get(url)
        if held is not None:
            return held
        if url in self._asked:
            return None
        self._asked.add(url)
        loader = self._listing.loader
        side = THUMB_SIZE[GROUPED_LIST_THUMB[self._listing.size][self._listing.density]]
        loader.load(url, lambda pixmap: self._landed(url, pixmap), QSize(side * 2, side * 2))
        return None

    def _landed(self, url: str, pixmap: QtGui.QPixmap | None) -> None:
        # A picture can land after the list that asked for it has gone; a deleted wrapper
        # raises, and the answer is dropped.
        if pixmap is not None and not pixmap.isNull():
            self._pixmaps[url] = pixmap
        try:
            self._touch()
        except RuntimeError:
            return


class _GroupDelegate(RowDelegate):
    """The rows of rule 9, and the heading over each run: a chevron, the value and the count."""

    def __init__(self, listing: GroupedList) -> None:
        super().__init__(
            listing.view,
            size=listing.size,
            thumbnail=listing.thumbnail is not False or listing.leading is not None,
            indicator="checkbox" if listing.selectable else "none",
            density=listing.density,
        )
        self._listing = listing
        self.set_bare_glyph(listing.thumbnail is False)

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        if index.data(Roles.KIND) == "heading":
            theme = theme_of(self._listing.view)
            step = ROW_TEXT[self._listing.size]
            metrics = QtGui.QFontMetrics(theme.font(step, QtGui.QFont.Weight.Medium))
            pad = max(2, ROW_PAD_Y // 2) if self._listing.density == "compact" else ROW_PAD_Y
            return QSize(option.rect.width(), max(metrics.height(), CHEVRON) + 2 * pad)
        return super().sizeHint(option, index)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        if index.data(Roles.KIND) != "heading":
            super().paint(painter, option, index)
            return
        group = index.data(Roles.ENTITY)
        if group is None:
            return
        theme = theme_of(self._listing.view)
        rect = option.rect
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(rect, with_alpha(theme.muted, 0.5))
        painter.fillRect(QRect(rect.left(), rect.bottom(), rect.width(), 1), theme.color("border"))
        open_ = bool(index.data(Roles.CHECKED))
        glyph = QRect(rect.left() + ROW_PAD_X, 0, CHEVRON, CHEVRON)
        glyph.moveTop(rect.center().y() - CHEVRON // 2)
        icons.paint_icon(
            painter,
            glyph,
            "chevron-down" if open_ else "chevron-right",
            theme.color("muted_foreground"),
        )
        left = glyph.right() + 1 + CHEVRON_GAP
        count = str(len(group.rows))
        mono = theme.font(CODE_TEXT)
        mono.setFamily(theme.font_mono)
        count_width = QtGui.QFontMetrics(mono).horizontalAdvance(count)
        room = max(0, rect.right() + 1 - ROW_PAD_X - count_width - CHEVRON_GAP - left)
        # The count follows the label in the same row, a gap away, as upstream's flex line
        # puts it: it is read as part of the heading, not as a column of its own.
        used = self._listing.paint_group_value(
            painter, QRect(left, rect.top(), room, rect.height()), group
        )
        painter.setFont(mono)
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            QRect(left + min(used, room) + CHEVRON_GAP, rect.top(), count_width, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            count,
        )
        painter.restore()


class _ListView(QtWidgets.QListView):
    """The scrolling body: our delegate, our overlay scrollbars, the list's own keys."""

    def __init__(self, listing: GroupedList) -> None:
        self._listing = listing
        super().__init__(listing)
        self._latch = WheelLatch(
            self, loading=lambda: self._listing.control.snapshot().status in ("loading", "loadingMore")
        )
        self.setObjectName("grouped-list-rows")
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
        # The gutter every list holds for its overlay scrollbar, so a secondary is never
        # drawn under the bar.
        self.setViewportMargins(0, 0, GUTTER, 0)
        install_overlay_scrollbars(self)


    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        """A gesture that reached the edge, or a page on its way, keeps the wheel off the page."""
        if self._latch.keeps(event):
            event.accept()
            return
        super().wheelEvent(event)
    # --- the pinned heading ----------------------------------------------------------------

    def pinned_heading(self) -> tuple[QModelIndex, QRect] | None:
        """The heading held at the top of the viewport, and where it is drawn.

        Upstream's heading is `sticky top-0` inside its group, so the heading of the group
        the reader is scrolled into stays at the top until the next group's heading pushes
        it up and takes its place. None while the heading at the top sits in its own place.
        """
        model = self._listing.model
        top = self.indexAt(QtCore.QPoint(0, 0))
        if not top.isValid():
            return None
        at = top.row()
        line = model.line_at(at)
        while line is not None and line.kind != "heading" and at > 0:
            at -= 1
            line = model.line_at(at)
        if line is None or line.kind != "heading":
            return None
        heading = model.index(at, 0)
        own = self.visualRect(heading)
        if own.top() >= 0:
            return None
        height = own.height()
        y = 0
        after = at + 1
        while after < model.rowCount():
            other = model.line_at(after)
            if other is not None and other.kind == "heading":
                y = min(0, self.visualRect(model.index(after, 0)).top() - height)
                break
            after += 1
        return heading, QRect(0, y, self.viewport().width(), height)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        pinned = self.pinned_heading()
        if pinned is None:
            return
        heading, rect = pinned
        option = QtWidgets.QStyleOptionViewItem()
        if hasattr(self, "initViewItemOption"):
            self.initViewItemOption(option)
        else:  # Qt 5
            option = self.viewOptions()
        option.rect = rect
        painter = QtGui.QPainter(self.viewport())
        # The heading's own wash is translucent, so the list's ground goes under it first: the
        # pinned band reads as the heading does in its place, not as the rows sliding under it.
        painter.fillRect(rect, theme_of(self).color("background"))
        self.itemDelegate().paint(painter, option, heading)
        painter.end()

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802
        super().scrollContentsBy(dx, dy)
        # The scrolled band is copied, so the pinned heading is redrawn by hand.
        self.viewport().update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event_point(event)
        pinned = self.pinned_heading()
        if pinned is not None and pinned[1].contains(point):
            self.setCurrentIndex(pinned[0])
            self._listing.on_line_pressed(pinned[0], point)
            return
        index = self.indexAt(point)
        if index.isValid():
            self.setCurrentIndex(index)
            self._listing.on_line_pressed(index, point)
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._listing.on_key(event):
            return
        super().keyPressEvent(event)


class GroupedList(QtWidgets.QWidget):
    """Rows grouped by a field, under headings that carry the count and collapse."""

    #: A row was opened. Carries the `EntityRow`.
    selected = Signal(object)
    #: The shut groups moved. Carries a `CollapseState`.
    collapsed_changed = Signal(object)
    #: The selected rows. Carries `list[EntityRef]`.
    selection_changed = Signal(object)
    #: The source's sort moved. Carries `list[SortSpec]`.
    sort_changed = Signal(object)
    #: The source's filter moved. Carries the wire group, or None.
    filters_changed = Signal(object)
    #: A read or a count raised. Carries the exception.
    error = Signal(object)

    def __init__(
        self,
        source: EntitySource,
        group_by: CollectionColumn | None = None,
        group_key: Callable[[EntityRow], Any] | None = None,
        group_label: Callable[[Any], str] | None = None,
        thumbnail: str | bool = False,
        label_field: str | None = None,
        sub_label_field: FieldSpec | None = None,
        sub_label: Callable[[EntityRow], str] | None = None,
        secondary_field: FieldSpec | None = None,
        secondary: Callable[[EntityRow], str] | None = None,
        show_code: bool = False,
        details: Sequence[CollectionColumn] = (),
        statuses: Mapping[str, StatusRecord] | None = None,
        context: SgContext | None = None,
        density: str = "default",
        size: str = "md",
        selectable: bool = False,
        selection: Sequence[EntityRef] | None = None,
        get_row_id: RowIdFn | None = None,
        is_row_disabled: RowDisabledFn | None = None,
        collapsed: Sequence[str] | CollapseState | None = None,
        sort: Sequence[SortSpec] | None = None,
        filters: SourceFilters = None,
        leading: Callable[[EntityRow], str] | None = None,
        page_sizes: Sequence[int] = DEFAULT_PAGE_SIZES,
        paging: str = "more",
        max_height: int | str = DEFAULT_MAX_HEIGHT,
        virtualize_after: int = 100,
        empty_label: str = NO_ROWS_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if group_by is None and group_key is None:
            raise ValueError(GROUPING_REQUIRED)
        self.setObjectName("grouped-list")
        self._group_by = group_by
        self._group_key = group_key
        self._group_label = group_label
        self._thumbnail = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._details = list(details)
        self._statuses = statuses
        self._context = context
        self._density = density if density in GROUPED_LIST_DENSITY_VALUES else "default"
        self._size = size if size in GROUPED_LIST_SIZE_VALUES else "md"
        self._selectable = bool(selectable)
        self._collapsed = as_collapse_state(collapsed)
        self._leading = leading
        self._virtualize_after = int(virtualize_after)
        self._loader = loader if loader is not None else image_loader()

        self.control = CollectionControl(
            source,
            paging=paging,
            sort=sort,
            filters=filters,
            selection=selection,
            get_row_id=get_row_id,
            is_row_disabled=is_row_disabled,
            loading_label=loading_label,
            empty_label=empty_label,
            error_label=error_label,
            model=GroupedListModel(self),
            parent=self,
        )
        self.model.set_collapsed(self._collapsed)
        self.model.set_group_by(self._grouping())

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(COLLECTION_GAP)

        self._header = QtWidgets.QWidget(self)
        self._header.setObjectName("grouped-list-header")
        head = QtWidgets.QHBoxLayout(self._header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(COLLECTION_GAP)
        self._header.hide()
        column.addWidget(self._header)

        self._box = QtWidgets.QWidget(self)
        self._box.setObjectName("grouped-list-scroll")
        body = QtWidgets.QVBoxLayout(self._box)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.view = _ListView(self)
        self._delegate = _GroupDelegate(self)
        self.view.setItemDelegate(self._delegate)
        self.view.setModel(self.model)
        self._max_height = _px(max_height)
        self.view.setMaximumHeight(self._max_height)
        body.addWidget(self.view)
        self._state = StateLine(pad="table", slot_name="grouped-list-state", parent=self._box)
        self._state.hide()
        body.addWidget(self._state)
        self._skeleton = _ListSkeleton(self._box)
        self._skeleton.hide()
        #: The height the rows last stood at, and their row height, for the next read's skeletons.
        self._rows_height = 0
        self._row_height = SKELETON_ROW_HEIGHT
        body.addWidget(self._skeleton)
        self._bottom = _BottomBlock(self._box)
        self._bottom.setObjectName("grouped-list-bottom")
        self._bottom.retry_requested.connect(self.control.retry)
        self._bottom.more_requested.connect(self.control.load_more)
        self._bottom.hide()
        body.addWidget(self._bottom)
        column.addWidget(self._box)

        self.footer = CollectionFooter(
            self.control.binding, page_sizes=page_sizes, slot_name="grouped-list", parent=self
        )
        column.addWidget(self.footer)

        self._footer_region = QtWidgets.QWidget(self)
        self._footer_region.setObjectName("grouped-list-footer-region")
        region = QtWidgets.QHBoxLayout(self._footer_region)
        region.setContentsMargins(0, 0, 0, 0)
        region.setSpacing(COLLECTION_GAP)
        self._footer_region.hide()
        column.addWidget(self._footer_region)

        self.control.changed.connect(self._sync)
        self.control.selection_changed.connect(self.selection_changed.emit)
        self.control.sort_changed.connect(self.sort_changed.emit)
        self.control.filters_changed.connect(self.filters_changed.emit)
        self.control.failed.connect(self.error.emit)
        bar = self.view.verticalScrollBar()
        if bar is not None:
            bar.valueChanged.connect(self._on_scrolled)
            bar.rangeChanged.connect(self._on_range)
        self._fill_timer = QtCore.QTimer(self)
        self._fill_timer.setSingleShot(True)
        self._fill_timer.timeout.connect(self._ask_if_unfilled)
        self.control.changed.connect(lambda: self._fill_timer.start(0))
        self.control.binding.idle.connect(lambda: self._fill_timer.start(0))
        self._lead_sort()
        self._sync()

    # --- the model ------------------------------------------------------------------------

    @property
    def model(self) -> CollectionModel:
        """The snapshot the three layouts share, with the row-anatomy roles added."""
        return self.control.model

    @property
    def source(self) -> EntitySource:
        return self.control.source

    @property
    def loader(self) -> ImageLoader:
        """Where a row's thumbnail is read from."""
        return self._loader

    # --- props ----------------------------------------------------------------------------

    @property
    def group_by(self) -> CollectionColumn | None:
        """Column the rows are grouped on. The source is sorted on it."""
        return self._group_by

    def set_group_by(self, value: CollectionColumn | None) -> None:
        self._group_by = value
        self.model.set_group_by(self._grouping())
        self._lead_sort()
        self._sync()

    @property
    def group_key(self) -> Callable[[EntityRow], Any] | None:
        """The value a row groups under, derived rather than read from a column."""
        return self._group_key

    def set_group_key(self, value: Callable[[EntityRow], Any] | None) -> None:
        self._group_key = value
        self.model.set_group_by(self._grouping())
        self._sync()

    @property
    def group_label(self) -> Callable[[Any], str] | None:
        """The heading's text for a derived key."""
        return self._group_label

    def set_group_label(self, value: Callable[[Any], str] | None) -> None:
        self._group_label = value
        self.view.viewport().update()

    @property
    def thumbnail(self) -> str | bool:
        """Field holding the thumbnail URL. False leaves the leading slot to `leading`."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self._rebuild_delegate()

    @property
    def label_field(self) -> str | None:
        """Field shown as the row's label. Defaults to the type's own display name."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self.view.viewport().update()

    @property
    def sub_label_field(self) -> FieldSpec | None:
        """The muted line under the label."""
        return self._sub_label_field

    def set_sub_label_field(self, value: FieldSpec | None) -> None:
        self._sub_label_field = value
        self.view.viewport().update()

    @property
    def sub_label(self) -> Callable[[EntityRow], str] | None:
        """The caller's own sub-label. Wins over `sub_label_field`."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[EntityRow], str] | None) -> None:
        self._sub_label = value
        self.view.viewport().update()

    @property
    def secondary_field(self) -> FieldSpec | None:
        """The right-aligned value at the end of the row."""
        return self._secondary_field

    def set_secondary_field(self, value: FieldSpec | None) -> None:
        self._secondary_field = value
        self.view.viewport().update()

    @property
    def secondary(self) -> Callable[[EntityRow], str] | None:
        """The caller's own right-aligned text. Wins over `secondary_field`."""
        return self._secondary

    def set_secondary(self, value: Callable[[EntityRow], str] | None) -> None:
        self._secondary = value
        self.view.viewport().update()

    @property
    def show_code(self) -> bool:
        """Show the row's `code` beside the label when the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self.view.viewport().update()

    @property
    def details(self) -> list[CollectionColumn]:
        """Extra values drawn on the sub-label line, each behind its own header."""
        return list(self._details)

    def set_details(self, value: Sequence[CollectionColumn]) -> None:
        self._details = list(value)
        self.view.viewport().update()

    @property
    def statuses(self) -> Mapping[str, StatusRecord] | None:
        """`Status` rows by code (probe 010)."""
        return self._statuses

    def set_statuses(self, value: Mapping[str, StatusRecord] | None) -> None:
        self._statuses = value
        self.view.viewport().update()

    @property
    def context(self) -> SgContext | None:
        """The widget context. Values render with its preferences."""
        return self._context

    def set_context(self, value: SgContext | None) -> None:
        self._context = value
        self.view.viewport().update()

    @property
    def density(self) -> str:
        """`compact` halves the vertical row padding."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value if value in GROUPED_LIST_DENSITY_VALUES else "default"
        self._rebuild_delegate()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the row text and the thumbnail step."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in GROUPED_LIST_SIZE_VALUES else "md"
        self._rebuild_delegate()

    @property
    def selectable(self) -> bool:
        """Draws a checkbox on each row."""
        return self._selectable

    def set_selectable(self, value: bool) -> None:
        self._selectable = bool(value)
        self._rebuild_delegate()

    @property
    def selection(self) -> list[EntityRef]:
        return self.control.selection

    def set_selection(self, value: Sequence[EntityRef]) -> None:
        self.control.set_selection(value)
        self.view.viewport().update()

    def set_get_row_id(self, fn: RowIdFn | None) -> None:
        self.control.set_get_row_id(fn)

    def set_is_row_disabled(self, fn: RowDisabledFn | None) -> None:
        self.control.set_is_row_disabled(fn)

    @property
    def collapsed(self) -> CollapseState:
        """Which groups are shut."""
        return self._collapsed

    def set_collapsed(self, value: Sequence[str] | CollapseState | None) -> None:
        state = as_collapse_state(value)
        if same_collapse(state, self._collapsed):
            return
        self._collapsed = state
        self.model.set_collapsed(state)
        self._sync()

    @property
    def sort(self) -> list[SortSpec]:
        return self.control.sort

    def set_sort(self, value: Sequence[SortSpec] | None) -> None:
        self.control.set_sort(value)

    @property
    def filters(self) -> SourceFilters:
        return self.control.filters

    def set_filters(self, value: SourceFilters) -> None:
        self.control.set_filters(value)

    @property
    def leading(self) -> Callable[[EntityRow], str] | None:
        """The row's leading mark when no thumbnail is wanted: a lucide name, or `#rrggbb`."""
        return self._leading

    def set_leading(self, value: Callable[[EntityRow], str] | None) -> None:
        self._leading = value
        self._rebuild_delegate()

    @property
    def paging(self) -> str:
        """`pages`, `more` or `scroll`."""
        return self.control.paging

    def set_paging(self, value: str) -> None:
        self.control.set_paging(value)
        self._sync()

    @property
    def page_sizes(self) -> list[int]:
        return self.footer.page_sizes

    def set_page_sizes(self, value: Sequence[int]) -> None:
        self.footer.set_page_sizes(value)

    @property
    def max_height(self) -> int:
        """Height of the scrolling body, in pixels."""
        return self._max_height

    def set_max_height(self, value: int | str) -> None:
        self._max_height = _px(value)
        self._fit()

    @property
    def virtualize_after(self) -> int:
        """Kept for parity. A `QListView` draws only the lines on screen at any length."""
        return self._virtualize_after

    def set_virtualize_after(self, value: int) -> None:
        self._virtualize_after = int(value)

    @property
    def empty_label(self) -> str:
        return self.control.labels.empty_label or NO_ROWS_LABEL

    def set_empty_label(self, value: str) -> None:
        labels = self.control.labels
        self.control.set_labels(
            StateLabels(
                empty_label=value,
                loading_label=labels.loading_label,
                error_label=labels.error_label,
            )
        )
        self._sync()

    def set_error_label(self, value: str | None) -> None:
        labels = self.control.labels
        self.control.set_labels(
            StateLabels(
                empty_label=labels.empty_label,
                loading_label=labels.loading_label,
                error_label=value,
            )
        )
        self._sync()

    # --- the regions ----------------------------------------------------------------------

    def set_header(self, *widgets: QtWidgets.QWidget) -> None:
        """The region above the list."""
        self._fill(self._header, widgets)

    def set_footer(self, *widgets: QtWidgets.QWidget) -> None:
        """The region below the footer."""
        self._fill(self._footer_region, widgets)

    def _fill(self, holder: QtWidgets.QWidget, widgets: Sequence[QtWidgets.QWidget]) -> None:
        layout = holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            made = item.widget()
            if made is not None:
                made.setParent(None)
        for widget in widgets:
            widget.setParent(holder)
            layout.addWidget(widget)
        holder.setVisible(layout.count() > 0)

    # --- what a row draws with ------------------------------------------------------------

    def label_of(self, row: EntityRow) -> str:
        if self._label_field:
            return str(cell_value(row, self._label_field) or "")
        return display_name_of(row.values, f"{row.type} #{row.id}")

    def code_of(self, row: EntityRow) -> str:
        """The programmatic name, when it says something the label does not."""
        if not self._show_code:
            return ""
        raw = cell_value(row, "code")
        label = self.label_of(row)
        return raw if isinstance(raw, str) and raw and raw != label else ""

    def sub_of(self, row: EntityRow) -> str:
        """The muted line under the label: the sub-label, then the details behind it."""
        parts: list[str] = []
        if self._sub_label is not None:
            parts.append(self._sub_label(row))
        else:
            text = self._text_of(row, self._sub_label_field)
            if text:
                parts.append(text)
        for column in self._details:
            value = cell_value(row, column.path)
            if is_empty_value(value):
                continue
            parts.append(
                column.header + DETAIL_GAP + field_text(value, column.data_type, self._text_options())
            )
        return DETAIL_SEPARATOR.join(part for part in parts if part)

    def secondary_of(self, row: EntityRow) -> str:
        if self._secondary is not None:
            return self._secondary(row)
        return self._text_of(row, self._secondary_field)

    def leading_of(self, row: EntityRow) -> str:
        """The leading mark of a row with no picture: the caller's glyph name or colour."""
        if self._leading is None:
            return ""
        return self._leading(row) or ""

    def thumbnail_of(self, row: EntityRow) -> str:
        if self._thumbnail is False:
            return ""
        raw = cell_value(row, str(self._thumbnail))
        return raw if isinstance(raw, str) and raw else ""

    def _text_of(self, row: EntityRow, spec: FieldSpec | None) -> str:
        path = path_of(spec)
        if not path:
            return ""
        value = cell_value(row, path)
        if is_empty_value(value):
            return ""
        column = to_column(spec if not isinstance(spec, str) else path)
        return field_text(value, column.data_type, self._text_options())

    def _text_options(self) -> Any:
        return preferences_of(self._context)

    def paint_group_value(self, painter: QtGui.QPainter, rect: QRect, group: Any) -> int:
        """The heading's value: by its column's data type, the caller's label, or its own text.

        Answers the width it drew, so the count can follow it in the same line.
        """
        if self._group_by is not None and self._group_key is None:
            options = FieldValueOptions(
                theme=theme_of(self.view),
                statuses=self._statuses,
                site_url=self._context.site_url if self._context is not None else "",
                density=self._density,
                text=self._text_options(),
                on_ready=self.view.viewport().update,
            )
            paint_field_value(painter, rect, group.value, self._group_by, options)
            wanted = field_value_size_hint(group.value, self._group_by, options).width()
            return min(wanted, rect.width())
        text = self._group_label(group.value) if self._group_label else group_key_text(group.value)
        theme = theme_of(self.view)
        # A heading reads at the row's own step, whether its value came from a column or a key.
        font = theme.font(ROW_TEXT[self._size], QtGui.QFont.Weight.Medium)
        metrics = QtGui.QFontMetrics(font)
        drawn = elide(metrics, text, rect.width())
        painter.setFont(font)
        painter.setPen(theme.color("foreground"))
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            drawn,
        )
        return min(metrics.horizontalAdvance(drawn), rect.width())

    # --- interaction ----------------------------------------------------------------------

    def on_line_pressed(self, index: QModelIndex, point: QtCore.QPoint) -> None:
        """A press on a heading collapses it; on a row it selects or opens."""
        line = self.model.line_at(index.row())
        if line is None:
            return
        if line.kind == "heading" and line.group is not None:
            self.toggle_group(line.group.key)
            return
        row = line.row
        if row is None or self.control.row_disabled(row):
            return
        self.control.set_cursor(line.index)
        if self._selectable:
            self.control.toggle(row)
            self.view.viewport().update()
            return
        self.selected.emit(row)

    def toggle_group(self, key: str) -> None:
        """Shut or open one group, keeping the mode a later page follows."""
        state = toggle_collapsed(self._collapsed, key)
        drawn = [group.key for group in self.model.groups]
        shut = [entry for entry in drawn if is_collapsed(state, entry)]
        self._collapsed = collapse_state_from(state, shut, drawn)
        self.model.set_collapsed(self._collapsed)
        self.collapsed_changed.emit(self._collapsed)
        self._sync()

    def on_key(self, event: QtGui.QKeyEvent) -> bool:
        """The arrows walk the rows; Enter and Space take a row or collapse a heading."""
        key = event.key()
        index = self.view.currentIndex()
        line = self.model.line_at(index.row()) if index.isValid() else None
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if line is None:
                return False
            if line.kind == "heading" and line.group is not None:
                self.toggle_group(line.group.key)
                return True
            if line.row is not None:
                if self._selectable:
                    self.control.toggle(line.row)
                    self.view.viewport().update()
                else:
                    self.selected.emit(line.row)
                return True
            return False
        if key not in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            return False
        step = 1 if key == Qt.Key.Key_Down else -1
        at = line.index if line is not None and line.kind == "row" else -1
        if at < 0:
            self._focus(max(0, self.control.active))
            return True
        if step > 0 and self.control.ask_for_page(at + 1):
            return True
        self._focus(self.control.step_cursor(step, at))
        return True

    def _focus(self, index: int) -> None:
        line = self.model.line_of_row_index(index)
        if line < 0:
            return
        self.control.set_cursor(index)
        target = self.model.index(line, 0)
        self.view.setCurrentIndex(target)
        self.view.scrollTo(target, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)

    def _on_scrolled(self, _value: int) -> None:
        last = self.view.indexAt(self.view.viewport().rect().bottomLeft())
        line = last.row() if last.isValid() else self.model.rowCount() - 1
        self.control.on_last_visible(self.model.last_row_of_line(line))

    def _on_range(self, _low: int, _high: int) -> None:
        self._fill_timer.start(0)

    def _ask_if_unfilled(self) -> None:
        """Rows that do not fill the view leave its end in sight, so it asks as a scroll would.

        Upstream's sentinel fires whenever it is visible, scrolled to or not. The check runs a
        turn after the rows landed or the range moved, once the view has laid them out.
        """
        bar = self.view.verticalScrollBar()
        if bar is None or not self.model.rows or not self.view.isVisible():
            return
        if bar.maximum() <= bar.minimum():
            self._on_scrolled(0)

    # --- internals ------------------------------------------------------------------------

    def _grouping(self) -> GroupBy:
        if self._group_key is not None:
            return self._group_key
        return self._group_by.path if self._group_by is not None else ""

    def _lead_sort(self) -> None:
        """A group is only whole when the server put its rows together, so the path leads the sort.

        A derived key has no path to sort on, and the order is then the caller's to set.
        """
        if self._group_key is not None or self._group_by is None:
            return
        path = self._group_by.path
        keys = self.control.sort
        if keys and keys[0].path == path:
            return
        self.control.apply_sort(
            [SortSpec(path=path, descending=False), *[key for key in keys if key.path != path]]
        )

    def _rebuild_delegate(self) -> None:
        self._delegate = _GroupDelegate(self)
        self.view.setItemDelegate(self._delegate)
        self.view.viewport().update()

    def _sync(self) -> None:
        state = self.control.snapshot()
        view = self.control.view(len(self.model.lines))
        if view == "loading" and self.model.lines and self.view.isVisible():
            # Read now, while the rows still stand, so the skeletons fill the height they had.
            first = next((i for i, line in enumerate(self.model.lines) if line.kind == "row"), 0)
            self._rows_height = self.view.height()
            self._row_height = max(SKELETON_HEIGHT + 2, self.view.sizeHintForRow(first))
        if view == "loading":
            if self._rows_height > 0:
                self._skeleton.set_rows(max(1, round(self._rows_height / self._row_height)), self._row_height)
            else:
                self._skeleton.set_rows(SKELETON_ROWS, self._row_height)
        self.view.setVisible(view == "rows")
        self._skeleton.setVisible(view == "loading")
        self._state.setVisible(view in ("empty", "error"))
        if view == "empty":
            self._state.set_icon(EMPTY_ICON)
            self._state.apply_state("empty", self.control.labels)
        elif view == "error":
            self._state.set_icon(ERROR_ICON)
            self._state.apply_state(
                "error", self.control.labels, None if state.error is None else str(state.error)
            )
        self._bottom.apply(
            self.control.bottom(),
            state_line("error", self.control.labels, None if state.error is None else str(state.error)),
            self.control.loading_text,
        )
        self.footer.set_pager(self.control.pager)
        self.footer.set_loading(state.status == "loading")
        waiting = self.control.take_pending_cursor()
        if waiting >= 0:
            self._focus(waiting)
        self._fit()
        self.view.viewport().update()

    def _fit(self) -> None:
        fit_body(
            self.view,
            rows_height(self.view, len(self.model.lines), self._max_height),
            self._max_height,
        )


class _SkeletonRow(QtWidgets.QWidget):
    """One row a read stands behind: a bar in the row's own inset, a half-tone rule under it.

    Upstream's loading row is the row's own class holding a `Skeleton h-5 w-full`, with
    `border-b border-border/50` between rows.
    """

    def __init__(self, height: int, last: bool, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._last = last
        self.setFixedHeight(height)
        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(ROW_PAD_X, 0, ROW_PAD_X, 0)
        line.addWidget(Skeleton(height=SKELETON_HEIGHT, parent=self))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._last:
            return
        painter = QtGui.QPainter(self)
        theme = theme_of(self)
        painter.fillRect(
            QRect(0, self.height() - 1, self.width(), 1), with_alpha(theme.color("border"), 0.5)
        )
        painter.end()


class _ListSkeleton(SkeletonBlock):
    """Rows a read stands behind, at the row height and as many as stood there.

    A first read draws upstream's eight; a re-read of rows already on screen, a sort or a new
    page, draws as many as fill the height the rows had, so the list keeps its height and
    nothing under it moves while the answer is on its way.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("grouped-list-loading")
        self.setAccessibleName("Loading…")
        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(0)
        self._rows = 0
        self.set_rows(SKELETON_ROWS, SKELETON_ROW_HEIGHT)

    @property
    def rows(self) -> int:
        """How many rows stand in the block."""
        return self._rows

    def set_rows(self, count: int, row_height: int) -> None:
        count = max(1, int(count))
        row_height = max(SKELETON_HEIGHT + 2, int(row_height))
        while self._column.count():
            item = self._column.takeAt(0)
            made = item.widget()
            if made is not None:
                made.setParent(None)
                made.deleteLater()
        for index in range(count):
            self._column.addWidget(_SkeletonRow(row_height, index == count - 1, self))
        self._rows = count
        self.setFixedHeight(count * row_height)
