"""Versions as tiles, at three sizes, selectable, without a picture, and with rows held back.

The port of `apps/site/src/demos/entity-grid/Demo.tsx`. Enter opens a tile, Space takes it, and
every third row is disabled in the last section so a held-back tile is on the page.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import EntitySourceOptions, create_entity_source, resolve_columns
from sg_widgets_core.filter import condition

from ...images import image_loader
from ...widgets.entity_grid import EntityGrid
from ...workers import default_pool
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: The artist column, and what a tile reads.
ARTIST = "user"
FIELDS = ("code", "image", "sg_status_list", ARTIST)
SIZES = ("sm", "md", "lg")

#: The pages the two sources open at.
PAGE_SIZE = 12
SHORT_PAGE_SIZE = 6


def _is_row_disabled(row: EntityRow) -> bool:
    """The demo holds every third tile back, to show what a disabled tile does."""
    return row.id % 3 == 0


class EntityGridDemo(QtWidgets.QWidget):
    """The four grids: the sizes, the selectable one, the one with no picture, the held-back one."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-grid-demo")
        self._context = context
        self._ready = False
        # The mock's rows are one project's already; a real site's are not.
        scope = (
            condition("project", "is", {"type": "Project", "id": context.project_id})
            if context.live
            else None
        )

        def source(page_size: int) -> Any:
            return create_entity_source(
                EntitySourceOptions(
                    client=context.client,
                    entity_type="Version",
                    fields=list(FIELDS),
                    filters=scope,
                    page_size=page_size,
                )
            )

        body = lay.column(self)

        self.grid = EntityGrid(
            source=source(PAGE_SIZE),
            context=context,
            secondary_field=ARTIST,
            size="md",
            max_height="26rem",
            parent=self,
        )
        self.grid.setObjectName("entity-grid")
        self.grid.selected.connect(self._on_open)
        sizes = QtWidgets.QWidget(self)
        picks = lay.FlowLayout(sizes)
        self._sizes: dict[str, Any] = {}
        for step in SIZES:
            made = chrome.toggle(step, size="sm", parent=sizes)
            made.setObjectName(f"grid-size-{step}")
            made.toggled.connect(lambda on, value=step: self._on_size(value, on))
            self._sizes[step] = made
            picks.addWidget(made)
        self._sizes["md"].set_checked(True)
        self._opened = chrome.TextLine("Enter opens a tile", size=12, parent=sizes)
        self._opened.setObjectName("opened")
        picks.addWidget(self._opened)
        body.addWidget(lay.section("Three sizes", sizes, self.grid, parent=self))

        self.selectable = EntityGrid(
            source=source(SHORT_PAGE_SIZE),
            context=context,
            secondary_field=ARTIST,
            size="sm",
            selectable=True,
            max_height="18rem",
            parent=self,
        )
        self.selectable.setObjectName("entity-grid-selectable")
        self._count = chrome.TextLine("0 selected", size=12, parent=self)
        self._count.setObjectName("selection-count")
        self.selectable.selection_changed.connect(
            lambda rows: self._count.set_text(f"{len(rows or [])} selected")
        )
        body.addWidget(lay.section("Selectable", self._count, self.selectable, parent=self))

        self.bare = EntityGrid(
            source=source(SHORT_PAGE_SIZE),
            context=context,
            thumbnail=False,
            secondary_field=ARTIST,
            size="sm",
            max_height="18rem",
            parent=self,
        )
        self.bare.setObjectName("entity-grid-no-image")
        body.addWidget(lay.section("No image", self.bare, parent=self))

        self.held = EntityGrid(
            source=source(SHORT_PAGE_SIZE),
            context=context,
            secondary_field=ARTIST,
            size="sm",
            selectable=True,
            is_row_disabled=_is_row_disabled,
            max_height="18rem",
            parent=self,
        )
        self.held.setObjectName("entity-grid-disabled")
        body.addWidget(lay.section("Every third tile held back", self.held, parent=self))

        default_pool().submit(
            _resolve, context, on_result=self._read, on_error=self._failed
        )

    @property
    def demo_ready(self) -> bool:
        """True once the artist column is resolved and the first page has settled."""
        return (
            self._ready
            and self.grid.control.snapshot().status in ("ready", "error")
            # A cell's picture lands after the rows do, and a screenshot wants both.
            and image_loader().pending == 0
        )

    def set_size(self, size: str) -> None:
        self._set_size(size if size in SIZES else "md")

    def _on_size(self, step: str, on: bool) -> None:
        """One toggle reports going down and coming up; only the first is a pick.

        Setting the other toggles up is reported for each of them, and a report read as a
        pick sets the rest up again, which never returns.
        """
        if not on:
            if not any(made.checked for made in self._sizes.values()):
                made = self._sizes[step]
                made.blockSignals(True)
                made.set_checked(True)
                made.blockSignals(False)
            return
        self._set_size(step)

    def _set_size(self, step: str) -> None:
        self.grid.set_size(step)
        for value, made in self._sizes.items():
            made.blockSignals(True)
            made.set_checked(value == step)
            made.blockSignals(False)

    def _on_open(self, row: object) -> None:
        self._opened.set_text(f"opened {row.type} {row.id}")  # type: ignore[union-attr]

    def _read(self, answer: Any) -> None:
        if not lay.alive(self):
            return
        artist, statuses = answer
        for grid in (self.grid, self.selectable, self.bare, self.held):
            grid.set_statuses(statuses)
            grid.set_secondary_field(artist)
        self.grid.control.count()
        self._ready = True

    def _failed(self, error: BaseException) -> None:
        if lay.alive(self):
            self._ready = True
            self.grid.failed.emit(error)


def _resolve(context: DemoContext) -> tuple[Any, Any]:
    """The artist column and the status table, both read on a worker thread."""
    columns = resolve_columns(context.schema, "Version", [ARTIST])
    return columns[0], dict(context.statuses.by_code())


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityGridDemo(context, parent)
