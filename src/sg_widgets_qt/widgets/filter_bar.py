"""Quick facets over one entity type.

Ported from `packages/react/src/registry/sg/components/filter-bar.tsx` and its Svelte twin.
An untouched facet is a quiet pill naming its field; ticking a value turns it into a pill
reading the field and the values ticked, and opening it again reopens the checklist. The pill
adds its condition to the bound tree, and More filters opens the same tree in the full editor,
so the two edit one value: a condition the editor wrote on an operator the checklist cannot
hold reads as text in its pill.

Each facet is counted against the whole filter less its own condition. With `counts` a facet's
values are the site's own groups; a field the site refuses to group, and every field without
`counts`, is tallied from one page of rows, and its list says so. Both reads run on a worker.

    bar = FilterBar(entity_type="Version", context=context, facets=["sg_status_list"])
    bar.changed.connect(apply)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, Qt, Signal

from sg_widgets_core.client import Page, SearchOptions
from sg_widgets_core.filter import FilterGroup, empty_filter
from sg_widgets_core.filter_ux import (
    FacetList,
    FacetReads,
    condition_parts,
    condition_values,
    describe_condition,
    facet_lists,
    facet_scopes,
    facet_shape,
    find_facet,
    set_facet,
    without_paths,
)
from sg_widgets_core.picker import as_filter_group
from sg_widgets_core.pickers import matches_tokens
from sg_widgets_core.render import render_kind_for
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.search import match_runs
from sg_widgets_core.status import StatusRecord, parse_bg_color

from ..primitives.base import (
    CHIP_CROSS,
    CONTROL_GLYPH,
    CONTROL_HEIGHT,
    CONTROL_PAD,
    ThemedWidget,
    elide,
    painter_for,
    text_width,
)
from ..primitives.button import Button
from ..primitives.command import Command
from ..primitives.popover import Popover
from ..primitives.remove_control import RemoveControl
from ..primitives.roles import Roles
from ..primitives.type_scale import line_box
from ..theme import theme_of
from ..workers import Ticket, default_pool
from .field_picker import schema_of
from .filter_dialog import FilterDialog
from .filter_editor import CONTROL_BUTTON, FILTER_EDITOR_SIZE_VALUES
from .state_line import StateLine
from .status_badge import StatusBadge

__all__ = [
    "FACET_POPOVER_WIDTH",
    "FilterBar",
    "FacetValueModel",
]

#: `w-64` of a facet's checklist.
FACET_POPOVER_WIDTH = 256

#: A cross inside the pill sits one step under it on the chip ladder.
CROSS_SIZE: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: A badge sits one step under the pill it is in.
BADGE_SIZE: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: `max-w-64`: what a pill's value takes before it truncates.
VALUE_WIDTH = 256

#: Between the parts inside a pill, and around the rows of the bar.
PILL_GAP = 6
BAR_GAP = 8

#: The line the checklist shows while the counts are on their way.
COUNTING_LABEL = "Counting…"
NO_VALUE_LABEL = "No value."


class FacetValueModel(QtCore.QAbstractListModel):
    """One facet's values: the tick, the status mark, the label with its matched runs, the count."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._values: list[Any] = []
        self._selected: set[str] = set()
        self._query = ""
        self._statuses: dict[str, StatusRecord] = {}
        self._status_field = False

    def set_values(self, values: Sequence[Any]) -> None:
        self.beginResetModel()
        self._values = list(values)
        self.endResetModel()

    def set_selected(self, keys: Sequence[str]) -> None:
        self._selected = {str(one) for one in keys}
        self._redraw()

    def set_query(self, value: str) -> None:
        self._query = value
        self._redraw()

    def set_statuses(self, table: dict[str, StatusRecord], is_status: bool) -> None:
        self._statuses = dict(table)
        self._status_field = bool(is_status)
        self._redraw()

    def value_at(self, row: int) -> Any:
        return self._values[row] if 0 <= row < len(self._values) else None

    def _redraw(self) -> None:
        if self._values:
            top = self.index(0, 0)
            bottom = self.index(len(self._values) - 1, 0)
            self.dataChanged.emit(top, bottom)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._values)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        option = self.value_at(index.row())
        if option is None:
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return option.label
        if role == Roles.RUNS:
            return match_runs(option.label, self._query) if self._query else None
        if role == Roles.SECONDARY:
            return _count_text(option.count)
        if role == Roles.CHECKED:
            return option.key in self._selected
        if role == Roles.GLYPH:
            return self._glyph(option.key)
        if role == Roles.ENTITY:
            return option
        if role == Roles.KIND:
            return "row"
        return None

    def _glyph(self, key: str) -> str | None:
        if not self._status_field:
            return None
        rgb = parse_bg_color(self._statuses[key].bg_color) if key in self._statuses else None
        return f"#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}" if rgb is not None else None

    def flags(self, index: QModelIndex) -> Any:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


def _count_text(count: float) -> str:
    whole = int(count)
    return str(whole) if float(whole) == float(count) else str(count)


class FilterBar(QtWidgets.QWidget):
    """The facet pills over one entity type, and the editor behind More filters."""

    #: The whole tree changed, on every tick and every clear.
    changed = Signal(object)
    #: The same payload under the name the query widgets share.
    filters_changed = Signal(object)
    #: What a failed tally said, or None once one answered.
    error_changed = Signal(object)

    def __init__(
        self,
        entity_type: str = "",
        context: Any = None,
        facets: Sequence[str] = (),
        labels: dict[str, str] | None = None,
        max_values: int = 2,
        value: FilterGroup | None = None,
        counts: Callable[..., Any] | None = None,
        sample_size: int = 200,
        base_filter: Any = None,
        hide_paths: Sequence[str] | None = None,
        disabled: bool = False,
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-bar")
        self._entity_type = str(entity_type or "")
        self._context = context
        self._facets = list(facets)
        self._labels = dict(labels or {})
        self._max_values = int(max_values)
        self._value = value if value is not None else empty_filter()
        self._counts = counts
        self._sample_size = int(sample_size)
        self._base_filter = base_filter
        self._hide_paths = list(hide_paths or [])
        self._disabled = bool(disabled)
        self._size = size if size in FILTER_EDITOR_SIZE_VALUES else "md"

        self._fields: dict[str, FieldSchema] = {}
        self._tally: dict[str, FacetList] = {}
        self._statuses: dict[str, StatusRecord] = {}
        self._refused: set[str] = set()
        self._counting = True
        self._failure: str | None = None
        self._pills: dict[str, _FacetPill] = {}
        self._fields_ticket = Ticket()
        self._counts_ticket = Ticket()
        # A bar taken down under a read in flight — a page left, a demo the toolbar rebuilds —
        # leaves the counts on their way to pills that have gone, and the answer reaches a
        # deleted command box and raises into the event loop. The tickets are plain objects and
        # outlive the widget, so taking them as it goes drops whatever is still out.
        tickets = (self._fields_ticket, self._counts_ticket)
        self.destroyed.connect(lambda *_ignored: [one.cancel() for one in tickets])
        self._open_facet: str | None = None

        self._flow = _FlowLayout(self, spacing=BAR_GAP)
        self._clear_all = Button(
            "Clear all", variant="ghost", size=CONTROL_BUTTON[self._size], parent=self
        )
        self._clear_all.setObjectName("filter-clear-all")
        self._clear_all.clicked.connect(self._on_clear_all)

        self._more = FilterDialog(
            entity_type=self._entity_type,
            context=context,
            value=self._value,
            hide_paths=self._hide_paths,
            label="More filters",
            size=self._size,
            parent=self,
        )
        self._more.changed.connect(self._emit)

        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(0)

        self._read_fields()
        self._read_statuses()
        self._rebuild()

    # --- props ----------------------------------------------------------------------------

    @property
    def entity_type(self) -> str:
        """Type the pills filter on."""
        return self._entity_type

    def set_entity_type(self, value: str) -> None:
        self._entity_type = str(value or "")
        self._more.set_entity_type(self._entity_type)
        self._fields = {}
        self._tally = {}
        self._read_fields()
        self._rebuild()

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._more.set_context(value)
        self._fields = {}
        self._tally = {}
        self._read_fields()
        self._read_statuses()
        self._rebuild()

    @property
    def facets(self) -> list[str]:
        """Field names offered as pills, in order."""
        return list(self._facets)

    def set_facets(self, value: Sequence[str]) -> None:
        self._facets = list(value)
        self._rebuild()
        self._read_counts()

    @property
    def labels(self) -> dict[str, str]:
        """A name per facet, for a field the page calls something else."""
        return dict(self._labels)

    def set_labels(self, value: dict[str, str] | None) -> None:
        self._labels = dict(value or {})
        self._rebuild()

    @property
    def max_values(self) -> int:
        """Values a pill names before the rest reads as `+n`. `0` names every one."""
        return self._max_values

    def set_max_values(self, value: int) -> None:
        self._max_values = int(value)
        self._rebuild()

    @property
    def value(self) -> FilterGroup:
        """The bound tree."""
        return self._value

    def set_value(self, value: FilterGroup | None) -> None:
        """Take a tree from outside. Nothing is emitted."""
        self._value = value if value is not None else empty_filter()
        self._more.set_value(self._value)
        self._rebuild()
        self._read_counts()

    @property
    def counts(self) -> Callable[..., Any] | None:
        """The site's own groups for one facet's field, or None to tally a page of rows."""
        return self._counts

    def set_counts(self, value: Callable[..., Any] | None) -> None:
        self._counts = value
        self._read_counts()

    @property
    def sample_size(self) -> int:
        """Rows read for a tally."""
        return self._sample_size

    def set_sample_size(self, value: int) -> None:
        self._sample_size = int(value)
        self._read_counts()

    @property
    def base_filter(self) -> Any:
        """Conditions every facet query carries, such as a project scope. Never edited here."""
        return self._base_filter

    def set_base_filter(self, value: Any) -> None:
        self._base_filter = value
        self._read_counts()

    @property
    def hide_paths(self) -> list[str]:
        """Paths kept out of the editor's field list."""
        return list(self._hide_paths)

    def set_hide_paths(self, value: Sequence[str] | None) -> None:
        self._hide_paths = list(value or [])
        self._more.set_hide_paths(self._hide_paths)

    @property
    def disabled(self) -> bool:
        """Blocks every pill, the clear controls and the editor."""
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self._more.set_disabled(self._disabled)
        self._rebuild()

    @property
    def size(self) -> str:
        """The control ladder the pills stand on."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in FILTER_EDITOR_SIZE_VALUES else "md"
        self._more.set_size(self._size)
        self._clear_all.set_size(CONTROL_BUTTON[self._size])
        self._rebuild()

    # --- the parts ------------------------------------------------------------------------

    def pills(self) -> dict[str, QtWidgets.QWidget]:
        """One pill per facet, by field name."""
        return dict(self._pills)

    def pill(self, name: str) -> QtWidgets.QWidget | None:
        """The pill of one facet."""
        return self._pills.get(name)

    def more_filters(self) -> FilterDialog:
        """The launcher that opens the same tree in the full editor."""
        return self._more

    def clear_all_button(self) -> Button:
        """The control that drops every facet condition."""
        return self._clear_all

    @property
    def counting(self) -> bool:
        """True while a tally is in flight."""
        return self._counting

    @property
    def failure(self) -> str | None:
        """What a failed tally said, shown in place of the values."""
        return self._failure

    def facet_list(self, name: str) -> FacetList | None:
        """What one facet lists, once its read has answered."""
        return self._tally.get(name)

    def field_of(self, name: str) -> FieldSchema | None:
        """The schema of one facet's field."""
        return self._fields.get(name)

    def label_of(self, name: str) -> str:
        """The caller's name, else the schema's, else the path."""
        found = self._fields.get(name)
        return self._labels.get(name) or (found.display_name if found is not None else name)

    def is_status(self, name: str) -> bool:
        """True where the facet's values are status codes, which draw as badges."""
        found = self._fields.get(name)
        return render_kind_for(found.data_type if found is not None else "") == "status"

    def selected_of(self, name: str) -> list[Any]:
        """The values one facet holds ticked."""
        found = find_facet(self._value, name, self._fields.get(name))
        return list(found.values) if found is not None else []

    # --- the reads ------------------------------------------------------------------------

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
        self._read_counts()

    def _read_statuses(self) -> None:
        table = getattr(self._context, "statuses", None)
        if table is None:
            return
        default_pool().submit(
            table.by_code,
            on_result=self._statuses_read,
            # A facet without the table still reads: a badge falls back to its own code.
            on_error=lambda _error: None,
        )

    def _statuses_read(self, table: Any) -> None:
        self._statuses = dict(table or {})
        self._rebuild()

    def _read_counts(self) -> None:
        present = [self._fields[name] for name in self._facets if name in self._fields]
        client = getattr(self._context, "client", None)
        if not present or client is None:
            return
        base = as_filter_group(self._base_filter)
        scopes = facet_scopes(self._value, base, list(self._facets))
        sample_size = self._sample_size
        entity_type = self._entity_type
        refused = self._refused
        counts = self._counts

        def sample(fields: list[str], filters: Any) -> Any:
            page = client.search(
                entity_type,
                SearchOptions(
                    filters=filters, fields=list(fields), page=Page(size=sample_size)
                ),
            )
            return list(page.data)

        def read() -> dict[str, FacetList]:
            return facet_lists(
                present, scopes, FacetReads(sample=sample, counts=counts, refused=refused)
            )

        self._counting = True
        self._failure = None
        self._refresh_lists()
        token = self._counts_ticket.next()
        default_pool().submit(
            read,
            on_result=self._counts_read,
            on_error=self._counts_failed,
            ticket=(self._counts_ticket, token),
        )

    def _counts_read(self, found: Any) -> None:
        self._tally = dict(found or {})
        self._counting = False
        self._set_failure(None)
        self._refresh_lists()

    def _counts_failed(self, error: BaseException) -> None:
        self._counting = False
        self._set_failure(str(error))
        self._refresh_lists()

    def _set_failure(self, message: str | None) -> None:
        if message != self._failure:
            self._failure = message
            self.error_changed.emit(message)

    # --- edits ----------------------------------------------------------------------------

    def toggle(self, name: str, key: str, value: Any) -> None:
        """Tick or untick one value of one facet."""
        selected = self.selected_of(name)
        keys = [_key_of(one) for one in selected]
        if key in keys:
            kept = [one for one in selected if _key_of(one) != key]
        else:
            kept = [*selected, value]
        field = self._fields.get(name)
        self._emit(set_facet(self._value, name, kept, self._list_operator(name), field))

    def clear_facet(self, name: str) -> None:
        """Untick every value of one facet, leaving its pill quiet."""
        self._emit(set_facet(self._value, name, [], "in", self._fields.get(name)))

    def remove_facet(self, name: str) -> None:
        """Drop whatever the tree holds on one facet's path."""
        self._emit(without_paths(self._value, [name]))

    def _list_operator(self, name: str) -> str:
        found = find_facet(self._value, name, self._fields.get(name))
        if found is not None and found.checklist:
            return found.operator
        return facet_shape(self._fields.get(name)).any

    def _on_clear_all(self) -> None:
        self._emit(without_paths(self._value, list(self._facets)))

    def _emit(self, value: FilterGroup) -> None:
        self._value = value
        self._more.set_value(value)
        self._rebuild()
        self._read_counts()
        self.changed.emit(value)
        self.filters_changed.emit(value)

    # --- the bar --------------------------------------------------------------------------

    def _rebuild(self) -> None:
        open_facet = self._open_facet
        for pill in self._pills.values():
            self._flow.removeWidget(pill)
            pill.setParent(None)
            pill.deleteLater()
        self._pills = {}
        while self._flow.count():
            self._flow.takeAt(0)

        for name in self._facets:
            pill = _FacetPill(self, name, self)
            self._flow.addWidget(pill)
            self._pills[name] = pill
        active = sum(1 for name in self._facets if find_facet(self._value, name, self._fields.get(name)))
        self._clear_all.setVisible(active > 0)
        self._clear_all.setEnabled(not self._disabled)
        self._flow.addWidget(self._clear_all)
        self._flow.addWidget(self._more)
        self._refresh_lists()
        if open_facet is not None and open_facet in self._pills:
            self._pills[open_facet].set_open(True)
        self.updateGeometry()

    def _refresh_lists(self) -> None:
        for name, pill in self._pills.items():
            pill.refresh_list(self._tally.get(name), self._counting, self._failure)

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True


def _key_of(value: Any) -> str:
    if isinstance(value, dict):
        return f"{value.get('type')}:{value.get('id')}"
    return str(value)


class _FlowLayout(QtWidgets.QLayout):
    """A row of pills that wraps at the width it is given, which is upstream's `flex-wrap`."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, spacing: int = BAR_GAP) -> None:
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._lay(QtCore.QRect(0, 0, width, 0), measure=True)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._lay(rect, measure=False)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:  # noqa: N802
        size = QtCore.QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _lay(self, rect: QtCore.QRect, measure: bool) -> int:
        space = self.spacing()
        x, y, line = rect.x(), rect.y(), 0
        pending: list[tuple[QtWidgets.QLayoutItem, int]] = []

        def flush() -> None:
            if measure:
                return
            for item, left in pending:
                hint = item.sizeHint()
                top = y + (line - hint.height()) // 2
                item.setGeometry(QtCore.QRect(QtCore.QPoint(left, top), hint))

        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line > 0:
                flush()
                pending = []
                x = rect.x()
                y += line + space
                line = 0
            pending.append((item, x))
            x += hint.width() + space
            line = max(line, hint.height())
        flush()
        return y + line - rect.y()


class _FacetPill(ThemedWidget):
    """One facet: a quiet dashed pill until a value is ticked, then the field and its values."""

    def __init__(self, bar: FilterBar, name: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._bar = bar
        self._name = name
        self._open = False
        self.setObjectName("filter-pill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

        size = bar.size
        self._found = find_facet(bar.value, name, bar.field_of(name))
        self._parts = condition_parts(self._found.summary, bar.field_of(name)) if self._found else None
        self._shown = (
            condition_values(self._found.summary, bar.field_of(name), bar.max_values)
            if self._found
            else None
        )

        line = QtWidgets.QHBoxLayout(self)
        cross_pad = max(2, (CONTROL_HEIGHT[size] - CHIP_CROSS[CROSS_SIZE[size]]) // 2 - 6)
        line.setContentsMargins(
            CONTROL_PAD[size], 0, cross_pad if self._found else CONTROL_PAD[size], 0
        )
        line.setSpacing(PILL_GAP)

        self._build(line)
        self.setFixedHeight(CONTROL_HEIGHT[size])
        if self._found is not None:
            self.setAccessibleName(describe_condition(self._found.summary, bar.field_of(name)))

        self._model = FacetValueModel(self)
        self._panel = self._build_panel()
        self._popover = Popover(
            self, self._panel, side="bottom", align="start", width=FACET_POPOVER_WIDTH,
            takes_focus=True,
        )
        self._popover.closed.connect(self._on_closed)
        self._popover.dismissed.connect(self._on_closed)
        self.setEnabled(not bar.disabled and bar.field_of(name) is not None)

    # --- the pill face --------------------------------------------------------------------

    def _build(self, line: QtWidgets.QHBoxLayout) -> None:
        bar = self._bar
        size = bar.size
        if self._found is None or self._parts is None:
            self._glyph: QtWidgets.QWidget | None = _Glyph("plus", size, self)
            line.addWidget(self._glyph)
            # An untouched facet is quiet: the whole pill, its name with its mark, is muted.
            line.addWidget(_PillText(bar.label_of(self._name), size, self, muted=True))
            self._cross: RemoveControl | None = None
            return
        self._glyph = None
        field_name = _PillText(bar.label_of(self._name), size, self, weight="medium")
        field_name.setObjectName("filter-pill-field")
        line.addWidget(field_name)
        if self._found.summary.operator != "in":
            line.addWidget(_PillText(self._parts.operator, size, self, muted=True))
        line.addWidget(self._values_widget(), 0, Qt.AlignmentFlag.AlignVCenter)
        # `REMOVE_CONTROL`: the cross and its 2px, on the step under the pill, so it sits level
        # with the chips beside it rather than standing an icon button's height over them.
        self._cross = RemoveControl(
            step=CROSS_SIZE[size], label=f"Remove {bar.label_of(self._name)} filter", parent=self
        )
        self._cross.setObjectName("filter-pill-remove")
        self._cross.setEnabled(not bar.disabled)
        self._cross.clicked.connect(lambda: bar.remove_facet(self._name))
        line.addWidget(self._cross, 0, Qt.AlignmentFlag.AlignVCenter)

    def _values_widget(self) -> QtWidgets.QWidget:
        bar = self._bar
        shown = self._shown
        holder = QtWidgets.QWidget(self)
        holder.setObjectName("filter-pill-values")
        # `items-center`: the run of values is as tall as the tallest thing in it — a chip, or
        # one line of text — and centres in the pill rather than filling its height.
        holder.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        row = QtWidgets.QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(PILL_GAP)
        if shown is None:
            return holder
        holder.setToolTip(shown.title)
        if bar.is_status(self._name) and shown.values:
            for scalar in shown.values:
                key = _key_of(scalar)
                row.addWidget(
                    StatusBadge(
                        code=key,
                        status=bar._statuses.get(key),  # noqa: SLF001
                        field=bar.field_of(self._name),
                        size=BADGE_SIZE[bar.size],
                        site_url=getattr(bar.context, "site_url", "") or "",
                        parent=holder,
                    )
                )
        elif shown.text:
            row.addWidget(_PillText(shown.text, bar.size, holder, max_width=VALUE_WIDTH))
        if shown.overflow > 0:
            overflow = _PillText(f"+{shown.overflow}", bar.size, holder, muted=True)
            overflow.setObjectName("filter-pill-overflow")
            row.addWidget(overflow)
        return holder

    # --- the checklist --------------------------------------------------------------------

    def _build_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("facet-panel")
        column = QtWidgets.QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self._command = Command(
            panel, placeholder="Search values…", should_filter=False, size=self._bar.size
        )
        self._command.set_model(self._model)
        surface = self._command.list_surface()
        delegate = surface.row_delegate()
        delegate.set_thumbnail(False)
        delegate.set_indicator("checkbox")
        delegate.set_bare_glyph(True)
        self._command.query_changed.connect(self._on_query)
        self._command.activated.connect(self._on_activated)
        column.addWidget(self._command)

        self._state = StateLine(
            state="loading", label=COUNTING_LABEL, slot_name="filter-bar-state", parent=panel
        )
        column.addWidget(self._state)

        self._sample = _SampleNote(panel)
        self._sample.setObjectName("facet-sample")
        column.addWidget(self._sample)

        self._clear = Button("Clear", variant="ghost", size="sm", parent=panel)
        self._clear.setObjectName("filter-pill-clear")
        self._clear.set_expanded(True)
        self._clear.clicked.connect(lambda: self._bar.clear_facet(self._name))
        column.addWidget(self._clear)
        return panel

    def refresh_list(
        self, listed: FacetList | None, counting: bool, failure: str | None
    ) -> None:
        """Take the values one read answered, or the line that stands in for them."""
        bar = self._bar
        self._model.set_statuses(bar._statuses, bar.is_status(self._name))  # noqa: SLF001
        self._model.set_selected([_key_of(one) for one in bar.selected_of(self._name)])
        query = self._command.query
        values = [
            option
            for option in (listed.values if listed is not None else [])
            if matches_tokens(query, option.label, option.key)
        ]
        self._model.set_values(values)
        if counting:
            self._state.set_state("loading")
            self._state.set_label(COUNTING_LABEL)
        elif failure:
            self._state.set_state("error")
            self._state.set_label(failure)
        elif not values:
            self._state.set_state("empty")
            self._state.set_label(NO_VALUE_LABEL)
        self._state.setVisible(counting or bool(failure) or not values)
        self._command.list_surface().setVisible(bool(values))
        sampled = listed.sampled if listed is not None else None
        self._sample.set_count(sampled if not counting and not failure else None)
        self._clear.setVisible(bool(bar.selected_of(self._name)))

    def _on_query(self, _text: str) -> None:
        self.refresh_list(
            self._bar.facet_list(self._name), self._bar.counting, self._bar.failure
        )

    def _on_activated(self, row: int) -> None:
        option = self._model.value_at(row)
        if option is not None:
            self._bar.toggle(self._name, option.key, option.value)

    # --- opening --------------------------------------------------------------------------

    @property
    def open(self) -> bool:
        """Whether the checklist is showing."""
        return self._open

    def set_open(self, value: bool) -> None:
        """Show or hide the checklist."""
        want = bool(value) and self.isEnabled()
        if want == self._open:
            return
        self._open = want
        self._bar._open_facet = self._name if want else None  # noqa: SLF001
        if want:
            self._popover.open()
            self._command.input().setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self._popover.close()
        self.update()

    def _on_closed(self) -> None:
        if self._open:
            self._open = False
            if self._bar._open_facet == self._name:  # noqa: SLF001
                self._bar._open_facet = None  # noqa: SLF001
            self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_open(not self._open)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.set_open(not self._open)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self._open:
            self.set_open(False)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = painter_for(self)
        radius = float(theme.radius_px("lg"))
        box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._found is not None:
            painter.setBrush(theme.color("background"))
            painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        else:
            pen = QtGui.QPen(theme.color("border"), 1.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pen)
        painter.drawRoundedRect(box, radius, radius)
        painter.end()


class _Glyph(ThemedWidget):
    """A lucide mark inside a pill, at the control's own glyph step."""

    def __init__(self, name: str, size: str = "md", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._side = CONTROL_GLYPH[size]
        self.setFixedSize(self._side, self._side)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        from .. import icons

        painter = painter_for(self)
        icons.paint_icon(painter, self.rect(), self._name, theme_of(self).color("muted_foreground"))
        painter.end()


class _PillText(ThemedWidget):
    """One run of a pill's own type step, elided at the width it is given."""

    def __init__(
        self,
        text: str = "",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
        muted: bool = False,
        weight: str = "regular",
        max_width: int = 0,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._muted = bool(muted)
        self._weight = weight
        self._max_width = int(max_width)
        self._step = 14 if size != "sm" else 13
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setToolTip(text)

    def text(self) -> str:
        return self._text

    @property
    def muted(self) -> bool:
        """True where the run is drawn in `muted_foreground`, as a quiet pill's is."""
        return self._muted

    def _font(self) -> QtGui.QFont:
        weight = QtGui.QFont.Weight.Medium if self._weight == "medium" else QtGui.QFont.Weight.Normal
        return theme_of(self).font(self._step, weight)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        """The run's own width, on the line its type step stands on.

        The line is the type scale's, not the font's: a pill holding a chip and a run of text
        keeps the two on one centre line whatever family the theme wears.
        """
        metrics = QtGui.QFontMetrics(self._font())
        width = text_width(metrics, self._text)
        if self._max_width:
            width = min(width, self._max_width)
        return QtCore.QSize(width, line_box(self._step))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = painter_for(self)
        painter.setFont(self._font())
        painter.setPen(theme.color("muted_foreground" if self._muted else "foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elide(painter, self._text, self.width()),
        )
        painter.end()


class _SampleNote(ThemedWidget):
    """A tally is as complete as the page it read, and the list says so."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._count: int | None = None
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.hide()

    @property
    def count(self) -> int | None:
        return self._count

    def set_count(self, value: int | None) -> None:
        self._count = value
        self.setVisible(value is not None)
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return "" if self._count is None else f"Counts from a sample of {self._count} rows"

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(theme_of(self).font(12))
        return QtCore.QSize(0, metrics.height() + 12)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = painter_for(self)
        painter.fillRect(QtCore.QRect(0, 0, self.width(), 1), theme.color("border"))
        painter.setFont(theme.font(12))
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            self.rect().adjusted(8, 0, -8, 0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elide(painter, self.text(), self.width() - 16),
        )
        painter.end()
