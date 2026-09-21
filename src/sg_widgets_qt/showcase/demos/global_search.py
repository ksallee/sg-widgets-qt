"""The palette behind a trigger, the inline variant scoped to a project, and the three sizes.

The port of `apps/site/src/demos/global-search/Demo.tsx`. The recents are prefilled, so the
palette has something to show before a word is typed, and the third case turns the row props on:
a description under the label and a status as the right-aligned value.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.global_search import GlobalSearch
from .. import chrome
from ..context import DemoContext
from . import _layout as lay
from . import _rows

__all__ = ["build"]

TYPES = ["Shot", "Asset", "Sequence", "Task", "Version", "HumanUser", "Project"]
SHOTS = ["Shot"]
SIZES = ("sm", "md", "lg")

#: The key the demo opens the palette on, so it does not take Cmd K from the browser it is beside.
HOTKEY = "."

#: Prefilled, so the palette has something to show before a word is typed.
RECENTS = (_rows.ref("Shot", 862), _rows.ref("Asset", 1226), _rows.ref("Project", 70))


class GlobalSearchDemo(QtWidgets.QWidget):
    """The palette, the inline box, the row props and the size ladder."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("global-search-demo")
        self._context = context
        #: Nothing is read until a word is typed, so the page stands ready as it is built.
        self.demo_ready = True
        self._recents = list(RECENTS)
        self._sized: list[GlobalSearch] = []

        body = lay.column(self)
        site = context.context

        self.palette = GlobalSearch(
            self,
            context=site,
            entity_types=TYPES,
            hotkey=HOTKEY,
            recents=self._recents,
            label="Search the site",
        )
        self.palette.setObjectName("global-search-palette")
        self.palette.recents_changed.connect(self._keep_recents)
        self.palette.selected.connect(self._picked)
        body.addWidget(
            lay.section("Palette, opened by the trigger or the hotkey", self.palette, parent=self)
        )

        self.scoped = GlobalSearch(
            self,
            context=site,
            entity_types=TYPES,
            project_id=context.project_for(70),
            inline=True,
            placeholder="Search one project…",
        )
        self.scoped.setObjectName("global-search-inline")
        self.scoped.selected.connect(self._picked)
        self.scoped.search_control().rows_changed.connect(self._settled)
        body.addWidget(lay.section("Inline, scoped to one project", self.scoped, parent=self))

        self.anatomy = GlobalSearch(
            self,
            context=site,
            entity_types=SHOTS,
            inline=True,
            sub_label_field="description",
            secondary_field="sg_status_list",
            placeholder="Search shots…",
        )
        self.anatomy.setObjectName("global-search-anatomy")
        self.anatomy.selected.connect(self._picked)
        body.addWidget(
            lay.section(
                "The row props: a description under the label and a typed secondary",
                self.anatomy,
                parent=self,
            )
        )

        self.picked = chrome.TextLine("Nothing selected yet.", size=13, parent=self)
        self.picked.setObjectName("demo-picked")
        body.addWidget(self.picked)

        sizes = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(sizes)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.INNER_GAP)
        for step in SIZES:
            search = GlobalSearch(
                sizes, context=site, entity_types=TYPES, size=step, label="Search the site"
            )
            search.setObjectName(f"global-search-{step}")
            search.setFixedWidth(256)
            self._sized.append(search)
            column.addWidget(
                lay.row(
                    search,
                    chrome.button("Button", variant="outline", size=step, parent=sizes),
                    parent=sizes,
                )
            )
        body.addWidget(
            lay.section("Sizes, each beside a button of the same step", sizes, parent=self)
        )

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The size row names its own."""
        for search in (self.palette, self.scoped, self.anatomy):
            search.set_size(size)

    def _keep_recents(self, recents: Any) -> None:
        self._recents = list(recents)

    def _picked(self, entity: Any) -> None:
        self.picked.set_text(f"Selected {entity.type} {entity.id} {entity.name or ''}".strip())

    def _settled(self) -> None:
        self.demo_ready = True


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return GlobalSearchDemo(context, parent)
