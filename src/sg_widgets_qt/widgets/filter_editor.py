"""A Flow Production Tracking filter tree, edited as rows and nested groups.

Ported from `packages/react/src/registry/sg/components/filter-editor.tsx` and its Svelte twin.
A row is a field, an operator and a value; a group nests rows under All or Any. The operator
menu and the value editor both come from the field's `data_type` through core, so a row can
only build a filter the API accepts (017_filter_operators). A row with no field, or one whose
operator still has no value, is dropped on serialisation rather than sent.

The field is chosen with `FieldPicker`, which descends through links, so a row may filter on a
dotted path; the leaf of that path is resolved through the schema service on a worker and is
what picks the operator menu and the value editor. An operator that pins its value draws no
editor at all.

    editor = FilterEditor(entity_type="Version", context=context, value=tree)
    editor.changed.connect(apply)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.filter import (
    EntityRef,
    FilterCondition,
    FilterGroup,
    FilterNode,
    empty_filter,
)
from sg_widgets_core.filter import condition as make_condition
from sg_widgets_core.filter import group as make_group
from sg_widgets_core.filter_ux import (
    NO_SCHEMA,
    append_at,
    apply_preset,
    condition_arity,
    condition_list,
    default_condition,
    field_operators,
    move_at,
    node_at,
    operator_menu,
    preset_by_id,
    preset_id_of,
    relative_window,
    remove_at,
    replace_at,
    time_unit_field,
    validate_condition,
    value_editor_for,
    with_added_list_value,
    with_list_value,
    with_relative_window,
    without_list_value,
)
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.state import NOTHING_CHOSEN_LABEL

from ..primitives.base import CONTROL_HEIGHT, ThemedWidget, painter_for
from ..primitives.button import Button
from ..primitives.checkbox import ToggleGroup
from ..primitives.remove_control import RemoveControl
from ..primitives.select import Select
from ..primitives.skeleton import Skeleton
from ..theme import theme_of, with_alpha
from ..workers import Ticket, default_pool
from ._sortable_rows import SortableRows, paint_drop_line
from .checkbox_editor import CheckboxEditor
from .color_editor import ColorEditor
from .date_editor import DateEditor
from .date_time_editor import DateTimeEditor
from .entity_multi_picker import EntityMultiPicker
from .entity_picker import EntityPicker
from .field_error import FieldError
from .field_picker import FieldPicker, schema_of
from .list_multi_picker import ListMultiPicker
from .list_picker import ListPicker
from .number_editor import NumberEditor
from .state_line import StateLine
from .status_multi_picker import StatusMultiPicker
from .status_picker import StatusPicker
from .text_editor import TextEditor
from .url_editor import UrlEditor

__all__ = [
    "FIELD_MAX_WIDTH",
    "FIELD_MIN_WIDTH",
    "FILTER_EDITOR_SIZE_VALUES",
    "OPERATOR_WIDTH",
    "RAIL_INDENT",
    "FilterEditor",
    "numeric_type",
]

#: `size`: the control ladder every control in a row stands on.
FILTER_EDITOR_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")

#: The six types NumberEditor parses. `footage` is numeric to the API and reads as a plain number.
NUMERIC_EDITORS: tuple[str, ...] = (
    "number", "float", "percent", "duration", "timecode", "currency",
)

#: `min-w-24 max-w-56`: the field is the row's widest cell and gives the rest back.
FIELD_MIN_WIDTH = 96
FIELD_MAX_WIDTH = 224

#: `w-40` of the operator select.
OPERATOR_WIDTH = 160

#: `border-l pl-3`: the rail a level of nesting hangs off, and the indent it costs.
RAIL_INDENT = 12

#: `p-2` and `bg-muted/40` of a nested group's own surface.
NEST_PAD = 8
NEST_WASH = 0.4

#: Between a group's header, its rows and its foot, and between the controls of a row.
ROW_GAP = 8

#: Between the two controls of the foot, which read as one run.
FOOT_GAP = 4

#: How many rows build their cells in the turn of the loop that draws the tree. The rest are
#: filled one to a turn, so a tall tree never holds the GUI thread.
EAGER_ROWS = 1

#: How many turns of the loop a row takes to build: the field and the operator, then the value.
ROW_TURNS = 2

#: A cross sits one step under the row's own control on the chip ladder.
CROSS_SIZE: dict[str, str] = {"sm": "xs", "md": "xs", "lg": "sm"}

#: The button step beside a control of each height.
CONTROL_BUTTON: dict[str, str] = {"sm": "sm", "md": "default", "lg": "lg"}

#: The icon-button step beside a control of each height.
ICON_BUTTON: dict[str, str] = {"sm": "icon-sm", "md": "icon-sm", "lg": "icon"}

#: The width a relative window's count and unit take, which never wrap the row.
COUNT_WIDTH = 64
UNIT_WIDTH = 96

#: `w-44` of the colour editor inside a row.
COLOR_WIDTH = 176


def numeric_type(data_type: str) -> str:
    """The numeric editor a data type reads as. Anything else is a plain number."""
    return data_type if data_type in NUMERIC_EDITORS else "number"


class _RowFiller(QtCore.QObject):
    """One row anywhere builds per turn of the loop, whichever tree it belongs to.

    A timer per editor is a row per editor per turn, and a page carries more than one tree: the
    showcase's own filter-editor page holds five, so five rows built in the turn one was meant
    to and the turn ran to 60ms. The editors queue here instead and take the turns in order.
    """

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._waiting: list[FilterEditor] = []
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._turn)

    def wants(self, editor: FilterEditor) -> None:
        """Put an editor with rows waiting in the queue."""
        if not any(one is editor for one in self._waiting):
            self._waiting.append(editor)
        if not self._timer.isActive():
            self._timer.start()

    def _turn(self) -> None:
        while self._waiting:
            editor = self._waiting.pop(0)
            if editor.gone():
                continue
            if editor.fill_one():
                if editor.pending_rows():
                    self._waiting.append(editor)
                break
        if self._waiting:
            self._timer.start()


_FILLER: _RowFiller | None = None


def row_filler() -> _RowFiller:
    """The one queue every editor's rows build from.

    It hangs off the application, so it goes when the application does rather than outliving it
    on a module of its own.
    """
    global _FILLER  # noqa: PLW0603
    if _FILLER is None or _FILLER.parent() is not QtWidgets.QApplication.instance():
        _FILLER = _RowFiller(QtWidgets.QApplication.instance())
    return _FILLER


def _text_value(value: Any) -> str | None:
    if value is None:
        return None
    return None if isinstance(value, (dict, list)) else str(value)


def _number_value(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float, str)) else None


def _codes_of(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [one for one in value if isinstance(one, str)]


def _entity_ref(value: Any) -> EntityRef | None:
    """One entity reference, however the tree spells it. A row may hold either shape."""
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, dict) and value.get("type") is not None and value.get("id") is not None:
        return EntityRef(type=str(value["type"]), id=int(value["id"]), name=value.get("name"))
    return None


def _entity_refs(value: Any) -> list[EntityRef]:
    """`is` takes one entity hash and `in` a list of them; a list under `is` is a 400."""
    items = value if isinstance(value, list) else [value]
    found = [_entity_ref(one) for one in items]
    return [one for one in found if one is not None]


def _dotted_paths(node: FilterNode, out: list[str] | None = None) -> list[str]:
    """Every dotted path the tree holds. A flat name needs no resolution."""
    found = out if out is not None else []
    if node.kind == "condition":
        if "." in node.path:
            found.append(node.path)
        return found
    for child in node.conditions:
        _dotted_paths(child, found)
    return found


class FilterEditor(QtWidgets.QWidget):
    """A filter tree, edited.

    A row is addressed by its path in the tree and never by the widget that drew it a moment
    ago: an edit hands the editor a whole new tree and the editor works out what that leaves
    standing. A group whose rows moved under it wears the new node in place, a row whose
    condition did not change is left where it is, and a type read on another entity keeps every
    widget of the tree and builds the rows' cells again a row to a turn of the loop. Keyboard
    focus is put back on the control it left.
    """

    #: The whole tree changed, on every edit.
    changed = Signal(object)
    #: The same payload under the name the query widgets share.
    filters_changed = Signal(object)
    #: The first thing wrong with the tree, or None once every row is complete.
    error_changed = Signal(object)
    #: One line for the live region, from core's sortable announcements.
    announced = Signal(str)

    def __init__(
        self,
        entity_type: str = "",
        context: Any = None,
        value: FilterGroup | None = None,
        hide_paths: Sequence[str] | None = None,
        project_id: int | None = None,
        empty_label: str = NOTHING_CHOSEN_LABEL,
        size: str = "md",
        disabled: bool = False,
        field_chooser: Callable[..., QtWidgets.QWidget] | None = None,
        value_editor: Callable[..., QtWidgets.QWidget] | None = None,
        entity_editor: Callable[..., QtWidgets.QWidget] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-editor")
        self._entity_type = str(entity_type or "")
        self._context = context
        self._value = value if value is not None else empty_filter()
        self._hide_paths = list(hide_paths or [])
        self._project_id = project_id
        self._empty_label = empty_label
        self._size = size if size in FILTER_EDITOR_SIZE_VALUES else "md"
        self._disabled = bool(disabled)
        self._field_chooser = field_chooser
        self._value_editor = value_editor
        self._entity_editor = entity_editor

        self._fields: dict[str, FieldSchema] = {}
        self._fields_loaded = False
        self._reading = False
        self._jobs: list[Any] = []
        self._leaves: dict[str, FieldSchema | None] = {}
        self._resolving: set[str] = set()
        self._fields_ticket = Ticket()
        self._error: str | None = None
        self._focus_at: tuple[tuple[int, ...], str] | None = None
        self._root_node: _GroupNode | None = None
        # What was drawn where, so a redraw builds only the rows whose node moved. A row is a
        # field picker, an operator menu and a value control, each with a popup window of its
        # own, so rebuilding ten of them costs a third of a second on the GUI thread; the tree
        # is redrawn on every edit, so a row that did not change is kept where it stands.
        self._built: dict[tuple[int, ...], tuple[FilterNode, QtWidgets.QWidget]] = {}
        self._building: dict[tuple[int, ...], tuple[FilterNode, QtWidgets.QWidget]] = {}
        self._chrome: tuple | None = None
        self._cells: tuple | None = None
        self._row_budget = 0
        self._to_fill: list[_ConditionRow] = []
        # Reads answer one at a time, so the redraws they ask for are coalesced into one.
        self._redraw = QtCore.QTimer(self)
        self._redraw.setSingleShot(True)
        self._redraw.timeout.connect(self._rebuild)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self._column = column
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        # A job outlives the widget that asked for it, and a widget deleted while its answer
        # is in flight is a crash on PyQt5 rather than a raise, so every job this editor puts
        # out is cancelled when it goes. The handler closes over the list alone: `destroyed`
        # runs while Qt is freeing the children, and nothing there may touch the widget.
        jobs = self._jobs

        def retire(*_args: object) -> None:
            for job in list(jobs):
                job.cancel()
            jobs.clear()

        self.destroyed.connect(retire)

        self._read_fields()
        self._resolve_leaves(_dotted_paths(self._value))
        self._rebuild()

    # --- props ----------------------------------------------------------------------------

    @property
    def entity_type(self) -> str:
        """Type the root of every field path is read on."""
        return self._entity_type

    def set_entity_type(self, value: str) -> None:
        if value == self._entity_type:
            return
        self._entity_type = str(value or "")
        self._fields = {}
        self._fields_loaded = False
        self._leaves = {}
        self._resolving = set()
        self._read_fields()
        self._rebuild()

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it, so widgets on a page share one cache."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._fields = {}
        self._fields_loaded = False
        self._leaves = {}
        self._resolving = set()
        self._read_fields()
        self._rebuild()

    @property
    def value(self) -> FilterGroup:
        """The tree."""
        return self._value

    def set_value(self, value: FilterGroup | None) -> None:
        """Take a tree from outside. Nothing is emitted."""
        self._value = value if value is not None else empty_filter()
        self._rebuild()

    @property
    def hide_paths(self) -> list[str]:
        """Paths kept out of the field list. A pattern hides itself and everything under it."""
        return list(self._hide_paths)

    def set_hide_paths(self, value: Sequence[str] | None) -> None:
        self._hide_paths = list(value or [])
        self._rebuild()

    @property
    def project_id(self) -> int | None:
        """Scopes the status pickers to the codes one project allows."""
        return self._project_id

    def set_project_id(self, value: int | None) -> None:
        self._project_id = value
        self._rebuild()

    @property
    def empty_label(self) -> str:
        """Shown when a group holds no condition."""
        return self._empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = str(value)
        self._rebuild()

    @property
    def size(self) -> str:
        """The control ladder: every control in a row stands at 28, 32 or 36."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in FILTER_EDITOR_SIZE_VALUES else "md"
        self._rebuild()

    @property
    def disabled(self) -> bool:
        """Dims the editor and blocks every control."""
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self._rebuild()

    @property
    def field_chooser(self) -> Callable[..., QtWidgets.QWidget] | None:
        """A caller's own field control, called with the row's arguments."""
        return self._field_chooser

    def set_field_chooser(self, value: Callable[..., QtWidgets.QWidget] | None) -> None:
        self._field_chooser = value
        self._rebuild()

    @property
    def value_editor(self) -> Callable[..., QtWidgets.QWidget] | None:
        """A caller's own value control, which replaces every editor below."""
        return self._value_editor

    def set_value_editor(self, value: Callable[..., QtWidgets.QWidget] | None) -> None:
        self._value_editor = value
        self._rebuild()

    @property
    def entity_editor(self) -> Callable[..., QtWidgets.QWidget] | None:
        """A caller's own entity control, which replaces the two entity pickers."""
        return self._entity_editor

    def set_entity_editor(self, value: Callable[..., QtWidgets.QWidget] | None) -> None:
        self._entity_editor = value
        self._rebuild()

    @property
    def error(self) -> str | None:
        """The first thing wrong with the tree, or None."""
        return self._error

    # --- what a path is -------------------------------------------------------------------

    def fields(self) -> dict[str, FieldSchema]:
        """The root type's fields, once the read has answered."""
        return dict(self._fields)

    def field_of(self, path: str) -> FieldSchema | None:
        """The leaf field of a path. A flat name is a field of the root type."""
        if not path:
            return None
        if "." not in path:
            return self._fields.get(path)
        return self._leaves.get(path)

    def data_type_of(self, path: str) -> str:
        found = self.field_of(path)
        return found.data_type if found is not None else ""

    def unresolved(self, path: str) -> bool:
        """True while the field behind a path is still being read; its leaf decides the row.

        The type's own fields are read once, and a row drawn before they land would build a
        control the answer replaces, so a row waits rather than guessing at a text editor.
        """
        if path and not self._fields_loaded:
            return True
        return "." in path and path not in self._leaves

    def _read_fields(self) -> None:
        schema = schema_of(self._context) if self._context is not None else None
        if schema is None or not self._entity_type:
            return
        token = self._fields_ticket.next()
        self._reading = True
        self._keep(default_pool().submit(
            schema.fields,
            self._entity_type,
            on_result=self._fields_read,
            on_error=self._fields_failed,
            ticket=(self._fields_ticket, token),
        ))

    def gone(self) -> bool:
        """True once Qt has deleted the widget under the wrapper a callback still holds."""
        try:
            self.objectName()
        except RuntimeError:
            return True
        return False

    def _fields_read(self, found: Any) -> None:
        if self.gone():
            return
        self._reading = False
        self._fields = dict(found or {})
        self._fields_loaded = True
        if not self._resolving:
            self._redraw.start(0)

    def _fields_failed(self, _error: BaseException) -> None:
        # A type the schema will not answer for still draws its rows, on the paths they hold.
        if self.gone():
            return
        self._reading = False
        self._fields_loaded = True
        if not self._resolving:
            self._redraw.start(0)

    def _resolve_leaf(self, path: str) -> None:
        """Walk one dotted path to its leaf."""
        self._resolve_leaves([path])

    def _resolve_leaves(self, paths: Sequence[str]) -> None:
        """Walk every dotted path a tree holds, on one job rather than one each.

        A job per path is a pool thread per path, and a schema walk is Python work that holds
        the interpreter while it runs, so four of them at once stall the GUI thread that the
        one they answer never would (`docs/design-rules.md` rule on the GUI thread).
        """
        schema = schema_of(self._context) if self._context is not None else None
        if schema is None:
            return
        wanted = [
            path
            for path in dict.fromkeys(paths)
            if path and path not in self._leaves and path not in self._resolving
        ]
        if not wanted:
            return
        self._resolving.update(wanted)
        entity_type = self._entity_type

        def walk() -> dict[str, Any]:
            found: dict[str, Any] = {}
            for path in wanted:
                try:
                    found[path] = schema.resolve_path(entity_type, path)
                except Exception:  # noqa: BLE001
                    # A path the schema no longer holds still has to be editable, so the row
                    # keeps it.
                    found[path] = None
            return found

        self._keep(
            default_pool().submit(
                walk,
                on_result=self._leaves_read,
                on_error=lambda _error, at=tuple(wanted): self._leaves_read(
                    dict.fromkeys(at, None)
                ),
            )
        )

    def _keep(self, job: Any) -> None:
        """Hold a job so it can be cancelled when the editor goes."""
        self._jobs = [one for one in self._jobs if one.live]
        self._jobs.append(job)

    def _leaves_read(self, found: Any) -> None:
        if self.gone():
            return
        for path, segments in (found or {}).items():
            self._leaf_read(path, segments)

    def _leaf_read(self, path: str, segments: Any) -> None:
        self._resolving.discard(path)
        leaf = None
        if segments:
            leaf = getattr(segments[-1], "field", None)
        self._leaves[path] = leaf
        # A tree of several dotted paths answers one at a time; the rows are drawn once every
        # answer is in, so a control is never built to be replaced a moment later.
        if not self._resolving:
            self._redraw.start(0)

    # --- edits ----------------------------------------------------------------------------

    def _commit(self, next_value: FilterGroup, rebuild: bool = True) -> None:
        self._value = next_value
        if rebuild:
            self._rebuild()
        else:
            # A value typed into a control the tree already holds changes no widget, so the
            # tree is left standing and only the lines under the rows are read again.
            self._refresh_issues()
        self.changed.emit(next_value)
        self.filters_changed.emit(next_value)

    def node_at(self, path: Sequence[int]) -> FilterNode | None:
        """The node the tree holds at a path, which is what a row edits."""
        return node_at(self._value, list(path))

    def set_condition_value(self, path: Sequence[int], value: Any) -> None:
        """Write one row's value. The control already shows it, so the tree is not redrawn."""
        node = self.node_at(path)
        if node is None or node.kind != "condition":
            return
        next_node = FilterCondition(path=node.path, operator=node.operator, value=value)
        # The control already shows the value, so the row that drew it is what the tree now
        # holds; saying so here keeps the next redraw from building that row again because the
        # node it remembers is one keystroke old.
        at = tuple(path)
        found = self._built.get(at)
        if found is not None:
            self._built[at] = (next_node, found[1])
        self._commit(replace_at(self._value, list(path), next_node), rebuild=False)

    def edit(self, path: Sequence[int], node: FilterNode) -> None:
        """Replace the node at a path."""
        self._commit(replace_at(self._value, list(path), node))

    def remove(self, path: Sequence[int]) -> None:
        """Drop the node at a path."""
        self._commit(remove_at(self._value, list(path)))

    def append(self, path: Sequence[int], node: FilterNode) -> None:
        """Add a node to the group at a path."""
        self._commit(append_at(self._value, list(path), node))

    def move(self, path: Sequence[int], delta: int) -> None:
        """Move the node at a path by `delta` places among its siblings."""
        if delta:
            self._commit(move_at(self._value, list(path), delta))

    def pick_field(self, path: Sequence[int], node: FilterCondition, chosen: str) -> None:
        """Point a row at another field. Moving to another data type resets the row."""
        before = self.data_type_of(node.path)
        if "." in chosen and chosen not in self._leaves:
            self._resolve_leaf(chosen)
            self._pending_field = (tuple(path), node, chosen, before)
            return
        self._apply_field(path, node, chosen, before)

    def _apply_field(
        self, path: Sequence[int], node: FilterCondition, chosen: str, before: str
    ) -> None:
        after = self.field_of(chosen)
        data_type = after.data_type if after is not None else ""
        if before == data_type and node.path:
            next_node: FilterNode = FilterCondition(
                path=chosen, operator=node.operator, value=node.value
            )
        else:
            next_node = default_condition(chosen, data_type, field_operators(after))
        self._commit(replace_at(self._value, list(path), next_node))

    def pick_preset(self, path: Sequence[int], node: FilterCondition, preset_id: str) -> None:
        """Move a row onto another entry of its operator menu."""
        data_type = self.data_type_of(node.path)
        preset = preset_by_id(data_type, preset_id, field_operators(self.field_of(node.path)))
        if preset is not None:
            self._commit(replace_at(self._value, list(path), apply_preset(node, preset, data_type)))

    # --- the tree -------------------------------------------------------------------------

    def root_group(self) -> QtWidgets.QWidget | None:
        """The widget the root group is drawn in."""
        return self._root_node

    def rows(self) -> list[QtWidgets.QWidget]:
        """Every condition row, in the order they are drawn."""
        return list(self._condition_rows())

    def _condition_rows(self) -> list[_ConditionRow]:
        """Every row of the tree, top to bottom.

        `findChildren` answers in the order Qt was handed the children, which is the order they
        were built: a redraw that keeps three rows and builds the second afresh would hand back
        the new one last. The rails know the order the rows stand in, so the tree is walked.
        """
        found: list[_ConditionRow] = []
        _rows_under(self._root_node, found)
        return found

    def issues(self) -> list[str]:
        """The line under every incomplete row, in the order they are drawn."""
        return [line.message for line in self._issue_lines() if line.message]

    def _issue_lines(self) -> list[FieldError]:
        found = [row.issue_line() for row in self._condition_rows()]
        return [line for line in found if line is not None]

    def _refresh_issues(self) -> None:
        for row in self._condition_rows():
            row.refresh_issue()
        self._refresh_error()

    def _chrome_stamp(self) -> tuple:
        """What a group's own chrome is built against.

        The rail, the All and Any toggle, the foot and the grips stand on the ladder step and on
        whether the editor takes an edit at all. Change either and every widget of the tree is
        drawn afresh, because there is no part of it the change leaves alone.
        """
        return (self._size, self._disabled, self._empty_label)

    def _cell_stamp(self) -> tuple:
        """What a row's three cells are built against, which the chrome knows nothing of.

        The schema behind a path decides the operator menu and the value control and nothing
        else, so a type read on another entity, another project or another chooser leaves the
        tree, the groups and the order they stand in exactly where they are: every row puts its
        skeleton back and builds its cells again on a turn of the loop of its own. Swapping a
        forty-row tree whole was 60ms of Qt work in the turn that asked for it and the same
        again to free what it replaced; this way no turn carries more than one row.
        """
        return (
            self._entity_type,
            self._project_id,
            tuple(self._hide_paths),
            self._fields_loaded,
            len(self._fields),
            tuple(
                sorted(
                    (path, None if leaf is None else leaf.data_type)
                    for path, leaf in self._leaves.items()
                )
            ),
            self._field_chooser,
            self._value_editor,
            self._entity_editor,
        )

    def reuse(self, path: Sequence[int], node: FilterNode) -> QtWidgets.QWidget | None:
        """The widget the last build drew for this path, if it holds the same node."""
        found = self._built.get(tuple(path))
        if found is None:
            return None
        was, widget = found
        if was != node:
            return None
        try:
            widget.objectName()
        except RuntimeError:
            # Qt deleted the widget under the wrapper; the row is built afresh.
            return None
        # A group kept whole keeps every row under it, and this build never walks them, so
        # what the last one drew there is carried over for the next one to keep too.
        at = tuple(path)
        for other, held in self._built.items():
            if len(other) > len(at) and other[: len(at)] == at:
                self._building[other] = held
        return widget

    def standing(self, path: Sequence[int]) -> QtWidgets.QWidget | None:
        """The widget the last build drew at a path, whatever node it held then.

        A group whose rows changed under it wears the new node rather than being built again,
        so the rows it keeps never change hands. `reuse` is the stricter question: the widget
        only where nothing at all under it moved.
        """
        found = self._built.get(tuple(path))
        if found is None:
            return None
        widget = found[1]
        try:
            widget.objectName()
        except RuntimeError:
            # Qt deleted the widget under the wrapper; the group is built afresh.
            return None
        return widget

    def remember(self, path: Sequence[int], node: FilterNode, widget: QtWidgets.QWidget) -> None:
        """Record what this build drew at a path, for the next one to reuse."""
        self._building[tuple(path)] = (node, widget)

    def drop(self, widget: QtWidgets.QWidget) -> None:
        """Take a widget out of the editor for good and leave Qt to free it.

        It leaves at once rather than when Qt gets to it, or a lookup that walks the editor
        would answer what was drawn a moment ago beside what is drawn now. What is leaving
        holds the theme it wears: reading it again over the catalogue on the way out was 38ms
        of the 60ms the move itself took.
        """
        hold = getattr(widget, "hold_theme", None)
        if callable(hold):
            hold(True)
        widget.setParent(None)
        widget.deleteLater()

    def _rebuild(self) -> None:
        self._redraw.stop()
        self._resolve_leaves(_dotted_paths(self._value))
        pending = getattr(self, "_pending_field", None)
        if pending is not None and pending[2] in self._leaves:
            self._pending_field = None
            self._apply_field(list(pending[0]), pending[1], pending[2], pending[3])
            return
        self._focus_at = self._focused_slot()
        chrome = self._chrome_stamp()
        cells = self._cell_stamp()
        restamp = False
        if chrome != self._chrome:
            # Nothing of the tree survives the ladder step or the disabled flag, so the cache
            # goes and every widget is built again, on the schema the editor holds now.
            self._built = {}
            self._chrome = chrome
        else:
            restamp = self._cells is not None and cells != self._cells
        self._cells = cells
        # The new tree is built first, so a row it keeps is reparented out of the old one
        # before that one goes.
        previous = self._root_node
        self._building = {}
        self._row_budget = EAGER_ROWS
        kept = self.reuse([], self._value) if previous is not None else None
        if kept is previous and previous is not None:
            # The whole tree holds the node it was drawn for, so not a widget of it is touched:
            # a type read on another entity is the rows' cells and nothing else.
            previous = None
        elif previous is not None and self.standing([]) is previous:
            # An edit changed something under the root: the root wears the new tree in place
            # and only the branch that changed is built again.
            previous.wear(self._value)
            previous = None
        else:
            self._root_node = _GroupNode(self, [], self._value, self)
            self._column.addWidget(self._root_node)
        self.remember([], self._value, self._root_node)
        self._built = self._building
        self._building = {}
        if previous is not None:
            self._column.removeWidget(previous)
            self.drop(previous)
        if restamp:
            for row in self._condition_rows():
                row.empty()
        self.setEnabled(not self._disabled)
        self._refresh_error()
        self._restore_focus()
        self._queue_fills()

    def take_row(self) -> bool:
        """Whether the row a group is about to draw may build its cells now."""
        if self._row_budget <= 0:
            return False
        self._row_budget -= 1
        return True

    def reading(self) -> bool:
        """True while an answer that would rebuild every row is still out."""
        return bool(self._reading or self._resolving)

    def _queue_fills(self) -> None:
        self._to_fill = [row for row in self._condition_rows() if not row.filled]
        # A row built while the schema it stands on is still being read would be thrown away
        # the moment that answer lands, and the reads its own controls put out would answer
        # into a widget that has gone. It stands on its skeleton until the answer is in.
        if self._to_fill and not self.reading():
            row_filler().wants(self)

    def fill_one(self) -> bool:
        """Give the next row waiting one turn. Answers whether a turn was used.

        The queue is the filler's, not this editor's: a page carries several trees and a turn
        of the loop belongs to one row of one of them. A row takes two turns and stays at the
        head of the queue until it has had both.
        """
        while self._to_fill:
            row = self._to_fill[0]
            try:
                done = row.filled
            except RuntimeError:
                # The row went with a redraw between two turns.
                self._to_fill.pop(0)
                continue
            if done:
                self._to_fill.pop(0)
                continue
            row.fill()
            if row.filled:
                self._to_fill.pop(0)
                self._refresh_error()
            return True
        return False

    def pending_rows(self) -> int:
        """How many rows are still waiting for their turn to build."""
        return len(self._to_fill)

    def _focused_slot(self) -> tuple[tuple[int, ...], str] | None:
        widget = QtWidgets.QApplication.focusWidget()
        while widget is not None and widget is not self:
            owner = getattr(widget, "slot_path", None)
            if owner is not None:
                return owner
            widget = widget.parentWidget()
        return None

    def _restore_focus(self) -> None:
        if self._focus_at is None:
            return
        for widget in self.findChildren(QtWidgets.QWidget):
            if getattr(widget, "slot_path", None) == self._focus_at:
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                return

    def _refresh_error(self) -> None:
        first = None
        for line in self._issue_lines():
            if line.message:
                first = line.message
                break
        if first != self._error:
            self._error = first
            self.error_changed.emit(first)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._disabled:
            return
        painter = painter_for(self)
        painter.setOpacity(0.5)
        painter.end()


def _rows_under(widget: QtWidgets.QWidget | None, out: list) -> None:
    """Every condition row at or under a widget of the tree, in the order the rails put them."""
    if widget is None:
        return
    if isinstance(widget, _ConditionRow):
        out.append(widget)
        return
    if not isinstance(widget, _GroupNode):
        return
    column = widget.body().layout()
    for i in range(column.count()):
        _rows_under(column.itemAt(i).widget(), out)


class _Moved(ThemedWidget):
    """A part of the tree that can change hands inside the editor without reading the theme again.

    A parent change has every themed widget under the one that moved read its theme afresh, so
    that a widget built before it joined its host wears the host's palette rather than the one it
    was born under. A row or a group a redraw keeps moves from the tree it replaces into the tree
    that replaces it, under the same editor and so under the same theme, and a tree on its way to
    `deleteLater` paints nothing at all: on the catalogue that walk was 58ms of GUI time in the
    turn that asked for the redraw, which is the whole budget `docs/design-rules.md` gives it.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._holds_theme = False

    def hold_theme(self, value: bool = True) -> None:
        """Keep the theme this widget wears through the moves that follow."""
        self._holds_theme = bool(value)

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        if self._holds_theme and event.type() == QtCore.QEvent.Type.ParentChange:
            QtWidgets.QWidget.changeEvent(self, event)
            return
        super().changeEvent(event)


class _GroupNode(_Moved):
    """A group: a header saying how its rows join, the rows on one rail, and a foot."""

    def __init__(
        self,
        owner: FilterEditor,
        path: Sequence[int],
        node: FilterGroup,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._owner = owner
        self._path = list(path)
        self._node = node
        self._depth = len(self._path)
        self.setObjectName("filter-group")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        pad = NEST_PAD if self._depth else 0
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(pad, pad, pad, pad)
        column.setSpacing(ROW_GAP)

        column.addWidget(self._header())
        self._body = _GroupBody(owner, self._path, node, self)
        column.addWidget(self._body)
        column.addWidget(self._foot())

    def _header(self) -> QtWidgets.QWidget:
        owner = self._owner
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("filter-group-header")
        line = QtWidgets.QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(ROW_GAP)
        line.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if self._depth:
            grip = _grip(holder, owner.size)
            grip.slot_path = (tuple(self._path), "grip")
            line.addWidget(grip)
            self._grip: QtWidgets.QWidget | None = grip
        else:
            self._grip = None

        logic = ToggleGroup(
            items=(("and", "All"), ("or", "Any")),
            value=self._node.logical_operator,
            size=owner.size,
            variant="outline",
            parent=holder,
        )
        self._logic = logic
        logic.setObjectName("filter-logic")
        logic.set_accessible_names({"and": "Match all", "or": "Match any"})
        logic.slot_path = (tuple(self._path), "logic")
        logic.setEnabled(not owner.disabled)
        logic.value_changed.connect(self._on_logic)
        line.addWidget(logic)

        line.addWidget(_Caption("of these match", holder))
        line.addStretch(1)

        if self._depth:
            cross = _cross(holder, owner.size, "Remove group")
            cross.slot_path = (tuple(self._path), "remove")
            cross.setEnabled(not owner.disabled)
            cross.clicked.connect(lambda: owner.remove(self._path))
            line.addWidget(cross)
        return holder

    def _foot(self) -> QtWidgets.QWidget:
        owner = self._owner
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("filter-foot")
        line = QtWidgets.QHBoxLayout(holder)
        line.setContentsMargins(RAIL_INDENT, 0, 0, 0)
        line.setSpacing(FOOT_GAP)

        add_row = Button(
            "Condition", icon="plus", variant="ghost", size=CONTROL_BUTTON[owner.size], parent=holder
        )
        add_row.setObjectName("filter-add-condition")
        add_row.slot_path = (tuple(self._path), "add-condition")
        add_row.setEnabled(not owner.disabled)
        add_row.clicked.connect(
            lambda: owner.append(self._path, make_condition("", "is", ""))
        )
        line.addWidget(add_row)

        add_group = Button(
            "Group", icon="plus", variant="ghost", size=CONTROL_BUTTON[owner.size], parent=holder
        )
        add_group.setObjectName("filter-add-group")
        add_group.slot_path = (tuple(self._path), "add-group")
        add_group.setEnabled(not owner.disabled)
        add_group.clicked.connect(lambda: owner.append(self._path, make_group("or")))
        line.addWidget(add_group)
        line.addStretch(1)
        return holder

    def _on_logic(self, picked: Any) -> None:
        if not picked or picked == self._node.logical_operator:
            return
        self._owner.edit(
            self._path,
            FilterGroup(logical_operator=str(picked), conditions=list(self._node.conditions)),
        )

    def wear(self, node: FilterGroup) -> None:
        """Take the node this group holds now, in place.

        The header, the rail and the foot are the same widgets whatever the rows under them
        are, so a change to the rows leaves them alone and every child the group keeps stays
        where it stands rather than moving into a group built to replace this one.
        """
        self._node = node
        self._logic.set_value(node.logical_operator)
        self._body.wear(node)

    def grip(self) -> QtWidgets.QWidget | None:
        """The handle a nested group is dragged by."""
        return self._grip

    def body(self) -> QtWidgets.QWidget:
        """The rows on the rail."""
        return self._body

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._depth:
            return
        theme = theme_of(self)
        painter = painter_for(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(theme.color("muted"), NEST_WASH))
        radius = float(theme.radius_px("lg"))
        painter.drawRoundedRect(QtCore.QRectF(self.rect()), radius, radius)
        painter.end()


class _GroupBody(ThemedWidget):
    """The children of one group, on the rail that makes a level of nesting one indent."""

    def __init__(
        self,
        owner: FilterEditor,
        path: Sequence[int],
        node: FilterGroup,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._owner = owner
        self._path = list(path)
        self.setObjectName("filter-group-body")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(RAIL_INDENT, 0, 0, 0)
        column.setSpacing(ROW_GAP)
        self._column = column

        self._sortable = SortableRows(self, label_of=self._label_of, parent=self)
        self._sortable.moved.connect(self._on_moved)
        self._sortable.announced.connect(owner.announced.emit)
        self._sortable.set_enabled(not owner.disabled)

        self.wear(node)

    def wear(self, node: FilterGroup) -> None:
        """Draw the children this group holds now, in the order it holds them.

        The rail is this widget whatever stands on it, so a child that was here a moment ago
        is taken out of the column and put back into it: a widget whose parent does not change
        never reads its theme again, and reading it again over a group of rows is what an edit
        cannot afford. What the new node no longer names is dropped at the end.
        """
        owner = self._owner
        column = self._column
        was = [column.itemAt(i).widget() for i in range(column.count())]
        while column.count():
            column.takeAt(0)

        ids: list[str] = []
        widgets: list[QtWidgets.QWidget] = []
        grips: list[QtWidgets.QWidget | None] = []
        for i, child in enumerate(node.conditions):
            at = [*self._path, i]
            kept = owner.reuse(at, child)
            wanted = _GroupNode if child.kind == "group" else _ConditionRow
            if isinstance(kept, wanted):
                made: QtWidgets.QWidget = kept
                # The schema behind the row may have landed since it was drawn.
                refresh = getattr(made, "refresh_issue", None)
                if callable(refresh):
                    refresh()
            elif child.kind == "group":
                # A group that held another node a moment ago wears the new one rather than
                # being built again: its own chrome never depended on the rows under it.
                standing = owner.standing(at)
                if isinstance(standing, _GroupNode):
                    made = standing
                    made.wear(child)
                else:
                    made = _GroupNode(owner, at, child, self)
            else:
                made = _ConditionRow(owner, at, child, self, deferred=not owner.take_row())
            grips.append(made.grip())
            moved = made.parentWidget() is not self
            if moved:
                # It comes out of the tree this one replaces, under the same editor and so
                # under the same theme, and reading that theme again over everything it holds
                # is the one thing a redraw cannot afford.
                made.hold_theme(True)
            column.addWidget(made)
            if moved:
                made.hold_theme(False)
            owner.remember(at, child, made)
            ids.append(str(i))
            widgets.append(made)
        if not node.conditions:
            empty = StateLine(
                state="empty",
                label=owner.empty_label,
                slot_name="filter-group-empty",
                size=owner.size,
                parent=self,
            )
            column.addWidget(empty)
        # `flex flex-col` upstream: a row keeps the height its own controls ask for and the room
        # left over falls to the bottom of the group. Without this a caller whose box is taller
        # than the tree stretches every row into it and the cells no longer read on one line.
        column.addStretch(0)

        # What the new node no longer names goes, whether it was a row, a nested group or the
        # empty line. A widget another group took over is that group's to keep.
        standing_now = {id(one) for one in widgets}
        for widget in was:
            if widget is not None and id(widget) not in standing_now and widget.parentWidget() is self:
                owner.drop(widget)

        self._sortable.set_rows(ids, widgets)
        for i, grip in enumerate(grips):
            if grip is not None:
                self._attach(grip, i)

    def _attach(self, grip: QtWidgets.QWidget, index: int) -> None:
        self._sortable.attach_grip(grip, index)
        grip.setEnabled(not self._owner.disabled and len(self._sortable.ids) > 1)

    def adopt_grip(self, row: QtWidgets.QWidget) -> None:
        """Put the handle of a row built after this group was drawn on the reorder model.

        A deferred row has no handle until its turn comes, so the model is given it then; the
        order itself never changed, so nothing else about the group is drawn again.
        """
        grip = row.grip()
        if grip is None:
            return
        for index, one in enumerate(self._sortable.widgets):
            if one is row:
                self._attach(grip, index)
                return

    def _label_of(self, one: str) -> str:
        try:
            index = int(one)
        except ValueError:
            return one
        return f"Row {index + 1}"

    def _on_moved(self, from_index: int, to_index: int) -> None:
        self._owner.move([*self._path, from_index], to_index - from_index)

    def sortable(self) -> SortableRows:
        """The reorder model this group's rows run on."""
        return self._sortable

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = painter_for(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("border"))
        painter.drawRect(QtCore.QRectF(0.0, 0.0, 1.0, float(self.height())))
        painter.end()
        paint_drop_line(self, self._sortable, theme.color("ring"), gap=ROW_GAP)


class _ConditionRow(_Moved):
    """A row: the field, the operator and the value on one line, the remove on its own axis.

    A deferred row is one skeleton band and nothing else. Everything it draws — the grip, the
    three cells, the issue line and the cross — is built by `fill`, on the turn of the loop the
    editor gives it, because a tree of forty rows cannot afford a single widget it does not yet
    need: the band alone is a third of what the whole row costs to put up.
    """

    def __init__(
        self,
        owner: FilterEditor,
        path: Sequence[int],
        node: FilterCondition,
        parent: QtWidgets.QWidget | None = None,
        deferred: bool = False,
    ) -> None:
        super().__init__(parent)
        self._owner = owner
        self._path = list(path)
        self._node = node
        self._filled = False
        self._grip: QtWidgets.QWidget | None = None
        self._grip_box: QtWidgets.QWidget | None = None
        self._content: QtWidgets.QWidget | None = None
        self._cross_box: QtWidgets.QWidget | None = None
        self._issue: FieldError | None = None
        self._band: QtWidgets.QWidget | None = None
        self._controls: QtWidgets.QHBoxLayout | None = None
        self._half = False
        self._stale: list[QtWidgets.QWidget] = []
        self.setObjectName("filter-row")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(ROW_GAP)
        self._line = line
        # The band is kept for the row's whole life, shown or hidden. A `Skeleton` is a themed
        # widget with an animation of its own and costs more to build than the three cells
        # spend on a keystroke, and a schema read under the tree hands it back to forty rows at
        # once (`empty`).
        self._waiting = self._skeleton_band(self)
        line.addWidget(self._waiting)

        if not deferred:
            self.build()

    def _skeleton_band(self, parent: QtWidgets.QWidget) -> Skeleton:
        """What stands where the row will, at the row's own height."""
        made = Skeleton(parent=parent)
        made.setObjectName("filter-row-skeleton")
        made.setFixedHeight(CONTROL_HEIGHT[self._owner.size])
        return made

    @property
    def filled(self) -> bool:
        """True once the row stands where the skeleton was."""
        return self._filled

    def empty(self) -> None:
        """Put the skeleton back over cells the schema has changed under.

        Taking the cells down costs as much as building them, so they are only hidden: forty
        rows are three hidden widgets each and one relayout, and the turn that asks for it
        carries nothing else. What is hidden is freed when the new cells stand in its place.
        """
        if self._half:
            # It is between its two turns, so what it has built stands on the schema that
            # changed and never reaches the line. It goes and the row starts over.
            self._half = False
            for widget in (self._grip_box, self._content, self._cross_box):
                if widget is not None:
                    self._owner.drop(widget)
            self._grip = self._grip_box = self._content = self._cross_box = None
            self._issue = None
            self._band = None
            self._controls = None
        if not self._filled:
            return
        self._filled = False
        for widget in (self._grip_box, self._content, self._cross_box):
            if widget is not None:
                widget.hide()
                self._stale.append(widget)
        self._grip = None
        self._grip_box = None
        self._content = None
        self._cross_box = None
        self._issue = None
        self._band = None
        self._waiting.set_animated(True)
        self._waiting.show()

    def fill(self) -> None:
        """Build the next part of the row. It takes two turns of the loop.

        A row is a field picker, an operator menu and a value control, each with a popup window
        of its own. The value control is two thirds of that on the rows that draw an entity
        picker or a relative window — 28ms of a 38ms row on the catalogue — so it takes a turn
        to itself. Nothing the row builds reaches the line until both turns are done, so the
        reader sees the skeleton and then the row, never half of one.
        """
        if self._filled:
            return
        if not self._half:
            self._draw_chrome()
            self._half = True
            return
        self._draw_value()
        self._half = False
        self._filled = True

    def build(self) -> None:
        """Build the whole row in this turn, however many the editor would have given it."""
        for _ in range(ROW_TURNS):
            if self._filled:
                return
            self.fill()

    def _draw_chrome(self) -> None:
        """The grip, the field, the operator, the issue line and the cross, off the line.

        None of it is put on the row's line yet: a widget with a parent is hidden until a
        layout shows it, so the skeleton is what stands while the value control is built.
        """
        owner = self._owner

        self._grip = _grip(self, owner.size)
        self._grip.slot_path = (tuple(self._path), "grip")
        # The grip and the cross hold the row's own axis at every height, so a value that
        # grows onto several lines never moves them off the first one.
        self._grip_box = _axis_box(self._grip, owner.size, self)

        content = QtWidgets.QWidget(self)
        content.setObjectName("filter-row-content")
        content.setMinimumWidth(0)
        stack = QtWidgets.QVBoxLayout(content)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(FOOT_GAP)

        band = QtWidgets.QWidget(content)
        band.setObjectName("filter-row-controls")
        band.setMinimumWidth(0)
        controls = QtWidgets.QHBoxLayout(band)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(ROW_GAP)
        field = self._field_slot(band)
        operator = self._operator_slot(band)
        controls.addWidget(field, 1)
        controls.addWidget(operator)
        self._band = band
        self._controls = controls
        stack.addWidget(band)

        self._issue = FieldError(self._issue_message(), None, content)
        self._issue.setObjectName("filter-issue")
        stack.addWidget(self._issue)
        self._content = content

        cross = _cross(self, owner.size, "Remove condition")
        cross.slot_path = (tuple(self._path), "remove")
        cross.setEnabled(not owner.disabled)
        cross.clicked.connect(lambda: owner.remove(self._path))
        # `self-start` on the cross's own box upstream: it keeps the axis of the row's first
        # line, so a value grown onto three lines leaves it beside the first of them rather
        # than floating to the middle of the row.
        self._cross_box = _axis_box(cross, owner.size, self)

    def _draw_value(self) -> None:
        """The value control, and the whole row onto its line."""
        owner = self._owner
        line = self._line
        band = self._band
        controls = self._controls
        values = self._value_slot(band)
        controls.addWidget(values, 2)
        # The three cells keep their own height and sit on the band's first line: a value that
        # grows onto several lines, one per value of an `in`, pushes only the rows under it,
        # and the field and the operator stay level with the first value, the grip and the
        # cross. Upstream's row is `items-start` the same way.
        for i in range(controls.count()):
            cell = controls.itemAt(i).widget()
            if cell is not None:
                controls.setAlignment(cell, Qt.AlignmentFlag.AlignTop)
        self._controls = None

        line.addWidget(self._grip_box, 0, Qt.AlignmentFlag.AlignTop)
        line.addWidget(self._content, 1)
        line.addWidget(self._cross_box, 0, Qt.AlignmentFlag.AlignTop)

        self._waiting.hide()
        self._waiting.set_animated(False)
        stale, self._stale = self._stale, []
        for widget in stale:
            line.removeWidget(widget)
            owner.drop(widget)

        # The group drew its reorder model before this row had a handle, so the handle joins it
        # now rather than on the next redraw.
        holder = self.parentWidget()
        if isinstance(holder, _GroupBody):
            holder.adopt_grip(self)

    def grip(self) -> QtWidgets.QWidget | None:
        """The handle the row is dragged by, once the row is built."""
        return self._grip

    def node(self) -> FilterCondition:
        """The condition the tree holds now, which a control read a moment ago may pre-date."""
        found = self._owner.node_at(self._path)
        return found if found is not None and found.kind == "condition" else self._node

    def issue_line(self) -> FieldError | None:
        """The line under the row, once the row is built."""
        return self._issue

    def refresh_issue(self) -> None:
        """Read the line under the row again. A row still on its skeleton says nothing yet."""
        if self._issue is not None:
            self._issue.set_message(self._issue_message())

    def _issue_message(self) -> str | None:
        owner = self._owner
        node = self.node()
        if owner.unresolved(node.path):
            return None
        field: Any = NO_SCHEMA
        if node.path:
            field = owner.field_of(node.path)
            if field is None and "." not in node.path and not owner.fields():
                field = NO_SCHEMA
        found = validate_condition(node, field)
        return found[0].message if found else None

    # --- the three cells ------------------------------------------------------------------

    def _field_slot(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        owner = self._owner
        holder = QtWidgets.QWidget(parent)
        holder.setObjectName("filter-field")
        holder.setMinimumWidth(FIELD_MIN_WIDTH)
        holder.setMaximumWidth(FIELD_MAX_WIDTH)
        box = QtWidgets.QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        if owner.field_chooser is not None:
            made = owner.field_chooser(
                entity_type=owner.entity_type,
                path=self._node.path,
                hide_paths=owner.hide_paths,
                filterable_only=True,
                disabled=owner.disabled,
                on_select=lambda chosen: owner.pick_field(self._path, self.node(), chosen),
            )
        else:
            made = FieldPicker(
                context=owner.context,
                entity_type=owner.entity_type,
                hide_paths=owner.hide_paths,
                disabled=owner.disabled,
                value=self._node.path,
                deep_links=True,
                filterable_only=True,
                clearable=False,
                size=owner.size,
                placeholder="Select a field",
                parent=holder,
            )
            made.value_changed.connect(
                lambda chosen: owner.pick_field(self._path, self.node(), chosen)
            )
        made.slot_path = (tuple(self._path), "field")
        box.addWidget(made)
        return holder

    def _operator_slot(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        owner = self._owner
        field = owner.field_of(self._node.path)
        data_type = field.data_type if field is not None else ""
        operators = field_operators(field)
        menu = operator_menu(data_type, operators)
        current = preset_id_of(self._node, data_type)
        found = preset_by_id(data_type, current, operators)

        select = Select(value=current, size=owner.size, parent=parent)
        select.setObjectName("filter-operator")
        select.slot_path = (tuple(self._path), "operator")
        select.setFixedWidth(OPERATOR_WIDTH)
        select.set_groups([(run.label, [(p.id, p.label) for p in run.presets]) for run in menu])
        select.set_value(current)
        select.set_placeholder(found.label if found is not None else current)
        select.setEnabled(not owner.disabled and len(menu) > 0)
        select.value_changed.connect(
            lambda picked: owner.pick_preset(self._path, self.node(), str(picked))
        )
        return select

    def _value_slot(self, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        owner = self._owner
        holder = QtWidgets.QWidget(parent)
        holder.setObjectName("filter-value")
        holder.setMinimumWidth(0)
        line = QtWidgets.QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(ROW_GAP)
        made = _value_widget(owner, self._path, self.node(), holder)
        if made is not None:
            made.slot_path = (tuple(self._path), "value")
            _place(line, made)
        return holder


# --- the value editors ---------------------------------------------------------------------




def _value_widget(  # noqa: C901, PLR0911, PLR0912
    owner: FilterEditor,
    path: Sequence[int],
    node: FilterCondition,
    parent: QtWidgets.QWidget,
) -> QtWidgets.QWidget | None:
    """The control one row draws, chosen by the operator's arity and the field's data type."""
    field = owner.field_of(node.path)
    data_type = field.data_type if field is not None else ""
    kind = value_editor_for(data_type, node.operator)
    arity = condition_arity(node, data_type)
    disabled = owner.disabled

    def commit(value: Any) -> None:
        owner.set_condition_value(path, value)

    if owner.unresolved(node.path):
        skeleton = Skeleton(parent=parent)
        skeleton.setFixedHeight(CONTROL_HEIGHT[owner.size])
        return skeleton
    if owner.value_editor is not None:
        # Integration point: a caller's own editors replace every one below.
        return owner.value_editor(
            field=field,
            data_type=data_type,
            operator=node.operator,
            value=node.value,
            arity=arity,
            disabled=disabled,
            on_change=commit,
        )
    if arity == "none":
        # `is empty` and the calendar presets pin their value; there is nothing to edit.
        return None
    if arity == "relative":
        return _RelativeValue(owner, node.value, commit, parent)
    if kind == "entity":
        if owner.entity_editor is not None:
            return owner.entity_editor(
                field=field,
                data_type=data_type,
                operator=node.operator,
                value=node.value,
                arity=arity,
                disabled=disabled,
                on_change=commit,
            )
        types = list(field.valid_types) if field is not None and field.valid_types else [
            owner.entity_type
        ]
        if arity == "many":
            picker: Any = EntityMultiPicker(
                entity_types=types,
                context=owner.context,
                value=_entity_refs(node.value),
                project_id=owner.project_id,
                size=owner.size,
                disabled=disabled,
                placeholder="Search entities",
                parent=parent,
            )
            picker.value_changed.connect(lambda refs, _rows=None: commit(list(refs or [])))
            return picker
        picker = EntityPicker(
            entity_types=types,
            context=owner.context,
            value=_entity_ref(node.value),
            project_id=owner.project_id,
            size=owner.size,
            disabled=disabled,
            placeholder="Search entities",
            parent=parent,
        )
        picker.value_changed.connect(lambda ref, _row=None: commit(ref if ref else ""))
        return picker
    if kind == "checkbox":
        editor = CheckboxEditor(
            value=node.value is True,
            field=field,
            size=owner.size,
            disabled=disabled,
            parent=parent,
        )
        editor.committed.connect(lambda next_value: commit(bool(next_value)))
        return editor
    if kind == "options" and data_type == "status_list":
        entity_type = field.entity_type if field is not None else owner.entity_type
        name = field.name if field is not None else None
        if arity == "many":
            statuses: Any = StatusMultiPicker(
                context=owner.context,
                entity_type=entity_type or owner.entity_type,
                field=name,
                project_id=owner.project_id,
                value=_codes_of(node.value),
                size=owner.size,
                disabled=disabled,
                parent=parent,
            )
            statuses.value_changed.connect(lambda codes: commit(list(codes or [])))
            return statuses
        statuses = StatusPicker(
            context=owner.context,
            entity_type=entity_type or owner.entity_type,
            field=name,
            project_id=owner.project_id,
            value=node.value if isinstance(node.value, str) and node.value else None,
            size=owner.size,
            disabled=disabled,
            parent=parent,
        )
        statuses.value_changed.connect(lambda code: commit(code or ""))
        return statuses
    if kind == "options":
        if arity == "many":
            listed: Any = ListMultiPicker(
                value=_codes_of(node.value),
                field=field,
                project_id=owner.project_id,
                size=owner.size,
                disabled=disabled,
                placeholder="Select values…",
                parent=parent,
            )
            listed.value_changed.connect(lambda codes: commit(list(codes or [])))
            return listed
        listed = ListPicker(
            value=node.value if isinstance(node.value, str) and node.value else None,
            field=field,
            project_id=owner.project_id,
            size=owner.size,
            disabled=disabled,
            placeholder="Select a value…",
            parent=parent,
        )
        listed.value_changed.connect(lambda code: commit(code or ""))
        return listed
    label = field.display_name if field is not None else "Value"
    if arity == "two":
        return _TwoValues(owner, kind, data_type, node.value, commit, parent)
    if arity == "many":
        return _ListValues(owner, kind, data_type, label, node.value, commit, parent)
    return _scalar_editor(owner, kind, data_type, label, node.value, commit, parent)


def _scalar_editor(  # noqa: PLR0911
    owner: FilterEditor,
    kind: str,
    data_type: str,
    label: str,
    value: Any,
    commit: Callable[[Any], None],
    parent: QtWidgets.QWidget,
) -> QtWidgets.QWidget:
    """One value editor sized for a row: a typed type takes the width its content needs."""
    field = FieldSchema(
        name="", display_name=label, entity_type="", data_type=data_type or "text",
        editable=True, mandatory=False, unique=False,
    )
    size = owner.size
    disabled = owner.disabled
    if kind == "number":
        made: Any = NumberEditor(
            value=_number_value(value),
            data_type=numeric_type(data_type),
            field=field,
            inline=True,
            size=size,
            disabled=disabled,
            parent=parent,
        )
    elif kind == "date":
        made = DateEditor(
            value=_text_value(value), field=field, inline=True, size=size,
            disabled=disabled, parent=parent,
        )
    elif kind == "date_time":
        made = DateTimeEditor(
            value=_text_value(value), field=field, inline=True, hint=False, size=size,
            disabled=disabled, parent=parent,
        )
    elif kind == "color":
        made = ColorEditor(
            value=_text_value(value), field=field, hint=False, size=size,
            disabled=disabled, parent=parent,
        )
        made.setFixedWidth(COLOR_WIDTH)
        # A colour takes the width its two fields need, so the row's free width is not its.
        made.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed, made.sizePolicy().verticalPolicy()
        )
    elif kind == "url":
        # The row compares the link itself, so the editor's name half is left out of the value.
        href = _text_value(value)
        made = UrlEditor(
            value={"url": str(href)} if href else None, field=field, size=size,
            disabled=disabled, parent=parent,
        )
        made.committed.connect(
            lambda next_value: commit(
                (next_value or {}).get("url", "") if isinstance(next_value, dict)
                else getattr(next_value, "url", "") or ""
            )
        )
        return made
    else:
        made = TextEditor(
            value=_text_value(value), field=field, size=size, disabled=disabled, parent=parent
        )
    made.committed.connect(lambda next_value: commit("" if next_value is None else next_value))
    return made


class _ListValues(QtWidgets.QWidget):
    """A list of values, one to a line, each in its data type's control with a cross.

    The lines are this control's own. A value typed into one needs no new line, so the tree is
    left standing where it is (`FilterEditor.set_condition_value`); adding a value and taking one
    away change how many lines there are, and upstream renders those from the new value, so the
    lines are drawn again here rather than by rebuilding the row and the caret with it.
    """

    def __init__(
        self,
        owner: FilterEditor,
        kind: str,
        data_type: str,
        label: str,
        value: Any,
        commit: Callable[[Any], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-list")
        self.setMinimumWidth(0)
        self._owner = owner
        self._kind = kind
        self._data_type = data_type
        self._label = label
        self._commit = commit
        self._values = condition_list(value)
        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(ROW_GAP)
        self._draw()

    @property
    def values(self) -> list:
        """The values the lines hold, in order."""
        return list(self._values)

    def _apply(self, next_values: list) -> None:
        """Take the new list, tell the tree, and draw the lines it now needs."""
        self._values = list(next_values)
        self._commit(self._values)
        self._draw()

    def _clear(self) -> None:
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
                continue
            inner = item.layout()
            if inner is not None:
                while inner.count():
                    held = inner.takeAt(0)
                    child = held.widget()
                    if child is not None:
                        child.setParent(None)
                        child.deleteLater()
                inner.setParent(None)

    def _draw(self) -> None:
        owner = self._owner
        self._clear()
        for i, item in enumerate(self._values):
            line = QtWidgets.QWidget(self)
            line.setObjectName("filter-list-value")
            row = QtWidgets.QHBoxLayout(line)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(FOOT_GAP + 2)
            _place(
                row,
                _scalar_editor(
                    owner,
                    self._kind,
                    self._data_type,
                    self._label,
                    item,
                    # A typed value replaces one line and draws no new one, so the tree alone
                    # is told: redrawing here would take the caret with it.
                    lambda next_value, at=i: self._typed(at, next_value),
                    line,
                ),
            )
            cross = _cross(line, owner.size, "Remove value")
            cross.setObjectName("filter-list-remove")
            cross.setEnabled(not owner.disabled)
            cross.clicked.connect(lambda at=i: self._apply(without_list_value(self._values, at)))
            row.addWidget(cross)
            row.addStretch(1)
            self._column.addWidget(line)
        add = Button(
            "Value", icon="plus", variant="ghost", size=CONTROL_BUTTON[owner.size], parent=self
        )
        add.setObjectName("filter-list-add")
        add.setEnabled(not owner.disabled)
        add.clicked.connect(lambda: self._apply(with_added_list_value(self._values)))
        holder = QtWidgets.QHBoxLayout()
        holder.setContentsMargins(0, 0, 0, 0)
        holder.setSpacing(0)
        holder.addWidget(add)
        holder.addStretch(1)
        self._column.addLayout(holder)

    def _typed(self, at: int, next_value: Any) -> None:
        self._values = with_list_value(self._values, at, next_value)
        self._commit(self._values)


class _TwoValues(QtWidgets.QWidget):
    """Both ends of a range on one line, joined by the word that reads it."""

    def __init__(
        self,
        owner: FilterEditor,
        kind: str,
        data_type: str,
        value: Any,
        commit: Callable[[Any], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-range")
        self.setMinimumWidth(0)
        pair = list(value) if isinstance(value, list) and len(value) == 2 else [None, None]
        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(ROW_GAP)
        line.addWidget(
            _scalar_editor(
                owner, kind, data_type, "From", pair[0],
                lambda next_value: commit([next_value, pair[1]]), self,
            )
        )
        line.addWidget(_Caption("and", self))
        line.addWidget(
            _scalar_editor(
                owner, kind, data_type, "To", pair[1],
                lambda next_value: commit([pair[0], next_value]), self,
            )
        )
        line.addStretch(1)


class _RelativeValue(QtWidgets.QWidget):
    """A window is a count and a unit: the number editor and the list a `list` field uses."""

    def __init__(
        self,
        owner: FilterEditor,
        value: Any,
        commit: Callable[[Any], None],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-window")
        window = relative_window(value)
        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(ROW_GAP)

        count = NumberEditor(
            value=window.count,
            data_type="number",
            field=FieldSchema(
                name="", display_name="Count", entity_type="", data_type="number",
                editable=True, mandatory=True, unique=False,
            ),
            inline=True,
            min=1,
            size=owner.size,
            disabled=owner.disabled,
            parent=self,
        )
        count.setFixedWidth(COUNT_WIDTH)
        count.committed.connect(
            lambda next_value: commit(
                with_relative_window(value, count=None if next_value is None else float(next_value))
            )
        )
        line.addWidget(count)

        unit = ListPicker(
            value=window.unit,
            field=time_unit_field(),
            size=owner.size,
            disabled=owner.disabled,
            parent=self,
        )
        unit.setFixedWidth(UNIT_WIDTH)
        unit.value_changed.connect(
            lambda picked: commit(with_relative_window(value, unit=picked or "DAY"))
        )
        line.addWidget(unit)
        line.addStretch(1)


# --- the small parts -------------------------------------------------------------------------


class _Caption(ThemedWidget):
    """One muted 12px run: the words that join a header or a range."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(theme_of(self).font(12))
        return QtCore.QSize(metrics.horizontalAdvance(self._text), metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setFont(theme_of(self).font(12))
        painter.setPen(theme_of(self).color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()


def _place(line: QtWidgets.QHBoxLayout, widget: QtWidgets.QWidget) -> None:
    """Put a control in a row: one that expands takes the room, one that does not keeps its width.

    A number, a date and a colour take the width their content needs, so the free width goes to
    the controls that hold a name (`docs/design-rules.md` rule 2).
    """
    expands = widget.sizePolicy().horizontalPolicy() in (
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.MinimumExpanding,
    )
    if expands:
        line.addWidget(widget, 1)
        return
    line.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)


def _axis_box(
    widget: QtWidgets.QWidget, size: str, parent: QtWidgets.QWidget
) -> QtWidgets.QWidget:
    """One control held on the axis of a row's first line, whatever the row grew to.

    Upstream puts the remove control in a `flex items-center self-start h-8` box, so a row whose
    value has grown onto three lines keeps the cross beside the first of them rather than letting
    it drift to the middle (`filter-editor.tsx`, the `ConditionRow` and `GroupHeader` boxes). The
    grip rides the same axis, so the pair reads as one.
    """
    holder = QtWidgets.QWidget(parent)
    holder.setObjectName("filter-row-axis")
    holder.setFixedHeight(CONTROL_HEIGHT[size])
    holder.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
    inner = QtWidgets.QHBoxLayout(holder)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(0)
    widget.setParent(holder)
    inner.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
    return holder


def _grip(parent: QtWidgets.QWidget, size: str) -> Button:
    """The mark a row is dragged by, and the handle Alt with an arrow moves it from."""
    made = Button(
        "", icon="grip-vertical", variant="ghost", size=ICON_BUTTON[size], parent=parent
    )
    made.setObjectName("filter-grip")
    made.setToolTip("Drag to reorder, or hold Alt and press the arrow keys")
    made.setAccessibleName("Reorder")
    return made


def _cross(parent: QtWidgets.QWidget, size: str, label: str) -> RemoveControl:
    """The control that removes a row, a group or a value.

    `REMOVE_CONTROL`, not a button: the cross and its 2px and nothing more, so it sits level
    with the controls in the row rather than standing a button's height over them. The hit box
    rule 3 asks for is centred on it and takes no room.
    """
    made = RemoveControl(step=CROSS_SIZE[size], label=label, parent=parent)
    made.setObjectName("filter-remove")
    return made
