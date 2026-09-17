"""Tree model.

The headless half of the tree widgets: nodes keyed by their path, one level read at a
time behind a loader, expand and collapse with a loading flag per node, tri-state
checkboxes that propagate both ways, single or multiple selection, a focus cursor
carrying the whole keyboard model, and a search that opens the tree onto its hits. There
is no Qt in it: a widget subscribes and redraws, and never reimplements propagation, the
cursor or type-ahead.

`hierarchy_expand` answers one level: the node itself, and children carrying a label, a
ref and `has_children`, so walking a project is one call per node
(post_hierarchy_expand). Which levels a project has is the site's own navigation
configuration and not a fixed hierarchy, the probed site's Shot path runs through the
field name `sg_sequence` (post_hierarchy_search), so a seed path is followed by taking
whichever child is a prefix of it rather than by parsing the path.

Searching is two endpoints, because neither does it alone: `text_search` matches the
words and `hierarchy_search` says where each hit sits, so the tree opens along every
answered path and marks the rows the words found (post_entity_text_search,
post_hierarchy_search).

Every call here is synchronous. `sg_widgets_qt.workers` runs `load`, `expand`,
`expand_all`, `expand_to_path` and `search` on a thread and calls back on the GUI
thread. A search holds a ticket, so the answer of a search the next one replaced is
dropped rather than written over it.
"""
from __future__ import annotations

import re
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Callable, Literal

from .client import HierarchyNode, HierarchyRef, SearchOptions, SgClient, hierarchy_entity
from .filter import EntityRef, WireCondition
from .schema import FieldSchema, status_field_for
from .schema_service import SchemaService
from .search import FieldLookup, matches_every_word, request_gate, scope_to_project
from .status import StatusRecord
from .status_service import StatusService

__all__ = [
    "TREE_CHECK_STATES",
    "TREE_SELECTION_MODES",
    "TREE_STATUSES",
    "TREE_STATUS_FIELDS",
    "HierarchyLoaderOptions",
    "HierarchySearcherOptions",
    "TreeCheckState",
    "TreeEngine",
    "TreeFieldPlan",
    "TreeKey",
    "TreeLevel",
    "TreeLoader",
    "TreeNode",
    "TreeOptions",
    "TreeRow",
    "TreeSearchHit",
    "TreeSearcher",
    "TreeSelectionMode",
    "TreeSourceNode",
    "TreeState",
    "TreeStatus",
    "create_tree",
    "hierarchy_loader",
    "hierarchy_searcher",
    "resolve_tree_fields",
]


# -------------------------------------------------------------------------- #
# nodes                                                                       #
# -------------------------------------------------------------------------- #


@dataclass
class TreeSourceNode:
    """One node of a level, as a loader hands it over."""

    #: The key everything else is held under, and what the loader is called with.
    path: str
    label: str
    ref: HierarchyRef
    #: False when opening this node would return nothing.
    has_children: bool = False
    #: Fields of the row the node stands for, flattened.
    values: dict[str, Any] | None = None


@dataclass
class TreeLevel:
    """One level: the node that was opened, and the level below it."""

    node: TreeSourceNode
    children: list[TreeSourceNode] = dc_field(default_factory=list)


TreeLoader = Callable[[str], TreeLevel]
"""Reads one level. A node already read is never read again."""


@dataclass
class TreeNode:
    """A node in the tree, with where it sits."""

    path: str
    label: str
    ref: HierarchyRef
    #: The row the node stands for, or None where it stands for a type or nothing.
    entity: EntityRef | None = None
    has_children: bool = False
    parent_path: str | None = None
    #: Depth below the root, which is 0.
    level: int = 0
    #: Fields of the row the node stands for, flattened. Empty until a loader fills it.
    values: dict[str, Any] = dc_field(default_factory=dict)


TreeCheckState = Literal["checked", "mixed", "unchecked"]
TREE_CHECK_STATES: tuple[TreeCheckState, ...] = ("checked", "mixed", "unchecked")

TreeSelectionMode = Literal["none", "single", "multiple"]
TREE_SELECTION_MODES: tuple[TreeSelectionMode, ...] = ("none", "single", "multiple")

TreeStatus = Literal["idle", "loading", "ready", "error"]
TREE_STATUSES: tuple[TreeStatus, ...] = ("idle", "loading", "ready", "error")


@dataclass
class TreeRow:
    """One line of the visible list, with everything a row draws itself from."""

    node: TreeNode
    expanded: bool = False
    #: True while this node's level is being read.
    loading: bool = False
    checked: TreeCheckState = "unchecked"
    selected: bool = False
    #: True on the one node that owns the tab stop.
    focused: bool = False
    #: True when the caller disabled the node: the cursor skips it and it never selects.
    disabled: bool = False
    #: True when the search placed this row, or its label holds every word.
    match: bool = False


@dataclass
class TreeState:
    """Everything a view renders. A new object on every change, so identity is the signal."""

    rows: list[TreeRow] = dc_field(default_factory=list)
    status: TreeStatus = "idle"
    error: Exception | None = None
    #: Path of the focus cursor, or None before the root is read.
    cursor: str | None = None
    #: The text the tree is searching for.
    search: str = ""
    #: True while a search is in flight.
    searching: bool = False
    #: Paths of the rows the search marked, in visible order.
    matches: list[str] = dc_field(default_factory=list)
    #: Paths whose box is fully checked, branches included.
    checked: list[str] = dc_field(default_factory=list)
    selected: list[str] = dc_field(default_factory=list)
    #: Paths that are open, in visible order.
    expanded: list[str] = dc_field(default_factory=list)


@dataclass
class TreeKey:
    """A keyboard event, reduced to what the model reads."""

    key: str
    ctrl_key: bool = False
    meta_key: bool = False
    shift_key: bool = False
    alt_key: bool = False


@dataclass
class TreeSearchHit:
    """One row a search found, and where the tree puts it."""

    ref: EntityRef
    label: str
    #: One path per level, root first; the last entry is the row itself.
    incremental_path: list[str] = dc_field(default_factory=list)


TreeSearcher = Callable[[str, Sequence[str]], list[TreeSearchHit]]
"""Matches words and answers where each hit sits."""


@dataclass
class TreeOptions:
    loader: TreeLoader
    #: Where the tree starts, `/Project/<id>` against the hierarchy loader.
    root_path: str = ""
    selection: TreeSelectionMode | None = None
    #: Places rows by text. Without one, a search marks the labels already loaded.
    searcher: TreeSearcher | None = None
    #: Types a search covers. Default: the types the levels already read stand for.
    search_types: Sequence[str] | None = None
    #: How many levels `expand_all` opens under a node. Default 3.
    expand_depth: int | None = None
    #: True for a node the cursor skips and selection refuses.
    disabled: Callable[[TreeNode], bool] | None = None
    #: How long a type-ahead buffer survives, in milliseconds. Default 800.
    type_ahead_ms: int | None = None
    #: The clock type-ahead measures on, in milliseconds.
    now: Callable[[], float] | None = None


#: How deep `expand_to_path` walks before it gives up.
MAX_SEED_DEPTH = 16
#: Hits one search places. `_text_search` answers at most 25 rows a page (probe 053).
MAX_SEARCH_HITS = 25
#: Levels one `expand_all` reads, whatever its depth.
MAX_EXPAND_READS = 64

_BUCKET = re.compile(r"/[A-Z][A-Za-z0-9]*/__none__(?=/|$)")
_REPEATED = re.compile(r"(.)\1*", re.DOTALL)


def _canonical_path(path: str) -> str:
    """A path in the one spelling both endpoints can be compared in.

    `_expand` writes the ungrouped bucket `<field>/<GroupType>/__none__` and `_search`
    writes `<field>/__none__`, and both answer the same rows (064_hierarchy_expand_buckets).
    A group type is capitalised where a field name is not, which is the same rule
    `path_refs` reads a path by.
    """
    return _BUCKET.sub("/__none__", path)


def _is_under(path: str, target: str) -> bool:
    """True when `target` is the path itself or sits under it, in either spelling."""
    here = _canonical_path(path)
    there = _canonical_path(target)
    return there == here or there.startswith(f"{here}/")


def _as_error(value: Any) -> Exception:
    return value if isinstance(value, Exception) else Exception(str(value))


def _from_hierarchy(raw: HierarchyNode) -> TreeSourceNode:
    """One node of `hierarchy_expand`, as the engine holds it."""
    return TreeSourceNode(path=raw.path, label=raw.label, ref=raw.ref, has_children=raw.has_children)


_MISSING = object()


class _Ordered:
    """A set that keeps insertion order, which is what the upstream `Set` gives."""

    __slots__ = ("_items",)

    def __init__(self, items: Iterable[str] = ()) -> None:
        self._items: dict[str, None] = dict.fromkeys(items)

    def add(self, value: str) -> None:
        self._items[value] = None

    def discard(self, value: str) -> bool:
        """True when the value was there, as `Set.delete` answers."""
        return self._items.pop(value, _MISSING) is not _MISSING

    def clear(self) -> None:
        self._items.clear()

    def __contains__(self, value: object) -> bool:
        return value in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


def _index_of(paths: Sequence[str], value: str | None) -> int:
    try:
        return paths.index(value)  # type: ignore[arg-type]
    except ValueError:
        return -1


def _now_ms() -> float:
    return time.monotonic() * 1000.0


class TreeEngine:
    """The entity tree over a hierarchy loader: nodes, expansion, the cursor and the search."""

    def __init__(self, options: TreeOptions) -> None:
        self._options = options
        self.root_path = options.root_path
        self._loader = options.loader
        self._selection_mode: TreeSelectionMode = options.selection if options.selection is not None else "single"
        self._type_ahead_ms = options.type_ahead_ms if options.type_ahead_ms is not None else 800
        self._now = options.now if options.now is not None else _now_ms

        self._nodes: dict[str, TreeNode] = {}
        self._levels: dict[str, list[str]] = {}
        self._expanded = _Ordered()
        self._loading = _Ordered()
        #: Nodes an `expand_all` is walking under, which read as busy while it runs.
        self._walking = _Ordered()
        self._checked = _Ordered()
        self._selected = _Ordered()
        self._matches = _Ordered()
        self._listeners: list[Callable[[], None]] = []

        self._status: TreeStatus = "idle"
        self._error: Exception | None = None
        self._cursor: str | None = None
        self._search_text = ""
        self._searching = False
        #: The expansion a search opened onto, restored when the text is cleared.
        self._before_search: _Ordered | None = None
        self._gate = request_gate()
        self._typed = ""
        self._typed_at = 0.0
        self._state = self._build()

    # the visible list ------------------------------------------------------ #

    def _emit(self) -> None:
        self._state = self._build()
        for listener in list(self._listeners):
            listener()

    def _build(self) -> TreeState:
        rows: list[TreeRow] = []
        marked: list[str] = []
        open_paths: list[str] = []

        def walk(path: str) -> None:
            node = self._nodes.get(path)
            if node is None:
                return
            match = path in self._matches
            if match:
                marked.append(path)
            if path in self._expanded:
                open_paths.append(path)
            rows.append(TreeRow(
                node=node,
                expanded=path in self._expanded,
                loading=path in self._loading or path in self._walking,
                checked=self.check_state_of(path),
                selected=path in self._selected,
                focused=self._cursor == path,
                disabled=self._is_disabled(path),
                match=match,
            ))
            if path in self._expanded:
                for child in self._levels.get(path, []):
                    walk(child)

        walk(self.root_path)
        return TreeState(
            rows=rows,
            status=self._status,
            error=self._error,
            cursor=self._cursor,
            search=self._search_text,
            searching=self._searching,
            matches=marked,
            checked=list(self._checked),
            selected=list(self._selected),
            expanded=open_paths,
        )

    def _is_disabled(self, path: str) -> bool:
        """True when the caller disabled the node the path stands for."""
        node = self._nodes.get(path)
        return node is not None and self._options.disabled is not None and self._options.disabled(node) is True

    def _visible_paths(self) -> list[str]:
        return [row.node.path for row in self._state.rows]

    # reading --------------------------------------------------------------- #

    def _ingest(self, level: TreeLevel) -> TreeNode:
        # The node was placed by the level above, so its depth and its parent are already known.
        placed = self._nodes.get(level.node.path)
        depth = placed.level if placed is not None else 0
        values = level.node.values
        if values is None:
            values = placed.values if placed is not None else {}
        own = TreeNode(
            path=level.node.path,
            label=level.node.label,
            ref=level.node.ref,
            entity=hierarchy_entity(level.node.ref),
            has_children=level.node.has_children,
            parent_path=placed.parent_path if placed is not None else None,
            level=depth,
            values=values,
        )
        self._nodes[own.path] = own
        paths: list[str] = []
        for child in level.children:
            # A placeholder child carries no path of its own and stands for an empty level
            # (post_hierarchy_expand); keeping it would key it over its own parent.
            if child.path == own.path:
                continue
            paths.append(child.path)
            self._nodes[child.path] = TreeNode(
                path=child.path,
                label=child.label,
                ref=child.ref,
                entity=hierarchy_entity(child.ref),
                has_children=child.has_children,
                parent_path=own.path,
                level=depth + 1,
                values=child.values if child.values is not None else {},
            )
            # A level read under a checked branch arrives checked, so a box ticked before
            # its children existed still means what it said.
            if own.path in self._checked:
                self._checked.add(child.path)
        self._levels[own.path] = paths
        return own

    def _read(self, path: str) -> TreeNode | None:
        self._loading.add(path)
        self._emit()
        try:
            level = self._loader(path)
        except Exception as thrown:
            self._error = _as_error(thrown)
            if path == self.root_path:
                self._status = "error"
            return None
        else:
            node = self._ingest(level)
            self._error = None
            return node
        finally:
            self._loading.discard(path)
            self._emit()

    def _root(self) -> TreeNode | None:
        """The root, read if it has not been."""
        known = self._nodes.get(self.root_path)
        if known is not None:
            return known
        self._status = "loading"
        self._emit()
        node = self._read(self.root_path)
        if node is not None:
            self._status = "ready"
            if self._cursor is None:
                self._cursor = self.root_path
            self._expanded.add(self.root_path)
            self._emit()
        return node

    # checkboxes ------------------------------------------------------------ #

    def check_state_of(self, path: str) -> TreeCheckState:
        if path in self._checked:
            return "checked"
        stack = list(self._levels.get(path, []))
        while stack:
            next_path = stack.pop()
            if next_path in self._checked:
                return "mixed"
            stack.extend(self._levels.get(next_path, []))
        return "unchecked"

    def _spread(self, path: str, on: bool) -> None:
        if on:
            self._checked.add(path)
        else:
            self._checked.discard(path)
        for child in self._levels.get(path, []):
            self._spread(child, on)

    def _settle_ancestors(self, path: str) -> None:
        """A parent is checked when every child it has read is, and drops out otherwise."""
        node = self._nodes.get(path)
        up = node.parent_path if node is not None else None
        while up is not None:
            children = self._levels.get(up, [])
            if len(children) > 0 and all(child in self._checked for child in children):
                self._checked.add(up)
            else:
                self._checked.discard(up)
            parent = self._nodes.get(up)
            up = parent.parent_path if parent is not None else None

    # the cursor ------------------------------------------------------------ #

    def _move_to(self, index: int) -> None:
        """The cursor lands on an enabled row or stays put, so a disabled node is never focused."""
        paths = self._visible_paths()
        if len(paths) == 0:
            return
        clamped = max(0, min(index, len(paths) - 1))
        step = 1 if clamped >= _index_of(paths, self._cursor) else -1
        at = clamped
        while 0 <= at < len(paths) and self._is_disabled(paths[at]):
            at += step
        if at < 0 or at >= len(paths):
            return
        next_path = paths[at]
        if next_path == self._cursor:
            return
        self._cursor = next_path
        self._emit()

    def _move_by(self, step: int) -> None:
        """Move one enabled row up or down."""
        paths = self._visible_paths()
        at = _index_of(paths, self._cursor)
        next_at = at + step
        while 0 <= next_at < len(paths):
            path = paths[next_at]
            if not self._is_disabled(path):
                self._cursor = path
                self._emit()
                return
            next_at += step

    def _type_ahead(self, char: str) -> bool:
        """The next visible node whose label starts with the buffer, wrapping past the cursor."""
        at = self._now()
        self._typed = char if at - self._typed_at > self._type_ahead_ms else self._typed + char
        self._typed_at = at
        # One letter pressed again walks the matches for that letter; a longer buffer may
        # still match where the cursor stands.
        repeated = _REPEATED.fullmatch(self._typed) is not None
        needle = (char if repeated else self._typed).lower()
        paths = self._visible_paths()
        if len(paths) == 0:
            return False
        start = max(0, _index_of(paths, self._cursor))
        offset = 1 if repeated else 0
        for step in range(len(paths)):
            path = paths[(start + offset + step) % len(paths)]
            if self._is_disabled(path):
                continue
            node = self._nodes.get(path)
            if node is not None and node.label.lower().startswith(needle):
                self._cursor = path
                self._emit()
                return True
        return False

    # searching -------------------------------------------------------------- #

    def _walk_to(self, target: str, done: _Ordered) -> TreeNode | None:
        """Open every level down to a path and answer the node it landed on.

        `done` carries the paths already opened, so hits sharing a branch open it once.
        """
        here = self._root()
        if here is None:
            return None
        for _ in range(MAX_SEED_DEPTH):
            if _canonical_path(here.path) == _canonical_path(target):
                break
            if here.path not in done:
                done.add(here.path)
                self.expand(here.path)
            next_path = next((p for p in self._levels.get(here.path, []) if _is_under(p, target)), None)
            if next_path is None:
                break
            node = self._nodes.get(next_path)
            if node is None:
                break
            here = node
        return here

    def _search_types(self) -> list[str]:
        """The types the levels already read stand for, which is what a search covers."""
        if self._options.search_types is not None:
            return list(self._options.search_types)
        types = _Ordered()
        for node in list(self._nodes.values()):
            entity = hierarchy_entity(node.ref)
            if entity is not None:
                types.add(entity.type)
            elif node.ref.kind == "entity_type" and isinstance(node.ref.value, str):
                types.add(node.ref.value)
        # The root is the project itself, and a project is never a row under it.
        types.discard("Project")
        return list(types)

    def _mark_loaded(self, text: str) -> None:
        """Loaded nodes whose label holds every word, which the server never answers for a folder."""
        for node in list(self._nodes.values()):
            if matches_every_word(node.label, text):
                self._matches.add(node.path)

    # the engine ------------------------------------------------------------ #

    def snapshot(self) -> TreeState:
        return self._state

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def node(self, path: str) -> TreeNode | None:
        """A node already loaded, by path."""
        return self._nodes.get(path)

    def child_paths(self, path: str) -> list[str]:
        """The paths of a node's level, once it has been read."""
        return list(self._levels.get(path, []))

    def load(self) -> None:
        """Read the root and open it."""
        self._root()

    def expand(self, path: str) -> None:
        node = self._nodes.get(path)
        if node is None or not node.has_children:
            return
        self._expanded.add(path)
        self._emit()
        # `children` names the next paths (post_hierarchy_expand), so a level already
        # read is never read again.
        if path not in self._levels:
            self._read(path)

    def collapse(self, path: str) -> None:
        if not self._expanded.discard(path):
            return
        self._emit()

    def toggle(self, path: str) -> None:
        if path in self._expanded:
            self.collapse(path)
        else:
            self.expand(path)

    def expand_to_path(self, refs: str | Sequence[str]) -> None:
        """Open every level down to a path, or to the deepest entry of an incremental path."""
        if isinstance(refs, str):
            target = refs
        else:
            target = refs[-1] if len(refs) > 0 else ""
        if len(target) == 0:
            return
        here = self._walk_to(target, _Ordered())
        if here is None:
            return
        self._cursor = here.path
        self._emit()

    def expand_all(self, path: str, depth: int | None = None) -> None:
        """Open every level under a node, breadth first, down to `depth`."""
        if depth is None:
            depth = self._options.expand_depth if self._options.expand_depth is not None else 3
        start = self._nodes.get(path)
        if start is None or not start.has_children:
            return
        self._walking.add(path)
        self._emit()
        try:
            frontier = [path]
            budget = MAX_EXPAND_READS
            level = 0
            while level < depth and len(frontier) > 0 and budget > 0:
                reads: list[str] = []
                for here in frontier:
                    node = self._nodes.get(here)
                    if node is None or not node.has_children:
                        continue
                    self._expanded.add(here)
                    if here in self._levels or budget == 0:
                        continue
                    budget -= 1
                    reads.append(here)
                for here in reads:
                    self._read(here)
                frontier = [child for here in frontier for child in self._levels.get(here, [])]
                level += 1
        finally:
            self._walking.discard(path)
            self._emit()

    def focus(self, path: str) -> None:
        """Move the focus cursor. A path outside the visible list is ignored."""
        if path not in self._nodes or self._cursor == path or self._is_disabled(path):
            return
        self._cursor = path
        self._emit()

    def set_expanded(self, paths: Sequence[str]) -> None:
        """Open exactly these paths, reading whatever level is not loaded, and shut the rest."""
        wanted = _Ordered(paths)
        # The root holds the list together: shutting it would empty the tree.
        wanted.add(self.root_path)
        for path in list(self._expanded):
            if path not in wanted:
                self._expanded.discard(path)
        self._emit()
        # Shallowest first: a deeper path is only a node once the level above it has been
        # read, so opening in order is what makes a whole branch reachable in one call.
        order = sorted(wanted, key=lambda path: len(path.split("/")))
        for path in order:
            if path in self._nodes:
                self.expand(path)

    def set_selected(self, paths: Sequence[str]) -> None:
        """Select exactly these paths. A path outside the tree is dropped."""
        wanted = [path for path in paths if path in self._nodes and not self._is_disabled(path)]
        only = wanted if self._selection_mode == "multiple" else wanted[:1]
        if self._selection_mode == "none":
            return
        self._selected.clear()
        for path in only:
            self._selected.add(path)
        self._emit()

    def set_checked(self, path: str, on: bool) -> None:
        if path not in self._nodes or self._is_disabled(path):
            return
        self._spread(path, on)
        self._settle_ancestors(path)
        self._emit()

    def toggle_checked(self, path: str) -> None:
        self.set_checked(path, self.check_state_of(path) != "checked")

    def checked_refs(self) -> list[EntityRef]:
        """The rows the checked nodes stand for, in visible order."""
        refs: list[EntityRef] = []

        def walk(path: str) -> None:
            node = self._nodes.get(path)
            if node is None:
                return
            if path in self._checked and node.entity is not None:
                refs.append(node.entity)
            for child in self._levels.get(path, []):
                walk(child)

        walk(self.root_path)
        return refs

    def select(self, path: str, additive: bool = False) -> None:
        """Select a node. `additive` adds to the selection, and is ignored outside `multiple`."""
        if self._selection_mode == "none" or path not in self._nodes or self._is_disabled(path):
            return
        if self._selection_mode == "multiple" and additive:
            if not self._selected.discard(path):
                self._selected.add(path)
        else:
            self._selected.clear()
            self._selected.add(path)
        self._cursor = path
        self._emit()

    def clear_selection(self) -> None:
        if len(self._selected) == 0:
            return
        self._selected.clear()
        self._emit()

    def search(self, text: str) -> None:
        """Place every row the words match, open the tree onto them and mark them.

        An empty text drops the marks and restores the expansion the search opened onto.
        The ticket taken here is what makes a search cancel the one before it: run on a
        worker thread, an answer whose ticket no longer holds is dropped.
        """
        ticket = self._gate.next()
        self._search_text = text
        self._matches.clear()
        if len(text.strip()) == 0:
            self._searching = False
            if self._before_search is not None:
                self._expanded.clear()
                for path in self._before_search:
                    self._expanded.add(path)
                self._before_search = None
            self._emit()
            return
        if self._options.searcher is None:
            self._mark_loaded(text)
            self._emit()
            return
        self._searching = True
        self._emit()
        try:
            hits = self._options.searcher(text, self._search_types())
        except Exception as thrown:
            if not self._gate.holds(ticket):
                return
            self._error = _as_error(thrown)
            self._searching = False
            self._emit()
            return
        if not self._gate.holds(ticket):
            return
        if self._before_search is None:
            self._before_search = _Ordered(self._expanded)
        done = _Ordered()
        placed: list[str] = []
        for hit in hits[:MAX_SEARCH_HITS]:
            target = hit.incremental_path[-1] if len(hit.incremental_path) > 0 else ""
            landed = self._walk_to(target, done)
            if not self._gate.holds(ticket):
                return
            if (
                landed is not None
                and landed.entity is not None
                and landed.entity.type == hit.ref.type
                and landed.entity.id == hit.ref.id
            ):
                placed.append(landed.path)
        for path in placed:
            self._matches.add(path)
        # A folder is not a row, so the server never returns one; its label matches all the same.
        self._mark_loaded(text)
        if len(placed) > 0:
            self._cursor = placed[0]
        self._searching = False
        self._emit()

    def key_down(self, event: TreeKey) -> bool:
        """True when the tree handled the key, which is when the caller stops it."""
        paths = self._visible_paths()
        index = _index_of(paths, self._cursor)
        path = paths[index] if index >= 0 else None
        node = None if path is None else self._nodes.get(path)
        key = event.key
        if key == "ArrowDown":
            self._move_by(1)
            return True
        if key == "ArrowUp":
            self._move_by(-1)
            return True
        if key == "ArrowRight":
            if node is None:
                return False
            if node.has_children and node.path not in self._expanded:
                self.expand(node.path)
            elif node.path in self._expanded and len(self._levels.get(node.path, [])) > 0:
                self._move_to(index + 1)
            return True
        if key == "ArrowLeft":
            if node is None:
                return False
            if node.path in self._expanded:
                self.collapse(node.path)
            elif node.parent_path is not None:
                self.focus(node.parent_path)
            return True
        if key == "Home":
            self._move_to(0)
            return True
        if key == "End":
            self._move_to(len(paths) - 1)
            return True
        if key == " ":
            if node is None:
                return False
            self.toggle_checked(node.path)
            return True
        if key == "Enter":
            if node is None:
                return False
            self.select(node.path, additive=event.ctrl_key or event.meta_key)
            return True
        if key == "*":
            # The ARIA tree pattern opens every branch at the focus level, not just this one.
            if node is None:
                return False
            if node.parent_path is None:
                level = [node.path]
            else:
                level = self._levels.get(node.parent_path, [node.path])
            for each in list(level):
                self.expand_all(each)
            return True
        if len(key) != 1 or event.ctrl_key or event.meta_key or event.alt_key:
            return False
        return self._type_ahead(key)


def create_tree(options: TreeOptions) -> TreeEngine:
    return TreeEngine(options)


# -------------------------------------------------------------------------- #
# the hierarchy adapter                                                       #
# -------------------------------------------------------------------------- #


@dataclass
class HierarchyLoaderOptions:
    #: Field paths read for the rows the nodes of a level stand for.
    fields: Sequence[str] | None = None


def hierarchy_loader(client: SgClient, options: HierarchyLoaderOptions | None = None) -> TreeLoader:
    """`hierarchy_expand` as a tree loader.

    With `fields`, the rows a level's nodes stand for are read once per type over the ids
    just returned, so a sub-label or a status comes back with the level rather than one
    read per row. A name a type does not have is dropped at 200, so one list of names
    serves every type (probe 003).
    """
    settings = options if options is not None else HierarchyLoaderOptions()
    wanted = list(dict.fromkeys(["id", *(settings.fields or [])]))

    def load(path: str) -> TreeLevel:
        answer = client.hierarchy_expand(path)
        children = _ungrouped(client, answer)
        if children is None:
            children = answer.children
        level = TreeLevel(
            node=_from_hierarchy(answer),
            children=[_from_hierarchy(child) for child in children],
        )
        if len(wanted) > 1:
            _read_values(client, [level.node, *level.children], wanted)
        return level

    return load


#: The segment sent to make the endpoint name the grouping field it expects.
_FIELD_PROBE = "__field__"
#: `Unexpected field name in path: nope (expecting sg_sequence)` (post_hierarchy_expand).
_EXPECTING = re.compile(r"expecting\s+([A-Za-z0-9_]+)")


def _ungrouped(client: SgClient, answer: HierarchyNode) -> list[HierarchyNode] | None:
    """The rows a grouped level hides, or None when there are none to find.

    A grouping field with no rows hides every row under it: the level answers one `empty`
    child and no bucket, although the `__none__` path under it answers all of them
    (064_hierarchy_expand_buckets). The field that path runs through is whatever the
    site's navigation groups by, and the 400 the endpoint answers a bogus segment names
    it (post_hierarchy_expand). The bucket is asked for in `_search`'s spelling,
    `<field>/__none__`, which needs no group type and answers the same rows.
    """
    only = answer.children[0] if len(answer.children) == 1 else None
    if only is None or only.ref.kind != "empty":
        return None
    # Grouping sits directly under the type folder, and a bucket never groups again.
    if answer.ref.kind != "entity_type" or "__none__" in answer.path:
        return None
    field: str | None = None
    try:
        client.hierarchy_expand(f"{answer.path}/{_FIELD_PROBE}")
    except Exception as thrown:
        found = _EXPECTING.search(str(_as_error(thrown)))
        field = found.group(1) if found else None
    if field is None:
        return None
    try:
        bucket = client.hierarchy_expand(f"{answer.path}/{field}/__none__")
    except Exception:
        return None
    rows = [child for child in bucket.children if child.ref.kind != "empty"]
    return rows if len(rows) > 0 else None


# -------------------------------------------------------------------------- #
# the search adapter                                                          #
# -------------------------------------------------------------------------- #


@dataclass
class HierarchySearcherOptions:
    #: Answers whether a type carries `project`, so the words are scoped to it.
    schema: FieldLookup | None = None
    #: Rows the text search asks for. Each one costs a path lookup. Default 10.
    limit: int | None = None


_ROOT_PROJECT = re.compile(r"^/Project/(\d+)")


def hierarchy_searcher(
    client: SgClient,
    root_path: str,
    options: HierarchySearcherOptions | None = None,
) -> TreeSearcher:
    """`text_search` and `hierarchy_search` chained, as a tree searcher.

    The hierarchy endpoint takes an entity and answers where it sits rather than matching
    words, so the words go to `text_search` first and each hit is then asked for its path
    (post_hierarchy_search). A root path naming a project scopes the words to it, on every
    type that carries a `project` field.
    """
    settings = options if options is not None else HierarchySearcherOptions()
    limit = settings.limit if settings.limit is not None else 10
    found_root = _ROOT_PROJECT.match(root_path)
    project_id = found_root.group(1) if found_root else None

    def search(text: str, entity_types: Sequence[str]) -> list[TreeSearchHit]:
        if len(entity_types) == 0:
            return []
        types: dict[str, list[WireCondition] | None] = {entity_type: None for entity_type in entity_types}
        if project_id is not None and settings.schema is not None:
            types = dict(scope_to_project(settings.schema, types, int(project_id)))
        found = client.text_search(text, types, {"size": limit, "number": 1})
        hits: list[TreeSearchHit] = []
        for row in found:
            try:
                answers = client.hierarchy_search(root_path, EntityRef(type=row.type, id=row.id))
            except Exception:
                # A row the tree has no place for under this root is not a hit.
                continue
            if len(answers) == 0:
                continue
            path = answers[0]
            hits.append(TreeSearchHit(ref=path.ref, label=path.label, incremental_path=list(path.incremental_path)))
        return hits

    return search


def _read_values(client: SgClient, level: Sequence[TreeSourceNode], fields: list[str]) -> None:
    """One read per type over the level, flattened onto the nodes that asked for it."""
    by_type: dict[str, list[int]] = {}
    for node in level:
        entity = hierarchy_entity(node.ref)
        if entity is None:
            continue
        by_type.setdefault(entity.type, []).append(entity.id)
    if len(by_type) == 0:
        return
    rows: dict[str, dict[str, Any]] = {}
    for entity_type, ids in by_type.items():
        filters = {"logical_operator": "and", "conditions": [["id", "in", ids]]}
        result = client.search(
            entity_type,
            SearchOptions(filters=filters, fields=list(fields), page={"size": len(ids)}),
        )
        for row in result.data:
            rows[f"{entity_type}:{row.id}"] = {**row.values, "id": row.id}
    for node in level:
        entity = hierarchy_entity(node.ref)
        values = rows.get(f"{entity.type}:{entity.id}") if entity is not None else None
        if values is not None:
            node.values = values


# -------------------------------------------------------------------------- #
# what a row draws with                                                       #
# -------------------------------------------------------------------------- #


@dataclass
class TreeFieldPlan:
    """The schemas a tree row needs, one entry per type the tree has shown."""

    #: The type's own status field, when it has a real one.
    status: dict[str, FieldSchema | None] = dc_field(default_factory=dict)
    #: The secondary column's field, per type.
    secondary: dict[str, FieldSchema | None] = dc_field(default_factory=dict)
    #: `Status` rows by code, read once and only when a status is on show (probe 010).
    statuses: dict[str, StatusRecord] | None = None


def resolve_tree_fields(
    schema: SchemaService,
    status_table: StatusService,
    types: Sequence[str],
    secondary_field: str | None = None,
) -> TreeFieldPlan:
    """The status field and the secondary field of every type a tree shows.

    A type's status field is whichever field is a `status_list`. Project's `sg_status` is
    a plain `list` with no Status row behind its values, so it carries no badge
    (entity_types/Project, probe 009).
    """
    plan = TreeFieldPlan()
    for entity_type in types:
        fields = schema.fields(entity_type)
        status = status_field_for(entity_type, fields)
        plan.status[entity_type] = None if isinstance(status, str) or status.data_type != "status_list" else status
        plan.secondary[entity_type] = fields.get(secondary_field) if secondary_field else None
    on_show = any(field is not None for field in plan.status.values()) or any(
        field is not None and field.data_type == "status_list" for field in plan.secondary.values()
    )
    if on_show:
        plan.statuses = dict(status_table.by_code())
    return plan


TREE_STATUS_FIELDS: tuple[str, ...] = ("sg_status_list", "sg_status")
"""The field names a level is read under so a row can show a status: the two the API uses."""
