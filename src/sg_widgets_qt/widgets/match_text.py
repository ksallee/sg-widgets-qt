"""A label with the words of a search query at the weight a match takes.

Ported from `packages/react/src/registry/sg/components/match-text.tsx` over core's `match_runs`.

`POST /entity/_text_search` matches a row when every word of the query appears in it, so every word
is marked wherever it occurs and overlapping words merge into one run
(053_text_search_matching). Emphasis is weight and never colour (`docs/design-rules.md` rule 6), so
a row already carrying a colour of its own still reads. The runs are text: nothing here draws
markup from a row, and they rebuild the label exactly, so a label the query does not touch draws
as itself.

    MatchText(text="sh010_0030_characterfx_v006", query="sh 30")
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.search import MatchRun, match_runs

from ..primitives.base import ThemedWidget, painter_for
from ..primitives.type_scale import line_box

__all__ = ["MATCH_TEXT_SIZE", "MatchText"]

#: The label's type step, on the leaf ladder. Body is the default (rule 6).
MATCH_TEXT_SIZE: dict[str, int] = {"sm": 12, "md": 14, "lg": 16}


class MatchText(ThemedWidget):
    """One label, the query's matched runs in DemiBold and the rest at the body weight."""

    def __init__(
        self,
        text: str = "",
        query: str = "",
        size: str = "md",
        muted: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("match-text")
        self._text = text
        self._query = query
        self._muted = bool(muted)
        self.set_size_step(size if size in MATCH_TEXT_SIZE else "md")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    # --- props ---

    @property
    def text(self) -> str:
        """The label to draw."""
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    @property
    def query(self) -> str:
        """What was searched for. Its whitespace-separated words are the ones marked."""
        return self._query

    def set_query(self, value: str) -> None:
        self._query = value
        self.updateGeometry()
        self.update()

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in MATCH_TEXT_SIZE else "md")
        self.updateGeometry()
        self.update()

    @property
    def muted(self) -> bool:
        """Draw the line in `muted_foreground`, where weight is the only mark."""
        return self._muted

    def set_muted(self, value: bool) -> None:
        self._muted = bool(value)
        self.update()

    # --- the runs ---

    @property
    def runs(self) -> list[MatchRun]:
        """The label as alternating plain and matched stretches, from core."""
        return match_runs(self._text, self._query)

    def run_font(self, matched: bool) -> QtGui.QFont:
        """The face a run is drawn in: DemiBold where the query matched, the body weight elsewhere.

        The mark is the weight the painter is given. A family with no DemiBold face of its own
        lands both runs on the same pixels, and the label asks for the heavier one either way.
        """
        weight = QtGui.QFont.Weight.DemiBold if matched else QtGui.QFont.Weight.Normal
        return self.theme.font(MATCH_TEXT_SIZE[self.size_step], weight)

    def _fonts(self) -> tuple[QtGui.QFont, QtGui.QFont]:
        return self.run_font(False), self.run_font(True)

    def _natural_width(self) -> int:
        base, bold = self._fonts()
        plain, heavy = QtGui.QFontMetrics(base), QtGui.QFontMetrics(bold)
        width = 0
        for run in self.runs:
            width += (heavy if run.match else plain).horizontalAdvance(run.text)
        return width + 1 if width else 0

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        # The line box of the step, not the font's own height: a list of labels keeps the pitch
        # its upstream twin has, whatever the platform's metrics say.
        return QtCore.QSize(self._natural_width(), line_box(MATCH_TEXT_SIZE[self.size_step]))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        painter.setPen(theme.color("muted_foreground" if self._muted else "foreground"))
        base, bold = self._fonts()

        x = 0
        right = self.width()
        cut = False
        for run in self.runs:
            if not run.text:
                continue
            if x >= right:
                cut = True
                break
            painter.setFont(bold if run.match else base)
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(run.text)
            shown = run.text
            room = right - x
            if width > room:
                shown = metrics.elidedText(run.text, QtCore.Qt.TextElideMode.ElideRight, room)
                cut = True
            painter.drawText(
                QtCore.QRect(x, 0, min(width, room), self.height()),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                shown,
            )
            x += width
        self.set_elide_tooltip(self._text, not cut)
        painter.end()
