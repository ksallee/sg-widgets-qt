"""Tasks by pipeline step, then Versions under the record each is of, from a derived key.

The port of `apps/site/src/demos/grouped-list/Demo.tsx`. The first list groups on a column and is
sorted on it; the second groups on a value the caller derives, so the caller's own sort is what
puts the runs together. The last two show the empty line and a page that failed.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import (
    EntitySourceOptions,
    SortSpec,
    cell_value,
    create_entity_source,
    resolve_columns,
)
from sg_widgets_core.collection_state import collapse_all, expand_all
from sg_widgets_core.filter import condition
from sg_widgets_core.schema import display_name_of

from ...widgets.grouped_list import GroupedList
from ...workers import default_pool
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: The column the Tasks group on, the muted line and the right-aligned value.
GROUP = "step.Step.code"
SUB = "sg_description"
SECONDARY = "due_date"
FIELDS = ("content", "sg_status_list", GROUP, SUB, SECONDARY)

#: A filter no Task matches, so the list draws the caller's own empty label.
NO_SUCH_TASK = "no such task"

PAGE_SIZE = 25


class GroupedListDemo(QtWidgets.QWidget):
    """The paged list, the derived one, and the two state blocks."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("grouped-list-demo")
        self._context = context
        self._ready = False
        # The mock's rows are one project's already; a real site's are not.
        scope = (
            condition("project", "is", {"type": "Project", "id": context.project_id})
            if context.live
            else None
        )
        source = create_entity_source(
            EntitySourceOptions(
                client=context.client,
                entity_type="Task",
                fields=list(FIELDS),
                filters=scope,
                mode="pages",
                page_size=PAGE_SIZE,
            )
        )
        empty_source = create_entity_source(
            EntitySourceOptions(
                client=context.client,
                entity_type="Task",
                fields=list(FIELDS),
                filters=condition("content", "is", NO_SUCH_TASK),
                mode="pages",
                page_size=PAGE_SIZE,
            )
        )
        # Versions under the Shot or Asset each is of. The record is `entity`, which no site
        # sorts on: the caller's own sort on `code` is what puts one record's versions together.
        record_source = create_entity_source(
            EntitySourceOptions(
                client=context.client,
                entity_type="Version",
                fields=["code", "sg_status_list", "entity", "description"],
                filters=scope,
                sort=[SortSpec(path="code", descending=False)],
                page_size=PAGE_SIZE,
            )
        )

        body = lay.column(self)

        bar = QtWidgets.QWidget(self)
        toggles = lay.FlowLayout(bar)
        self._compact = chrome.toggle("Compact", size="sm", parent=bar)
        self._compact.setObjectName("compact")
        self._compact.toggled.connect(
            lambda on: self.listing.set_density("compact" if on else "default")
        )
        toggles.addWidget(self._compact)
        toggles.addWidget(
            chrome.button(
                "Collapse all", variant="outline", size="sm", parent=bar,
                on_click=lambda: self.listing.set_collapsed(collapse_all()),
            )
        )
        toggles.addWidget(
            chrome.button(
                "Expand all", variant="outline", size="sm", parent=bar,
                on_click=lambda: self.listing.set_collapsed(expand_all()),
            )
        )
        self._count = chrome.TextLine("0 selected", size=12, parent=bar)
        self._count.setObjectName("selection-count")
        toggles.addWidget(self._count)

        self.listing = GroupedList(
            source=source,
            context=context,
            paging="pages",
            group_by=_placeholder(GROUP),
            label_field="content",
            selectable=True,
            leading=self._status_colour,
            parent=self,
        )
        self.listing.selection_changed.connect(
            lambda rows: self._count.set_text(f"{len(rows or [])} selected")
        )
        body.addWidget(lay.section("Tasks by pipeline step", bar, self.listing, parent=self))

        derived = QtWidgets.QWidget(self)
        derived_bar = lay.FlowLayout(derived)
        derived_bar.addWidget(
            chrome.button(
                "Collapse all", variant="outline", size="sm", parent=derived,
                on_click=lambda: self.derived.set_collapsed(collapse_all()),
            )
        )
        derived_bar.addWidget(
            chrome.button(
                "Expand all", variant="outline", size="sm", parent=derived,
                on_click=lambda: self.derived.set_collapsed(expand_all()),
            )
        )
        self._sorted = chrome.TextLine("Sorted on code", size=12, parent=derived)
        self._sorted.setObjectName("derived-sort")
        derived_bar.addWidget(self._sorted)

        self.derived = GroupedList(
            source=record_source,
            context=context,
            paging="more",
            group_key=lambda row: cell_value(row, "entity"),
            group_label=lambda value: display_name_of(value if isinstance(value, dict) else {}),
            label_field="code",
            sub_label_field="description",
            max_height="16rem",
            parent=self,
        )
        self.derived.setObjectName("grouped-list-derived")
        self.derived.sort_changed.connect(self._on_sort)
        body.addWidget(
            lay.section("Grouped on a derived key", derived, self.derived, parent=self)
        )

        self.empty = GroupedList(
            source=empty_source,
            context=context,
            paging="pages",
            group_by=_placeholder(GROUP),
            label_field="content",
            max_height="12rem",
            empty_label="No Task in this window",
            parent=self,
        )
        self.empty.setObjectName("grouped-list-empty")
        body.addWidget(lay.section("Empty", self.empty, parent=self))

        self._statuses: dict[str, Any] = {}
        default_pool().submit(_resolve, context, on_result=self._read, on_error=self._failed)

    @property
    def demo_ready(self) -> bool:
        """True once the columns are resolved and the first page has settled."""
        return self._ready and self.listing.control.snapshot().status in ("ready", "error")

    def set_size(self, size: str) -> None:
        for listing in (self.listing, self.derived, self.empty):
            listing.set_size(size if size in ("sm", "md", "lg") else "md")

    def _status_colour(self, row: EntityRow) -> str:
        """The row's leading mark: the status colour the site gave it, as a dot."""
        code = str(cell_value(row, "sg_status_list") or "")
        record = self._statuses.get(code)
        colour = getattr(record, "bg_color", "") or ""
        return _hex(colour)

    def _on_sort(self, keys: object) -> None:
        paths = ", ".join(key.path for key in keys or [])
        self._sorted.set_text(f"Sorted on {paths or 'nothing'}")

    def _read(self, answer: Any) -> None:
        if not lay.alive(self):
            return
        columns, statuses = answer
        self._statuses = statuses
        self.listing.set_statuses(statuses)
        self.listing.set_group_by(columns[0])
        self.listing.set_sub_label_field(columns[1])
        self.listing.set_secondary_field(columns[2])
        self.derived.set_statuses(statuses)
        self.empty.set_statuses(statuses)
        self.empty.set_group_by(columns[0])
        self.listing.control.count()
        self._ready = True

    def _failed(self, error: BaseException) -> None:
        if lay.alive(self):
            self._ready = True
            self.listing.failed.emit(error)


def _placeholder(path: str) -> Any:
    """A column that names nothing but its path, until the schema answers for it."""
    from sg_widgets_core.collection import to_column

    return to_column(path)


def _hex(colour: str) -> str:
    """A site's `r,g,b` colour as the `#rrggbb` a leading mark is drawn in."""
    parts = [part.strip() for part in colour.split(",")]
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return ""
    return "#" + "".join(f"{int(part):02x}" for part in parts)


def _resolve(context: DemoContext) -> tuple[Any, Any]:
    """The three columns and the status table, both read on a worker thread."""
    columns = resolve_columns(context.schema, "Task", [GROUP, SUB, SECONDARY])
    return columns, dict(context.statuses.by_code())


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return GroupedListDemo(context, parent)
