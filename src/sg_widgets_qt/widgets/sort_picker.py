"""The `sort` a query carries, as an ordered list.

Ported from `packages/react/src/registry/sg/components/sort-picker.tsx` and its Svelte twin.
Each key is a field and a direction; the list serialises to the comma-joined string a search
takes, a leading `-` marking a descending key (026_result_order). Order is meaningful: the first
key wins, and id ascending breaks every remaining tie whether or not it is in the list.

A key may be a dotted path, so the field list descends through links. An unsortable or unknown
field is a silent 200 no-op with the rows in default order, so only types that sort are offered.

    picker = SortPicker(entity_type="Version", context=context, value=[SortKey("code", "asc")])
    picker.changed.connect(apply)
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.filter_ux import SortKey, is_sortable, to_sort_string
from sg_widgets_core.pickers import friendly_field_path
from sg_widgets_core.schema import FieldSchema

from ..primitives.base import ThemedWidget, elide, painter_for
from ..primitives.button import Button
from ..primitives.checkbox import ToggleGroup
from ..primitives.label import Separator
from ..primitives.popover import Popover
from ..theme import theme_of
from ..workers import default_pool
from ._sortable_rows import SortableRows, paint_drop_line
from .field_picker import FieldPicker, schema_of
from .state_line import StateLine

__all__ = [
    "SORT_PICKER_SIZE_VALUES",
    "SORT_POPOVER_WIDTH",
    "SortPicker",
]

#: `size`: the control ladder the trigger stands on.
SORT_PICKER_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")

#: `w-96` of the popover, and the `p-3` inside it.
SORT_POPOVER_WIDTH = 384
POPOVER_PAD = 12

#: Between the sections of the popover, and between the controls of a key row.
SECTION_GAP = 12
ROW_GAP = 8

#: `px-2 py-0.5` of a key row: rule 2's list-row inset for a row holding icon buttons.
KEY_PAD_X = 8
KEY_PAD_Y = 2

#: The count beside the label is a chip, so it takes the step under the control.
COUNT_CHIP_SIZE: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: The button step beside a control of each height.
CONTROL_BUTTON: dict[str, str] = {"sm": "sm", "md": "default", "lg": "lg"}

#: The line the list shows when nothing is chosen.
EMPTY_LABEL = "No sort. Rows come back id ascending."
EMPTY_GLYPH = "arrow-up-down"


class SortPicker(QtWidgets.QWidget):
    """The ordered sort keys, their directions, and the field picker that adds one."""

    #: The keys and the `sort` string they serialise to.
    changed = Signal(object, str)
    #: The same payload under the name the query widgets share.
    sort_changed = Signal(object)
    #: The popover opened or closed.
    open_changed = Signal(bool)
    #: One line for the live region, from core's sortable announcements.
    announced = Signal(str)

    def __init__(
        self,
        entity_type: str = "",
        context: Any = None,
        value: Sequence[SortKey] | None = None,
        hide_paths: Sequence[str] | None = None,
        paths: Sequence[str] | None = None,
        size: str = "md",
        disabled: bool = False,
        open: bool = False,  # noqa: A002
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sort-picker")
        self._entity_type = str(entity_type or "")
        self._context = context
        self._value: list[SortKey] = list(value or [])
        self._hide_paths = list(hide_paths or [])
        self._paths = list(paths) if paths is not None else None
        self._size = size if size in SORT_PICKER_SIZE_VALUES else "md"
        self._disabled = bool(disabled)
        self._open = False
        self._labels: dict[str, str] = {}
        self._resolving: set[str] = set()
        self._announcement = ""

        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)

        # The count is part of the trigger: a chip inside its own border, a glyph gap from
        # the keys it names.
        self._trigger = _SortTrigger(self._size, self)
        self._trigger.clicked.connect(self.toggle)
        line.addWidget(self._trigger)
        line.addStretch(1)

        self._panel = QtWidgets.QWidget()
        self._panel.setObjectName("sort-panel")
        panel = QtWidgets.QVBoxLayout(self._panel)
        panel.setContentsMargins(POPOVER_PAD, POPOVER_PAD, POPOVER_PAD, POPOVER_PAD)
        panel.setSpacing(SECTION_GAP)

        self._keys = _SortKeys(self, self._panel)
        panel.addWidget(self._keys)
        panel.addWidget(Separator(parent=self._panel))

        self._field_picker = FieldPicker(
            context=context,
            entity_type=self._entity_type,
            hide_paths=self._hide_paths,
            disabled=self._disabled,
            value="",
            deep_links=True,
            clearable=False,
            size=self._size,
            filter=self.offers,
            placeholder="Add a field",
            search_placeholder="Add a field…",
            empty_label="No field left to sort on",
            parent=self._panel,
        )
        self._field_picker.setObjectName("sort-add-field")
        self._field_picker.value_changed.connect(self._on_add)
        panel.addWidget(self._field_picker)

        self._popover = Popover(
            self._trigger, self._panel, side="bottom", align="start", width=SORT_POPOVER_WIDTH
        )
        self._popover.closed.connect(self._on_closed)
        self._popover.dismissed.connect(self._on_closed)
        self._popover.add_pass_through(self._field_picker.control.popup())

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self._refresh()
        if open:
            self.set_open(True)

    # --- props ----------------------------------------------------------------------------

    @property
    def entity_type(self) -> str:
        """Type the field list is read on."""
        return self._entity_type

    def set_entity_type(self, value: str) -> None:
        self._entity_type = str(value or "")
        self._field_picker.set_entity_type(self._entity_type)
        self._labels = {}
        self._refresh()

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._field_picker.set_context(value)
        self._labels = {}
        self._refresh()

    @property
    def value(self) -> list[SortKey]:
        """The ordered keys."""
        return list(self._value)

    def set_value(self, value: Sequence[SortKey] | None) -> None:
        """Take the keys from outside. Nothing is emitted."""
        self._value = list(value or [])
        self._refresh()

    @property
    def sort(self) -> str:
        """The `sort` string the keys serialise to."""
        return to_sort_string(self._value)

    @property
    def hide_paths(self) -> list[str]:
        """Paths kept out of the field list."""
        return list(self._hide_paths)

    def set_hide_paths(self, value: Sequence[str] | None) -> None:
        self._hide_paths = list(value or [])
        self._field_picker.set_hide_paths(self._hide_paths)

    @property
    def paths(self) -> list[str] | None:
        """Only these paths are offered; a link stays while a path runs through it."""
        return list(self._paths) if self._paths is not None else None

    def set_paths(self, value: Sequence[str] | None) -> None:
        self._paths = list(value) if value is not None else None
        self._field_picker.set_filter(self.offers)

    @property
    def size(self) -> str:
        """The control ladder the trigger and the field picker stand on."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in SORT_PICKER_SIZE_VALUES else "md"
        self._trigger.set_size(self._size)
        self._field_picker.set_size(self._size)
        self._refresh()

    @property
    def disabled(self) -> bool:
        """Blocks the trigger, the key rows and the field picker."""
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self._trigger.setEnabled(not self._disabled)
        self._field_picker.set_disabled(self._disabled)
        if self._disabled:
            self.set_open(False)
        self._refresh()

    @property
    def open(self) -> bool:
        """Whether the popover is showing."""
        return self._open

    def set_open(self, value: bool) -> None:
        """Show or hide the list."""
        want = bool(value) and not self._disabled
        if want == self._open:
            return
        self._open = want
        if want:
            self._popover.open()
        else:
            self._popover.close()
        self._trigger.set_expanded(want)
        self.open_changed.emit(want)

    def toggle(self) -> None:
        """Open a closed list, close an open one."""
        self.set_open(not self._open)

    # --- the parts ------------------------------------------------------------------------

    def trigger(self) -> QtWidgets.QWidget:
        """The button that opens the list."""
        return self._trigger

    def field_picker(self) -> FieldPicker:
        """The picker that adds a key."""
        return self._field_picker

    def key_rows(self) -> QtWidgets.QWidget:
        """The column the keys are drawn in."""
        return self._keys

    @property
    def announcement(self) -> str:
        """The last line put in the live region."""
        return self._announcement

    def name_of(self, path: str) -> str:
        """The friendly label of a path, or the path until the read answers."""
        return self._labels.get(path, path)

    # --- edits ----------------------------------------------------------------------------

    def _commit(self, keys: Sequence[SortKey]) -> None:
        self._value = list(keys)
        self._refresh()
        self.changed.emit(list(self._value), to_sort_string(self._value))
        self.sort_changed.emit(list(self._value))

    def add(self, path: str) -> None:
        """Append a key on a path, ascending."""
        if path:
            self._commit([*self._value, SortKey(field=path, direction="asc")])

    def remove(self, index: int) -> None:
        """Drop the key at an index."""
        if 0 <= index < len(self._value):
            self._commit([k for i, k in enumerate(self._value) if i != index])

    def set_direction(self, index: int, direction: str) -> None:
        """Turn one key ascending or descending."""
        if not 0 <= index < len(self._value) or direction not in ("asc", "desc"):
            return
        if self._value[index].direction == direction:
            return
        self._commit(
            [
                SortKey(field=k.field, direction=direction) if i == index else k
                for i, k in enumerate(self._value)
            ]
        )

    def move(self, index: int, to: int) -> None:
        """Move the key at an index to another place."""
        if not 0 <= index < len(self._value) or not 0 <= to < len(self._value) or index == to:
            return
        keys = list(self._value)
        keys.insert(to, keys.pop(index))
        self._commit(keys)

    def _on_add(self, path: str) -> None:
        if not path:
            return
        self.add(path)
        self._field_picker.set_value("")

    def offers(self, field: FieldSchema, path: str) -> bool:
        """A sortable field the caller offers, and never one already chosen."""
        if not is_sortable(field.data_type):
            return False
        if path in [k.field for k in self._value]:
            return False
        if self._paths is None:
            return True
        return path in self._paths or any(p.startswith(f"{path}.") for p in self._paths)

    # --- the labels -----------------------------------------------------------------------

    def _resolve_labels(self) -> None:
        schema = schema_of(self._context) if self._context is not None else None
        if schema is None or not self._entity_type:
            return
        for key in self._value:
            path = key.field
            if path in self._labels or path in self._resolving:
                continue
            self._resolving.add(path)
            default_pool().submit(
                schema.resolve_path,
                self._entity_type,
                path,
                on_result=lambda segments, at=path: self._label_read(at, segments),
                on_error=lambda _error, at=path: self._label_read(at, None),
            )

    def _label_read(self, path: str, segments: Any) -> None:
        self._resolving.discard(path)
        self._labels[path] = friendly_field_path(segments) if segments else path
        self._refresh()

    def _announce(self, line: str) -> None:
        self._announcement = line
        self._keys.setAccessibleDescription(line)
        self.announced.emit(line)

    def _on_closed(self) -> None:
        if self._open:
            self._open = False
            self._trigger.set_expanded(False)
            self.open_changed.emit(False)

    def _refresh(self) -> None:
        self._resolve_labels()
        names = [self.name_of(key.field) for key in self._value]
        self._trigger.set_label("Sort" if not names else ", ".join(names))
        self._trigger.setEnabled(not self._disabled)
        self._trigger.set_count_size(COUNT_CHIP_SIZE[self._size])
        self._trigger.set_count(str(len(self._value)) if len(self._value) > 1 else "")
        self._field_picker.set_filter(self.offers)
        self._keys.rebuild()


class _SortKeys(ThemedWidget):
    """The ordered key rows: a grip, the name, the direction toggle and the remove control."""

    def __init__(self, owner: SortPicker, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._owner = owner
        self.setObjectName("sort-keys")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        # A list of rows takes a zero gap, so a drop target and a hover fill run edge to edge.
        column.setSpacing(0)
        self._column = column
        self._rows: list[QtWidgets.QWidget] = []
        self._sortable = SortableRows(self, label_of=owner.name_of, parent=self)
        self._sortable.moved.connect(self._on_moved)
        self._sortable.announced.connect(owner._announce)  # noqa: SLF001

    def sortable(self) -> SortableRows:
        """The reorder model the keys run on."""
        return self._sortable

    def rows(self) -> list[QtWidgets.QWidget]:
        """One widget per key, in the order they are drawn."""
        return list(self._rows)

    def _on_moved(self, from_index: int, to_index: int) -> None:
        self._owner.move(from_index, to_index)

    def rebuild(self) -> None:
        """Draw the keys the picker now holds."""
        for row in self._rows:
            self._column.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        owner = self._owner
        for i, key in enumerate(owner.value):
            row = _SortKeyRow(owner, i, key, self)
            self._column.addWidget(row)
            self._rows.append(row)
        if not owner.value:
            self._column.addWidget(
                StateLine(
                    state="empty",
                    label=EMPTY_LABEL,
                    icon=EMPTY_GLYPH,
                    slot_name="sort-empty",
                    size=owner.size,
                    parent=self,
                )
            )
        self._sortable.set_rows([k.field for k in owner.value], self._rows)
        self._sortable.set_enabled(not owner.disabled)
        for i, row in enumerate(self._rows):
            self._sortable.attach_grip(row.grip(), i)
            row.grip().setEnabled(not owner.disabled and len(self._rows) > 1)
        self.updateGeometry()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        paint_drop_line(self, self._sortable, theme_of(self).color("ring"))


class _SortKeyRow(ThemedWidget):
    """One key: the grip, the name, ascending and descending, and the cross."""

    def __init__(
        self,
        owner: SortPicker,
        index: int,
        key: SortKey,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._owner = owner
        self._index = index
        self._key = key
        self.setObjectName("sort-key")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(KEY_PAD_X, KEY_PAD_Y, KEY_PAD_X, KEY_PAD_Y)
        line.setSpacing(ROW_GAP)

        self._grip = Button("", icon="grip-vertical", variant="ghost", size="icon-sm", parent=self)
        self._grip.setObjectName("sort-grip")
        self._grip.setAccessibleName(f"Reorder {owner.name_of(key.field)}")
        self._grip.setToolTip("Drag to reorder, or hold Alt and press the arrow keys")
        line.addWidget(self._grip)

        self._name = _KeyName(owner.name_of(key.field), key.field, self)
        line.addWidget(self._name, 1)

        self._direction = ToggleGroup(
            items=(("asc", "", "arrow-up"), ("desc", "", "arrow-down")),
            value=key.direction,
            size="sm",
            parent=self,
        )
        self._direction.setObjectName("sort-direction")
        self._direction.setEnabled(not owner.disabled)
        self._direction.value_changed.connect(self._on_direction)
        line.addWidget(self._direction)

        cross = Button("", icon="x", variant="ghost", size="icon-sm", parent=self)
        cross.setObjectName("sort-remove")
        cross.setAccessibleName("Remove")
        cross.setEnabled(not owner.disabled)
        cross.clicked.connect(lambda: owner.remove(self._index))
        line.addWidget(cross)

    def grip(self) -> Button:
        """The handle the key is dragged by."""
        return self._grip

    def direction(self) -> ToggleGroup:
        """The ascending and descending pair."""
        return self._direction

    def _on_direction(self, picked: Any) -> None:
        if picked:
            self._owner.set_direction(self._index, str(picked))


class _KeyName(ThemedWidget):
    """A key's friendly path, elided with the dotted path as its tooltip."""

    def __init__(
        self, text: str = "", path: str = "", parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._text = text
        self.setToolTip(path or text)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(theme_of(self).font(14))
        return QtCore.QSize(0, metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = painter_for(self)
        painter.setFont(theme.font(14))
        painter.setPen(theme.color("foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elide(painter, self._text, self.width()),
        )
        painter.end()


class _SortTrigger(Button):
    """The control that opens the list: the glyph, the keys it holds, and their count."""

    def __init__(self, size: str = "md", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(
            "Sort", icon="arrow-up-down", variant="outline",
            size=CONTROL_BUTTON[size], parent=parent,
        )
        self.setObjectName("sort-trigger")
        self._label = "Sort"
        self._step = size

    def set_size(self, value: str) -> None:  # type: ignore[override]
        if value in SORT_PICKER_SIZE_VALUES:
            self._step = value
            super().set_size(CONTROL_BUTTON[value])
        else:
            super().set_size(value)

    def set_label(self, text: str) -> None:
        """The keys the trigger names, comma-joined."""
        self._label = text
        self.setToolTip(text)
        self.set_text(text)
