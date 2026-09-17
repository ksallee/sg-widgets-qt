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
    FilterCondition,
    FilterGroup,
    FilterNode,
    condition as make_condition,
    empty_filter,
    group as make_group,
)
from sg_widgets_core.filter_ux import (
    NO_SCHEMA,
    append_at,
    apply_preset,
    condition_arity,
    condition_list,
    default_condition,
    field_operators,
    move_at,
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

from ..primitives.base import CHIP_CROSS, CONTROL_HEIGHT, ThemedWidget, painter_for
from ..primitives.button import Button
from ..primitives.checkbox import ToggleGroup
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

#: `w-40` of the operator select, and the room the value keeps whatever it draws.
OPERATOR_WIDTH = 160
VALUE_MIN_WIDTH = 160

#: `border-l pl-3`: the rail a level of nesting hangs off, and the indent it costs.
RAIL_INDENT = 12

#: `p-2` and `bg-muted/40` of a nested group's own surface.
NEST_PAD = 8
NEST_WASH = 0.4

#: Between a group's header, its rows and its foot, and between the controls of a row.
ROW_GAP = 8

#: Between the two controls of the foot, which read as one run.
FOOT_GAP = 4

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


def _entity_refs(value: Any) -> list[Any]:
    """`is` takes one entity hash and `in` a list of them; a list under `is` is a 400."""
    if isinstance(value, list):
        return [one for one in value if isinstance(one, dict)]
    return [value] if isinstance(value, dict) else []


def _entity_ref(value: Any) -> Any:
    return value if isinstance(value, dict) else None


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


class _EditorContext:
    """Everything a row needs that does not come from its own node."""

    def __init__(self, owner: FilterEditor) -> None:
        self.owner = owner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.owner, name)


class FilterEditor(QtWidgets.QWidget):
    """A filter tree, edited.

    The tree is rebuilt on every change, so a row is addressed by its path in the tree and
    never by the widget that drew it a moment ago. Keyboard focus is put back on the control
    it left.
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
        self._leaves: dict[str, FieldSchema | None] = {}
        self._resolving: set[str] = set()
        self._fields_ticket = Ticket()
        self._error: str | None = None
        self._focus_at: tuple[tuple[int, ...], str] | None = None
        self._root_node: _GroupNode | None = None

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self._column = column
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        self._read_fields()
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
        """True while a dotted path is still being walked; its leaf decides the whole row."""
        return "." in path and path not in self._leaves

    def _read_fields(self) -> None:
        schema = schema_of(self._context) if self._context is not None else None
        if schema is None or not self._entity_type:
            return
        token = self._fields_ticket.next()
        default_pool().submit(
            schema.fields,
            self._entity_type,
            on_result=self._fields_read,
            on_error=lambda _error: None,
            ticket=(self._fields_ticket, token),
        )

    def _fields_read(self, found: Any) -> None:
        self._fields = dict(found or {})
        self._rebuild()

    def _resolve_leaf(self, path: str) -> None:
        schema = schema_of(self._context) if self._context is not None else None
        if schema is None or not path or path in self._leaves or path in self._resolving:
            return
        self._resolving.add(path)
        default_pool().submit(
            schema.resolve_path,
            self._entity_type,
            path,
            on_result=lambda segments, at=path: self._leaf_read(at, segments),
            # A path the schema no longer holds still has to be editable, so the row keeps it.
            on_error=lambda _error, at=path: self._leaf_read(at, None),
        )

    def _leaf_read(self, path: str, segments: Any) -> None:
        self._resolving.discard(path)
        leaf = None
        if segments:
            leaf = getattr(segments[-1], "field", None)
        self._leaves[path] = leaf
        self._rebuild()

    # --- edits ----------------------------------------------------------------------------

    def _commit(self, next_value: FilterGroup) -> None:
        self._value = next_value
        self._rebuild()
        self.changed.emit(next_value)
        self.filters_changed.emit(next_value)

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
        return self.findChildren(QtWidgets.QWidget, "filter-row")

    def issues(self) -> list[str]:
        """The line under every incomplete row, in the order they are drawn."""
        return [line.message for line in self._issue_lines() if line.message]

    def _issue_lines(self) -> list[FieldError]:
        return self.findChildren(FieldError, "filter-issue")

    def _rebuild(self) -> None:
        for path in _dotted_paths(self._value):
            self._resolve_leaf(path)
        pending = getattr(self, "_pending_field", None)
        if pending is not None and pending[2] in self._leaves:
            self._pending_field = None
            self._apply_field(list(pending[0]), pending[1], pending[2], pending[3])
            return
        self._focus_at = self._focused_slot()
        if self._root_node is not None:
            self._column.removeWidget(self._root_node)
            self._root_node.setParent(None)
            self._root_node.deleteLater()
        self._root_node = _GroupNode(self, [], self._value, self)
        self._column.addWidget(self._root_node)
        self.setEnabled(not self._disabled)
        self._refresh_error()
        self._restore_focus()

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


class _GroupNode(ThemedWidget):
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
            parent=holder,
        )
        logic.setObjectName("filter-logic")
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

        self._sortable = SortableRows(self, label_of=self._label_of, parent=self)
        self._sortable.moved.connect(self._on_moved)
        self._sortable.announced.connect(owner.announced.emit)
        self._sortable.set_enabled(not owner.disabled)

        ids: list[str] = []
        widgets: list[QtWidgets.QWidget] = []
        grips: list[QtWidgets.QWidget | None] = []
        for i, child in enumerate(node.conditions):
            at = [*self._path, i]
            if child.kind == "group":
                made: QtWidgets.QWidget = _GroupNode(owner, at, child, self)
                grips.append(made.grip())
            else:
                made = _ConditionRow(owner, at, child, self)
                grips.append(made.grip())
            column.addWidget(made)
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

        self._sortable.set_rows(ids, widgets)
        for i, grip in enumerate(grips):
            if grip is not None:
                self._sortable.attach_grip(grip, i)
                grip.setEnabled(not owner.disabled and len(ids) > 1)

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


class _ConditionRow(ThemedWidget):
    """A row: the field, the operator and the value on one line, the remove on its own axis."""

    def __init__(
        self,
        owner: FilterEditor,
        path: Sequence[int],
        node: FilterCondition,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._owner = owner
        self._path = list(path)
        self._node = node
        self.setObjectName("filter-row")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(ROW_GAP)
        line.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._grip = _grip(self, owner.size)
        self._grip.slot_path = (tuple(self._path), "grip")
        line.addWidget(self._grip)

        content = QtWidgets.QWidget(self)
        content.setObjectName("filter-row-content")
        content.setMinimumWidth(0)
        stack = QtWidgets.QVBoxLayout(content)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(FOOT_GAP)

        controls = QtWidgets.QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(ROW_GAP)
        controls.addWidget(self._field_slot(content), 1)
        controls.addWidget(self._operator_slot(content))
        controls.addWidget(self._value_slot(content), 2)
        stack.addLayout(controls)

        self._issue = FieldError(self._issue_message(), None, content)
        self._issue.setObjectName("filter-issue")
        stack.addWidget(self._issue)
        line.addWidget(content, 1)

        cross = _cross(self, owner.size, "Remove condition")
        cross.slot_path = (tuple(self._path), "remove")
        cross.setEnabled(not owner.disabled)
        cross.clicked.connect(lambda: owner.remove(self._path))
        line.addWidget(cross)

    def grip(self) -> QtWidgets.QWidget:
        """The handle the row is dragged by."""
        return self._grip

    def _issue_message(self) -> str | None:
        owner = self._owner
        if owner.unresolved(self._node.path):
            return None
        field: Any = NO_SCHEMA
        if self._node.path:
            field = owner.field_of(self._node.path)
            if field is None and "." not in self._node.path and not owner.fields():
                field = NO_SCHEMA
        found = validate_condition(self._node, field)
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
                on_select=lambda chosen: owner.pick_field(self._path, self._node, chosen),
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
                lambda chosen: owner.pick_field(self._path, self._node, chosen)
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
            lambda picked: owner.pick_preset(self._path, self._node, str(picked))
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
        made = _value_widget(owner, self._path, self._node, holder)
        if made is not None:
            made.slot_path = (tuple(self._path), "value")
            line.addWidget(made, 1)
        line.addStretch(0)
        return holder


# --- the value editors ---------------------------------------------------------------------


def _set_value(owner: FilterEditor, path: Sequence[int], node: FilterCondition, value: Any) -> None:
    owner.edit(path, FilterCondition(path=node.path, operator=node.operator, value=value))


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
        _set_value(owner, path, node, value)

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
    """A list of values, one to a line, each in its data type's control with a cross."""

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
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(ROW_GAP)
        items = condition_list(value)
        for i, item in enumerate(items):
            line = QtWidgets.QWidget(self)
            line.setObjectName("filter-list-value")
            row = QtWidgets.QHBoxLayout(line)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(FOOT_GAP + 2)
            row.addWidget(
                _scalar_editor(
                    owner,
                    kind,
                    data_type,
                    label,
                    item,
                    lambda next_value, at=i: commit(with_list_value(value, at, next_value)),
                    line,
                ),
                1,
            )
            cross = _cross(line, owner.size, "Remove value")
            cross.setObjectName("filter-list-remove")
            cross.setEnabled(not owner.disabled)
            cross.clicked.connect(lambda at=i: commit(without_list_value(value, at)))
            row.addWidget(cross)
            column.addWidget(line)
        add = Button(
            "Value", icon="plus", variant="ghost", size=CONTROL_BUTTON[owner.size], parent=self
        )
        add.setObjectName("filter-list-add")
        add.setEnabled(not owner.disabled)
        add.clicked.connect(lambda: commit(with_added_list_value(value)))
        holder = QtWidgets.QHBoxLayout()
        holder.setContentsMargins(0, 0, 0, 0)
        holder.setSpacing(0)
        holder.addWidget(add)
        holder.addStretch(1)
        column.addLayout(holder)


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


def _grip(parent: QtWidgets.QWidget, size: str) -> Button:
    """The mark a row is dragged by, and the handle Alt with an arrow moves it from."""
    made = Button(
        "", icon="grip-vertical", variant="ghost", size=ICON_BUTTON[size], parent=parent
    )
    made.setObjectName("filter-grip")
    made.setToolTip("Drag to reorder, or hold Alt and press the arrow keys")
    made.setAccessibleName("Reorder")
    return made


def _cross(parent: QtWidgets.QWidget, size: str, label: str) -> Button:
    """The control that removes a row, a group or a value."""
    made = Button("", icon="x", variant="ghost", size=ICON_BUTTON[size], parent=parent)
    made.setObjectName("filter-remove")
    made.setAccessibleName(label)
    made.setToolTip(label)
    made.setFixedWidth(max(24, CHIP_CROSS[CROSS_SIZE[size]] + 12))
    return made
