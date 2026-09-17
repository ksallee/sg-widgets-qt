"""One entity, chosen by server-side search.

Ported from `packages/react/src/registry/sg/components/entity-picker.tsx` and its Svelte twin.
A query past `min_query_length` becomes one `contains` condition per word, `or`'d across the
type's display-name fields, and goes to one search per searched type. Under it the same search
runs without the name condition, so an open picker lists the rows worked on most recently. The
list does no filtering of its own: the site is the only authority on what matches.

The read runs on `sg_widgets_qt.workers`: the pause a typist leaves, then `fetch_page` on a
worker, then `deliver` back here with the ticket `begin` handed out, so an answer to a query the
typist has already replaced is dropped rather than written.

    picker = EntityPicker(entity_types=["Shot"], context=context)
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Signal

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import (
    EntitySearchOptions,
    EntitySearchState,
    PickerRow,
    create_entity_search,
    entity_key,
    placeholder_name,
    with_selected_pinned,
)
from sg_widgets_core.row import path_of, row_thumbnail
from sg_widgets_core.state import NO_MATCH_LABEL

from ..images import image_loader
from ..primitives.badge import Chip
from ..primitives.row_delegate import RowDelegate
from ..workers import DEFAULT_DEBOUNCE_MS, JobPool, QueryRunner
from .picker_control import PICKER_CHIP, PICKER_SIZE_VALUES, PickerControl
from .picker_row import PickerRowModel

__all__ = ["EntityPicker", "EntitySearchPicker", "search_pool"]

#: Threads the pickers read on. Small, because a site rate limits.
SEARCH_THREADS = 4

_SEARCH_POOL: JobPool | None = None


def search_pool() -> JobPool:
    """The pool every picker's reads run on.

    A pool of its own, never the one `images.py` reads pictures on: a page of rows with
    thumbnails would otherwise hold every thread and the next query would wait behind them.
    """
    global _SEARCH_POOL
    if _SEARCH_POOL is None:
        _SEARCH_POOL = JobPool(SEARCH_THREADS)
    return _SEARCH_POOL

#: The chip a picker falls back to while `entity_chip.py` has not landed.
try:  # pragma: no cover - the entity chip is the other half of the display wave.
    from .entity_chip import EntityChip as _EntityChip
except Exception:  # pragma: no cover
    _EntityChip = None


class _Bus(QtCore.QObject):
    """Carries a state or a failure from the read's thread onto this one.

    Core's hydration writes on the thread it runs on, so its answers cross back through a
    queued signal rather than reaching a widget where they were produced.
    """

    state = Signal(object)
    failed = Signal(object)


class EntitySearchPicker(QtWidgets.QWidget):
    """What both entity pickers are: one core search, one control, one row model.

    They differ only in the shape of the value, which is `_refs`, `_emit_value` and the
    control's shape. Everything here is shared, so the two cannot drift.
    """

    #: The read failed.
    error = Signal(object)
    #: The popup opened or closed.
    open_changed = Signal(bool)

    #: Several keys may be chosen at once.
    MULTIPLE = False

    def __init__(
        self,
        entity_types: Sequence[str] = (),
        context: Any = None,
        label_field: str | None = None,
        search_fields: Any = None,
        secondary_field: Any = None,
        secondary: Callable[[PickerRow], str] | None = None,
        sub_label_field: Any = None,
        sub_label: Callable[[PickerRow], str] | None = None,
        thumbnail: Any = "image",
        round_thumbnail: bool = False,
        show_code: bool = False,
        site_url: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Any = None,
        project_id: int | None = None,
        exclude: Sequence[EntityRef] | None = None,
        min_query_length: int = 0,
        page_size: int = 20,
        placeholder: str = "Search for an entity",
        search_placeholder: str = "Search…",
        empty_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        clearable: bool = True,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
        open: bool = False,
        summary: str = "chips",
        max: int = 0,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._site_url = site_url
        self._secondary = secondary
        self._sub_label = sub_label
        self._thumbnail = thumbnail
        self._round_thumbnail = bool(round_thumbnail)
        self._show_code = bool(show_code)
        self._size = size if size in PICKER_SIZE_VALUES else "md"
        self._entity_types = list(entity_types)
        self._page = 1
        self._pending_query = ""
        self._state = EntitySearchState()

        self._bus = _Bus(self)
        self._bus.state.connect(self._on_state)
        self._bus.failed.connect(self._on_failed)

        self._search = create_entity_search(EntitySearchOptions(
            client=_client_of(context),
            schema=getattr(context, "schema", None),
            entity_types=list(entity_types),
            label_field=label_field,
            search_fields=search_fields,
            secondary_field=secondary_field,
            sub_label_field=sub_label_field,
            thumbnail=thumbnail,
            fields=list(fields) if fields is not None else None,
            filters=filters,
            project_id=project_id,
            exclude=list(exclude) if exclude is not None else None,
            min_query_length=min_query_length,
            page_size=page_size,
            on_error=self._bus.failed.emit,
        ))
        self._search.subscribe(self._bus.state.emit)
        self._runner = QueryRunner(search_pool(), delay_ms=debounce_ms, parent=self)

        self._rows = PickerRowModel(
            (),
            self,
            context=context,
            thumbnail=thumbnail,
            label_field=label_field,
            sub_label_field=sub_label_field,
            sub_label=sub_label,
            secondary_field=secondary_field,
            secondary=self._secondary_of,
            show_code=show_code,
            round_thumbnail=round_thumbnail,
            size=self._size,
            fields=list(fields) if fields is not None else (),
            site_url=site_url,
        )
        self._rows.rows_changed.connect(self._refresh_chips)

        delegate = RowDelegate(
            None,
            size=self._size,
            thumbnail=thumbnail is not False,
            round_thumbnail=round_thumbnail,
            indicator="checkbox" if self.MULTIPLE else "tick",
        )
        self._control = PickerControl(
            slot="entity-picker",
            picker="entity-multi" if self.MULTIPLE else "entity",
            multiple=self.MULTIPLE,
            summary=summary if self.MULTIPLE else "chips",
            max=max,
            chip_row=self.MULTIPLE,
            inline=(summary == "chips") if self.MULTIPLE else True,
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
            row_model=self._rows,
            row_delegate=delegate,
            parent=self,
        )
        delegate.setParent(self._control.list_surface())
        self._control.set_chip_factory(self._chip_for)
        self._control.selected.connect(self._on_selected)
        self._control.open_changed.connect(self._on_open_changed)
        self._control.query_changed.connect(self._on_query)
        self._control.remove_requested.connect(self._on_remove_at)
        self._control.cleared.connect(self._on_clear)
        self._control.load_more_requested.connect(self._on_load_more)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._control)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self.setObjectName("entity-picker")
        # The core search outlives the widget unless it is told to stop, and a state written
        # after the widget has gone would reach a deleted control.
        search = self._search
        self.destroyed.connect(lambda *_: search.dispose())
        if open:
            self._control.set_open(True)

    # --- the value, which is where the two differ ------------------------------------------

    def _refs(self) -> list[EntityRef]:
        raise NotImplementedError

    def _emit_value(self, refs: Sequence[EntityRef]) -> None:
        raise NotImplementedError

    def _row_of(self, ref: EntityRef) -> PickerRow:
        found = self._search.known.get(entity_key(ref))
        if found is not None:
            return found
        return PickerRow(
            type=ref.type, id=ref.id, name=ref.name or placeholder_name(ref), values={},
        )

    # --- the control ------------------------------------------------------------------------

    @property
    def control(self) -> PickerControl:
        """The control box and popup shell this picker is built on."""
        return self._control

    @property
    def search(self) -> Any:
        """The core search this picker drives."""
        return self._search

    @property
    def rows_model(self) -> PickerRowModel:
        """The rows the list draws."""
        return self._rows

    @property
    def state(self) -> EntitySearchState:
        """The query the rows answer, and whether a read is in flight or failed."""
        return self._state

    # --- props ------------------------------------------------------------------------------

    @property
    def entity_types(self) -> list[str]:
        """Types to search. One for a homogeneous picker, several for a polymorphic one."""
        return list(self._entity_types)

    def set_entity_types(self, value: Sequence[str]) -> None:
        self._entity_types = list(value)
        self._search.update(entity_types=list(value))

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it, so widgets share one cache."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._rows.set_context(value)
        self._search.update(client=_client_of(value), schema=getattr(value, "schema", None))

    @property
    def label_field(self) -> str | None:
        """Field holding the row label. Defaults to the display-name chain."""
        return self._rows.label_field

    def set_label_field(self, value: str | None) -> None:
        self._rows.set_label_field(value)
        self._search.update(label_field=value)

    @property
    def search_fields(self) -> Any:
        """Extra fields the query is matched against, on top of the display-name chain."""
        return self._search._opts.search_fields

    def set_search_fields(self, value: Any) -> None:
        self._search.update(search_fields=value)

    @property
    def secondary_field(self) -> Any:
        """Field shown right-aligned, drawn by its data type."""
        return self._rows.secondary_field

    def set_secondary_field(self, value: Any) -> None:
        self._rows.set_secondary_field(value)
        self._search.update(secondary_field=value)

    @property
    def secondary(self) -> Callable[[PickerRow], str] | None:
        """Right-aligned text of the caller's own making. Wins over `secondary_field`."""
        return self._secondary

    def set_secondary(self, value: Callable[[PickerRow], str] | None) -> None:
        self._secondary = value
        self._rows.set_secondary(self._secondary_of)

    @property
    def sub_label_field(self) -> Any:
        """Field shown under the label."""
        return self._rows.sub_label_field

    def set_sub_label_field(self, value: Any) -> None:
        self._rows.set_sub_label_field(value)
        self._search.update(sub_label_field=value)

    @property
    def sub_label(self) -> Callable[[PickerRow], str] | None:
        """The muted line of the caller's own making. Wins over `sub_label_field`."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[PickerRow], str] | None) -> None:
        self._sub_label = value
        self._rows.set_sub_label(value)

    @property
    def thumbnail(self) -> Any:
        """Field holding the thumbnail URL. `False` hides the leading slot."""
        return self._thumbnail

    def set_thumbnail(self, value: Any) -> None:
        self._thumbnail = value
        self._rows.set_thumbnail(value)
        self._control.row_delegate().set_thumbnail(value is not False)
        self._search.update(thumbnail=value)
        self._control.rebuild_chips()

    @property
    def round_thumbnail(self) -> bool:
        return self._round_thumbnail

    def set_round_thumbnail(self, value: bool) -> None:
        self._round_thumbnail = bool(value)
        self._rows.set_round_thumbnail(self._round_thumbnail)

    @property
    def show_code(self) -> bool:
        """Show the row's code beside the label when the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._rows.set_show_code(self._show_code)

    @property
    def site_url(self) -> str:
        """The site a status glyph is served from. Defaults to the context's."""
        return self._rows.site_url

    def set_site_url(self, value: str | None) -> None:
        self._site_url = value
        self._rows.set_site_url(value)

    @property
    def fields(self) -> list[str]:
        """Extra fields to request, so a caller's own sub-label or secondary can be read."""
        return self._rows.fields

    def set_fields(self, value: Sequence[str]) -> None:
        self._rows.set_fields(value)
        self._search.update(fields=list(value))

    @property
    def filters(self) -> Any:
        """Pre-filter merged into every search with `and`."""
        return self._search._opts.filters

    def set_filters(self, value: Any) -> None:
        self._search.update(filters=value)

    @property
    def project_id(self) -> int | None:
        """Sugar for a project condition. Skipped on a type with no project link."""
        return self._search._opts.project_id

    def set_project_id(self, value: int | None) -> None:
        self._search.update(project_id=value)

    @property
    def exclude(self) -> list[EntityRef]:
        """Rows to keep out of the results. Pushed into the server filter as `id not_in`."""
        return list(self._search._opts.exclude or [])

    def set_exclude(self, value: Sequence[EntityRef] | None) -> None:
        self._search.update(exclude=list(value) if value is not None else None)

    @property
    def min_query_length(self) -> int:
        return self._search._opts.min_query_length or 0

    def set_min_query_length(self, value: int) -> None:
        self._search.update(min_query_length=int(value))

    @property
    def page_size(self) -> int:
        return self._search._opts.page_size or 20

    def set_page_size(self, value: int) -> None:
        self._search.update(page_size=int(value))

    @property
    def debounce_ms(self) -> int:
        """The pause a typist leaves before a query is asked for."""
        return self._runner.delay_ms

    def set_debounce_ms(self, value: int) -> None:
        self._runner.set_delay_ms(int(value))

    @property
    def placeholder(self) -> str:
        return self._control.placeholder

    def set_placeholder(self, value: str) -> None:
        self._control.set_placeholder(value)
        self._sync_input_placeholder()

    @property
    def search_placeholder(self) -> str:
        return self._control.search_placeholder

    def set_search_placeholder(self, value: str) -> None:
        self._control.set_search_placeholder(value)
        self._sync_input_placeholder()

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
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in PICKER_SIZE_VALUES else "md"
        self._control.set_size(self._size)
        self._rows.set_size(self._size)
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
    def open(self) -> bool:
        """Whether the popup is showing."""
        return self._control.is_open

    def set_open(self, value: bool) -> None:
        self._control.set_open(value)

    # --- the read ---------------------------------------------------------------------------

    def _request(self, query: str, number: int, delay_ms: int | None = None) -> None:
        """The worker split: `begin` here, `fetch_page` on a thread, `deliver` back here."""
        ticket = self._search.begin()
        self._page = number
        self._runner.start(
            self._search.fetch_page,
            query,
            number,
            on_result=lambda result: self._search.deliver(ticket, query, number, result),
            on_error=lambda error: self._search.fail(ticket, _as_error(error)),
            delay_ms=delay_ms,
        )

    def _hydrate(self, refs: Sequence[EntityRef]) -> None:
        """Read the rows behind bare references, off the GUI thread."""
        wanted = list(refs)
        if not wanted:
            return
        search_pool().submit(self._search.hydrate, wanted)

    def _on_query(self, query: str) -> None:
        self._pending_query = query
        if self._control.is_open:
            self._request(query, 1)

    def _on_open_changed(self, is_open: bool) -> None:
        if is_open:
            self._request(self._control.query, 1)
        self.open_changed.emit(is_open)

    def _on_load_more(self) -> None:
        if not self._state.has_more or self._state.loading:
            return
        self._request(self._state.query, self._page + 1, delay_ms=0)

    def _on_state(self, state: EntitySearchState) -> None:
        self._state = state
        self._refresh()

    def _on_failed(self, error: object) -> None:
        self.error.emit(_as_error(error))

    # --- what the control shows ---------------------------------------------------------------

    def _options(self) -> list[PickerRow]:
        return with_selected_pinned(self._state.rows, self._refs(), self._search.known)

    def _refresh(self) -> None:
        refs = self._refs()
        options = self._options()
        self._rows.set_query(self._state.query)
        self._rows.set_rows(options)
        if self.MULTIPLE:
            self._rows.set_checked_keys(entity_key(ref) for ref in refs)
        self._control.set_items([entity_key(row) for row in options])
        self._control.set_keys([entity_key(ref) for ref in refs])
        self._control.set_loading(self._state.loading and len(options) == 0)
        self._control.set_error(str(self._state.error) if self._state.error is not None else None)
        self._control.set_empty(len(options) == 0)
        self._control.set_has_more(self._state.has_more)
        self._refresh_chips()

    def _refresh_chips(self) -> None:
        self._control.set_labels([self._row_of(ref).name for ref in self._refs()])
        self._sync_input_placeholder()

    def _sync_input_placeholder(self) -> None:
        """The caret beside a chosen chip invites the next query.

        Upstream's single picker passes `inputPlaceholder={chipEntity ? searchPlaceholder :
        placeholder}`, so a filled control reads "Search…" beside its chip rather than nothing.
        A token field passes none and keeps the base's rule, which is the empty string once it
        holds chips: there the chips already say what the field is for.
        """
        if self.MULTIPLE:
            return
        filled = bool(self._control.labels)
        self._control.set_input_placeholder(
            self._control.search_placeholder if filled else self._control.placeholder
        )

    def _secondary_of(self, row: PickerRow) -> str:
        """The caller's own secondary, and the type on a polymorphic list that names none."""
        if self._secondary is not None:
            return self._secondary(row)
        if not path_of(self._rows.secondary_field) and len(self._entity_types) > 1:
            return row.type
        return ""

    # --- the chip -----------------------------------------------------------------------------

    def _chip_for(self, index: int) -> QtWidgets.QWidget | None:
        refs = self._refs()
        if not 0 <= index < len(refs):
            return None
        ref = refs[index]
        row = self._row_of(ref)
        step = PICKER_CHIP[self._size]
        removable = self.MULTIPLE and not self._control.readonly and not self._control.disabled
        url = row_thumbnail(row.values, self._rows.anatomy())
        if _EntityChip is not None:
            # An empty href leaves the chip inert, so a press on it reaches the control and
            # toggles the list, which is clause 1 of the contract.
            chip: QtWidgets.QWidget = _EntityChip(
                entity=EntityRef(type=row.type, id=row.id, name=row.name),
                href="",
                context=self._context,
                site_url=self._site_url or "",
                size=step,
                removable=removable,
                parent=self._control,
            )
        else:
            chip = Chip(row.name, size=step, removable=removable, parent=self._control)
        # The picture is read here rather than by the chip, so a chip the selection replaced
        # while its read was in flight is dropped rather than written to.
        if url:
            side = QtCore.QSize(*_chip_picture_size(step))
            image_loader().load(url, _chip_picture(chip), side)
        return chip

    # --- picking --------------------------------------------------------------------------------

    def _on_selected(self, keys: list) -> None:
        raise NotImplementedError

    def _on_remove_at(self, index: int) -> None:
        raise NotImplementedError

    def _on_clear(self) -> None:
        self._emit_value([])

    # --- teardown --------------------------------------------------------------------------------

    def dispose(self) -> None:
        """Drop the read in flight and stop writing state. Called when the widget goes."""
        self._runner.cancel()
        self._search.dispose()


def _chip_picture_size(step: str) -> tuple[int, int]:
    from ..primitives.base import CHIP_GLYPH

    side = CHIP_GLYPH.get(step, 14)
    return side, side


def _chip_picture(chip: QtWidgets.QWidget) -> Callable[[Any], None]:
    def landed(picture: Any) -> None:
        try:
            if picture is not None and not picture.isNull():
                chip.set_pixmap(picture)
        except RuntimeError:  # The chip went while the picture was in flight.
            pass

    return landed


def _client_of(context: Any) -> Any:
    """The cached client a context reads through, or the object itself where it is one."""
    found = getattr(context, "client", None)
    return found if found is not None else context


def _as_error(cause: Any) -> Exception:
    return cause if isinstance(cause, Exception) else Exception(str(cause))


class EntityPicker(EntitySearchPicker):
    """One entity, chosen by server-side search.

    The chosen row is an `EntityRef`; a bare `{type, id}` handed in is resolved by one batched
    read. The secondary column is drawn by the field's data type, so a status is a glyph and a
    name and a date is formatted.
    """

    #: The chosen reference and the row behind it, or None and None.
    value_changed = Signal(object, object)

    MULTIPLE = False

    def __init__(
        self,
        entity_types: Sequence[str] = (),
        context: Any = None,
        value: EntityRef | None = None,
        placeholder: str = "Search for an entity",
        **props: Any,
    ) -> None:
        self._value: EntityRef | None = None
        super().__init__(
            entity_types=entity_types, context=context, placeholder=placeholder, **props
        )
        self.setObjectName("entity-picker")
        self.set_value(value)

    @property
    def value(self) -> EntityRef | None:
        """The chosen row. A bare `{type, id}` is resolved on the way in."""
        return self._value

    def set_value(self, value: EntityRef | None) -> None:
        """Choose a row, or nothing. A bare reference is hydrated by one batched read."""
        self._value = value
        if value is not None:
            self._hydrate([value])
        self._refresh()

    def _refs(self) -> list[EntityRef]:
        return [self._value] if self._value is not None else []

    def _emit_value(self, refs: Sequence[EntityRef]) -> None:
        self._value = refs[0] if refs else None
        self._refresh()
        row = self._row_of(self._value) if self._value is not None else None
        self.value_changed.emit(self._value, row)

    def _on_selected(self, keys: list) -> None:
        if not keys:
            self._emit_value([])
            return
        row = next((one for one in self._options() if entity_key(one) == keys[0]), None)
        if row is None:
            return
        self._search.remember([row])
        self._emit_value([EntityRef(type=row.type, id=row.id, name=row.name)])

    def _on_remove_at(self, _index: int) -> None:
        self._emit_value([])
