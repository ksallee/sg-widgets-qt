"""One status, picked from the codes a project offers.

Ported from `packages/react/src/registry/sg/components/status-picker.tsx` and its Svelte twin.
The list picker with a status row and a badge for its value. The options are `valid_values` minus
the project's `hidden_values`, read with `project_id`; over several projects they are the
intersection of those sets. REST does not enforce `hidden_values` on write, so the subtraction is
the client's job (probe 009). A code the option set does not carry still renders, as itself: a row
may legally hold one (field_types/status_list). When a later option set drops the selected code,
the picker clears it and emits once.

A row is the shared picker row of rule 9: the status glyph as the leading mark, the display label
as the row's text, and the code right-aligned. The badge stays in the control, where a status is a
value rather than an option.

    picker = StatusPicker(context=context, entity_type="Version", project_id=70)
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Signal

from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.state import NO_ROWS_LABEL, error_text
from sg_widgets_core.status import StatusOption, StatusRecord

from ..primitives.roles import Roles
from ..primitives.row_delegate import RowDelegate
from ..theme import Theme
from ..workers import QueryRunner
from .entity_picker import search_pool
from .list_picker import ListOption, ListPicker
from .picker_control import PICKER_CHIP, PICKER_SIZE_VALUES, PickerControl
from .status_badge import StatusBadge
from .status_glyph import StatusGlyphSource

__all__ = ["StatusLoad", "StatusLeadDelegate", "StatusOptionsLoader", "StatusPicker"]


@dataclass
class StatusLoad:
    """One load: the options, the field they came from, and the site's Status table."""

    loading: bool = True
    error: str | None = None
    options: list[StatusOption] = dc_field(default_factory=list)
    #: The field the codes come from, which is what clause 8 reads `mandatory` off.
    field: FieldSchema | None = None
    statuses: dict[str, StatusRecord] = dc_field(default_factory=dict)


def _read_options(
    context: Any, entity_type: str, project_ids: Sequence[int], name: str | None
) -> StatusLoad:
    """The one read behind both status pickers. Runs on a worker, never on the GUI thread."""
    schema = context.schema
    ids = list(project_ids)
    if len(ids) == 0:
        options = schema.status_options(entity_type, None, name)
    elif len(ids) == 1:
        options = schema.status_options(entity_type, ids[0], name)
    else:
        options = schema.status_options_for_projects(entity_type, ids, name)
    # The field itself, for its display name and its `mandatory` flag.
    found = schema.status_field(entity_type) if name is None else schema.field(entity_type, name)
    return StatusLoad(
        loading=False,
        error=None,
        options=list(options),
        field=None if isinstance(found, str) or found is None else found,
        statuses=dict(context.statuses.by_code()),
    )


class StatusOptionsLoader(QtCore.QObject):
    """The status read both status pickers share, off the GUI thread.

    Every read goes through the context's own services, so the schema and the Status table are
    fetched once for a whole page. A later request makes the one in flight stale.
    """

    #: The read answered or failed. Carries a `StatusLoad`.
    settled = Signal(object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = QueryRunner(search_pool(), delay_ms=0, parent=self)

    def reload(
        self,
        context: Any,
        entity_type: str,
        project_ids: Sequence[int],
        name: str | None,
    ) -> None:
        """Ask for the options a type offers in these projects."""
        if context is None or not entity_type:
            self.settled.emit(StatusLoad(loading=False))
            return
        self.settled.emit(StatusLoad(loading=True))
        self._runner.start(
            _read_options,
            context,
            entity_type,
            list(project_ids),
            name,
            on_result=self.settled.emit,
            on_error=lambda error: self.settled.emit(
                StatusLoad(loading=False, error=error_text(error))
            ),
            delay_ms=0,
        )

    def cancel(self) -> None:
        self._runner.cancel()


class StatusLeadDelegate(RowDelegate):
    """The shared row, with the status glyph in the leading slot.

    Rule 9: a status offered as an option is its glyph and its name as plain text. The badge is
    what a status is where it is a value, which the control draws instead.
    """

    def __init__(
        self,
        sources: dict[str, StatusGlyphSource],
        parent: QtWidgets.QWidget | None = None,
        **props: Any,
    ) -> None:
        super().__init__(parent, **props)
        self._sources = sources

    def _source_for(self, index: QtCore.QModelIndex) -> StatusGlyphSource | None:
        option = index.data(Roles.ENTITY)
        code = getattr(option, "code", "")
        return self._sources.get(code) if code else None

    def _paint_lead(
        self, painter: QtGui.QPainter, slot: QtCore.QRect, index: QtCore.QModelIndex, theme: Theme
    ) -> None:
        source = self._source_for(index)
        if source is None:
            super()._paint_lead(painter, slot, index, theme)
            return
        source.paint(painter, slot, theme, fallback=True)


class StatusPicker(QtWidgets.QWidget):
    """One status, picked from the codes a project offers.

    The clear follows clause 8 of the picker contract: the field's own schema decides, and a site
    that flags its status field mandatory gets no cross.
    """

    #: The chosen code, or None once the clear control was pressed.
    value_changed = Signal(object)
    #: The popup opened or closed.
    open_changed = Signal(bool)

    #: Several codes may be chosen at once.
    MULTIPLE = False

    def __init__(
        self,
        context: Any = None,
        entity_type: str = "",
        project_id: int | None = None,
        project_ids: Sequence[int] | None = None,
        field: str | None = None,
        value: str | None = None,
        placeholder: str = "Select a status",
        empty_label: str = NO_ROWS_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        clearable: bool | None = None,
        readonly: bool = False,
        disabled: bool = False,
        invalid: bool = False,
        show_code: bool = True,
        secondary: Callable[[StatusOption], str] | None = None,
        sub_label: Callable[[StatusOption], str] | None = None,
        site_url: str | None = None,
        size: str = "md",
        open: bool = False,
        on_value_change: Callable[[Any], None] | None = None,
        on_open_change: Callable[[bool], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._entity_type = entity_type
        self._project_ids = _project_ids(project_id, project_ids)
        self._field_name = field
        self._value: Any = value
        self._size = size if size in PICKER_SIZE_VALUES else "md"
        self._site_url = site_url
        self._load = StatusLoad()
        self._seen: str | None = None
        self._sources: dict[str, StatusGlyphSource] = {}
        # The list picker builds its chips while it is still being constructed, so the badge
        # factory has to answer before this is bound.
        self._list: Any = None
        self._on_value_change = on_value_change
        self._on_open_change = on_open_change

        self._list = self._build_list(
            value=value,
            placeholder=placeholder,
            empty_label=empty_label,
            loading_label=loading_label,
            error_label=error_label,
            clearable=clearable,
            readonly=readonly,
            disabled=disabled,
            invalid=invalid,
            show_code=show_code,
            secondary=secondary,
            sub_label=sub_label,
        )
        self._delegate = StatusLeadDelegate(
            self._sources,
            self._list.control.list_surface(),
            size=self._size,
            thumbnail=True,
            indicator="checkbox" if self.MULTIPLE else "tick",
        )
        self._list.control.set_row_delegate(self._delegate)
        self._list.open_changed.connect(self._on_open_changed)
        self._list.value_changed.connect(self._on_picked)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._list)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self.setObjectName(self.SLOT)

        self._loader = StatusOptionsLoader(self)
        self._loader.settled.connect(self._settled)
        self._reload()
        if open:
            self._list.set_open(True)

    #: The object-name prefix every part of this picker carries.
    SLOT = "status-picker"

    def _build_list(self, **props: Any) -> ListPicker:
        return ListPicker(
            slot=self.SLOT,
            picker="status",
            size=self._size,
            loading=True,
            clear_label="Clear the status",
            trigger_label="Show the statuses",
            mark=lambda option: "",
            value_chip=self._badge_for,
            parent=self,
            **props,
        )

    # --- the read ---------------------------------------------------------------------------

    def _reload(self) -> None:
        # `seen` survives a reload: a project change is exactly the case where a later option
        # set drops the selected code.
        self._loader.reload(
            self._context, self._entity_type, self._project_ids, self._field_name
        )

    def _settled(self, load: StatusLoad) -> None:
        self._load = load
        self._list.set_loading(load.loading)
        self._list.set_load_error(load.error)
        self._list.set_field(load.field)
        self._list.set_options(list(load.options))
        self._rebuild_sources()
        self._list.control.rebuild_chips()
        if not load.loading and load.error is None:
            self._drop_missing()

    def _rebuild_sources(self) -> None:
        for source in self._sources.values():
            source.deleteLater()
        self._sources.clear()
        site = self.site_url
        codes = [option.code for option in self._load.options]
        codes.extend(code for code in self._held() if code not in codes)
        for code in codes:
            source = StatusGlyphSource(self._load.statuses.get(code), site, parent=self)
            source.changed.connect(self._redraw_rows)
            self._sources[code] = source

    def _redraw_rows(self) -> None:
        surface = self._list.control.list_surface()
        surface.viewport().update()

    def _drop_missing(self) -> None:
        """A later option set that no longer carries the value clears it, once.

        The first option set is not a change: it is what the widget was built to show.
        """
        codes = ",".join(option.code for option in self._load.options)
        held = self._held()
        dropped = [
            code
            for code in held
            if self._seen is not None
            and self._seen != codes
            and not any(option.code == code for option in self._load.options)
        ]
        self._seen = codes
        if dropped:
            self._emit_dropped(dropped)

    def _held(self) -> list[str]:
        return [self._value] if self._value else []

    def _emit_dropped(self, _dropped: Sequence[str]) -> None:
        self._set_value(None, emit=True)

    # --- the value --------------------------------------------------------------------------

    @property
    def value(self) -> str | None:
        """The selected code."""
        return self._value

    def set_value(self, value: str | None) -> None:
        self._set_value(value, emit=False)

    def _set_value(self, value: Any, emit: bool) -> None:
        self._value = value
        self._list.set_value(value)
        if emit:
            self._announce(value)

    def _announce(self, value: Any) -> None:
        if self._on_value_change is not None:
            self._on_value_change(value)
        self.value_changed.emit(value)

    def _on_picked(self, value: Any) -> None:
        self._value = value
        self._announce(value)

    def _on_open_changed(self, is_open: bool) -> None:
        if self._on_open_change is not None:
            self._on_open_change(is_open)
        self.open_changed.emit(is_open)

    # --- the badge --------------------------------------------------------------------------

    def _badge_for(self, code: str) -> QtWidgets.QWidget | None:
        if not code:
            return None
        return StatusBadge(
            code=code,
            status=self._load.statuses.get(code),
            field=self._load.field,
            size=PICKER_CHIP[self._size],
            site_url=self.site_url,
            removable=False,
        )

    def label_of(self, code: str) -> str:
        """A code's label, or the code itself where the option set does not carry it."""
        for option in self._load.options:
            if option.code == code:
                return option.label
        return code

    def _interactive(self) -> bool:
        return self._list is None or (not self._list.readonly and not self._list.disabled)

    # --- what the wrapper carries -------------------------------------------------------------

    @property
    def control(self) -> PickerControl:
        """The control box and popup shell this picker is built on."""
        return self._list.control

    @property
    def list_picker(self) -> ListPicker:
        """The fixed-set picker under this one."""
        return self._list

    @property
    def rows_model(self) -> Any:
        """The rows the list draws."""
        return self._list.rows_model

    @property
    def load(self) -> StatusLoad:
        """The options on offer, the field behind them and the Status table."""
        return self._load

    @property
    def options(self) -> list[ListOption]:
        """The codes on offer."""
        return list(self._load.options)

    # --- props --------------------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. The options and the Status table are read through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._reload()

    @property
    def entity_type(self) -> str:
        """The type whose status field is offered."""
        return self._entity_type

    def set_entity_type(self, value: str) -> None:
        self._entity_type = value
        self._reload()

    @property
    def project_id(self) -> int | None:
        """Offer the codes this project allows."""
        return self._project_ids[0] if self._project_ids else None

    def set_project_id(self, value: int | None) -> None:
        self._project_ids = _project_ids(value, None)
        self._reload()

    @property
    def project_ids(self) -> list[int]:
        """Offer the codes every one of these projects allows."""
        return list(self._project_ids)

    def set_project_ids(self, value: Sequence[int] | None) -> None:
        self._project_ids = _project_ids(None, value)
        self._reload()

    @property
    def field(self) -> str | None:
        """A list or status field other than the type's own. Project's is `sg_status`."""
        return self._field_name

    def set_field(self, value: str | None) -> None:
        self._field_name = value
        self._reload()

    @property
    def show_code(self) -> bool:
        """Draw the code as a row's secondary, when it says more than the label."""
        return self._list.show_code

    def set_show_code(self, value: bool) -> None:
        self._list.set_show_code(value)

    @property
    def secondary(self) -> Callable[[StatusOption], str] | None:
        """A row's right-aligned value, of the caller's own making. Wins over the code."""
        return self._list.secondary

    def set_secondary(self, value: Callable[[StatusOption], str] | None) -> None:
        self._list.set_secondary(value)

    @property
    def sub_label(self) -> Callable[[StatusOption], str] | None:
        """The muted line under a row's label."""
        return self._list.sub_label

    def set_sub_label(self, value: Callable[[StatusOption], str] | None) -> None:
        self._list.set_sub_label(value)

    @property
    def site_url(self) -> str:
        """The site the stock sprite is served from. Defaults to the context's."""
        if self._site_url is not None:
            return self._site_url
        return getattr(self._context, "site_url", "") or ""

    def set_site_url(self, value: str | None) -> None:
        self._site_url = value
        self._rebuild_sources()
        self._list.control.rebuild_chips()

    @property
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in PICKER_SIZE_VALUES else "md"
        self._list.set_size(self._size)
        self._delegate.set_size(self._size)

    @property
    def clearable(self) -> bool | None:
        """Unset, it follows the field: a mandatory field offers no clear."""
        return self._list.clearable

    def set_clearable(self, value: bool | None) -> None:
        self._list.set_clearable(value)

    @property
    def readonly(self) -> bool:
        return self._list.readonly

    def set_readonly(self, value: bool) -> None:
        self._list.set_readonly(value)

    @property
    def disabled(self) -> bool:
        return self._list.disabled

    def set_disabled(self, value: bool) -> None:
        self._list.set_disabled(value)

    @property
    def invalid(self) -> bool:
        return self._list.invalid

    def set_invalid(self, value: bool) -> None:
        self._list.set_invalid(value)

    @property
    def placeholder(self) -> str:
        return self._list.placeholder

    def set_placeholder(self, value: str) -> None:
        self._list.set_placeholder(value)

    @property
    def empty_label(self) -> str:
        return self._list.empty_label

    def set_empty_label(self, value: str) -> None:
        self._list.set_empty_label(value)

    @property
    def loading_label(self) -> str | None:
        return self._list.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._list.set_loading_label(value)

    @property
    def error_label(self) -> str | None:
        return self._list.error_label

    def set_error_label(self, value: str | None) -> None:
        self._list.set_error_label(value)

    @property
    def open(self) -> bool:
        """Whether the popup is showing."""
        return self._list.open

    def set_open(self, value: bool) -> None:
        self._list.set_open(value)

    def set_on_value_change(self, value: Callable[[Any], None] | None) -> None:
        self._on_value_change = value

    def set_on_open_change(self, value: Callable[[bool], None] | None) -> None:
        self._on_open_change = value


def _project_ids(project_id: int | None, project_ids: Sequence[int] | None) -> list[int]:
    """The projects a read is scoped to: the list wins, then the single id, then none."""
    if project_ids is not None:
        return [int(one) for one in project_ids]
    return [] if project_id is None else [int(project_id)]
