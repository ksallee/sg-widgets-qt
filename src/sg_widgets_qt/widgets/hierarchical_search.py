"""Drill down to one row, by browsing the navigation tree or by searching it.

The port of `hierarchical-search.tsx`. Browsing is `hierarchy_expand`, one call a level:
`children` names the next paths and `has_children` says which are worth opening. Searching
cannot go through the same endpoint, because `hierarchy/_search` takes an entity and answers
where it sits rather than matching words (post_hierarchy_search). So the words go to
`text_search` and each hit is then asked for its path, which is what makes a result a
breadcrumb.

    tree = HierarchicalSearch(context=context, root_path="/Project/70")
    tree.selected.connect(open_row)

A level of the tree carries no picture, so those rows show the type glyph `entity_glyphs`
gives them; a searched row shows the thumbnail the second read answered.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QVBoxLayout, QWidget

from sg_widgets_core.client import hierarchy_entity
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.row import path_of
from sg_widgets_core.search import (
    HIERARCHY_LEAF_LIMIT,
    breadcrumb,
    hydrate,
    path_refs,
    project_of_path,
    scope_to_project,
    search_type_map,
)
from sg_widgets_core.state import NO_MATCH_LABEL, NO_ROWS_LABEL

from ..primitives.base import THUMB_SIZE
from .entity_glyphs import entity_glyph
from .picker_row import PickerRowModel
from .search_control import SearchAnswer, SearchControl, SearchRequest

__all__ = [
    "HIERARCHICAL_SEARCH_TYPES",
    "HierarchicalSearch",
    "HierarchicalSearchRow",
]

#: Leaf types a drill-down usually ends on.
HIERARCHICAL_SEARCH_TYPES: list[str] = ["Shot", "Asset", "Sequence", "Task"]

#: The glyph a level of the tree draws, and the one the row back up draws.
FOLDER_GLYPH = "folder"
UP_GLYPH = "chevron-left"

#: What the group over the rows is called.
RESULTS_HEADING = "Results"
TREE_HEADING = "Tree"
UP_LABEL = "Back"


@dataclass
class HierarchicalSearchRow:
    """A path found by searching, or a node of the level being browsed."""

    #: The row's own label, the last crumb.
    label: str = ""
    #: The crumbs above it, project first when the search answered one.
    crumbs: list[str] = dc_field(default_factory=list)
    #: The row itself, when it is an entity rather than a type folder.
    ref: EntityRef | None = None
    #: The fields a search read for the row. Empty on a folder, which is not an entity.
    values: dict = dc_field(default_factory=dict)
    #: Every row the path runs through, root first.
    path: list = dc_field(default_factory=list)
    #: The tree path to feed back to `hierarchy_expand`.
    node_path: str = ""
    has_children: bool = False
    selectable: bool = False
    #: True on the row that goes back up a level.
    up: bool = False

    @property
    def type(self) -> str:
        """The type the row anatomy reads it as."""
        return self.ref.type if self.ref is not None else ""

    @property
    def id(self) -> int:
        return self.ref.id if self.ref is not None else 0

    @property
    def name(self) -> str:
        return self.label


@dataclass
class _Heading:
    """The group heading over the rows."""

    name: str
    type: str = ""
    id: int = 0
    values: dict = dc_field(default_factory=dict)


@dataclass
class _Crumb:
    """One level above the one being browsed: its label, and the path back to it."""

    label: str
    path: str


@dataclass
class _Level:
    """The level being browsed, and the levels above it."""

    path: str
    crumbs: list = dc_field(default_factory=list)


class HierarchicalSearch(QWidget):
    """The navigation tree, browsed level by level or searched into breadcrumbs.

    `entity_types` limits what a search returns; browsing reaches every level whatever it
    says, and a row that is not one of those types opens instead of being picked.
    """

    #: A row was picked, with every row its path runs through, root first.
    selected = Signal(object, object)
    #: The level being browsed changed.
    level_changed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        context: Any = None,
        root_path: str = "/",
        entity_types: Sequence[str] | dict[str, Any] | None = None,
        thumbnail: str | bool = "image",
        label_field: str | None = None,
        sub_label_field: Any = None,
        sub_label: Callable[[HierarchicalSearchRow], str] | None = None,
        secondary_field: Any = None,
        secondary: Callable[[HierarchicalSearchRow], str] | None = None,
        show_code: bool = False,
        fields: Sequence[str] = (),
        placeholder: str = "Search the hierarchy…",
        empty_label: str = NO_ROWS_LABEL,
        no_match_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        size: str = "md",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("hierarchical-search")
        self._context = context
        self._root_path = root_path
        self._entity_types: Any = (
            list(HIERARCHICAL_SEARCH_TYPES) if entity_types is None else entity_types
        )
        self._thumbnail = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._fields = list(fields)
        self._empty_label = empty_label
        self._no_match_label = no_match_label
        self._size = size
        self._level = _Level(path=root_path, crumbs=[])
        self._control: SearchControl | None = None

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self._model = PickerRowModel([], self, context=context, size=size)
        self._control = SearchControl(
            self,
            load=self._load,
            model=self._model,
            request=self._level.path,
            reads_empty=True,
            placeholder=placeholder,
            empty_label=empty_label,
            loading_label=loading_label,
            error_label=error_label,
            size=size,
            skeleton_lead=QSize(THUMB_SIZE[size], THUMB_SIZE[size]),
            row_mapper=self._rows_of,
            on_key_down=self._on_key_down,
        )
        column.addWidget(self._control)
        self._control.activated.connect(self._on_activated)
        self._control.drill_requested.connect(self._on_drill)
        self._control.query_changed.connect(self._on_query)
        self._apply_row_props()

    # --- the keywords ---------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._model.set_context(value)
        self._control.set_request(self._level.path + "|" + str(id(value)))

    @property
    def root_path(self) -> str:
        """Where the tree starts, `/Project/70` for one project or `/` for the site."""
        return self._root_path

    def set_root_path(self, value: str) -> None:
        """Only a new root reopens the tree; drilling moves the level itself."""
        if value == self._root_path:
            return
        self._root_path = value
        self._set_level(_Level(path=value, crumbs=[]))

    @property
    def entity_types(self) -> Any:
        """Types a search may end on."""
        return self._entity_types

    def set_entity_types(self, value: Sequence[str] | dict[str, Any]) -> None:
        self._entity_types = value
        self._control.set_request(self._level.path + "|types")

    @property
    def thumbnail(self) -> str | bool:
        """Field holding the thumbnail URL. A row with no picture falls back to its glyph."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self._apply_row_props()

    @property
    def label_field(self) -> str | None:
        """Field holding the row label."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self._apply_row_props()

    @property
    def sub_label_field(self) -> Any:
        """The muted line under the label."""
        return self._sub_label_field

    def set_sub_label_field(self, value: Any) -> None:
        self._sub_label_field = value
        self._apply_row_props()

    @property
    def sub_label(self) -> Callable[[HierarchicalSearchRow], str] | None:
        """The muted line of the caller's own making. Wins over `sub_label_field`."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[HierarchicalSearchRow], str] | None) -> None:
        self._sub_label = value
        self._apply_row_props()

    @property
    def secondary_field(self) -> Any:
        """The right-aligned value, drawn by its data type."""
        return self._secondary_field

    def set_secondary_field(self, value: Any) -> None:
        self._secondary_field = value
        self._apply_row_props()

    @property
    def secondary(self) -> Callable[[HierarchicalSearchRow], str] | None:
        """Right-aligned text of the caller's own making."""
        return self._secondary

    def set_secondary(self, value: Callable[[HierarchicalSearchRow], str] | None) -> None:
        self._secondary = value
        self._apply_row_props()

    @property
    def show_code(self) -> bool:
        """Show the row's code beside the label when the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._apply_row_props()

    @property
    def fields(self) -> list[str]:
        """Extra fields to request."""
        return list(self._fields)

    def set_fields(self, value: Sequence[str]) -> None:
        self._fields = list(value)
        self._apply_row_props()

    @property
    def placeholder(self) -> str:
        """Text in the search box."""
        return self._control.placeholder

    def set_placeholder(self, value: str) -> None:
        self._control.set_placeholder(value)

    @property
    def empty_label(self) -> str:
        """Shown when a level holds nothing."""
        return self._empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = value
        self._apply_empty_label()

    @property
    def no_match_label(self) -> str:
        """Shown when a query matches nothing."""
        return self._no_match_label

    def set_no_match_label(self, value: str) -> None:
        self._no_match_label = value
        self._apply_empty_label()

    @property
    def loading_label(self) -> str | None:
        """Names the skeletons a read stands behind."""
        return self._control.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._control.set_loading_label(value)

    @property
    def error_label(self) -> str | None:
        """Shown in place of what the failed read said."""
        return self._control.error_label

    def set_error_label(self, value: str | None) -> None:
        self._control.set_error_label(value)

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: row text, leading slot and glyphs."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value
        self._control.set_size(value)
        self._control.set_skeleton_lead(QSize(THUMB_SIZE[value], THUMB_SIZE[value]))

    @property
    def query(self) -> str:
        """What the caret holds."""
        return self._control.query

    def set_query(self, value: str) -> None:
        self._control.set_query(value)

    @property
    def level_path(self) -> str:
        """The tree path being browsed."""
        return self._level.path

    def search_control(self) -> SearchControl:
        """The lifecycle and the list under the tree."""
        return self._control

    @property
    def searching(self) -> bool:
        """True while a query is typed, which replaces the level with its results."""
        return self._control is not None and len(self._control.query.strip()) > 0

    # --- the read -----------------------------------------------------------------------

    def _load(self, request: SearchRequest) -> SearchAnswer:
        if len(request.query.strip()) == 0:
            return SearchAnswer(items=self._browse(self._level), has_more=False)
        return SearchAnswer(items=self._search_leaves(request.query), has_more=False)

    def _browse(self, level: _Level) -> list[HierarchicalSearchRow]:
        """Open one level of the tree. `children` names the next paths (post_hierarchy_expand)."""
        context = self._context
        if context is None:
            return []
        node = context.client.hierarchy_expand(level.path)
        above = [*[c.label for c in level.crumbs], node.label]
        return [self._browse_row(child, above) for child in node.children]

    def _browse_row(self, node: Any, crumbs: list[str]) -> HierarchicalSearchRow:
        entity = hierarchy_entity(node.ref)
        allowed = list(search_type_map(self._entity_types))
        ref = (
            EntityRef(type=entity.type, id=entity.id, name=node.label)
            if entity is not None
            else None
        )
        return HierarchicalSearchRow(
            label=node.label,
            crumbs=list(crumbs),
            ref=ref,
            values={},
            path=path_refs(node.path),
            node_path=node.path,
            has_children=bool(node.has_children),
            selectable=entity is not None and entity.type in allowed,
        )

    def _search_leaves(self, text: str) -> list[HierarchicalSearchRow]:
        """Find the leaves, then ask where each one sits (post_hierarchy_search)."""
        context = self._context
        if context is None:
            return []
        types = search_type_map(self._entity_types)
        project_id = project_of_path(self._root_path)
        if project_id is not None:
            types = scope_to_project(context.schema, types, project_id)
        found = context.client.text_search(
            text, types, {"size": HIERARCHY_LEAF_LIMIT, "number": 1}
        )
        hits = hydrate(
            context.client,
            found,
            fields=self._model.read_fields(),
            label_field=self._label_field,
        )
        rows: list[HierarchicalSearchRow] = []
        for hit in hits:
            try:
                answers = context.client.hierarchy_search(self._root_path, hit.ref)
            except Exception:  # A row the tree cannot place is not a result.
                continue
            path = answers[0] if answers else None
            if path is None:
                continue
            crumbs = breadcrumb(path)
            own = (hit.ref.name if self._label_field else "") or (
                crumbs[-1] if crumbs else hit.ref.name
            )
            rows.append(
                HierarchicalSearchRow(
                    label=own,
                    crumbs=list(crumbs[:-1]),
                    ref=EntityRef(type=hit.ref.type, id=hit.ref.id, name=path.label),
                    values=dict(hit.values),
                    path=path_refs(path.incremental_path),
                    node_path=(
                        path.incremental_path[-1]
                        if path.incremental_path
                        else self._root_path
                    ),
                    has_children=False,
                    selectable=True,
                )
            )
        return rows

    # --- the rows -----------------------------------------------------------------------

    def _apply_row_props(self) -> None:
        model = self._model
        model.set_context(self._context)
        model.set_thumbnail(self._thumbnail)
        model.set_label_field(self._label_field)
        model.set_sub_label_field(self._sub_label_field)
        model.set_secondary_field(self._secondary_field)
        model.set_show_code(self._show_code)
        model.set_fields(self._fields)
        model.set_size(self._size)
        model.set_kind_of(lambda row: "heading" if isinstance(row, _Heading) else "row")
        model.set_glyph_of(self._glyph_of)
        model.set_drillable_of(self._drillable)
        model.set_crumbs_of(lambda row: getattr(row, "crumbs", ()) or ())
        named = self._sub_label is not None or not path_of(self._sub_label_field)
        model.set_sub_label(self._sub_of if named else None)
        model.set_secondary(self._secondary_of if self._secondary is not None else None)
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        if self._control is not None:
            self._control.set_row_mapper(self._rows_of)

    def _drillable(self, row: Any) -> bool:
        """A level of the tree opens; a search shows paths, so a result opens nothing."""
        return (
            isinstance(row, HierarchicalSearchRow)
            and row.has_children
            and not row.up
            and not self.searching
        )

    def _on_drill(self, index: int) -> None:
        """A press on the drill control opens the level, where a press on the row picks it."""
        row = self._model.row_at(index)
        if isinstance(row, HierarchicalSearchRow):
            self.drill(row)

    def _glyph_of(self, row: Any) -> str:
        if getattr(row, "up", False):
            return UP_GLYPH
        ref = getattr(row, "ref", None)
        return entity_glyph(ref.type) if ref is not None else FOLDER_GLYPH

    def _sub_of(self, row: Any) -> str:
        if not isinstance(row, HierarchicalSearchRow):
            return ""
        if row.up:
            return ""
        if self._sub_label is not None:
            return self._sub_label(row) or ""
        return row.type if row.selectable else "Group"

    def _secondary_of(self, row: Any) -> str:
        if self._secondary is None or not isinstance(row, HierarchicalSearchRow):
            return ""
        return self._secondary(row) or ""

    def _heading(self) -> str:
        if self.searching:
            return RESULTS_HEADING
        trail = " › ".join(c.label for c in self._level.crumbs)
        return trail or TREE_HEADING

    def _rows_of(self, items: Sequence[Any]) -> list[Any]:
        rows: list[Any] = [_Heading(self._heading())]
        if not self.searching and self._level.crumbs:
            rows.append(
                HierarchicalSearchRow(label=UP_LABEL, node_path="..", up=True, selectable=False)
            )
        rows.extend(items)
        return rows

    def _apply_empty_label(self) -> None:
        if self._control is None:
            return
        self._control.set_empty_label(
            self._no_match_label if self.searching else self._empty_label
        )

    def _on_query(self, _text: str) -> None:
        self._apply_empty_label()
        self._refresh_rows()

    # --- walking the tree ----------------------------------------------------------------

    def _set_level(self, level: _Level) -> None:
        self._level = level
        if self._control is not None:
            self._control.set_request(level.path)
        self.level_changed.emit(level.path)

    def drill(self, row: HierarchicalSearchRow) -> None:
        """Open the level under a row. A search shows paths, so it drills nothing."""
        if not row.has_children or self.searching:
            return
        crumbs = [*self._level.crumbs, _Crumb(label=row.label, path=self._level.path)]
        self._set_level(_Level(path=row.node_path, crumbs=crumbs))

    def up(self) -> None:
        """Go back one level. A search owns the list, so it goes nowhere."""
        if self.searching or not self._level.crumbs:
            return
        parent = self._level.crumbs[-1]
        self._set_level(_Level(path=parent.path, crumbs=list(self._level.crumbs[:-1])))

    def _on_activated(self, index: int) -> None:
        row = self._model.row_at(index)
        if not isinstance(row, HierarchicalSearchRow):
            return
        if row.up:
            self.up()
            return
        if row.selectable and row.ref is not None:
            self.selected.emit(row.ref, list(row.path))
            return
        self.drill(row)

    def _on_key_down(self, event: QKeyEvent, _items: list) -> bool:
        """Left and Right walk the tree the way Up and Down walk a level."""
        if self.searching:
            return False
        key = event.key()
        if key == Qt.Key.Key_Left or (
            key == Qt.Key.Key_Backspace and len(self._control.query) == 0
        ):
            self.up()
            return True
        if key != Qt.Key.Key_Right:
            return False
        row = self._model.row_at(self._control.list_surface().highlighted())
        if not isinstance(row, HierarchicalSearchRow) or not row.has_children:
            return False
        self.drill(row)
        return True
