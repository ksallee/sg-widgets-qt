"""The entity chip in its three variants, with glyphs, thumbnails, a hover card and a cross.

The port of `apps/site/src/demos/entity-chip/Demo.tsx`. The chips with a thumbnail and the ones
with a hover card are read through the demo context; the rest name fixture rows, so the type
glyphs and the remove control are always on show.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.filter import EntityRef

from ...images import image_loader
from ...widgets.entity_chip import EntityChip
from ...widgets.state_line import StateLine
from ...workers import default_pool
from .. import chrome
from ..context import DemoContext
from . import _layout as lay
from . import _rows

__all__ = ["build"]

#: Three paths for the hover card, one of them dotted through a link with several valid types.
PREVIEW = ("sg_status_list", "user", "entity.Shot.sg_sequence")

#: Types the glyph map covers, plus one it does not.
TYPES = (
    "Shot",
    "Asset",
    "Sequence",
    "Version",
    "Task",
    "HumanUser",
    "Project",
    "Note",
    "PublishedFile",
    "CustomEntity07",
)

#: The rows the cross may take from.
REMOVABLE = tuple(_rows.refs("Asset", 1226, 1227, 1228))

#: The row every plain example points at.
SHOT = _rows.ref("Shot", 862)

#: A task, for the link example.
TASK = _rows.ref("Task", 5700)

#: A site to address rows on, so the link variant has somewhere to go.
DEMO_SITE = "https://demo.example.com"

#: How many rows each read asks for.
ROWS = 3


class EntityChipDemo(QtWidgets.QWidget):
    """The chip across its variants, its sizes, its glyphs and its remove control."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-chip-demo")
        self._context = context
        self._chips: list[EntityChip] = []
        self._removed: list[tuple[str, int]] = []
        self._read_done = False

        self._site = context.site_url or DEMO_SITE
        self._body = lay.column(self)
        self._body.addWidget(self._plain_sections())
        self._state = StateLine(state="empty", label="Loading shots…", pad="none", parent=self)
        self._state.setObjectName("demo-state")
        self._body.addWidget(self._state)

        default_pool().submit(self._read, on_result=self._answered, on_error=self._failed)

    def demo_ready(self) -> bool:
        """True once the rows have answered and every thumbnail they named has landed."""
        return self._read_done and image_loader().pending == 0

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds, where the example does not name its own."""
        for chip in self._chips:
            chip.set_size(size)

    # --- the read ---

    def _read(self) -> tuple[list, list]:
        client = self._context.client
        shots = client.search("Shot", SearchOptions(fields=["code", "image"], page={"size": ROWS}))
        versions = client.search("Version", SearchOptions(fields=["code"], page={"size": ROWS}))
        picked = [
            (EntityRef(type=r.type, id=r.id, name=str(r.values.get("code") or "")), r.values.get("image"))
            for r in shots.data
        ]
        linked = [
            EntityRef(type=r.type, id=r.id, name=str(r.values.get("code") or ""))
            for r in versions.data
        ]
        return picked, linked

    def _answered(self, answer: Any) -> None:
        if not lay.alive(self):
            return
        picked, linked = answer
        self._state.setParent(None)
        self._body.addWidget(self._read_sections(picked, linked))
        self._read_done = True

    def _failed(self, error: BaseException) -> None:
        if not lay.alive(self):
            return
        self._state.apply_state("error", message=str(error))
        self._read_done = True

    # --- the sections ---

    def _chip(self, entity: EntityRef, **kwargs: Any) -> EntityChip:
        chip = EntityChip(entity=entity, parent=self, **kwargs)
        if "size" not in kwargs:
            self._chips.append(chip)
        return chip

    def _plain_sections(self) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)

        column.addWidget(
            lay.section(
                "Sizes",
                lay.row(*(self._chip(SHOT, size=step) for step in ("xs", "sm", "md", "lg"))),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "Variants",
                lay.row(*(self._chip(SHOT, variant=name) for name in ("chip", "link", "text"))),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "Linked to a site",
                lay.row(
                    self._chip(SHOT, site_url=self._site, variant="chip"),
                    self._chip(TASK, site_url=self._site, variant="link"),
                ),
                parent=self,
            )
        )
        glyphs = lay.section(
            "Type glyphs",
            lay.flow(
                *(self._chip(EntityRef(type=name, id=1, name=name), size="sm") for name in TYPES)
            ),
            parent=self,
        )
        glyphs.setObjectName("case-glyphs")
        column.addWidget(glyphs)

        bare = lay.section(
            "No name, link, button",
            lay.row(
                self._chip(EntityRef(type="Version", id=17055)),
                self._chip(TASK, href="#entity-chip"),
                self._chip(
                    EntityRef(type="HumanUser", id=20, name="Ada Lovelace"),
                    on_click=lambda: None,
                ),
            ),
            parent=self,
        )
        bare.setObjectName("case-bare")
        column.addWidget(bare)

        self._removable_holder = lay.flow(parent=self)
        self._fill_removable()
        removable = lay.section("Removable", self._removable_holder, parent=self)
        removable.setObjectName("case-removable")
        column.addWidget(removable)
        return holder

    def _read_sections(self, picked: list, linked: list) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)

        card = lay.section(
            "Hover card",
            lay.flow(
                *(
                    self._chip(
                        entity,
                        preview=list(PREVIEW),
                        context=self._context.context,
                        site_url=self._site,
                    )
                    for entity in linked
                )
            ),
            parent=self,
        )
        card.setObjectName("case-hover-card")
        column.addWidget(card)

        thumbs = lay.section(
            "With a thumbnail",
            lay.flow(*(self._chip(entity, thumbnail=image) for entity, image in picked)),
            parent=self,
        )
        thumbs.setObjectName("case-thumbnail")
        column.addWidget(thumbs)
        return holder

    # --- the cross ---

    def _fill_removable(self) -> None:
        layout = self._removable_holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        shown = [ref for ref in REMOVABLE if (ref.type, ref.id) not in self._removed]
        for ref in shown:
            chip = self._chip(ref, removable=True)
            chip.removed.connect(self._drop)
            layout.addWidget(chip)
        if not shown:
            back = chrome.button(
                "Put them back",
                variant="link",
                size="sm",
                parent=self._removable_holder,
                on_click=self._restore,
            )
            back.setObjectName("put-them-back")
            layout.addWidget(back)
        self._removable_holder.updateGeometry()

    def _drop(self, ref: object) -> None:
        key = (getattr(ref, "type", ""), getattr(ref, "id", 0))
        if key not in self._removed:
            self._removed.append(key)
        self._fill_removable()

    def _restore(self) -> None:
        self._removed.clear()
        self._fill_removable()


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityChipDemo(context, parent)
