"""The card at its three sizes, reading a picked reference, and its three states.

The port of `apps/site/src/demos/entity-card/Demo.tsx`. The rows come from the demo context on a
worker: one read asking for the type's identity chain, its thumbnail, its status field and the
four paths below at once.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtGui, QtWidgets

from sg_widgets_core.client import EntityRow, SearchOptions
from sg_widgets_core.entity_card import EntityCardOptions, entity_card_fields
from sg_widgets_core.filter import EntityRef

from ...images import image_loader
from ...primitives.base import ThemedWidget, fill_round_rect, painter_for
from ...widgets.entity_card import EntityCard
from ...widgets.entity_picker import EntityPicker
from ...widgets.state_line import StateLine
from ...workers import default_pool
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: Four paths. The first dotted through a link that accepts several types, so its label names the
#: type it travels through, and the last the row's own status, which the header draws and the grid
#: therefore does not.
FIELDS = ("entity.Shot.sg_sequence", "user", "description", "sg_status_list")

SIZES = ("sm", "md", "lg")

#: How many rows the read asks for.
ROWS = 3

#: A reference no site has, so the card shows what the failed read said.
MISSING = EntityRef(type="Version", id=0)

#: The field the thumbnail comes from, which the picture-less example drops.
IMAGE_PATH = "image"

#: The card surface's own padding, rule 2's default.
BOX_PAD = 12


class _NeverPool:
    """A pool that takes a read and never answers, so a card keeps its skeleton on show."""

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        return None


class EntityCardDemo(QtWidgets.QWidget):
    """The card from a row, from a reference, with no picture, loading and failed."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-card-demo")
        self._context = context
        self._cards: list[EntityCard] = []
        #: Every card whose own read has to settle before the page is still.
        self._settling: list[EntityCard] = []
        self._picked: EntityRef | None = None
        self._read_done = False

        self._body = lay.column(self)
        self._state = StateLine(state="empty", label="Loading a version…", pad="none", parent=self)
        self._state.setObjectName("demo-state")
        self._body.addWidget(self._state)
        default_pool().submit(self._read, on_result=self._answered, on_error=self._failed)

    def demo_ready(self) -> bool:
        """True once every read has settled and every picture it named has landed.

        The loading example is left out of the wait: its read is one that never answers.
        """
        return (
            self._read_done
            and all(not card.loading for card in self._settling)
            and image_loader().pending == 0
        )

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds, where the example does not name its own."""
        for card in self._cards:
            card.set_size(size)

    # --- the read ---

    def _read(self) -> list[EntityRow]:
        context = self._context.context
        fields = entity_card_fields(
            context, "Version", EntityCardOptions(fields=list(FIELDS), image_path=IMAGE_PATH)
        )
        filters = None
        if self._context.live:
            filters = {
                "logical_operator": "and",
                "conditions": [
                    ["project", "is", {"type": "Project", "id": self._context.project_id}]
                ],
            }
        found = self._context.client.search(
            "Version", SearchOptions(filters=filters, fields=fields, page={"size": ROWS})
        )
        if not found.data:
            raise ValueError("The site has no Version to show.")
        return found.data

    def _answered(self, rows: Any) -> None:
        if not lay.alive(self):
            return
        self._state.setParent(None)
        self._body.addWidget(self._sections(list(rows)))
        self._read_done = True

    def _failed(self, error: BaseException) -> None:
        if not lay.alive(self):
            return
        self._state.apply_state("error", message=str(error))
        self._read_done = True

    # --- the sections ---

    def _card(self, boxed: bool = True, **kwargs: Any) -> QtWidgets.QWidget:
        card = EntityCard(context=self._context.context, parent=self, **kwargs)
        if "size" not in kwargs:
            self._cards.append(card)
        if "pool" not in kwargs:
            self._settling.append(card)
        return _box(card, self) if boxed else card

    def _sections(self, rows: list[EntityRow]) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)
        row = rows[0]

        sizes = QtWidgets.QWidget(holder)
        stack = QtWidgets.QVBoxLayout(sizes)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(lay.INNER_GAP)
        for step in SIZES:
            stack.addWidget(self._card(row=row, fields=list(FIELDS), size=step))
        section = lay.section("From a row", sizes, parent=self)
        section.setObjectName("case-sizes")
        column.addWidget(section)

        self._picker = EntityPicker(
            context=self._context.context,
            entity_types=["Version"],
            placeholder="Search versions…",
            clearable=True,
            parent=self,
        )
        self._picker.value_changed.connect(self._pick)
        self._read_card = EntityCard(
            context=self._context.context, fields=list(FIELDS), parent=self
        )
        self._settling.append(self._read_card)
        picked = QtWidgets.QWidget(holder)
        stack = QtWidgets.QVBoxLayout(picked)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(lay.INNER_GAP)
        stack.addWidget(self._picker)
        stack.addWidget(_box(self._read_card, self))
        section = lay.section("From a reference", picked, parent=self)
        section.setObjectName("case-reference")
        column.addWidget(section)
        self._pick(EntityRef(type=rows[-1].type, id=rows[-1].id))

        bare = EntityRow(type=row.type, id=row.id, values={**row.values, IMAGE_PATH: None})
        section = lay.section(
            "With no picture", self._card(row=bare, fields=list(FIELDS)), parent=self
        )
        section.setObjectName("case-no-picture")
        column.addWidget(section)

        section = lay.section(
            "Loading",
            self._card(row=row, fields=list(FIELDS), pool=_NeverPool()),
            parent=self,
        )
        section.setObjectName("case-loading")
        column.addWidget(section)

        section = lay.section(
            "A read that failed", self._card(entity=MISSING, fields=list(FIELDS)), parent=self
        )
        section.setObjectName("case-error")
        column.addWidget(section)
        return holder

    def _pick(self, value: Any, row: Any = None) -> None:
        """A pick hands the card a type and an id only, so the card reads the row itself."""
        self._picked = value
        self._read_card.set_entity(
            EntityRef(type=value.type, id=value.id) if value is not None else None
        )


class _Box(ThemedWidget):
    """The bordered surface the demo stands each card on, `rounded-lg p-3` upstream."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("demo-box")

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        theme = self.theme
        fill_round_rect(
            painter, self.rect(), float(theme.radius_px("lg")), theme.color("card"), theme.color("border")
        )
        painter.end()


def _box(widget: QtWidgets.QWidget, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """One card on that surface."""
    holder = _Box(parent)
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(BOX_PAD, BOX_PAD, BOX_PAD, BOX_PAD)
    layout.setSpacing(0)
    widget.setParent(holder)
    layout.addWidget(widget)
    return holder


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityCardDemo(context, parent)
