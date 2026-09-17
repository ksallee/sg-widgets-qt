"""One value of a `list` field, picked from the set its schema declares.

Ported from `packages/react/src/registry/sg/components/list-picker.tsx` and its Svelte twin.
Despite the name the value is one bare string, and a write outside `valid_values` is a 400 and
case-sensitive, so the schema's vocabulary is the whole set a picker may offer
(field_types/list). With a project id the field's hidden values are subtracted, which REST does
not do on write (probe 009).

The set is fixed and read once, so there is no search row unless a caller asks for one, and the
control is the base's summary trigger: the value reads as plain text, the way a select does.
This module also holds the option model and the plain-text value every fixed-set picker here
draws, so the list, the status and the entity-type pickers share one row.

    picker = ListPicker(field=schema.field("Shot", "sg_shot_type"))
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.picker import clearable_for_field
from sg_widgets_core.pickers import matches_tokens
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.search import match_runs
from sg_widgets_core.state import NO_ROWS_LABEL
from sg_widgets_core.status import StatusOption, status_label, usable_statuses

from ..primitives.base import CONTROL_HEIGHT, ThemedWidget, elide, painter_for, text_width
from ..primitives.roles import Roles
from ..primitives.row_delegate import ROW_TEXT, RowDelegate
from .field_error import FieldError
from .picker_control import PICKER_SIZE_VALUES, PickerControl

__all__ = [
    "LIST_ROW_TYPE",
    "ListOption",
    "ListPicker",
    "OptionRowModel",
    "ValueText",
    "options_for_field",
    "secondary_of",
]

#: A row stands for a value, not an entity, so it carries a type of its own and no values.
LIST_ROW_TYPE = "ListValue"

ListOption = StatusOption
"""One offered value: the string a write sends, and the label the schema gives it."""

#: The root of a list model, held once so it is not built in a default argument.
_ROOT = QtCore.QModelIndex()


def options_for_field(field: Any, project_id: int | None = None) -> list[ListOption]:
    """The set a field offers: its valid values, minus the hidden ones under a project id.

    Hidden values reach the schema only when it is read with a project id, and REST does not
    enforce them on write, so the subtraction is the client's (probe 009).
    """
    if field is None:
        return []
    if project_id is not None:
        return usable_statuses(field)
    return [
        ListOption(code=code, label=status_label(field, code))
        for code in (getattr(field, "valid_values", None) or [])
    ]


def secondary_of(
    option: ListOption,
    show_code: bool,
    own: Callable[[ListOption], str] | None = None,
) -> str:
    """The right-aligned value: the caller's, else the stored string where it says more."""
    if own is not None:
        return own(option) or ""
    return option.code if show_code and option.code != option.label else ""


class OptionRowModel(QtCore.QAbstractListModel):
    """The rows a fixed-set picker lists, in the roles `RowDelegate` paints.

    A value has no entity behind it, so the row is the label with the matched runs bold, the
    caller's muted sub-label, a right-aligned secondary and, where the picker supplies one, a
    leading mark. `checked_codes` fills the indicator column.
    """

    def __init__(
        self,
        options: Sequence[ListOption] = (),
        parent: QtCore.QObject | None = None,
        query: str = "",
        show_code: bool = False,
        secondary: Callable[[ListOption], str] | None = None,
        sub_label: Callable[[ListOption], str] | None = None,
        glyph: Callable[[ListOption], str] | None = None,
        code: Callable[[ListOption], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._options: list[ListOption] = list(options)
        self._query = query
        self._show_code = bool(show_code)
        self._secondary = secondary
        self._sub_label = sub_label
        self._glyph = glyph
        self._code = code
        self._checked: set[str] = set()

    # --- what it holds --------------------------------------------------------------------

    @property
    def options(self) -> list[ListOption]:
        """The rows on show."""
        return list(self._options)

    def set_options(self, value: Sequence[ListOption]) -> None:
        self.beginResetModel()
        self._options = list(value)
        self.endResetModel()

    def option_at(self, row: int) -> ListOption | None:
        return self._options[row] if 0 <= row < len(self._options) else None

    @property
    def query(self) -> str:
        """The query whose matched runs are drawn in DemiBold."""
        return self._query

    def set_query(self, value: str) -> None:
        self._query = value
        self._redraw()

    @property
    def show_code(self) -> bool:
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._redraw()

    def set_secondary(self, value: Callable[[ListOption], str] | None) -> None:
        self._secondary = value
        self._redraw()

    def set_sub_label(self, value: Callable[[ListOption], str] | None) -> None:
        self._sub_label = value
        self._redraw()

    def set_glyph(self, value: Callable[[ListOption], str] | None) -> None:
        self._glyph = value
        self._redraw()

    def set_code(self, value: Callable[[ListOption], str] | None) -> None:
        """The programmatic name drawn beside the label, in the mono family (rule 6)."""
        self._code = value
        self._redraw()

    def set_checked_codes(self, codes: Iterable[str]) -> None:
        """The codes a multi picker holds, drawn in the indicator column."""
        self._checked = set(codes)
        self._redraw()

    @property
    def checked_codes(self) -> set[str]:
        return set(self._checked)

    def _redraw(self) -> None:
        if not self._options:
            return
        top = self.index(0, 0)
        bottom = self.index(len(self._options) - 1, 0)
        self.dataChanged.emit(top, bottom)

    # --- the model ------------------------------------------------------------------------

    def rowCount(self, parent: QtCore.QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._options)

    def data(self, index: QtCore.QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        option = self.option_at(index.row()) if index.isValid() else None
        if option is None:
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return option.label
        if role == Roles.RUNS:
            return [(run.text, run.match, False) for run in match_runs(option.label, self._query)]
        if role == Roles.CODE:
            return self._code(option) or "" if self._code is not None else ""
        if role == Roles.SECONDARY:
            return secondary_of(option, self._show_code, self._secondary)
        if role == Roles.SUB_LABEL:
            return self._sub_label(option) or "" if self._sub_label is not None else ""
        if role == Roles.GLYPH:
            return self._glyph(option) or "" if self._glyph is not None else ""
        if role == Roles.CHECKED:
            return option.code in self._checked if self._checked is not None else None
        if role == Roles.ENTITY:
            return option
        if role == Qt.ItemDataRole.ToolTipRole:
            return option.label
        return None

    def flags(self, index: QtCore.QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class ValueText(ThemedWidget):
    """The control's value as plain text, the way a select reads.

    It is what the control's chip factory answers where the caller supplies no chip of its own,
    so a fixed-set picker takes the reading inset rather than the chip inset.
    """

    def __init__(
        self, text: str = "", size: str = "md", parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._text = text
        self.set_size_step(size if size in PICKER_SIZE_VALUES else "md")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(ROW_TEXT[self.size_step])

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(
            text_width(metrics, self._text), max(metrics.height(), CONTROL_HEIGHT["sm"] - 8)
        )

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        font = self._font()
        painter.setFont(font)
        painter.setPen(self.theme.color("foreground"))
        shown = elide(painter, self._text, self.width())
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            shown,
        )
        painter.end()
        self.set_elide_tooltip(self._text, shown == self._text)


class ListPicker(QtWidgets.QWidget):
    """One value of a `list` field, picked from the set its schema declares.

    The control is the picker base's summary trigger, anchored to its own width. `mark` and
    `value_chip` are the two hooks: a leading mark per row, and the widget the control shows in
    place of plain text.
    """

    #: The chosen string, or None once the clear control was pressed.
    value_changed = Signal(object)
    #: The message under the control changed. It is cleared by every pick.
    error_changed = Signal(object)
    #: The popup opened or closed.
    open_changed = Signal(bool)

    #: Several values may be chosen at once.
    MULTIPLE = False

    def __init__(
        self,
        value: str | None = None,
        field: FieldSchema | None = None,
        project_id: int | None = None,
        options: Sequence[ListOption] | None = None,
        show_code: bool = False,
        secondary: Callable[[ListOption], str] | None = None,
        sub_label: Callable[[ListOption], str] | None = None,
        load_error: str | None = None,
        slot: str = "list-picker",
        picker: str = "list",
        searchable: bool = False,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        clearable: bool | None = None,
        placeholder: str = "Choose",
        search_placeholder: str = "Search values…",
        open: bool = False,
        loading: bool = False,
        error: str | None = None,
        empty_label: str = NO_ROWS_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        clear_label: str = "Clear the value",
        trigger_label: str = "Show the values",
        mark: Callable[[ListOption], str] | None = None,
        value_chip: Callable[[str], QtWidgets.QWidget | None] | None = None,
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[Any], None] | None = None,
        on_open_change: Callable[[bool], None] | None = None,
        on_error_change: Callable[[Any], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._field = field
        self._project_id = project_id
        self._given = list(options) if options is not None else None
        self._show_code = bool(show_code)
        self._secondary = secondary
        self._sub_label = sub_label
        self._mark = mark
        self._value_chip = value_chip
        self._size = size if size in PICKER_SIZE_VALUES else "md"
        self._searchable = bool(searchable)
        self._clearable = clearable
        self._loading = bool(loading)
        self._on_value_change = on_value_change
        self._on_open_change = on_open_change
        self._on_error_change = on_error_change
        self._shown: list[ListOption] = []

        self._rows = OptionRowModel(
            (),
            self,
            show_code=self._show_code,
            secondary=self._secondary,
            sub_label=self._sub_label,
            glyph=self._mark,
        )
        delegate = RowDelegate(
            None,
            size=self._size,
            thumbnail=mark is not None,
            indicator="checkbox" if self.MULTIPLE else "tick",
        )
        shape: dict[str, Any] = {
            "slot": slot,
            "picker": picker,
            "multiple": self.MULTIPLE,
            "anchored": True,
            "inline": False,
            "text_value": not self.MULTIPLE and value_chip is None,
            "searchable": self._searchable,
            "size": self._size,
            "disabled": disabled,
            "inert": not readonly and (disabled or self._loading),
            "readonly": readonly,
            "invalid": invalid,
            "placeholder": placeholder,
            "search_placeholder": search_placeholder,
            "empty_label": empty_label,
            "loading_label": loading_label,
            "error_label": error_label,
            "clear_label": clear_label,
            "trigger_label": trigger_label,
            "loading": self._loading,
            "error": load_error,
            "row_model": self._rows,
            "row_delegate": delegate,
        }
        shape.update(self._control_options())
        self._control = PickerControl(parent=self, **shape)
        self._control.set_chip_factory(self._chip_for)
        self._control.selected.connect(self._on_selected)
        self._control.open_changed.connect(self._on_open_changed)
        self._control.query_changed.connect(self._on_query)
        self._control.remove_requested.connect(self._on_remove_at)
        self._control.cleared.connect(self._clear)

        self._error = FieldError(error, error_message, self)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.addWidget(self._control)
        column.addWidget(self._error)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self.setObjectName(slot)
        self._refresh()
        if open:
            self._control.set_open(True)

    def _control_options(self) -> dict[str, Any]:
        """What the control takes beyond the shared props. The multi picker adds its shape."""
        return {}

    # --- the control ------------------------------------------------------------------------

    @property
    def control(self) -> PickerControl:
        """The control box and popup shell this picker is built on."""
        return self._control

    @property
    def rows_model(self) -> OptionRowModel:
        """The rows the list draws."""
        return self._rows

    @property
    def options(self) -> list[ListOption]:
        """The set on offer: the caller's own, else the field's valid values."""
        if self._given is not None:
            return list(self._given)
        return options_for_field(self._field, self._project_id)

    def set_options(self, value: Sequence[ListOption] | None) -> None:
        self._given = list(value) if value is not None else None
        self._refresh()

    @property
    def shown(self) -> list[ListOption]:
        """The rows the search box left, which is every row while it is off."""
        return list(self._shown)

    # --- the value --------------------------------------------------------------------------

    @property
    def value(self) -> str | None:
        """The stored string, one of the field's valid values, or None (field_types/list)."""
        return self._value

    def set_value(self, value: str | None) -> None:
        self._value = value
        self._refresh()

    def _rows_for(self) -> list[ListOption]:
        """The options, and the stored value where the offered set does not carry it.

        A row may legally hold a value outside the set, so it keeps a row of its own labelled
        with the value (probe 009).
        """
        rows = self.options
        if self._value and not any(option.code == self._value for option in rows):
            rows = [*rows, ListOption(code=self._value, label=self._value)]
        return rows

    def label_of(self, code: str) -> str:
        """A code's label, or the code itself where the set does not carry it."""
        for option in self._rows_for():
            if option.code == code:
                return option.label
        return code

    def _emit(self, value: str | None) -> None:
        self._value = value
        self._refresh()
        self.set_error(None)
        if self._on_value_change is not None:
            self._on_value_change(value)
        self.value_changed.emit(value)

    def _clear(self) -> None:
        self._emit(None)

    def _on_remove_at(self, _index: int) -> None:
        self._clear()

    def _on_selected(self, keys: list) -> None:
        chosen = keys[0] if keys else None
        if chosen == self._value:
            return
        self._emit(chosen)

    # --- the rows ---------------------------------------------------------------------------

    def _refresh(self) -> None:
        rows = self._rows_for()
        query = self._control.query if self._searchable else ""
        # The vocabulary is one read, so a search box narrows it here.
        self._shown = (
            [one for one in rows if matches_tokens(query, one.label, one.code)]
            if self._searchable
            else rows
        )
        self._rows.set_query(query)
        self._rows.set_options(self._shown)
        if self.MULTIPLE:
            self._rows.set_checked_codes(self._keys())
        else:
            self._rows.set_checked_codes([self._value] if self._value else [])
        self._control.set_items([one.code for one in self._shown])
        self._control.set_keys(self._keys())
        self._control.set_labels([self.label_of(code) for code in self._keys()])
        self._control.set_empty(len(self._shown) == 0)
        self._control.set_clearable(self._clearable_now())
        self._control.rebuild_chips()

    def _keys(self) -> list[str]:
        return [self._value] if self._value else []

    def _clearable_now(self) -> bool:
        return clearable_for_field(self._clearable, self._field)

    def _on_query(self, _query: str) -> None:
        self._refresh()

    def _on_open_changed(self, is_open: bool) -> None:
        if is_open:
            self._highlight_held()
        if self._on_open_change is not None:
            self._on_open_change(is_open)
        self.open_changed.emit(is_open)

    def _highlight_held(self) -> None:
        """Open with the cursor on the value the picker holds, the way upstream's does.

        A picker holding a value opens with that row under the cursor; the multi picker uses the
        first of its values. One holding nothing opens with nothing highlighted, and the first
        `Down` takes the first row, which is the base's own rule.
        """
        codes = [one.code for one in self._shown]
        for code in self._keys():
            if code in codes:
                self._control.list_surface().set_highlight(codes.index(code))
                return

    def _chip_for(self, index: int) -> QtWidgets.QWidget | None:
        keys = self._keys()
        if not 0 <= index < len(keys):
            return None
        code = keys[index]
        if self._value_chip is not None:
            return self._value_chip(code)
        return ValueText(self.label_of(code), size=self._size, parent=self._control)

    # --- props ------------------------------------------------------------------------------

    @property
    def field(self) -> FieldSchema | None:
        """The field schema. Its valid values are the whole vocabulary a write may use."""
        return self._field

    def set_field(self, value: FieldSchema | None) -> None:
        self._field = value
        self._refresh()

    @property
    def project_id(self) -> int | None:
        """Given, the field's hidden values are removed from the list."""
        return self._project_id

    def set_project_id(self, value: int | None) -> None:
        self._project_id = value
        self._refresh()

    @property
    def show_code(self) -> bool:
        """Draw the stored string as a row's secondary, where it says more than the label."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._rows.set_show_code(self._show_code)

    @property
    def secondary(self) -> Callable[[ListOption], str] | None:
        """A row's right-aligned value, of the caller's own making. Wins over the code."""
        return self._secondary

    def set_secondary(self, value: Callable[[ListOption], str] | None) -> None:
        self._secondary = value
        self._rows.set_secondary(value)

    @property
    def sub_label(self) -> Callable[[ListOption], str] | None:
        """The muted line under a row's label."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[ListOption], str] | None) -> None:
        self._sub_label = value
        self._rows.set_sub_label(value)

    @property
    def mark(self) -> Callable[[ListOption], str] | None:
        """A row's leading mark, as a glyph name. Given, every row carries one."""
        return self._mark

    def set_mark(self, value: Callable[[ListOption], str] | None) -> None:
        self._mark = value
        self._rows.set_glyph(value)
        self._control.row_delegate().set_thumbnail(value is not None)

    @property
    def value_chip(self) -> Callable[[str], QtWidgets.QWidget | None] | None:
        """What the control shows for the value, in place of plain text."""
        return self._value_chip

    def set_value_chip(self, value: Callable[[str], QtWidgets.QWidget | None] | None) -> None:
        self._value_chip = value
        self._control.set_text_value(not self.MULTIPLE and value is None)
        self._control.rebuild_chips()

    @property
    def error_message(self) -> Callable[[str], QtWidgets.QWidget] | None:
        """What draws the message under the control."""
        return self._error.error_message

    def set_error_message(self, value: Callable[[str], QtWidgets.QWidget] | None) -> None:
        self._error.set_error_message(value)

    @property
    def searchable(self) -> bool:
        """Offer a search box. The set is fixed, so it is off."""
        return self._searchable

    def set_searchable(self, value: bool) -> None:
        self._searchable = bool(value)
        self._control.set_searchable(self._searchable)
        self._refresh()

    @property
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in PICKER_SIZE_VALUES else "md"
        self._control.set_size(self._size)
        self._control.rebuild_chips()

    @property
    def disabled(self) -> bool:
        return self._control.disabled

    def set_disabled(self, value: bool) -> None:
        self._control.set_disabled(value)
        self._sync_inert()

    @property
    def readonly(self) -> bool:
        return self._control.readonly

    def set_readonly(self, value: bool) -> None:
        self._control.set_readonly(value)
        self._sync_inert()
        self._control.rebuild_chips()

    @property
    def invalid(self) -> bool:
        return self._control.invalid

    def set_invalid(self, value: bool) -> None:
        self._control.set_invalid(value)

    @property
    def clearable(self) -> bool | None:
        """Unset, it follows the field: a mandatory field offers no clear."""
        return self._clearable

    def set_clearable(self, value: bool | None) -> None:
        self._clearable = value
        self._control.set_clearable(self._clearable_now())

    @property
    def placeholder(self) -> str:
        return self._control.placeholder

    def set_placeholder(self, value: str) -> None:
        self._control.set_placeholder(value)

    @property
    def search_placeholder(self) -> str:
        return self._control.search_placeholder

    def set_search_placeholder(self, value: str) -> None:
        self._control.set_search_placeholder(value)

    @property
    def open(self) -> bool:
        """Whether the popup is showing."""
        return self._control.is_open

    def set_open(self, value: bool) -> None:
        self._control.set_open(value)

    @property
    def loading(self) -> bool:
        """A caller's read is in flight: skeletons, and the control is inert."""
        return self._loading

    def set_loading(self, value: bool) -> None:
        self._loading = bool(value)
        self._control.set_loading(self._loading)
        self._sync_inert()

    def _sync_inert(self) -> None:
        self._control.set_inert(
            not self._control.readonly and (self._control.disabled or self._loading)
        )

    @property
    def load_error(self) -> str | None:
        """What a caller's read failed with, drawn in place of the list."""
        return self._control.error

    def set_load_error(self, value: str | None) -> None:
        self._control.set_error(value)

    @property
    def error(self) -> str | None:
        """A message from the caller, drawn under the control."""
        return self._error.message

    def set_error(self, value: str | None) -> None:
        if self._error.message == (value if value else None):
            return
        self._error.set_message(value)
        if self._on_error_change is not None:
            self._on_error_change(self._error.message)
        self.error_changed.emit(self._error.message)

    @property
    def empty_label(self) -> str:
        return self._control.empty_label

    def set_empty_label(self, value: str) -> None:
        self._control.set_empty_label(value)

    @property
    def loading_label(self) -> str | None:
        return self._control.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._control.set_loading_label(value)

    @property
    def error_label(self) -> str | None:
        return self._control.error_label

    def set_error_label(self, value: str | None) -> None:
        self._control.set_error_label(value)

    @property
    def clear_label(self) -> str:
        return self._control.clear_label

    def set_clear_label(self, value: str) -> None:
        self._control.set_clear_label(value)

    @property
    def trigger_label(self) -> str:
        return self._control.trigger_label

    def set_trigger_label(self, value: str) -> None:
        self._control.set_trigger_label(value)

    @property
    def slot(self) -> str:
        """The object-name prefix every part of this picker carries."""
        return self._control.slot

    def set_slot(self, value: str) -> None:
        self._control.set_slot(value)
        self.setObjectName(value)

    @property
    def picker(self) -> str:
        """What the popup answers to."""
        return self._control.picker

    def set_picker(self, value: str) -> None:
        self._control.set_picker(value)

    def set_on_value_change(self, value: Callable[[Any], None] | None) -> None:
        self._on_value_change = value

    def set_on_open_change(self, value: Callable[[bool], None] | None) -> None:
        self._on_open_change = value

    def set_on_error_change(self, value: Callable[[Any], None] | None) -> None:
        self._on_error_change = value
