"""One live demo, on the stage it stands on.

The port of `Demo.astro`: a caption carrying the example's title and the controls that shape it,
and under them the stage itself, a surface of its own holding the widget the demo built.

A demo is `src/sg_widgets_qt/showcase/demos/<name>.py`, found by name, defining

    def build(context: DemoContext, parent: QWidget) -> QWidget

A name with no module draws a muted line; a `build` that raises draws the error in `destructive`
and logs it, so one broken demo never takes the page with it.
"""
from __future__ import annotations

import importlib
import logging
import time

from qtpy import QtCore, QtGui, QtWidgets

from ..theme import Theme, theme_of, watch_theme
from .context import DemoContext
from .prefs import Prefs
from .toolbar import STAGE_KEYS, PrefsToolbar

__all__ = ["DemoStage", "Surface", "demo_module_name"]

log = logging.getLogger(__name__)

#: What the stage leaves for a read to settle before it calls itself ready.
SETTLE_MS = 220

#: The keys whose change rebuilds the demo rather than repainting it.
REBUILD_KEYS = ("source", "size", "density")


def demo_module_name(name: str) -> str:
    """The module a demo of that item name lives in."""
    return "sg_widgets_qt.showcase.demos." + name.replace("-", "_")


class Surface(QtWidgets.QWidget):
    """A `background` surface with a 1px `border`, rounded at the theme's radius."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        token: str = "background",
        border: bool = True,
        radius: str = "lg",
    ) -> None:
        super().__init__(parent)
        self._token = token
        self._border = border
        self._radius = radius
        watch_theme(self, lambda _theme: self.update())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = float(theme.radius_px(self._radius))
        painter.setPen(
            QtGui.QPen(theme.color("border"), 1.0) if self._border else QtCore.Qt.PenStyle.NoPen
        )
        painter.setBrush(theme.color(self._token))
        painter.drawRoundedRect(box, radius, radius)
        painter.end()


class DemoStage(QtWidgets.QWidget):
    """The figure one example is drawn in: its caption, its toolbar and the demo under them."""

    #: The demo was built, or rebuilt.
    built = QtCore.Signal()

    def __init__(
        self,
        name: str,
        title: str = "",
        context: DemoContext | None = None,
        prefs: Prefs | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("demo")
        #: The item name, the `data-demo-name` the driver finds a stage by.
        self.data_name = name
        self.setProperty("data_name", name)
        self.data_title = title
        self._context = context
        self._prefs = prefs if prefs is not None else Prefs(self, persist=False)
        self._widget: QtWidgets.QWidget | None = None
        self._built_at = 0.0
        self._error: str = ""

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._frame = Surface(self)
        self._frame.setObjectName("demo-frame")
        frame_layout = QtWidgets.QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self._caption = _Caption(self._frame)
        self._caption.setObjectName("demo-caption")
        caption_layout = QtWidgets.QHBoxLayout(self._caption)
        caption_layout.setContentsMargins(12, 8, 12, 8)
        caption_layout.setSpacing(12)
        self._title = _Elided(title, self._caption)
        self._title.setObjectName("demo-title")
        caption_layout.addWidget(self._title, 1)
        self.toolbar = PrefsToolbar(self._prefs, STAGE_KEYS, size="sm", parent=self._caption)
        self.toolbar.setObjectName("demo-toolbar")
        caption_layout.addWidget(self.toolbar, 0)
        frame_layout.addWidget(self._caption)

        self._stage = QtWidgets.QWidget(self._frame)
        self._stage.setObjectName("demo-body")
        self._body = QtWidgets.QVBoxLayout(self._stage)
        self._body.setContentsMargins(16, 16, 16, 16)
        self._body.setSpacing(12)
        frame_layout.addWidget(self._stage)

        outer.addWidget(self._frame)
        self._prefs.changed.connect(self._on_prefs)
        self._view = self._prefs.values()
        self.build()

    # --- the demo ----------------------------------------------------------------------------

    @property
    def widget(self) -> QtWidgets.QWidget | None:
        """The widget the demo built, while it stands."""
        return self._widget

    @property
    def error(self) -> str:
        """What the demo's `build` raised, or an empty string."""
        return self._error

    @property
    def ready(self) -> bool:
        """True once the demo is built and its first read has had time to settle."""
        if self._widget is None and not self._error:
            return False
        if self._built_at and (time.monotonic() - self._built_at) * 1000.0 < SETTLE_MS:
            return False
        flag = getattr(self._widget, "demo_ready", None)
        if callable(flag):
            return bool(flag())
        if isinstance(flag, bool):
            return flag
        return True

    def build(self) -> None:
        """Build the demo, replacing whatever stood here."""
        self._clear()
        self._error = ""
        context = self._context if self._context is not None else _lazy_context(self._prefs)
        try:
            module = importlib.import_module(demo_module_name(self.data_name))
        except ImportError:
            self._body.addWidget(_Line(f"No demo for {self.data_name} yet", "muted", self._stage))
            self._built_at = time.monotonic()
            self.built.emit()
            return
        try:
            widget = module.build(context, self._stage)
        except Exception as error:  # A broken demo never takes the page with it.
            log.exception("demo %s failed to build", self.data_name)
            self._error = f"{type(error).__name__}: {error}"
            self._body.addWidget(_Line(self._error, "destructive", self._stage))
            self._built_at = time.monotonic()
            self.built.emit()
            return
        self._apply_view(widget)
        self._widget = widget
        self._body.addWidget(widget)
        self._built_at = time.monotonic()
        self.built.emit()

    def _apply_view(self, widget: QtWidgets.QWidget) -> None:
        """Hand the widget the size and the density the toolbar holds, where it takes them."""
        for name, value in (("set_size", self._prefs.size), ("set_density", self._prefs.density)):
            setter = getattr(widget, name, None)
            if callable(setter):
                try:
                    setter(value)
                except Exception:  # A demo that takes no size step keeps the one it was built at.
                    log.debug("demo %s refused %s", self.data_name, name)

    def _clear(self) -> None:
        self._widget = None
        while self._body.count():
            item = self._body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _on_prefs(self) -> None:
        was, self._view = self._view, self._prefs.values()
        if any(was.get(key) != self._view.get(key) for key in REBUILD_KEYS):
            self._context = None if was.get("source") != self._view.get("source") else self._context
            self.build()
        self._prefs.apply(self)
        self.update()

    def set_context(self, context: DemoContext) -> None:
        """Read from another context from here on, and rebuild."""
        self._context = context
        self.build()


def _lazy_context(prefs: Prefs) -> DemoContext:
    from .context import demo_context

    return demo_context(live=prefs.live)


class _Caption(QtWidgets.QWidget):
    """The caption row: a `muted` band with the border under it."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        watch_theme(self, lambda _theme: self.update())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        radius = float(theme.radius_px("lg"))
        path = QtGui.QPainterPath()
        box = QtCore.QRectF(self.rect())
        path.addRoundedRect(box.adjusted(0.5, 0.5, -0.5, 0.0), radius, radius)
        path.addRect(QtCore.QRectF(box.left() + 0.5, box.bottom() - radius, box.width() - 1.0, radius))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("muted"))
        painter.drawPath(path.simplified())
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.drawLine(
            QtCore.QPointF(box.left(), box.bottom() - 0.5),
            QtCore.QPointF(box.right(), box.bottom() - 0.5),
        )
        painter.end()


class _Elided(QtWidgets.QWidget):
    """One line of 12px `muted_foreground`, elided at the end with the whole value as its tooltip."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setToolTip(text)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)
        self.setFixedHeight(16)
        watch_theme(self, lambda _theme: self.update())

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self.setToolTip(text)
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setFont(theme.font(12))
        painter.setPen(theme.color("muted_foreground"))
        metrics = QtGui.QFontMetrics(painter.font())
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(self._text, QtCore.Qt.TextElideMode.ElideRight, self.width()),
        )
        painter.end()


class _Line(QtWidgets.QWidget):
    """One 14px line in a token colour: what a missing or broken demo draws."""

    def __init__(
        self, text: str, token: str = "muted", parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("state-line")
        self._text = text
        self._token = "muted_foreground" if token == "muted" else token
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        watch_theme(self, lambda _theme: self.update())

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        theme: Theme = theme_of(self)
        metrics = QtGui.QFontMetrics(theme.font(14))
        return QtCore.QSize(metrics.horizontalAdvance(self._text), max(20, metrics.height()))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setFont(theme.font(14))
        painter.setPen(theme.color(self._token))
        painter.drawText(
            self.rect(),
            int(
                QtCore.Qt.AlignmentFlag.AlignVCenter
                | QtCore.Qt.AlignmentFlag.AlignLeft
                | QtCore.Qt.TextFlag.TextWordWrap
            ),
            self._text,
        )
        painter.end()

