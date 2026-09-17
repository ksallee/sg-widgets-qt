"""One entity type, as a searchable combobox.

Ported from `packages/react/src/registry/sg/components/entity-type-picker.tsx` and its Svelte
twin. The list is every type the site has enabled, its display name with the code beside it when
the two differ and its glyph in the leading slot. `allow` and `deny` narrow the derived options
rather than the read, so a caller switching sets sees the list change without a second call. The
vocabulary is one read, so the query input narrows it here. A pick closes the list.

    picker = EntityTypePicker(context=context, allow=["Shot", "Asset"])
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtWidgets
from qtpy.QtCore import Signal

from sg_widgets_core.client import EntityTypeInfo
from sg_widgets_core.pickers import EntityTypeOptions, EntityTypeOptionsInput, entity_type_options
from sg_widgets_core.state import NO_MATCH_LABEL, error_text

from ..primitives.badge import Chip
from ..primitives.row_delegate import RowDelegate
from ..workers import QueryRunner
from .entity_glyphs import entity_glyph
from .entity_picker import search_pool
from .list_picker import ListOption, OptionRowModel
from .picker_control import PICKER_CHIP, PICKER_SIZE_VALUES, PickerControl

__all__ = ["EntityTypePicker"]


class EntityTypePicker(QtWidgets.QWidget):
    """One entity type, as a searchable combobox.

    The control is the picker base's token field: the caret sits in the control and typing
    narrows the derived list. One read per site, cached by the schema service: `/schema` is 12KB
    and holds every enabled type, custom slots included (probe 002).
    """

    #: The chosen type code, or None once the clear control was pressed.
    value_changed = Signal(object)
    #: The read failed.
    error = Signal(object)
    #: The popup opened or closed.
    open_changed = Signal(bool)

    #: Several codes may be chosen at once.
    MULTIPLE = False

    #: The object-name prefix every part of this picker carries.
    SLOT = "entity-type-picker"

    def __init__(
        self,
        context: Any = None,
        value: Any = None,
        allow: Sequence[str] | None = None,
        deny: Sequence[str] | None = None,
        placeholder: str = "Select an entity type",
        search_placeholder: str = "Search types…",
        empty_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        clearable: bool = True,
        readonly: bool = False,
        disabled: bool = False,
        invalid: bool = False,
        show_code: bool = True,
        summary: str = "ellipsis",
        max: int = 0,
        size: str = "md",
        open: bool = False,
        on_value_change: Callable[[Any], None] | None = None,
        on_open_change: Callable[[bool], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._value: Any = value
        self._allow = list(allow) if allow is not None else None
        self._deny = list(deny) if deny is not None else None
        self._show_code = bool(show_code)
        self._size = size if size in PICKER_SIZE_VALUES else "md"
        self._loaded: list[EntityTypeInfo] | None = None
        self._failure: str | None = None
        self._on_value_change = on_value_change
        self._on_open_change = on_open_change
        self._options: EntityTypeOptions = entity_type_options(None, EntityTypeOptionsInput())

        self._rows = OptionRowModel(
            (), self, glyph=lambda option: entity_glyph(option.code), code=self._code_of
        )
        delegate = RowDelegate(
            None,
            size=self._size,
            thumbnail=True,
            indicator="checkbox" if self.MULTIPLE else "tick",
        )
        self._control = PickerControl(
            slot=self.SLOT,
            picker="entity-type-multi" if self.MULTIPLE else "entity-type",
            multiple=self.MULTIPLE,
            chip_row=True,
            summary=summary,
            max=max,
            inline=summary == "chips" if self.MULTIPLE else True,
            token_input=self.MULTIPLE,
            size=self._size,
            disabled=disabled,
            readonly=readonly,
            invalid=invalid,
            clearable=clearable,
            placeholder=placeholder,
            search_placeholder=search_placeholder,
            empty_label=empty_label,
            loading_label=loading_label,
            error_label=error_label,
            loading=True,
            trigger_label="Show the entity types",
            row_model=self._rows,
            row_delegate=delegate,
            parent=self,
        )
        delegate.setParent(self._control.list_surface())
        self._control.set_chip_factory(self._chip_for)
        self._control.selected.connect(self._on_selected)
        self._control.open_changed.connect(self._on_open_changed)
        self._control.query_changed.connect(lambda _query: self._refresh())
        self._control.remove_requested.connect(self._on_remove_at)
        self._control.cleared.connect(self._on_clear)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._control)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self.setObjectName(self.SLOT)

        self._runner = QueryRunner(search_pool(), delay_ms=0, parent=self)
        self._refresh()
        self._read()
        if open:
            self._control.set_open(True)

    # --- the read ---------------------------------------------------------------------------

    def _read(self) -> None:
        """One read per site. The schema service caches it, so a page costs one call."""
        if self._context is None:
            self._loaded = []
            self._refresh()
            return
        schema = self._context.schema
        self._runner.start(
            schema.entity_types, on_result=self._landed, on_error=self._failed, delay_ms=0
        )

    def _landed(self, types: Any) -> None:
        self._loaded = list(types or [])
        self._failure = None
        self._refresh()

    def _failed(self, cause: Any) -> None:
        self._loaded = []
        self._failure = error_text(cause)
        self._refresh()
        self.error.emit(cause if isinstance(cause, Exception) else Exception(str(cause)))

    # --- what the control shows ----------------------------------------------------------------

    def _code_of(self, option: ListOption) -> str:
        """The code beside the display name, in the mono family, where the two differ."""
        if not self._show_code or option.code == option.label:
            return ""
        return option.code

    def _refresh(self) -> None:
        loading = self._loaded is None and self._failure is None
        query = self._control.query
        self._options = entity_type_options(
            self._loaded,
            EntityTypeOptionsInput(allow=self._allow, deny=self._deny, query=query),
        )
        shown = [
            ListOption(code=one.name, label=one.display_name) for one in self._options.shown
        ]
        self._rows.set_query(query)
        self._rows.set_options(shown)
        self._rows.set_checked_codes(self._keys())
        self._control.set_items([one.code for one in shown])
        self._control.set_keys(self._keys())
        self._control.set_labels([self._options.label_of(code) for code in self._keys()])
        self._control.set_loading(loading)
        self._control.set_error(self._failure)
        self._control.set_empty(len(shown) == 0)
        self._control.set_overflow_label(f"Show all {len(self._keys())} types")
        self._control.rebuild_chips()

    def _keys(self) -> list[str]:
        return [self._value] if self._value else []

    def _chip_for(self, index: int) -> QtWidgets.QWidget | None:
        keys = self._keys()
        if not 0 <= index < len(keys):
            return None
        code = keys[index]
        label = self._options.label_of(code)
        interactive = (
            self.MULTIPLE and not self._control.readonly and not self._control.disabled
        )
        chip = Chip(
            label,
            size=PICKER_CHIP[self._size],
            removable=interactive,
            parent=self._control,
        )
        chip.setToolTip(label)
        return chip

    # --- the value ------------------------------------------------------------------------------

    @property
    def value(self) -> Any:
        """The chosen type code."""
        return self._value

    def set_value(self, value: Any) -> None:
        self._value = value
        self._refresh()

    def _emit(self, value: Any) -> None:
        self._value = value
        self._refresh()
        if self._on_value_change is not None:
            self._on_value_change(value)
        self.value_changed.emit(value)

    def _on_selected(self, keys: list) -> None:
        self._emit(keys[0] if keys else None)

    def _on_remove_at(self, _index: int) -> None:
        self._emit(None)

    def _on_clear(self) -> None:
        self._emit(None)

    def _on_open_changed(self, is_open: bool) -> None:
        if self._on_open_change is not None:
            self._on_open_change(is_open)
        self.open_changed.emit(is_open)

    # --- what the wrapper carries ----------------------------------------------------------------

    @property
    def control(self) -> PickerControl:
        """The control box and popup shell this picker is built on."""
        return self._control

    @property
    def rows_model(self) -> OptionRowModel:
        """The rows the list draws."""
        return self._rows

    @property
    def types(self) -> list[EntityTypeInfo]:
        """The types on offer, `allow` first and `deny` second."""
        return list(self._options.types)

    @property
    def shown(self) -> list[EntityTypeInfo]:
        """Those the query matched, on display name or code."""
        return list(self._options.shown)

    def label_of(self, code: str) -> str:
        """A code's display name, or the code itself where the site offers no such type."""
        return self._options.label_of(code)

    # --- props -------------------------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. The site's enabled types are read through it, once per page."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._loaded = None
        self._failure = None
        self._refresh()
        self._read()

    @property
    def allow(self) -> list[str] | None:
        """Codes on offer. Empty or absent means every enabled type."""
        return list(self._allow) if self._allow is not None else None

    def set_allow(self, value: Sequence[str] | None) -> None:
        self._allow = list(value) if value is not None else None
        self._refresh()

    @property
    def deny(self) -> list[str] | None:
        """Codes withheld, applied after `allow`."""
        return list(self._deny) if self._deny is not None else None

    def set_deny(self, value: Sequence[str] | None) -> None:
        self._deny = list(value) if value is not None else None
        self._refresh()

    @property
    def show_code(self) -> bool:
        """Show the code beside the display name where the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._rows.set_code(self._code_of)

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

    @property
    def readonly(self) -> bool:
        return self._control.readonly

    def set_readonly(self, value: bool) -> None:
        self._control.set_readonly(value)
        self._control.rebuild_chips()

    @property
    def invalid(self) -> bool:
        return self._control.invalid

    def set_invalid(self, value: bool) -> None:
        self._control.set_invalid(value)

    @property
    def clearable(self) -> bool:
        return self._control.clearable

    def set_clearable(self, value: bool) -> None:
        self._control.set_clearable(value)

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
    def open(self) -> bool:
        """Whether the popup is showing."""
        return self._control.is_open

    def set_open(self, value: bool) -> None:
        self._control.set_open(value)

    def set_on_value_change(self, value: Callable[[Any], None] | None) -> None:
        self._on_value_change = value

    def set_on_open_change(self, value: Callable[[bool], None] | None) -> None:
        self._on_open_change = value
