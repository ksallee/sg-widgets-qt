"""The hello demo: the button in every variant, and one read through the context.

The port of `apps/site/src/demos/hello/Demo.tsx`. It proves the harness end to end: the buttons
are the primitive, the read goes through the demo context on a worker, and the line under them is
what the site answered.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

from ...theme import theme_of, watch_theme
from ...workers import default_pool
from .. import chrome
from ..context import DemoContext

__all__ = ["build"]

VARIANTS = (
    ("secondary", "Secondary"),
    ("outline", "Outline"),
    ("ghost", "Ghost"),
    ("destructive", "Destructive"),
)


class Hello(QtWidgets.QWidget):
    """The demo: the buttons, the read, and the line the answer lands in."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hello")
        self._context = context
        self._busy = False
        #: True once the first read has answered or failed. The stage polls it.
        self.demo_ready = True

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)

        row = QtWidgets.QWidget(self)
        row.setObjectName("hello-buttons")
        buttons = QtWidgets.QHBoxLayout(row)
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.load = chrome.button(
            "Load entity types", variant="default", size="md", parent=row, on_click=self._read
        )
        self.load.setObjectName("load-entity-types")
        buttons.addWidget(self.load)
        for variant, label in VARIANTS:
            made = chrome.button(label, variant=variant, size="md", parent=row)
            made.setObjectName("button-" + variant)
            buttons.addWidget(made)
        buttons.addStretch(1)
        column.addWidget(row)

        self.output = _Output("Nothing loaded yet.", self)
        self.output.setObjectName("demo-output")
        column.addWidget(self.output)

        leaf = _leaf(context, self)
        if leaf is not None:
            column.addWidget(leaf)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for child in self.findChildren(QtWidgets.QWidget):
            setter = getattr(child, "set_size", None)
            if callable(setter) and child is not self:
                setter(size)

    def _read(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.demo_ready = False
        self.load.setEnabled(False)
        self.output.set_text("Loading…")
        default_pool().submit(
            self._context.client.entity_types, on_result=self._answered, on_error=self._failed
        )

    def _answered(self, types: Any) -> None:
        names = [getattr(one, "display_name", str(one)) for one in types or []]
        self.output.set_text(" · ".join(names) if names else "The site answered no types.")
        self._settled()

    def _failed(self, error: BaseException) -> None:
        self.output.set_text(str(error), token="destructive")
        self._settled()

    def _settled(self) -> None:
        self._busy = False
        self.demo_ready = True
        self.load.setEnabled(True)


class _Output(QtWidgets.QWidget):
    """The line under the buttons: 14px, `muted_foreground`, wrapped."""

    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._token = "muted_foreground"
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        watch_theme(self, lambda _theme: self.update())

    def text(self) -> str:
        return self._text

    def set_text(self, text: str, token: str = "muted_foreground") -> None:
        self._text = text
        self._token = token
        self.updateGeometry()
        self.update()

    def _metrics(self) -> QtGui.QFontMetrics:
        return QtGui.QFontMetrics(theme_of(self).font(14))

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        box = self._metrics().boundingRect(
            QtCore.QRect(0, 0, max(120, self.width()), 10000),
            int(QtCore.Qt.TextFlag.TextWordWrap),
            self._text,
        )
        return QtCore.QSize(0, max(20, box.height()))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.updateGeometry()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setFont(theme.font(14))
        painter.setPen(theme.color(self._token))
        painter.drawText(
            self.rect(),
            int(
                QtCore.Qt.AlignmentFlag.AlignTop
                | QtCore.Qt.AlignmentFlag.AlignLeft
                | QtCore.Qt.TextFlag.TextWordWrap
            ),
            self._text,
        )
        painter.end()


def _leaf(context: DemoContext, parent: QtWidgets.QWidget) -> QtWidgets.QWidget | None:
    """Every leaf primitive under the buttons, where `primitives/demo_leaf.py` carries them."""
    try:
        from ...primitives import demo_leaf  # type: ignore[attr-defined]
    except Exception:
        return None
    builder = getattr(demo_leaf, "build", None)
    if builder is None:
        return None
    try:
        return builder(parent)
    except Exception:  # The leaf page is a bonus; a demo never fails over it.
        return None


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return Hello(context, parent)
