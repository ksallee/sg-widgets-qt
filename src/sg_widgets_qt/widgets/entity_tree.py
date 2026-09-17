"""A project's navigation tree, one level per call.

Ported from `packages/react/src/registry/sg/components/entity-tree.tsx` over core's `create_tree`.

`POST /hierarchy/_expand` answers one level: the node, and children carrying a label, a ref and
whether expanding them is worth it, so walking a project is one call per node
(post_hierarchy_expand). Which levels a project has is the site's own navigation configuration
and not a fixed hierarchy, the probed site's Shot path runs through the field name `sg_sequence`
(post_hierarchy_search), so `seed_path` is followed by taking whichever child is a prefix of it
rather than by parsing the path.

Every row's fields come with its level: one read per type over the ids just returned, so a
sub-label or a status costs nothing per row.

Searching is two calls a query: `_text_search` matches the words and `hierarchy/_search` says
where each hit sits, so the tree opens along every answered path, marks the rows the words found
and dims the rest (post_entity_text_search, post_hierarchy_search).

    tree = EntityTree(context=context, root_path="/Project/70", checkable=True, searchable=True)
    tree.checked_changed.connect(store)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QAbstractItemModel, QModelIndex, QObject, QRect, QSize, Qt, Signal

from sg_widgets_core.collection import to_column
from sg_widgets_core.collection_state import same_ids
from sg_widgets_core.context import SgContext, preferences_of
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.render import field_text, is_empty_value
from sg_widgets_core.row import FieldSpec, path_of
from sg_widgets_core.search import match_runs
from sg_widgets_core.state import NO_MATCH_LABEL, NO_ROWS_LABEL, StateLabels, state_line
from sg_widgets_core.tree import (
    TREE_STATUS_FIELDS,
    HierarchyLoaderOptions,
    HierarchySearcherOptions,
    TreeFieldPlan,
    TreeKey,
    TreeNode,
    TreeOptions,
    TreeRow,
    TreeState,
    create_tree,
    hierarchy_loader,
    hierarchy_searcher,
    resolve_tree_fields,
)

from .. import icons
from ..images import ImageLoader, image_loader
from ..primitives.base import CONTROL_HEIGHT, THUMB_SIZE
from ..primitives.input import Input
from ..primitives.list_view import GUTTER
from ..primitives.roles import Roles
from ..primitives.row_delegate import LEAD_GLYPH, ROW_PAD_X, ROW_PAD_Y, RowDelegate
from ..primitives.scrollbar import install_overlay_scrollbars
from ..primitives.skeleton import Skeleton
from ..theme import theme_of
from ..workers import DEFAULT_DEBOUNCE_MS, Debounce, JobPool
from .collection_control import COLLECTION_GAP
from .entity_glyphs import entity_glyph
from .entity_table import fit_body
from .picker_row import status_painter
from .state_line import StateLine

__all__ = [
    "ENTITY_TREE_DENSITY_VALUES",
    "ENTITY_TREE_INDENT",
    "ENTITY_TREE_SIZE_VALUES",
    "EntityTree",
]

#: The root index every model call takes as its default parent.
_ROOT = QModelIndex()

ENTITY_TREE_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")
ENTITY_TREE_DENSITY_VALUES: tuple[str, ...] = ("compact", "default")

#: One level of depth, upstream's `--tree-indent: 1rem`.
ENTITY_TREE_INDENT = 16

#: The chevron and the gap between it and the row, rule 2's inline gap.
CHEVRON: dict[str, int] = {"sm": 14, "md": 16, "lg": 20}
CHEVRON_GAP = 6

#: A leaf inside a row sits one step down the thumbnail ladder.
TREE_THUMB: dict[str, str] = {"sm": "sm", "md": "sm", "lg": "md"}

#: Height of the scrolling body, upstream's `24rem` in pixels.
DEFAULT_MAX_HEIGHT = 384

#: Rows a first read stands behind.
SKELETON_ROWS = 5
SKELETON_HEIGHT = 20

#: What the empty, the no-match and the error blocks are drawn with.
EMPTY_ICON = "inbox"
NO_MATCH_ICON = "search-x"
ERROR_ICON = "circle-alert"

#: The Qt keys core's tree model names, in its own spelling.
_KEYS: dict[int, str] = {
    int(Qt.Key.Key_Down): "ArrowDown",
    int(Qt.Key.Key_Up): "ArrowUp",
    int(Qt.Key.Key_Right): "ArrowRight",
    int(Qt.Key.Key_Left): "ArrowLeft",
    int(Qt.Key.Key_Home): "Home",
    int(Qt.Key.Key_End): "End",
    int(Qt.Key.Key_Space): " ",
    int(Qt.Key.Key_Return): "Enter",
    int(Qt.Key.Key_Enter): "Enter",
    int(Qt.Key.Key_Asterisk): "*",
}


class _TreeBinding(QObject):
    """The engine, read off the GUI thread, with its snapshot delivered on it.

    Core's tree is synchronous, so every call that reads a level runs on a pool of one thread
    and the snapshot crosses back on a queued signal. A search holds the engine's own ticket, so
    the answer of a search the next one replaced is dropped rather than written over it.
    """

    changed = Signal()
    failed = Signal(object)
    _published = Signal()

    def __init__(self, engine: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._pool = JobPool(1, self)
        self._published.connect(self.changed.emit, Qt.ConnectionType.QueuedConnection)
        self._unsubscribe = engine.subscribe(self._published.emit)

    def snapshot(self) -> TreeState:
        return self.engine.snapshot()

    @property
    def pool(self) -> JobPool:
        """The one thread the engine is read on. A schema lookup beside it submits here too."""
        return self._pool

    @property
    def busy(self) -> bool:
        """True while a level, a seed walk or a search is still being read."""
        return self._pool.running > 0

    def run(self, name: str, *args: Any) -> None:
        """Call one of the engine's methods on the pool."""
        self._pool.submit(getattr(self.engine, name), *args, on_error=self.failed.emit)

    def wait(self, timeout_ms: int = 5000) -> bool:
        """Block until every call is answered, then deliver what they published. For a test."""
        done = self._pool.wait(timeout_ms)
        QtCore.QCoreApplication.processEvents()
        return done

    def close(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._pool.cancel_all()


class _Handle:
    """What an index points at: one path, held by the model so the pointer stays alive.

    A `QModelIndex` carries a pointer, and a Python object handed to `createIndex` is only
    valid while something else holds a reference to it. Handles are therefore kept for every
    path the tree has ever shown, so an index made before a reset never dangles.
    """

    __slots__ = ("path",)

    def __init__(self, path: str) -> None:
        self.path = path


class TreeModel(QAbstractItemModel):
    """The engine's visible rows as a hierarchy, keyed by path.

    Every row the model holds is one the engine says is visible, so the view shows them all and
    a collapse is the engine dropping rows rather than the view hiding them.
    """

    def __init__(self, tree: EntityTree) -> None:
        super().__init__(tree)
        self._tree = tree
        self._rows: dict[str, TreeRow] = {}
        self._children: dict[str, list[str]] = {}
        self._roots: list[str] = []
        self._handles: dict[str, _Handle] = {}

    # --- what it holds --------------------------------------------------------------------

    def set_rows(self, rows: Sequence[TreeRow]) -> None:
        self.beginResetModel()
        self._rows = {row.node.path: row for row in rows}
        paths = [row.node.path for row in rows]
        self._children = {path: [] for path in paths}
        self._roots = []
        held = set(paths)
        for path in paths:
            if path not in self._handles:
                self._handles[path] = _Handle(path)
        for row in rows:
            parent = row.node.parent_path
            if parent is not None and parent in held:
                self._children[parent].append(row.node.path)
            else:
                self._roots.append(row.node.path)
        self.endResetModel()

    def row_of(self, path: str) -> TreeRow | None:
        return self._rows.get(path)

    def path_of(self, index: QModelIndex) -> str:
        handle = index.internalPointer()
        return handle.path if isinstance(handle, _Handle) else ""

    def index_of(self, path: str) -> QModelIndex:
        row = self._rows.get(path)
        handle = self._handles.get(path)
        if row is None or handle is None:
            return QModelIndex()
        parent = row.node.parent_path
        siblings = self._children.get(parent, []) if parent is not None else self._roots
        if path not in siblings:
            siblings = self._roots
        if path not in siblings:
            return QModelIndex()
        return self.createIndex(siblings.index(path), 0, handle)

    # --- the model ------------------------------------------------------------------------

    def index(self, row: int, column: int, parent: QModelIndex = _ROOT) -> QModelIndex:
        siblings = self._children.get(self.path_of(parent), []) if parent.isValid() else self._roots
        if row < 0 or row >= len(siblings) or column != 0:
            return QModelIndex()
        handle = self._handles.get(siblings[row])
        if handle is None:
            return QModelIndex()
        return self.createIndex(row, column, handle)

    def parent(self, child: QModelIndex = _ROOT) -> QModelIndex:  # noqa: A003
        if not child.isValid():
            return QModelIndex()
        row = self._rows.get(self.path_of(child))
        if row is None or row.node.parent_path is None:
            return QModelIndex()
        return self.index_of(row.node.parent_path)

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        if not parent.isValid():
            return len(self._roots)
        return len(self._children.get(self.path_of(parent), []))

    def columnCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        row = self._rows.get(self.path_of(index))
        if row is not None and row.disabled:
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        row = self._rows.get(self.path_of(index))
        if row is None:
            return None
        return self._tree.row_data(row, role)


class _TreeDelegate(RowDelegate):
    """The tree row: the chevron, the tri-state box, and the row of rule 9 after them."""

    def __init__(self, tree: EntityTree) -> None:
        super().__init__(
            tree.view,
            size=tree.size,
            thumbnail=True,
            indicator="checkbox" if tree.checkable else "none",
            density=tree.density,
        )
        self._tree = tree
        self.set_bare_glyph(tree.thumbnail is False)

    def _lead(self) -> int:
        return CHEVRON[self._tree.size] + CHEVRON_GAP

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), CHEVRON[self._tree.size] + 2 * ROW_PAD_Y))

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        row = self._tree.row_at(index)
        theme = theme_of(self._tree.view)
        side = CHEVRON[self._tree.size]
        rect = option.rect
        shifted = QtWidgets.QStyleOptionViewItem(option)
        shifted.rect = QRect(rect.left() + self._lead(), rect.top(), max(0, rect.width() - self._lead()), rect.height())
        super().paint(painter, shifted, index)
        if row is None or not row.node.has_children:
            return
        box = QRect(rect.left() + ROW_PAD_X, 0, side, side)
        box.moveTop(rect.center().y() - side // 2)
        if row.loading:
            icons.paint_icon(painter, box, "loader", theme.color("muted_foreground"))
            return
        icons.paint_icon(
            painter,
            box,
            "chevron-down" if row.expanded else "chevron-right",
            theme.color("muted_foreground"),
        )

    def chevron_rect(self, rect: QRect) -> QRect:
        """Where the chevron sits, so the view can tell a press on it apart."""
        side = CHEVRON[self._tree.size]
        box = QRect(rect.left() + ROW_PAD_X, 0, side, side)
        box.moveTop(rect.center().y() - side // 2)
        return box.adjusted(-2, -2, 2, 2)

    def checkbox_rect(self, rect: QRect) -> QRect:
        """Where the row's own box sits, after the chevron."""
        left = rect.left() + self._lead() + ROW_PAD_X
        return QRect(left, rect.top(), 16, rect.height())

    def _paint_checkbox(
        self, painter: QtGui.QPainter, column: QRect, index: QModelIndex, theme: Any
    ) -> None:
        """The tri-state box: a part-checked branch carries a minus, not a tick."""
        if index.data(Roles.CHECKED) != "mixed":
            super()._paint_checkbox(painter, column, index, theme)
            return
        box = QRect(column.left(), column.top() + (column.height() - 16) // 2, 16, 16)
        radius = float(theme.radius_px("sm"))
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("primary"))
        painter.drawRoundedRect(box, radius, radius)
        icons.paint_icon(painter, box.adjusted(2, 2, -2, -2), "minus", theme.color("primary_foreground"))
        painter.restore()


class _TreeView(QtWidgets.QTreeView):
    """The scrolling body: our delegate, our overlay scrollbars, the engine's keyboard model."""

    def __init__(self, tree: EntityTree) -> None:
        self._tree = tree
        super().__init__(tree)
        self.setObjectName("entity-tree-list")
        self.setFrameShape(QtWidgets.QTreeView.Shape.NoFrame)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        self.setExpandsOnDoubleClick(False)
        self.setIndentation(ENTITY_TREE_INDENT)
        self.setUniformRowHeights(False)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # The gutter every list holds for its overlay scrollbar, so a status badge is never
        # drawn under the bar.
        self.setViewportMargins(0, 0, GUTTER, 0)
        install_overlay_scrollbars(self)

    def drawBranches(self, painter: QtGui.QPainter, rect: QRect, index: QModelIndex) -> None:  # noqa: N802
        """Nothing: the chevron belongs to the row, so the host's branch marks are never drawn."""
        return

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(point)
        if index.isValid():
            self._tree.on_row_pressed(index, point, bool(event.modifiers() & _BRANCH_MODIFIERS))
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._tree.on_key(event):
            return
        super().keyPressEvent(event)


#: Alt or Cmd/Ctrl on the chevron opens the whole branch rather than one level.
_BRANCH_MODIFIERS = (
    Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.MetaModifier
)


class EntityTree(QtWidgets.QWidget):
    """A project's navigation tree: expand and collapse one level at a time, search, and check."""

    #: A leaf was chosen. Carries the `TreeNode`.
    selected = Signal(object)
    #: The selected paths. Carries `list[str]`.
    selection_changed = Signal(object)
    #: The open paths. Carries `list[str]`.
    expanded_changed = Signal(object)
    #: The checked rows. Carries `list[EntityRef]`.
    checked_changed = Signal(object)
    #: A read failed. Carries the exception.
    error = Signal(object)

    def __init__(
        self,
        context: SgContext,
        root_path: str = "",
        seed_path: str | Sequence[str] | None = None,
        checkable: bool = False,
        selection_mode: str = "single",
        selection: Sequence[str] | None = None,
        expanded: Sequence[str] | None = None,
        is_row_disabled: Callable[[TreeNode], bool] | None = None,
        searchable: bool = False,
        search_placeholder: str = "Search",
        expand_depth: int = 3,
        thumbnail: str | bool = False,
        label_field: str | None = None,
        sub_label_field: FieldSpec | None = None,
        sub_label: Callable[[TreeNode], str] | None = None,
        secondary_field: FieldSpec | None = None,
        secondary: Callable[[TreeNode], str] | None = None,
        show_code: bool = False,
        fields: Sequence[str] | None = None,
        site_url: str = "",
        label: str = "Project hierarchy",
        max_height: int | str = DEFAULT_MAX_HEIGHT,
        empty_label: str = NO_ROWS_LABEL,
        no_match_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        size: str = "md",
        density: str = "default",
        loader: ImageLoader | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-tree")
        self._context = context
        self._root_path = root_path
        self._seed_path = seed_path
        self._checkable = bool(checkable)
        self._selection_mode = selection_mode
        self._is_row_disabled = is_row_disabled
        self._searchable = bool(searchable)
        self._expand_depth = int(expand_depth)
        self._thumbnail = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._fields = list(fields or [])
        self._site_url = site_url
        self._label = label
        self._no_match_label = no_match_label
        self._labels = StateLabels(
            empty_label=empty_label, loading_label=loading_label, error_label=error_label
        )
        self._size = size if size in ENTITY_TREE_SIZE_VALUES else "md"
        self._density = density if density in ENTITY_TREE_DENSITY_VALUES else "default"
        self._loader = loader if loader is not None else image_loader()
        self._plan = TreeFieldPlan()
        self._pixmaps: dict[str, QtGui.QPixmap] = {}
        self._asked: set[str] = set()
        self._types = ""
        self._expanded_seen: list[str] = []
        self._selected_seen: list[str] = []
        self._checked_seen: list[str] = []

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(COLLECTION_GAP)

        self._header = QtWidgets.QWidget(self)
        self._header.setObjectName("entity-tree-header")
        head = QtWidgets.QHBoxLayout(self._header)
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(COLLECTION_GAP)
        self._header.hide()
        column.addWidget(self._header)

        self._search = Input(placeholder=search_placeholder, size=self._size, parent=self)
        self._search.setObjectName("entity-tree-search")
        self._search.setAccessibleName(search_placeholder)
        self._search.setVisible(self._searchable)
        self._search.textChanged.connect(self._on_query)
        column.addWidget(self._search)
        self._debounce = Debounce(DEFAULT_DEBOUNCE_MS, self)

        self._box = QtWidgets.QWidget(self)
        self._box.setObjectName("entity-tree-scroll")
        body = QtWidgets.QVBoxLayout(self._box)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.view = _TreeView(self)
        self.model = TreeModel(self)
        self.view.setModel(self.model)
        self._delegate = _TreeDelegate(self)
        self.view.setItemDelegate(self._delegate)
        self._max_height = _height(max_height)
        self.view.setMaximumHeight(self._max_height)
        self.view.setAccessibleName(label)
        body.addWidget(self.view)
        self._state = StateLine(pad="table", slot_name="entity-tree-state", parent=self._box)
        self._state.hide()
        body.addWidget(self._state)
        self._skeleton = _TreeSkeleton(self._box)
        body.addWidget(self._skeleton)
        column.addWidget(self._box)

        self._footer = QtWidgets.QWidget(self)
        self._footer.setObjectName("entity-tree-footer")
        foot = QtWidgets.QHBoxLayout(self._footer)
        foot.setContentsMargins(0, 0, 0, 0)
        foot.setSpacing(COLLECTION_GAP)
        self._footer.hide()
        column.addWidget(self._footer)

        self.binding = _TreeBinding(self._build_engine(), self)
        self.binding.changed.connect(self._sync)
        self.binding.failed.connect(self.error.emit)
        if selection:
            self.engine.set_selected(list(selection))
        if expanded:
            self.binding.run("set_expanded", list(expanded))
        elif seed_path:
            self.binding.run("expand_to_path", seed_path)
        else:
            self.binding.run("load")
        self._sync()

    # --- the engine -----------------------------------------------------------------------

    @property
    def engine(self) -> Any:
        """Core's tree: the nodes, the cursor, the checkboxes and the search."""
        return self.binding.engine

    def snapshot(self) -> TreeState:
        return self.binding.snapshot()

    def _build_engine(self) -> Any:
        requested = [
            *TREE_STATUS_FIELDS,
            *([] if self._thumbnail is False else [str(self._thumbnail)]),
            *([self._label_field] if self._label_field else []),
            *([path_of(self._sub_label_field)] if path_of(self._sub_label_field) else []),
            *(
                [path_of(self._secondary_field)]
                if path_of(self._secondary_field) and path_of(self._secondary_field) != "id"
                else []
            ),
            *self._fields,
        ]
        return create_tree(
            TreeOptions(
                loader=hierarchy_loader(
                    self._context.client, HierarchyLoaderOptions(fields=list(dict.fromkeys(requested)))
                ),
                root_path=self._root_path,
                selection=self._selection_mode,
                expand_depth=self._expand_depth,
                disabled=self._is_row_disabled,
                searcher=hierarchy_searcher(
                    self._context.client,
                    self._root_path,
                    HierarchySearcherOptions(schema=self._context.schema),
                ),
            )
        )

    # --- props ----------------------------------------------------------------------------

    @property
    def context(self) -> SgContext:
        """The widget context. Every read goes through it, so widgets on a page share one cache."""
        return self._context

    @property
    def root_path(self) -> str:
        """Where the tree starts, `/Project/<id>`."""
        return self._root_path

    def set_root_path(self, value: str) -> None:
        self._root_path = value
        self._restart()

    @property
    def seed_path(self) -> str | Sequence[str] | None:
        """Opens the tree down to this path on mount, one level per call."""
        return self._seed_path

    def set_seed_path(self, value: str | Sequence[str] | None) -> None:
        self._seed_path = value
        if value:
            self.binding.run("expand_to_path", value)

    @property
    def checkable(self) -> bool:
        """Draws a checkbox per node and reports the checked rows."""
        return self._checkable

    def set_checkable(self, value: bool) -> None:
        self._checkable = bool(value)
        self._rebuild_delegate()

    @property
    def selection_mode(self) -> str:
        """`none`, `single` or `multiple`."""
        return self._selection_mode

    def set_selection_mode(self, value: str) -> None:
        self._selection_mode = value
        self._restart()

    @property
    def selection(self) -> list[str]:
        """Paths of the selected nodes."""
        return list(self.snapshot().selected)

    def set_selection(self, value: Sequence[str]) -> None:
        if same_ids(value, self.snapshot().selected):
            return
        self.engine.set_selected(list(value))

    @property
    def expanded(self) -> list[str]:
        """Paths of the open nodes."""
        return list(self.snapshot().expanded)

    def set_expanded(self, value: Sequence[str]) -> None:
        if same_ids(value, self.snapshot().expanded):
            return
        self.binding.run("set_expanded", list(value))

    def set_is_row_disabled(self, fn: Callable[[TreeNode], bool] | None) -> None:
        self._is_row_disabled = fn
        self._restart()

    @property
    def searchable(self) -> bool:
        """Shows an input that searches the project and opens the tree onto the hits."""
        return self._searchable

    def set_searchable(self, value: bool) -> None:
        self._searchable = bool(value)
        self._search.setVisible(self._searchable)

    @property
    def search_placeholder(self) -> str:
        return self._search.placeholderText()

    def set_search_placeholder(self, value: str) -> None:
        self._search.setPlaceholderText(value)
        self._search.setAccessibleName(value)

    @property
    def expand_depth(self) -> int:
        """How many levels a whole-branch expansion opens."""
        return self._expand_depth

    def set_expand_depth(self, value: int) -> None:
        self._expand_depth = int(value)
        self._restart()

    @property
    def thumbnail(self) -> str | bool:
        """Field holding the thumbnail URL. False, the default, leaves the entity glyph."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self._restart()

    @property
    def label_field(self) -> str | None:
        """Field shown as the row's label, in place of the tree's own."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self._restart()

    @property
    def sub_label_field(self) -> FieldSpec | None:
        """Field shown under the label."""
        return self._sub_label_field

    def set_sub_label_field(self, value: FieldSpec | None) -> None:
        self._sub_label_field = value
        self._restart()

    @property
    def sub_label(self) -> Callable[[TreeNode], str] | None:
        """Muted line under the label, of the caller's own making."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[TreeNode], str] | None) -> None:
        self._sub_label = value
        self.view.viewport().update()

    @property
    def secondary_field(self) -> FieldSpec | None:
        """Right-aligned field. Without one, the row's status takes that slot."""
        return self._secondary_field

    def set_secondary_field(self, value: FieldSpec | None) -> None:
        self._secondary_field = value
        self._restart()

    @property
    def secondary(self) -> Callable[[TreeNode], str] | None:
        """Right-aligned text of the caller's own making."""
        return self._secondary

    def set_secondary(self, value: Callable[[TreeNode], str] | None) -> None:
        self._secondary = value
        self.view.viewport().update()

    @property
    def show_code(self) -> bool:
        """Show the schema name beside the label on a node that stands for a type."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self.view.viewport().update()

    @property
    def fields(self) -> list[str]:
        """Extra fields to request, so a caller's own sub-label or secondary can read them."""
        return list(self._fields)

    def set_fields(self, value: Sequence[str]) -> None:
        self._fields = list(value)
        self._restart()

    @property
    def site_url(self) -> str:
        """The site the status sprite is served from. Defaults to the context's."""
        return self._site_url or self._context.site_url

    def set_site_url(self, value: str) -> None:
        self._site_url = value
        self.view.viewport().update()

    @property
    def label(self) -> str:
        """The accessible name of the tree."""
        return self._label

    def set_label(self, value: str) -> None:
        self._label = value
        self.view.setAccessibleName(value)

    @property
    def max_height(self) -> int:
        """Height of the scrolling body, in pixels."""
        return self._max_height

    def set_max_height(self, value: int | str) -> None:
        self._max_height = _height(value)
        self._fit()

    @property
    def empty_label(self) -> str:
        return self._labels.empty_label or NO_ROWS_LABEL

    def set_empty_label(self, value: str) -> None:
        self._labels = StateLabels(
            empty_label=value,
            loading_label=self._labels.loading_label,
            error_label=self._labels.error_label,
        )
        self._sync()

    @property
    def no_match_label(self) -> str:
        """Shown when the query matched nothing."""
        return self._no_match_label

    def set_no_match_label(self, value: str) -> None:
        self._no_match_label = value
        self._sync()

    def set_loading_label(self, value: str | None) -> None:
        self._labels = StateLabels(
            empty_label=self._labels.empty_label,
            loading_label=value,
            error_label=self._labels.error_label,
        )

    def set_error_label(self, value: str | None) -> None:
        self._labels = StateLabels(
            empty_label=self._labels.empty_label,
            loading_label=self._labels.loading_label,
            error_label=value,
        )
        self._sync()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the row text, the leading slot and the search input."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in ENTITY_TREE_SIZE_VALUES else "md"
        self._search.set_size(self._size)
        self._rebuild_delegate()

    @property
    def density(self) -> str:
        """`compact` halves the vertical row padding."""
        return self._density

    def set_density(self, value: str) -> None:
        self._density = value if value in ENTITY_TREE_DENSITY_VALUES else "default"
        self._rebuild_delegate()

    @property
    def search(self) -> str:
        """The text the tree is searching for."""
        return self._search.text()

    def set_search(self, value: str) -> None:
        self._search.setText(value)

    # --- the regions ----------------------------------------------------------------------

    def set_header(self, *widgets: QtWidgets.QWidget) -> None:
        """The region above the tree."""
        self._fill(self._header, widgets)

    def set_footer(self, *widgets: QtWidgets.QWidget) -> None:
        """The region below the tree."""
        self._fill(self._footer, widgets)

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

    def row_at(self, index: QModelIndex) -> TreeRow | None:
        return self.model.row_of(self.model.path_of(index))

    def row_data(self, row: TreeRow, role: int) -> Any:
        node = row.node
        state = self.snapshot()
        if role == Qt.ItemDataRole.DisplayRole or role == Roles.LABEL:
            return self._label_of(node)
        if role == Roles.RUNS:
            return self._runs_of(node, state)
        if role == Roles.CODE:
            return self._code_of(node)
        if role == Roles.SUB_LABEL:
            return self._sub_of(node)
        if role == Roles.SECONDARY:
            return self._secondary_text(node)
        if role == Roles.PAINTER:
            return self._secondary_painter(node)
        if role == Roles.PIXMAP:
            return self._picture(node)
        if role == Roles.GLYPH:
            return entity_glyph(node.entity.type) if node.entity is not None else "folder"
        if role == Roles.CHECKED:
            if not self._checkable:
                return None
            return True if row.checked == "checked" else ("mixed" if row.checked == "mixed" else False)
        if role == Roles.DISABLED:
            return row.disabled
        if role == Roles.KIND:
            return "row"
        if role == Roles.ENTITY:
            return node
        return None

    def _label_of(self, node: TreeNode) -> str:
        if self._label_field:
            value = node.values.get(self._label_field)
            if isinstance(value, str) and value:
                return value
        return node.label

    def _runs_of(self, node: TreeNode, state: TreeState) -> list[tuple[str, bool, bool]]:
        """The label's matched runs in DemiBold, with a row the search did not place muted."""
        label = self._label_of(node)
        dimming = bool(state.search.strip()) and len(state.matches) > 0
        muted = dimming and node.path not in state.matches
        if not state.search.strip():
            return [(label, False, False)]
        return [(run.text, run.match, muted) for run in match_runs(label, state.search)]

    def _code_of(self, node: TreeNode) -> str:
        """The schema name a folder stands for, which is the only code a tree row has."""
        if not self._show_code or node.ref.kind != "entity_type":
            return ""
        return node.ref.value if isinstance(node.ref.value, str) else ""

    def _sub_of(self, node: TreeNode) -> str:
        if self._sub_label is not None:
            return self._sub_label(node)
        path = path_of(self._sub_label_field)
        if not path:
            return ""
        raw = node.values.get(path)
        return "" if raw is None else str(raw)

    def _status_of(self, node: TreeNode) -> str:
        field = self._plan.status.get(node.entity.type) if node.entity is not None else None
        code = node.values.get(field.name) if field is not None else None
        return code if isinstance(code, str) else ""

    def _secondary_text(self, node: TreeNode) -> str:
        if self._secondary is not None:
            return self._secondary(node)
        path = path_of(self._secondary_field)
        if not path:
            return ""
        value = node.entity.id if path == "id" and node.entity is not None else node.values.get(path)
        if is_empty_value(value):
            return ""
        column = to_column(self._secondary_field if not isinstance(self._secondary_field, str) else path)
        data_type = column.data_type
        if data_type == "text" and path == "id":
            data_type = "number"
        return field_text(value, data_type, preferences_of(self._context))

    def _secondary_painter(self, node: TreeNode) -> Any:
        """The row's status badge, unless a secondary of the caller's own has the slot."""
        if self._secondary is not None or path_of(self._secondary_field):
            return None
        code = self._status_of(node)
        if not code:
            return None
        field = self._plan.status.get(node.entity.type) if node.entity is not None else None
        return status_painter(
            code,
            field,
            self._plan.statuses,
            self.site_url,
            self.view.viewport().update,
        )

    def _picture(self, node: TreeNode) -> QtGui.QPixmap | None:
        if self._thumbnail is False:
            return None
        url = node.values.get(str(self._thumbnail))
        if not isinstance(url, str) or not url:
            return None
        held = self._pixmaps.get(url)
        if held is not None:
            return held
        if url in self._asked:
            return None
        self._asked.add(url)
        side = THUMB_SIZE[TREE_THUMB[self._size]]
        self._loader.load(url, lambda pixmap: self._landed(url, pixmap), QSize(side * 2, side * 2))
        return None

    def _landed(self, url: str, pixmap: QtGui.QPixmap | None) -> None:
        # A picture can land after the tree that asked for it has gone; a deleted wrapper
        # raises, and the answer is dropped.
        if pixmap is not None and not pixmap.isNull():
            self._pixmaps[url] = pixmap
        try:
            self.view.viewport().update()
        except RuntimeError:
            return

    # --- interaction ----------------------------------------------------------------------

    def on_row_pressed(self, index: QModelIndex, point: QtCore.QPoint, whole_branch: bool) -> None:
        """The chevron opens a level, the box takes the node, anything else activates the row."""
        row = self.row_at(index)
        if row is None:
            return
        rect = self.view.visualRect(index)
        path = row.node.path
        if row.node.has_children and self._delegate.chevron_rect(rect).contains(point):
            self.engine.focus(path)
            if whole_branch:
                self.binding.run("expand_all", path, self._expand_depth)
            else:
                self.binding.run("toggle", path)
            return
        if self._checkable and self._delegate.checkbox_rect(rect).contains(point):
            self.engine.focus(path)
            self.engine.toggle_checked(path)
            return
        self.activate(row)

    def activate(self, row: TreeRow) -> None:
        """A branch opens; a leaf is selected and reported."""
        self.engine.focus(row.node.path)
        if row.node.has_children:
            self.binding.run("toggle", row.node.path)
            return
        self.engine.select(row.node.path)
        self.selected.emit(row.node)

    def on_key(self, event: QtGui.QKeyEvent) -> bool:
        """The whole keyboard model is core's `key_down`; only the names are translated."""
        name = _KEYS.get(int(event.key()))
        if name is None:
            text = event.text()
            if not text or not text.isprintable():
                return False
            name = text
        modifiers = event.modifiers()
        before = self.snapshot().cursor
        handled = self.engine.key_down(
            TreeKey(
                key=name,
                ctrl_key=bool(modifiers & Qt.KeyboardModifier.ControlModifier),
                meta_key=bool(modifiers & Qt.KeyboardModifier.MetaModifier),
                shift_key=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
                alt_key=bool(modifiers & Qt.KeyboardModifier.AltModifier),
            )
        )
        if not handled:
            return False
        if name == "Enter" and before is not None:
            node = self.engine.node(before)
            if node is not None and not node.has_children:
                self.selected.emit(node)
        self._sync()
        return True

    def _on_query(self, text: str) -> None:
        """A pause before the query is asked for; an empty one clears at once."""
        if not text.strip():
            self._debounce.cancel()
            self.binding.run("search", "")
            return
        self._debounce.call(lambda: self.binding.run("search", text))

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self._search.hasFocus() and self._search.text():
            self._search.clear()
            return
        super().keyPressEvent(event)

    # --- drawing --------------------------------------------------------------------------

    def _restart(self) -> None:
        """Rebuild the engine: what a level is read under has moved."""
        self.binding.close()
        self.binding = _TreeBinding(self._build_engine(), self)
        self.binding.changed.connect(self._sync)
        self.binding.failed.connect(self.error.emit)
        self.binding.run("load")
        self._rebuild_delegate()

    def _rebuild_delegate(self) -> None:
        self._delegate = _TreeDelegate(self)
        self.view.setItemDelegate(self._delegate)
        self.view.viewport().update()

    def _read_plan(self, state: TreeState) -> None:
        """The status field and the secondary field of every type on show, read once per set."""
        types = sorted({row.node.entity.type for row in state.rows if row.node.entity is not None})
        key = ",".join(types)
        if key == self._types:
            return
        self._types = key
        path = path_of(self._secondary_field)
        self.binding.pool.submit(
            resolve_tree_fields,
            self._context.schema,
            self._context.statuses,
            types,
            path or None,
            on_result=self._plan_read,
            on_error=self.error.emit,
        )

    def _plan_read(self, plan: TreeFieldPlan) -> None:
        self._plan = plan
        self.view.viewport().update()

    def _sync(self) -> None:
        state = self.snapshot()
        self.model.set_rows(state.rows)
        self.view.expandAll()
        self._read_plan(state)
        loading = state.status in ("idle", "loading")
        searching = state.search.strip()
        no_match = bool(searching) and not state.searching and len(state.matches) == 0
        empty = not loading and len(state.rows) == 0
        failed = state.status == "error"
        self._skeleton.setVisible(loading)
        self.view.setVisible(not loading and not failed and not empty and not no_match)
        self._state.setVisible(failed or empty or no_match)
        if failed:
            self._state.set_icon(ERROR_ICON)
            self._state.apply_state(
                "error", self._labels, None if state.error is None else str(state.error)
            )
        elif no_match:
            self._state.set_slot_name("entity-tree-no-match")
            self._state.set_icon(NO_MATCH_ICON)
            self._state.set_state("empty")
            self._state.set_label(self._no_match_label)
        elif empty:
            self._state.set_slot_name("entity-tree-state")
            self._state.set_icon(EMPTY_ICON)
            self._state.apply_state("empty", self._labels)
        self._skeleton.setAccessibleName(state_line("loading", self._labels))
        if not same_ids(state.expanded, self._expanded_seen):
            self._expanded_seen = list(state.expanded)
            self.expanded_changed.emit(list(state.expanded))
        if not same_ids(state.selected, self._selected_seen):
            self._selected_seen = list(state.selected)
            self.selection_changed.emit(list(state.selected))
        if not same_ids(state.checked, self._checked_seen):
            self._checked_seen = list(state.checked)
            self.checked_changed.emit(self.engine.checked_refs())
        cursor = state.cursor
        if cursor:
            index = self.model.index_of(cursor)
            if index.isValid():
                self.view.setCurrentIndex(index)
                self.view.scrollTo(index, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)
        self._fit()
        self.view.viewport().update()

    def _fit(self) -> None:
        rows = len(self.snapshot().rows)
        fit_body(self.view, rows * max(1, self.view.sizeHintForRow(0)) + ROW_PAD_Y, self._max_height)

    def checked_refs(self) -> list[EntityRef]:
        """The rows whose boxes are fully checked."""
        return self.engine.checked_refs()


class _TreeSkeleton(QtWidgets.QWidget):
    """Rows a first read stands behind: the same inset, the same height, the same zero gap."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-tree-loading")
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(ROW_PAD_X, ROW_PAD_Y, ROW_PAD_X, ROW_PAD_Y)
        column.setSpacing(0)
        for _ in range(SKELETON_ROWS):
            column.addWidget(Skeleton(height=SKELETON_HEIGHT, parent=self))


def _height(value: int | str) -> int:
    """A height as pixels. A `rem` string is the upstream prop, at 16px to the rem."""
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        if text.endswith("rem"):
            return int(round(float(text[:-3]) * 16))
        if text.endswith("px"):
            return int(round(float(text[:-2])))
        return int(round(float(text)))
    except ValueError:
        return DEFAULT_MAX_HEIGHT


#: The control ladder the search input stands on, kept so a caller can match a button to it.
TREE_CONTROL_HEIGHT = CONTROL_HEIGHT
#: The glyph step a row's leading slot takes, kept beside the ladder above.
TREE_LEAD_GLYPH = LEAD_GLYPH
