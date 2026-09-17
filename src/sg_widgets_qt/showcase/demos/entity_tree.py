"""A project seeded open to one shot, with checkboxes, a search, thumbnails and the three sizes.

The port of `apps/site/src/demos/entity-tree/Demo.tsx`. The first tree opens onto a seeded path
and reports what is picked and what is checked; the second is a project whose shots sit under no
sequence; the last row of trees stands each size beside a button of the same step.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets
from qtpy.QtCore import Qt

from ...primitives.button import Button
from ...widgets.entity_tree import EntityTree
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

SIZES = ("sm", "md", "lg")

#: The button step beside a control of each height.
CONTROL_BUTTON: dict[str, str] = {"sm": "sm", "md": "default", "lg": "lg"}

#: The shot the first tree opens onto, in the mock's own hierarchy.
SEED = "/Shot/sg_sequence/Sequence/100/id/862"

#: The mock project whose shots sit under no sequence at all.
LOOSE_PROJECT = 72

#: The width a tree in the size row takes, and the height each body keeps.
SIZE_WIDTH = 288
SIZE_HEIGHT = "8rem"


class EntityTreeDemo(QtWidgets.QWidget):
    """The seeded tree, the loose one, the one with thumbnails, and the three sizes."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-tree-demo")
        self._context = context
        root = f"/Project/{context.project_id}"
        seed = None if context.live else root + SEED
        placeholder = "Search" if context.live else "Search, e.g. sh020_0030"

        body = lay.column(self)

        bar = QtWidgets.QWidget(self)
        controls = lay.FlowLayout(bar)
        open_assets = chrome.button(
            "Open Assets", variant="outline", size="sm", parent=bar,
            on_click=lambda: self._open(root + "/Asset"),
        )
        open_assets.setObjectName("open-assets")
        controls.addWidget(open_assets)
        self._open_count = chrome.TextLine("0 open", size=12, parent=bar)
        self._open_count.setObjectName("expanded-count")
        controls.addWidget(self._open_count)

        self.tree = EntityTree(
            context=context,
            root_path=root,
            seed_path=seed,
            checkable=True,
            searchable=True,
            search_placeholder=placeholder,
            show_code=True,
            parent=self,
        )
        self.tree.expanded_changed.connect(
            lambda paths: self._open_count.set_text(f"{len(paths or [])} open")
        )
        self.tree.selected.connect(self._on_pick)
        self.tree.checked_changed.connect(self._on_checked)
        self._picked = chrome.TextLine("nothing selected", size=12, parent=self)
        self._picked.setObjectName("picked")
        self._checked = chrome.TextLine("0 checked", size=12, parent=self)
        self._checked.setObjectName("checked-count")
        report = QtWidgets.QWidget(self)
        line = lay.FlowLayout(report)
        line.addWidget(self._picked)
        line.addWidget(self._checked)
        body.addWidget(
            lay.section(
                "A project, seeded open, searchable, with checkboxes",
                bar,
                self.tree,
                report,
                parent=self,
            )
        )

        self.loose = EntityTree(
            context=context,
            root_path=f"/Project/{context.project_for(LOOSE_PROJECT)}",
            max_height="12rem",
            parent=self,
        )
        self.loose.setObjectName("entity-tree-loose")
        body.addWidget(
            lay.section("A project whose shots sit under no sequence", self.loose, parent=self)
        )

        self.pictures = EntityTree(
            context=context,
            root_path=root,
            thumbnail="image",
            sub_label_field="description",
            max_height="16rem",
            parent=self,
        )
        self.pictures.setObjectName("entity-tree-thumbnails")
        body.addWidget(lay.section("The same tree with thumbnails", self.pictures, parent=self))

        self._steps: list[EntityTree] = []
        rows: list[QtWidgets.QWidget] = []
        for step in SIZES:
            row = QtWidgets.QWidget(self)
            row.setObjectName(f"entity-tree-size-{step}")
            line = QtWidgets.QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(12)
            made = EntityTree(
                context=context,
                root_path=root,
                searchable=True,
                size=step,
                max_height=SIZE_HEIGHT,
                parent=row,
            )
            made.setFixedWidth(SIZE_WIDTH)
            self._steps.append(made)
            line.addWidget(made)
            beside = Button("Button", variant="outline", size=CONTROL_BUTTON[step], parent=row)
            line.addWidget(beside, 0, Qt.AlignmentFlag.AlignTop)
            line.addStretch(1)
            rows.append(row)
        body.addWidget(
            lay.section("Sizes, each beside a button of the same step", *rows, parent=self)
        )

    @property
    def demo_ready(self) -> bool:
        """True once every tree's root read has settled."""
        trees = [self.tree, self.loose, self.pictures, *self._steps]
        return all(tree.snapshot().status in ("ready", "error") for tree in trees)

    def set_size(self, size: str) -> None:
        step = size if size in SIZES else "md"
        for tree in (self.tree, self.loose, self.pictures):
            tree.set_size(step)

    def _open(self, path: str) -> None:
        held = self.tree.expanded
        if path not in held:
            self.tree.set_expanded([*held, path])

    def _on_pick(self, node: Any) -> None:
        self._picked.set_text(node.label if node is not None else "nothing selected")

    def _on_checked(self, rows: object) -> None:
        self._checked.set_text(f"{len(rows or [])} checked")


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityTreeDemo(context, parent)
