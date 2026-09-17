"""A modal panel over a dimmed window, painted like the popover surface.

The dialog is a frameless translucent `QDialog` drawn by this package: the `popover` fill, the
hairline ring, the `xl` radius and a painted shadow. A separate overlay widget dims the parent
window behind it, and both fade in over 100ms. Escape closes it, and the modality traps the
keyboard inside it.

    dialog = Dialog(window, title="Delete the shot", description="This cannot be undone.")
    dialog.footer.add_button(Button("Cancel", variant="outline"))
    dialog.open()
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, QRect, QSize, Qt, Signal

from ..theme import theme_of, with_alpha
from .base import DURATION, EASE_IN, EASE_OUT, ThemedWidget
from .button import Button
from .popover import SHADOW_MARGIN, paint_surface

__all__ = [
    "DIALOG_MAX_WIDTH",
    "DIALOG_PADDING",
    "SCRIM_OPACITY",
    "Dialog",
    "DialogFooter",
    "DialogScrim",
]

#: `max-w-lg` of the panel and `p-6` inside it.
DIALOG_MAX_WIDTH = 512
DIALOG_PADDING = 24

#: Between the title, the description and the content.
DIALOG_GAP = 12

#: The scrim over the parent window.
SCRIM_OPACITY = 0.5

#: The room the panel leaves at the edge of the window it covers.
DIALOG_INSET = 16

_SCALE_FROM = 0.95


class DialogScrim(ThemedWidget):
    """The dimmed sheet over the window a dialog covers, which fades with it."""

    def __init__(self, host: QtWidgets.QWidget) -> None:
        super().__init__(host)
        self._host = host
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._fade = self.animated(DURATION["popover"], EASE_OUT)
        self.setGeometry(host.rect())
        host.installEventFilter(self)
        self.hide()

    def reveal(self) -> None:
        """Cover the window and fade in."""
        self.setGeometry(self._host.rect())
        self.show()
        self.raise_()
        self._fade.set(1.0, easing=EASE_OUT)

    def dismiss(self) -> None:
        """Fade out and leave."""
        self._fade.set(0.0, easing=EASE_IN)
        QtCore.QTimer.singleShot(DURATION["popover"], self._hide_if_clear)

    def _hide_if_clear(self) -> None:
        if self._fade.value <= 0.0:
            self.hide()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self._host and event.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(self._host.rect())
        return False

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        color = QtGui.QColor(0, 0, 0)
        color.setAlphaF(SCRIM_OPACITY * self._fade.value)
        painter.fillRect(self.rect(), color)
        painter.end()


class DialogFooter(ThemedWidget):
    """The row of buttons at the foot of a dialog, on a muted band with a rule above it."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(
            DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING
        )
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

    def add_button(self, button: QtWidgets.QWidget) -> QtWidgets.QWidget:
        """Put a button at the trailing edge, after the ones already there."""
        self._layout.addWidget(button)
        return button

    @property
    def is_empty(self) -> bool:
        """True while no button has been added."""
        return self._layout.count() <= 1

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        radius = float(theme.radius_px("xl"))
        path = QtGui.QPainterPath()
        box = QtCore.QRectF(self.rect())
        path.addRoundedRect(box.adjusted(0, -radius, 0, 0), radius, radius)
        painter.setClipRect(box)
        painter.fillPath(path, with_alpha(theme.color("muted"), 0.5))
        painter.fillRect(QRect(0, 0, self.width(), 1), theme.color("border"))
        painter.end()


class Dialog(QtWidgets.QDialog):
    """A modal panel painted like a popover, over a dimmed parent window.

    `title` and `description` are the header, `content` the body under it, and `show_close`
    draws the `x` at the top right. `footer` is the button row, empty until a button lands.
    """

    dismissed = Signal()

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        title: str = "",
        description: str = "",
        content: QtWidgets.QWidget | None = None,
        show_close: bool = True,
    ) -> None:
        super().__init__(parent)
        self._host = parent.window() if parent is not None else None
        self._progress = 0.0
        self._animating = False
        self._closing = False
        self._result_code = int(QtWidgets.QDialog.DialogCode.Rejected)
        self._frame = QtGui.QPixmap()

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN)
        outer.setSpacing(0)
        self._frame_widget = QtWidgets.QWidget(self)
        self._frame_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        outer.addWidget(self._frame_widget)

        stack = QtWidgets.QVBoxLayout(self._frame_widget)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(0)

        self._body = QtWidgets.QWidget(self._frame_widget)
        self._body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        body = QtWidgets.QVBoxLayout(self._body)
        body.setContentsMargins(
            DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING
        )
        body.setSpacing(DIALOG_GAP)
        self._body_layout = body
        stack.addWidget(self._body)

        self._title = _DialogTitle(title, self._body)
        self._description = _DialogDescription(description, self._body)
        body.addWidget(self._title)
        body.addWidget(self._description)
        self._title.setVisible(bool(title))
        self._description.setVisible(bool(description))

        self._content: QtWidgets.QWidget | None = None
        if content is not None:
            self.set_content(content)

        self._footer = DialogFooter(self._frame_widget)
        stack.addWidget(self._footer)
        self._footer.setVisible(False)

        self._close_button: Button | None = None
        if show_close:
            self._close_button = Button("", icon="x", variant="ghost", size="icon-sm", parent=self)
            self._close_button.clicked.connect(self.close)

        self._scrim = DialogScrim(self._host) if self._host is not None else None

        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(DURATION["popover"])
        self._animation.valueChanged.connect(self._on_progress)
        self._animation.finished.connect(self._on_animation_done)

    # --- contents -----------------------------------------------------------------------

    @property
    def footer(self) -> DialogFooter:
        """The button row. It appears once a button is added to it."""
        self._footer.setVisible(True)
        return self._footer

    def set_content(self, widget: QtWidgets.QWidget | None) -> None:
        """Put a widget under the header."""
        if self._content is not None:
            self._body_layout.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        if widget is not None:
            self._body_layout.addWidget(widget)

    def set_title(self, text: str) -> None:
        """Replace the heading."""
        self._title.set_text(text)
        self._title.setVisible(bool(text))

    def set_description(self, text: str) -> None:
        """Replace the muted line under the heading."""
        self._description.set_text(text)
        self._description.setVisible(bool(text))

    @property
    def scrim(self) -> DialogScrim | None:
        """The sheet dimming the parent window, or `None` when the dialog has no parent."""
        return self._scrim

    # --- opening and closing ------------------------------------------------------------

    def open(self) -> None:
        """Show the scrim and the panel, without blocking the caller."""
        if self.isVisible():
            return
        self._closing = False
        if self._scrim is not None:
            self._scrim.reveal()
        self._place()
        self.show()
        self._start(1.0)

    def close(self) -> bool:
        """Fade the panel out and take the scrim with it."""
        self.done(int(QtWidgets.QDialog.DialogCode.Rejected))
        return True

    def reject(self) -> None:
        """Escape and the close control land here, so the dialog reports it was dismissed."""
        self.dismissed.emit()
        self.done(int(QtWidgets.QDialog.DialogCode.Rejected))

    def done(self, result: int) -> None:
        """Leave through the fade, so the scrim and the panel go together."""
        self._result_code = int(result)
        if not self.isVisible():
            super().done(self._result_code)
            return
        if self._closing:
            return
        self._closing = True
        if self._scrim is not None:
            self._scrim.dismiss()
        self._start(0.0)

    def _place(self) -> None:
        hint = self._frame_widget.sizeHint()
        width = min(DIALOG_MAX_WIDTH, max(hint.width(), 320))
        host = self._host
        if host is not None:
            width = min(width, max(240, host.width() - 2 * DIALOG_INSET))
        height = self._frame_widget.heightForWidth(width)
        if height <= 0:
            height = hint.height()
        height = max(height, self._frame_widget.minimumSizeHint().height())
        self.resize(width + 2 * SHADOW_MARGIN, height + 2 * SHADOW_MARGIN)
        centre = (
            host.mapToGlobal(host.rect().center())
            if host is not None
            else QtCore.QPoint(self.width() // 2, self.height() // 2)
        )
        self.move(centre.x() - self.width() // 2, centre.y() - self.height() // 2)
        if self._close_button is not None:
            spot = self.surface_rect()
            size = self._close_button.sizeHint()
            self._close_button.setGeometry(
                QRect(
                    spot.right() + 1 - 8 - size.width(),
                    spot.top() + 8,
                    size.width(),
                    size.height(),
                )
            )
            self._close_button.raise_()

    def surface_rect(self) -> QRect:
        """The panel inside the window, which holds the shadow in its margins."""
        return self.rect().adjusted(SHADOW_MARGIN, SHADOW_MARGIN, -SHADOW_MARGIN, -SHADOW_MARGIN)

    # --- animation ----------------------------------------------------------------------

    def _start(self, target: float) -> None:
        self._animation.stop()
        reduced = _reduced_motion(self)
        if not reduced:
            frame = self._frame_widget.grab()
            if not frame.isNull():
                self._frame = frame
            self._frame_widget.setVisible(False)
            if self._close_button is not None:
                self._close_button.setVisible(False)
        self._animation.setStartValue(float(self._progress))
        self._animation.setEndValue(float(target))
        self._animation.setEasingCurve(EASE_OUT if target >= 1.0 else EASE_IN)
        self._animating = True
        self._animation.start()

    def _on_progress(self, value: object) -> None:
        self._progress = float(value)  # type: ignore[arg-type]
        self.setWindowOpacity(self._progress)
        self.update()

    def _on_animation_done(self) -> None:
        self._animating = False
        self._progress = float(self._animation.endValue())
        self.setWindowOpacity(self._progress)
        self._frame = QtGui.QPixmap()
        self._frame_widget.setVisible(True)
        if self._close_button is not None:
            self._close_button.setVisible(True)
        if self._progress <= 0.0:
            self._closing = False
            if self._scrim is not None:
                self._scrim.hide()
            super().done(self._result_code)
        self.update()

    # --- painting -----------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = self._frame_widget.sizeHint()
        return QSize(
            min(DIALOG_MAX_WIDTH, hint.width()) + 2 * SHADOW_MARGIN,
            hint.height() + 2 * SHADOW_MARGIN,
        )

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.surface_rect()
        if self._animating:
            scale = _SCALE_FROM + (1.0 - _SCALE_FROM) * self._progress
            centre = QtCore.QPointF(QtCore.QRectF(rect).center())
            painter.translate(centre)
            painter.scale(scale, scale)
            painter.translate(-centre)
        theme = theme_of(self)
        paint_surface(painter, rect, theme, radius="xl")
        if self._animating and not self._frame.isNull():
            painter.drawPixmap(
                QtCore.QRectF(rect), self._frame, QtCore.QRectF(self._frame.rect())
            )
        painter.end()


class _DialogTitle(ThemedWidget):
    """The heading of a dialog: `text-base leading-none font-medium`."""

    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self.theme.font(16, QtGui.QFont.Weight.Medium))
        return QSize(metrics.horizontalAdvance(self._text), metrics.height())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self.theme.font(16, QtGui.QFont.Weight.Medium))
        painter.setPen(self.theme.color("popover_foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._text,
        )
        painter.end()


class _DialogDescription(ThemedWidget):
    """The muted paragraph under a dialog's heading, wrapped to the panel's width."""

    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def _wrapped(self, width: int) -> QRect:
        metrics = QtGui.QFontMetrics(self.theme.font(14))
        return metrics.boundingRect(
            QRect(0, 0, max(1, width), 1 << 16), int(Qt.TextFlag.TextWordWrap), self._text
        )

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._wrapped(width).height()

    def sizeHint(self) -> QSize:  # noqa: N802
        box = self._wrapped(DIALOG_MAX_WIDTH - 2 * DIALOG_PADDING)
        return QSize(box.width(), box.height())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(self.theme.font(14))
        painter.setPen(self.theme.color("muted_foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            self._text,
        )
        painter.end()


def _reduced_motion(widget: QtWidgets.QWidget) -> bool:
    return bool(theme_of(widget).reduced_motion)
