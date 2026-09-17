"""The query lifecycle in three shapes: a paged query, a list with no query, and a failed read.

The port of `apps/site/src/demos/search-control/Demo.tsx`. The rows are a static crew list read
behind a 300ms pause, four to a page, so the debounce, the load-more row and the error line are
all on show without a site.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.search import has_more_page, matches_every_word

from ...widgets.picker_row import PickerRowModel
from ...widgets.search_control import SearchAnswer, SearchControl, SearchRequest
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]


@dataclass
class Member:
    """One crew member, which is all a row of this demo holds."""

    id: str
    name: str
    department: str


#: The set every read here answers from. A wrapper's own read is all it adds.
CREW: tuple[Member, ...] = (
    Member("avdm", "Anna van der Meer", "Layout"),
    Member("poos", "Piet Oosterhuis", "Animation"),
    Member("mhal", "Mira Halloran", "Lighting"),
    Member("tber", "Tomas Bergqvist", "Compositing"),
    Member("inak", "Iris Nakamura", "Effects"),
    Member("rcha", "Ravi Chandrasekar", "Matchmove"),
    Member("edua", "Elena Duarte", "Rigging"),
    Member("jkle", "Jonas Klein", "Editorial"),
    Member("nokb", "Nora Okonjo", "Layout"),
    Member("sfer", "Sofia Ferreira", "Animation"),
    Member("lmar", "Luca Marchetti", "Lighting"),
    Member("yhas", "Yuki Hasegawa", "Compositing"),
)

#: The page this demo reads at, small enough that a load-more row is always there.
PAGE = 4

#: What every read here waits before it answers.
PAUSE_S = 0.3


@dataclass
class _Row:
    """The shape `PickerRowModel` reads: a type, an id, a label and the values."""

    type: str
    id: int
    name: str
    values: dict = field(default_factory=dict)


def _rows(members: tuple[Member, ...]) -> list[Any]:
    """A member as the row anatomy reads it: the name, and the department on the right."""
    return [
        _Row(type="Crew", id=i, name=member.name, values={"department": member.department})
        for i, member in enumerate(members)
    ]


def find(request: SearchRequest) -> SearchAnswer:
    """One page of the crew matching every word of the query."""
    time.sleep(PAUSE_S)
    matched = tuple(
        m for m in CREW if matches_every_word(f"{m.name} {m.department}", request.query)
    )
    start = (request.page - 1) * PAGE
    page = matched[start : start + PAGE]
    return SearchAnswer(
        items=_rows(page),
        has_more=has_more_page(len(page), PAGE) and start + PAGE < len(matched),
    )


def everyone(_request: SearchRequest) -> SearchAnswer:
    """The whole crew, in one read, for a list that takes no query."""
    time.sleep(PAUSE_S)
    return SearchAnswer(items=_rows(CREW[:4]), has_more=False)


def fails(_request: SearchRequest) -> SearchAnswer:
    """A read that answers with a failure."""
    time.sleep(PAUSE_S)
    raise RuntimeError("The crew list is not answering.")


def _model(parent: QtWidgets.QWidget) -> PickerRowModel:
    return PickerRowModel(
        [], parent, thumbnail=False, secondary_field="department", size="md"
    )


class SearchControlDemo(QtWidgets.QWidget):
    """The three cases upstream draws, in one column."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("search-control-demo")
        self._context = context
        #: True once the first read has answered or failed. The stage polls it.
        self.demo_ready = False

        body = lay.column(self)

        self.search = SearchControl(
            self,
            load=find,
            model=_model(self),
            paging=True,
            placeholder="Search the crew…",
            empty_label="No one by that name",
        )
        self.search.setObjectName("search-control-query")
        self.search.activated.connect(self._picked)
        self.picked = chrome.TextLine("Nothing yet", size=12, parent=self)
        self.picked.setObjectName("demo-picked")
        body.addWidget(
            lay.section(
                "A query, debounced, paged and picked", self.search, self.picked, parent=self
            )
        )

        self.listed = SearchControl(
            self,
            load=everyone,
            model=_model(self),
            shell="bare",
            reads_empty=True,
            skeleton_lines=2,
        )
        self.listed.setObjectName("search-control-bare")
        self.listed.rows_changed.connect(self._settled)
        body.addWidget(
            lay.section("No query: one read, the same list", self.listed, parent=self)
        )

        self.failing = SearchControl(
            self,
            load=fails,
            model=_model(self),
            shell="bare",
            reads_empty=True,
            skeleton_lines=2,
        )
        self.failing.setObjectName("search-control-error")
        self.failing.error.connect(lambda _message: self._settled())
        body.addWidget(lay.section("A read that failed", self.failing, parent=self))

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for control in (self.search, self.listed, self.failing):
            control.set_size(size)

    def set_density(self, density: str) -> None:
        for control in (self.search, self.listed, self.failing):
            control.set_density(density)

    def _picked(self, row: int) -> None:
        found = self.search.model.row_at(row)
        self.picked.set_text(getattr(found, "name", "Nothing yet"))

    def _settled(self) -> None:
        self.demo_ready = not self.listed.loading and not self.failing.loading


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return SearchControlDemo(context, parent)
