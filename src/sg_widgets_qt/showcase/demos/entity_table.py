"""320 Versions in pages of 25, with a column picker and a sort picker in the toolbar.

The port of `apps/site/src/demos/entity-table/Demo.tsx`. The toggles above the table group the
rows by status, collapse and expand every header, halve the row padding, switch how the set is
walked, and move every cell editor between a popover and the cell itself. A double-click or Enter
on an editable cell opens that editor.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.collection import (
    ColumnSpec,
    EntitySourceOptions,
    create_entity_source,
    resolve_columns,
)
from sg_widgets_core.collection_state import collapse_all, expand_all, to_sort_specs
from sg_widgets_core.filter import condition
from sg_widgets_core.mock import MockCounts

from ...widgets.column_picker import ColumnPicker
from ...widgets.entity_table import EntityTable
from ...workers import default_pool
from .. import chrome
from ..context import DemoContext, demo_context
from . import _layout as lay

__all__ = ["build"]

#: The columns the demo offers, and the width each opens at.
WIDTHS: dict[str, int] = {
    "code": 260,
    "entity": 150,
    "sg_status_list": 150,
    "image": 90,
    "description": 260,
    "user": 160,
    "created_at": 170,
    "updated_at": 170,
}
PATHS = tuple(WIDTHS)
SHOWN = ("code", "entity", "sg_status_list", "image", "description", "user")

#: The three ways a set is walked, and the two places an editor opens.
PAGING = (("pages", "Pages"), ("more", "Load more"), ("scroll", "Scroll"))
PLACEMENTS = (("popover", "Popover editor"), ("inline", "Inline editor"))

#: Versions the mock answers for this page, so the footer has a set worth walking.
VERSIONS = 320
PAGE_SIZE = 25

#: The column picker's own width, so the toolbar keeps its shape when it opens.
PICKER_WIDTH = 224


class EntityTableDemo(QtWidgets.QWidget):
    """The toolbar of toggles, and the table under it."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-table-demo")
        self._context = context
        self._ready = False
        # The mock's rows are one project's already; a real site's are not.
        scope = (
            condition("project", "is", {"type": "Project", "id": context.project_id})
            if context.live
            else None
        )
        self._source = create_entity_source(
            EntitySourceOptions(
                client=context.client,
                entity_type="Version",
                fields=list(PATHS),
                filters=scope,
                mode="pages",
                page_size=PAGE_SIZE,
            )
        )
        self.table = EntityTable(
            source=self._source,
            context=context,
            selectable=True,
            editable=True,
            paging="pages",
            editor_placement="popover",
            parent=self,
        )
        self.table.selection_changed.connect(self._on_selection)
        self.table.columns_changed.connect(self._on_columns)

        body = lay.column(self)
        bar = QtWidgets.QWidget(self)
        toggles = lay.FlowLayout(bar)
        self._grouped = chrome.toggle("Group by status", size="sm", parent=bar)
        self._grouped.setObjectName("group-by-status")
        self._grouped.toggled.connect(self._on_group)
        toggles.addWidget(self._grouped)
        self._collapse = chrome.button(
            "Collapse all", variant="outline", size="sm", parent=bar,
            on_click=lambda: self.table.set_collapsed(collapse_all()),
        )
        self._collapse.setObjectName("collapse-all")
        self._collapse.setEnabled(False)
        toggles.addWidget(self._collapse)
        self._expand = chrome.button(
            "Expand all", variant="outline", size="sm", parent=bar,
            on_click=lambda: self.table.set_collapsed(expand_all()),
        )
        self._expand.setObjectName("expand-all")
        self._expand.setEnabled(False)
        toggles.addWidget(self._expand)
        self._compact = chrome.toggle("Compact", size="sm", parent=bar)
        self._compact.setObjectName("compact")
        self._compact.toggled.connect(
            lambda on: self.table.set_density("compact" if on else "default")
        )
        toggles.addWidget(self._compact)
        self._paging = _radio(bar, toggles, PAGING, "paging", self.table.set_paging)
        self._placement = _radio(
            bar, toggles, PLACEMENTS, "placement", self.table.set_editor_placement
        )
        self._count = chrome.TextLine("0 selected", size=12, parent=bar)
        self._count.setObjectName("selection-count")
        toggles.addWidget(self._count)
        body.addWidget(bar)
        body.addWidget(self.table)

        # The column picker sits behind a toggle, as upstream does: a list of six paths is
        # taller than the table's own toolbar.
        self._columns_box = QtWidgets.QWidget(self)
        columns = QtWidgets.QVBoxLayout(self._columns_box)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(8)
        self._columns_toggle = chrome.toggle("Columns", size="sm", parent=self._columns_box)
        self._columns_toggle.setObjectName("columns-toggle")
        self._columns_toggle.toggled.connect(self._on_picking)
        columns.addWidget(self._columns_toggle)
        self._picker = ColumnPicker(
            context=context,
            entity_type="Version",
            value=list(SHOWN),
            deep_links=False,
            size="sm",
            filter=lambda _field, path: path in PATHS,
            parent=self._columns_box,
        )
        self._picker.setFixedWidth(PICKER_WIDTH)
        self._picker.hide()
        self._picker.value_changed.connect(self._pick_columns)
        columns.addWidget(self._picker)

        self._sort = _sort_picker(context, self)
        self.table.set_toolbar_start(self._columns_box)
        if self._sort is not None:
            self._sort.sort_changed.connect(self._on_sort_keys)
            self.table.set_toolbar_end(self._sort)

        self._read_columns(list(SHOWN))

    @property
    def demo_ready(self) -> bool:
        """True once the columns are resolved and the first page has settled."""
        return self._ready and self.table.control.snapshot().status in ("ready", "error")

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        self.table.set_size(size if size in ("sm", "md", "lg") else "md")

    # --- the columns ----------------------------------------------------------------------

    def _read_columns(self, paths: list[str]) -> None:
        specs = [ColumnSpec(path=path, width=WIDTHS.get(path)) for path in paths]
        default_pool().submit(
            _resolve, self._context, specs, on_result=self._columns_read, on_error=self._failed
        )

    def _columns_read(self, answer: Any) -> None:
        if not lay.alive(self):
            return
        columns, statuses = answer
        self.table.set_statuses(statuses)
        self.table.set_columns(columns)
        self.table.control.count()
        self._ready = True

    def _failed(self, error: BaseException) -> None:
        if lay.alive(self):
            self._ready = True
            self.table.failed.emit(error)

    def _on_picking(self, on: bool) -> None:
        self._picker.setVisible(bool(on))

    def _pick_columns(self, paths: object) -> None:
        self._read_columns([str(path) for path in paths or []])

    def _on_columns(self, columns: object) -> None:
        self._picker.set_value([column.path for column in columns or []])

    # --- the toggles ----------------------------------------------------------------------

    def _on_group(self, on: bool) -> None:
        self.table.set_group_by("sg_status_list" if on else None)
        self._collapse.setEnabled(on)
        self._expand.setEnabled(on)

    def _on_selection(self, rows: object) -> None:
        self._count.set_text(f"{len(rows or [])} selected")

    def _on_sort_keys(self, keys: object) -> None:
        self.table.set_sort(to_sort_specs(list(keys or [])))


def _radio(
    parent: QtWidgets.QWidget,
    layout: Any,
    options: tuple[tuple[str, str], ...],
    name: str,
    apply: Any,
) -> dict[str, Any]:
    """One toggle per option, of which exactly one stays down."""
    made: dict[str, Any] = {}

    def choose(value: str) -> None:
        apply(value)
        for key, toggle in made.items():
            toggle.set_checked(key == value)

    for value, label in options:
        toggle = chrome.toggle(label, size="sm", parent=parent)
        toggle.setObjectName(f"{name}-{value}")
        toggle.toggled.connect(lambda _on, picked=value: choose(picked))
        made[value] = toggle
        layout.addWidget(toggle)
    made[options[0][0]].set_checked(True)
    return made


def _sort_picker(context: DemoContext, parent: QtWidgets.QWidget) -> Any:
    """The sort picker, when it has landed. Without it the header clicks are the only sort."""
    try:
        from ...widgets.sort_picker import SortPicker
    except Exception:
        return None
    return SortPicker(
        entity_type="Version", context=context, paths=list(PATHS), size="sm", parent=parent
    )


def _resolve(context: DemoContext, specs: list[ColumnSpec]) -> tuple[Any, Any]:
    """The columns and the status table, both read on a worker thread."""
    columns = resolve_columns(context.schema, "Version", specs)
    return columns, dict(context.statuses.by_code())


def table_context(context: DemoContext) -> DemoContext:
    """The context this page reads through: the mock sized to 320 Versions, or the site itself."""
    if context.live:
        return context
    return demo_context(counts=MockCounts(versions=VERSIONS))


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityTableDemo(table_context(context), parent)
