"""A query marked across names, paths and an address.

The port of `apps/site/src/demos/match-text/Demo.tsx`. Typing in the query box re-marks every
label under it; nothing is read from a site.
"""
from __future__ import annotations

from qtpy import QtWidgets

from ...widgets.match_text import MatchText
from .. import chrome
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: Labels of the shape a text search answers: a name, a path, a person, an address.
LABELS = (
    "sh010_0030_characterfx_v006",
    "Ada Lovelace",
    "Blue Moon Rising / Sequence sq020 / sh020_0050",
    "propCrate_model_v002",
    "anna.van.der.meer@example.com",
)

#: The line the muted section marks.
MUTED_LINE = "Review submission for sh010_0030, waiting on Ada"

#: What the box starts on.
QUERY = "ad mo"

#: `w-64` of the upstream query box.
QUERY_WIDTH = 256

#: Between the lines of a list, which is a zero gap plus the line's own leading.
LINE_GAP = 6


class MatchTextDemo(QtWidgets.QWidget):
    """The query box, the labels it marks, and the same marking in a muted line."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("match-text-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True
        self._labels: list[MatchText] = []

        body = lay.column(self)
        self.query = chrome.SearchField(placeholder="Query", size="sm", parent=self)
        self.query.setObjectName("match-query")
        self.query.setFixedWidth(QUERY_WIDTH)
        self.query.set_text(QUERY)
        self.query.text_changed.connect(self._on_query)
        body.addWidget(lay.section("Query", lay.row(self.query, parent=self), parent=self))

        lines = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(lines)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(LINE_GAP)
        for text in LABELS:
            column.addWidget(self._label(text, lines))
        listed = lay.section("Every word, wherever it occurs", lines, parent=self)
        listed.setObjectName("case-labels")
        body.addWidget(listed)

        muted = lay.section(
            "In a muted line, where weight is the only mark",
            lay.row(self._label(MUTED_LINE, self, muted=True), parent=self),
            parent=self,
        )
        muted.setObjectName("case-muted")
        body.addWidget(muted)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for label in self._labels:
            label.set_size(size)

    def _label(self, text: str, parent: QtWidgets.QWidget, muted: bool = False) -> MatchText:
        label = MatchText(text=text, query=QUERY, muted=muted, parent=parent)
        self._labels.append(label)
        return label

    def _on_query(self, text: str) -> None:
        for label in self._labels:
            label.set_query(text)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return MatchTextDemo(context, parent)
