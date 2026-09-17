"""Browse one project's tree, or search it and read the path a result carries.

The port of `apps/site/src/demos/hierarchical-search/Demo.tsx`. The line under the list is the
path the pick ran through, chip by chip, with the row it ended on.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.entity_chip import EntityChip
from ...widgets.hierarchical_search import HierarchicalSearch
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

TYPES = ["Shot", "Asset", "Sequence", "Task"]

#: The project the mock fixtures are built around.
MOCK_PROJECT = 70


class HierarchicalSearchDemo(QtWidgets.QWidget):
    """The tree scoped to one project, and the path a pick answers."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hierarchical-search-demo")
        self._context = context
        #: True once the first read has answered or failed. The stage polls it.
        self.demo_ready = False

        body = lay.column(self)
        self.tree = HierarchicalSearch(
            self,
            context=context.context,
            root_path=f"/Project/{context.project_for(MOCK_PROJECT)}",
            entity_types=TYPES,
            secondary_field="sg_status_list",
        )
        self.tree.setObjectName("hierarchical-search")
        self.tree.selected.connect(self._picked)
        self.tree.search_control().rows_changed.connect(self._settled)
        self.tree.search_control().error.connect(lambda _message: self._settled())
        body.addWidget(lay.section("Scoped to one project", self.tree, parent=self))

        self._path = QtWidgets.QWidget(self)
        self._path.setObjectName("demo-picked")
        self._path_row = QtWidgets.QHBoxLayout(self._path)
        self._path_row.setContentsMargins(0, 0, 0, 0)
        self._path_row.setSpacing(lay.ROW_GAP)
        self._empty = chrome.TextLine("Nothing selected yet.", size=13, parent=self._path)
        self._path_row.addWidget(self._empty)
        self._path_row.addStretch(1)
        body.addWidget(self._path)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        self.tree.set_size(size)

    def _picked(self, leaf: Any, path: Any) -> None:
        while self._path_row.count():
            item = self._path_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for step in path:
            self._path_row.addWidget(
                EntityChip(entity=step, size="sm", context=self._context.context, parent=self._path)
            )
        self._path_row.addWidget(
            chrome.TextLine(f"leaf {leaf.type} {leaf.id}", size=13, parent=self._path)
        )
        self._path_row.addStretch(1)

    def _settled(self) -> None:
        self.demo_ready = True


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return HierarchicalSearchDemo(context, parent)
