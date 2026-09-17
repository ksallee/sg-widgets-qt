"""The same rows walked with a load-more row, with the programmatic path beside each header.

The port of `apps/site/src/demos/entity-table-infinite/Demo.tsx`, the second stage of the entity
table's page: one source in `infinite` mode, four columns, and `more` under the rows.
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
from sg_widgets_core.filter import condition

from ...widgets.entity_table import EntityTable
from ...workers import default_pool
from ..context import DemoContext
from . import _layout as lay
from .entity_table import table_context

__all__ = ["build"]

#: The four columns this stage shows, and the width each opens at.
COLUMNS = (
    ColumnSpec(path="code", width=260),
    ColumnSpec(path="sg_status_list", width=150),
    ColumnSpec(path="user", width=160),
    ColumnSpec(path="created_at", width=170),
)

PAGE_SIZE = 50
MAX_HEIGHT = "22rem"


class EntityTableInfiniteDemo(QtWidgets.QWidget):
    """One table in `more` mode, with the field path beside every header."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-table-infinite-demo")
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
                entity_type="Version",
                fields=[spec.path for spec in COLUMNS],
                filters=scope,
                page_size=PAGE_SIZE,
            )
        )
        self.table = EntityTable(
            source=source,
            context=context,
            show_code=True,
            paging="more",
            max_height=MAX_HEIGHT,
            parent=self,
        )
        body = lay.column(self)
        body.addWidget(self.table)
        default_pool().submit(
            _resolve, context, on_result=self._read, on_error=self._failed
        )

    @property
    def demo_ready(self) -> bool:
        """True once the columns are resolved and the first page has settled."""
        return self._ready and self.table.control.snapshot().status in ("ready", "error")

    def set_size(self, size: str) -> None:
        self.table.set_size(size if size in ("sm", "md", "lg") else "md")

    def _read(self, answer: Any) -> None:
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


def _resolve(context: DemoContext) -> tuple[Any, Any]:
    """The columns and the status table, both read on a worker thread."""
    return resolve_columns(context.schema, "Version", list(COLUMNS)), dict(
        context.statuses.by_code()
    )


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityTableInfiniteDemo(table_context(context), parent)
