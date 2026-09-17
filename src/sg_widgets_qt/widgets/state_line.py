"""The empty and error line every data widget draws in place of its rows.

Ported from `packages/react/src/registry/sg/components/state-line.tsx`. One centred line, a glyph
in front of it, in the room the surface it sits on asks for: `docs/design-rules.md` rule 5 gives a
popup list 24px of vertical padding and a table body 40, and a line under rows already drawn takes
none, because the block around it owns the inset.

Loading is not one of the two: it is skeletons shaped like the rows they stand in for, so it stays
with the widget that knows that shape.

    line = StateLine(state="empty", label="No department matches", icon="search-x")
    line.apply_state("error", labels, message=str(error))
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.state import StateLabels, state_line

from ..icons import paint_icon
from ..primitives.base import ThemedWidget, painter_for, text_width

__all__ = ["STATE_LINE_GLYPH", "STATE_LINE_PAD", "STATE_LINE_TEXT", "StateLine"]

#: The room around the line, per surface. `docs/design-rules.md` rule 5.
STATE_LINE_PAD: dict[str, int] = {"popover": 24, "table": 40, "none": 0}

#: The line's own type step, on the leaf ladder.
STATE_LINE_TEXT: dict[str, int] = {"sm": 12, "md": 14, "lg": 16}

#: The glyph in front of it, `size-4` at the default step.
STATE_LINE_GLYPH: dict[str, int] = {"sm": 14, "md": 16, "lg": 20}

#: Between an inline glyph and its text, rule 2.
GLYPH_GAP = 6

#: The two states this line covers. Loading is skeletons, not a line.
STATE_VALUES: tuple[str, ...] = ("empty", "error")

#: The token each state is drawn in.
STATE_TOKEN: dict[str, str] = {"empty": "muted_foreground", "error": "destructive"}


class StateLine(ThemedWidget):
    """One centred line saying a read returned nothing, or that it failed."""

    def __init__(
        self,
        state: str = "empty",
        label: str = "",
        icon: str | None = None,
        pad: str = "popover",
        slot_name: str = "state-line",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state if state in STATE_VALUES else "empty"
        self._label = label
        self._icon = icon
        self._pad = pad if pad in STATE_LINE_PAD else "popover"
        self._slot_name = slot_name or "state-line"
        self.set_size_step(size if size in STATE_LINE_TEXT else "md")
        self.setObjectName(self._slot_name)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    # --- props ---

    @property
    def state(self) -> str:
        """`empty` or `error`."""
        return self._state

    def set_state(self, value: str) -> None:
        self._state = value if value in STATE_VALUES else "empty"
        self.update()

    @property
    def label(self) -> str:
        return self._label

    def set_label(self, value: str) -> None:
        self._label = value
        self.updateGeometry()
        self.update()

    @property
    def icon(self) -> str | None:
        """The lucide glyph name in front of the line, or None for a bare line."""
        return self._icon

    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self.updateGeometry()
        self.update()

    @property
    def pad(self) -> str:
        """`popover`, `table` or `none`: the room the line takes."""
        return self._pad

    def set_pad(self, value: str) -> None:
        self._pad = value if value in STATE_LINE_PAD else "popover"
        self.updateGeometry()
        self.update()

    @property
    def slot_name(self) -> str:
        """The object name this block carries, which is how a driver finds it."""
        return self._slot_name

    def set_slot_name(self, value: str) -> None:
        self._slot_name = value or "state-line"
        self.setObjectName(self._slot_name)

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in STATE_LINE_TEXT else "md")
        self.updateGeometry()
        self.update()

    # --- core's labels ---

    def apply_state(
        self, state: str, labels: StateLabels | None = None, message: str | None = None
    ) -> None:
        """Show a state with the line core settles for it.

        An error falls back to what the read said and then to a fixed line, so a failure is never
        a blank block.
        """
        self.set_state(state)
        self.set_label(state_line(state, labels if labels is not None else StateLabels(), message))

    # --- geometry ---

    def _font(self) -> QtGui.QFont:
        return self.theme.font(STATE_LINE_TEXT[self.size_step])

    def _glyph(self) -> int:
        return STATE_LINE_GLYPH[self.size_step]

    def _pad_y(self) -> int:
        return STATE_LINE_PAD[self._pad]

    def _content_width(self) -> int:
        width = text_width(QtGui.QFontMetrics(self._font()), self._label)
        if self._icon:
            width += self._glyph() + GLYPH_GAP
        return width

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        line = max(QtGui.QFontMetrics(self._font()).height(), self._glyph())
        return QtCore.QSize(self._content_width(), line + 2 * self._pad_y())

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        font = self._font()
        painter.setFont(font)
        ink = self.theme.color(STATE_TOKEN[self._state])

        glyph = self._glyph() if self._icon else 0
        gap = GLYPH_GAP if self._icon else 0
        room = max(0, self.width() - glyph - gap)
        metrics = QtGui.QFontMetrics(font)
        shown = self.elide(metrics, self._label, room)
        self.set_elide_tooltip(self._label, shown == self._label)

        width = min(self._content_width(), self.width())
        left = (self.width() - width) // 2
        centre = self.height() // 2
        if self._icon:
            box = QtCore.QRect(left, centre - glyph // 2, glyph, glyph)
            paint_icon(painter, box, self._icon, ink)
            left += glyph + gap

        painter.setPen(ink)
        painter.drawText(
            QtCore.QRect(left, 0, max(0, self.width() - left), self.height()),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            shown,
        )
        painter.end()
