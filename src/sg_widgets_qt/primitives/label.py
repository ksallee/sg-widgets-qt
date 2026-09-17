"""The three quiet leaves: a label, a keyboard key and a rule.

Ported from `packages/react/src/components/ui/label.tsx`, `kbd.tsx` and `separator.tsx`. All three
are painted, so a label carries the theme's family and weight rather than the host's.

    form.addWidget(Label("Status"))
    row.addWidget(Kbd("Ctrl"))
    column.addWidget(Separator())
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from .base import ThemedWidget, fill_round_rect, painter_for, text_width

__all__ = ["KBD_HEIGHT", "Kbd", "Label", "Separator"]

#: `text-sm` of `label.tsx`, in the medium weight rule 6 keeps for emphasis.
LABEL_SIZE = 14

#: `h-5 min-w-5 px-1 text-xs` of `kbd.tsx`.
KBD_HEIGHT = 20
KBD_PAD = 4
KBD_SIZE = 12


class Label(ThemedWidget):
    """A line of text at the body step, elided at the end with the full value as its tooltip."""

    def __init__(
        self,
        text: str = "",
        muted: bool = False,
        weight: QtGui.QFont.Weight = QtGui.QFont.Weight.Medium,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._muted = bool(muted)
        # `label.tsx` is `font-medium`; a line that is a value rather than a name is plain
        # `text-sm`, which is what the caller asks for with the normal weight.
        self._weight = weight
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    @property
    def muted(self) -> bool:
        return self._muted

    def set_muted(self, value: bool) -> None:
        self._muted = bool(value)
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(LABEL_SIZE, self._weight)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(text_width(metrics, self._text), max(metrics.height(), LABEL_SIZE + 4))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, self.sizeHint().height())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        font = self._font()
        painter.setFont(font)
        theme = self.theme
        painter.setPen(theme.color("muted_foreground" if self._muted else "foreground"))
        label = self.elide(QtGui.QFontMetrics(font), self._text, self.width())
        self.set_elide_tooltip(self._text, label == self._text)
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            label,
        )
        painter.end()


class Kbd(ThemedWidget):
    """One keyboard key: the mono step on `muted`, rounded `sm` inside a 1px border."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    def _font(self) -> QtGui.QFont:
        return self.theme.font(KBD_SIZE, QtGui.QFont.Weight.Medium, mono=True)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        width = text_width(metrics, self._text) + KBD_PAD * 2
        return QtCore.QSize(max(KBD_HEIGHT, width), KBD_HEIGHT)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        box = QtCore.QRect(0, 0, self.width(), min(self.height(), KBD_HEIGHT))
        box.moveCenter(self.rect().center())
        fill_round_rect(
            painter, box, float(theme.radius_px("sm")), theme.color("muted"), theme.color("border")
        )
        painter.setFont(self._font())
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(box, QtCore.Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class Separator(ThemedWidget):
    """A 1px rule in `border`, across the row it is in or down the column."""

    def __init__(
        self,
        orientation: str = "horizontal",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._orientation = orientation
        self._apply_policy()

    @property
    def orientation(self) -> str:
        return self._orientation

    def set_orientation(self, value: str) -> None:
        self._orientation = value
        self._apply_policy()
        self.updateGeometry()
        self.update()

    def _apply_policy(self) -> None:
        policy = QtWidgets.QSizePolicy.Policy
        if self._orientation == "vertical":
            self.setSizePolicy(policy.Fixed, policy.Expanding)
            self.setFixedWidth(1)
            self.setMaximumHeight(16777215)
        else:
            self.setSizePolicy(policy.Expanding, policy.Fixed)
            self.setFixedHeight(1)
            self.setMaximumWidth(16777215)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(1, 1)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setOpacity(self.disabled_opacity())
        painter.fillRect(self.rect(), self.theme.color("border"))
        painter.end()
