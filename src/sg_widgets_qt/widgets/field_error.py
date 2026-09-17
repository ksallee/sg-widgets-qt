"""The line a field editor shows under its control.

Ported from `packages/react/src/registry/sg/components/field-error.tsx`. A parse that was refused,
or a message the caller named, becomes one wrapped 12px line in `destructive` under the control.
Nothing to say and the line takes no room at all.

    error = FieldError("Not a date. Use YYYY-MM-DD.")
    error.set_message(None)
"""
from __future__ import annotations

from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets

from ..primitives.base import ThemedWidget

__all__ = ["FIELD_ERROR_SIZE", "FIELD_ERROR_SLOT", "FieldError"]

#: The `data-slot` upstream gives the line, which is this widget's object name.
FIELD_ERROR_SLOT = "field-editor-error"

#: `text-xs` of `field-error.tsx`, the metadata step of `docs/design-rules.md` rule 6.
FIELD_ERROR_SIZE = 12


class _ErrorLine(ThemedWidget):
    """One run of 12px `destructive`, wrapped to the width it is given."""

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        self.setMinimumWidth(0)

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.updateGeometry()
        self.update()

    def _metrics(self) -> QtGui.QFontMetrics:
        return QtGui.QFontMetrics(self.theme.font(FIELD_ERROR_SIZE))

    def _flags(self) -> int:
        return int(
            QtCore.Qt.AlignmentFlag.AlignTop
            | QtCore.Qt.AlignmentFlag.AlignLeft
            | QtCore.Qt.TextFlag.TextWordWrap
        )

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = self._metrics()
        if not self._text:
            return QtCore.QSize(0, 0)
        box = metrics.boundingRect(
            QtCore.QRect(0, 0, max(80, self.width()), 10000), self._flags(), self._text
        )
        return QtCore.QSize(0, max(metrics.height(), box.height()))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, 0 if not self._text else self._metrics().height())

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.updateGeometry()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._text:
            return
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(theme.font(FIELD_ERROR_SIZE))
        painter.setPen(theme.color("destructive"))
        painter.drawText(self.rect(), self._flags(), self._text)
        painter.end()


class FieldError(QtWidgets.QWidget):
    """The message under a control, or nothing at all.

    `error_message` takes the message and answers the widget that draws it, in place of the line.
    """

    def __init__(
        self,
        message: str | None = None,
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(FIELD_ERROR_SLOT)
        self._message: str | None = None
        self._renderer = error_message
        self._custom: QtWidgets.QWidget | None = None

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self._line = _ErrorLine("", self)
        column.addWidget(self._line)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        self.set_message(message)

    @property
    def message(self) -> str | None:
        """The message, or None when there is nothing to say."""
        return self._message

    def set_message(self, value: str | None) -> None:
        self._message = value if value else None
        self._rebuild()

    @property
    def error_message(self) -> Callable[[str], QtWidgets.QWidget] | None:
        """What draws the message. None is the line under the control."""
        return self._renderer

    def set_error_message(self, renderer: Callable[[str], QtWidgets.QWidget] | None) -> None:
        self._renderer = renderer
        self._rebuild()

    def _rebuild(self) -> None:
        column = self.layout()
        if self._custom is not None:
            column.removeWidget(self._custom)
            self._custom.setParent(None)
            self._custom.deleteLater()
            self._custom = None
        if self._message is None:
            self._line.set_text("")
            self._line.setVisible(False)
            self.setVisible(False)
            self.updateGeometry()
            return
        if self._renderer is not None:
            self._line.setVisible(False)
            self._custom = self._renderer(self._message)
            self._custom.setParent(self)
            column.addWidget(self._custom)
            self._custom.show()
        else:
            self._line.set_text(self._message)
            self._line.setVisible(True)
        self.setVisible(True)
        self.updateGeometry()
