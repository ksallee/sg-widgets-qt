"""The shell's own controls.

The sidebar, the header and a stage's caption wear the same primitives the widgets do, so the
chrome and the demos read as one hand. This module is the few shapes `primitives/` does not carry:
a line of text, a flat ground, the switch with its label, and the search box the rail filters on.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets

from ..primitives.button import Button
from ..primitives.checkbox import Switch, Toggle
from ..primitives.input import Input
from ..primitives.scrollbar import install_overlay_scrollbars
from ..primitives.select import Select
from ..theme import theme_of, watch_theme

__all__ = [
    "BUTTON_SIZES",
    "HEIGHTS",
    "Ground",
    "SearchField",
    "SwitchRow",
    "TextLine",
    "button",
    "overlay_scroll_area",
    "select",
    "switch",
    "toggle",
]

#: The height ladder: `sm`, `md`, `lg`.
HEIGHTS: dict[str, int] = {"sm": 28, "md": 32, "lg": 36}

#: Our size step as `primitives/button.py` spells it.
BUTTON_SIZES: dict[str, str] = {"sm": "sm", "md": "default", "lg": "lg"}


class TextLine(QtWidgets.QWidget):
    """One line of text in a token colour, at a size on the type scale."""

    def __init__(
        self,
        text: str = "",
        size: int = 13,
        token: str = "muted_foreground",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._size = size
        self._token = token
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        watch_theme(self, lambda _theme: self.updateGeometry())

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(theme_of(self).font(self._size))
        return QtCore.QSize(metrics.horizontalAdvance(self._text), metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setFont(theme.font(self._size))
        painter.setPen(theme.color(self._token))
        painter.drawText(
            self.rect(),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            self._text,
        )
        painter.end()


class Ground(QtWidgets.QWidget):
    """A flat surface in one token, so the area behind a page is the theme's and not the host's."""

    def __init__(self, token: str = "background", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._token = token
        watch_theme(self, lambda _theme: self.update())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), theme_of(self).color(self._token))
        painter.end()


class SwitchRow(QtWidgets.QWidget):
    """The switch with its label beside it, as one control."""

    toggled = QtCore.Signal(bool)

    def __init__(
        self,
        label: str = "",
        checked: bool = False,
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("switch")
        self.track = Switch(checked=checked, parent=self)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.track)
        self.label = TextLine(label, 13, "muted_foreground", self)
        row.addWidget(self.label)
        self.setFixedHeight(HEIGHTS.get(size, HEIGHTS["md"]))
        self.track.toggled.connect(self.toggled)

    def is_checked(self) -> bool:
        return self.track.checked

    def set_checked(self, checked: bool) -> None:
        self.track.set_checked(bool(checked))


class SearchField(QtWidgets.QWidget):
    """A search box: the input primitive with the glyph in its leading slot."""

    text_changed = QtCore.Signal(str)

    def __init__(
        self,
        placeholder: str = "Search",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("search-field")
        self.setFixedHeight(HEIGHTS.get(size, HEIGHTS["md"]))
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.input = Input(placeholder=placeholder, size=size, parent=self)
        self.input.setObjectName("search-input")
        self.input.set_leading_icon("search")
        self.input.textChanged.connect(self.text_changed)
        row.addWidget(self.input)

    def text(self) -> str:
        return self.input.text()

    def set_text(self, text: str) -> None:
        self.input.setText(text)


def button(
    text: str = "",
    variant: str = "default",
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_click: Callable[[], None] | None = None,
) -> Button:
    """A button at our size step."""
    made = Button(
        text=text, variant=variant, size=BUTTON_SIZES.get(size, "default"), parent=parent
    )
    if on_click is not None:
        made.clicked.connect(lambda *_args: on_click())
    return made


def select(
    options: Sequence[tuple[str, str]],
    value: str = "",
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_pick: Callable[[str], None] | None = None,
) -> Select:
    """A select over `(value, label)` pairs."""
    made = Select(items=list(options), value=value, size=size, parent=parent)
    _hold_label(made)
    if on_pick is not None:
        made.value_changed.connect(lambda picked: on_pick(str(picked)))
    return made


def switch(
    label: str = "",
    checked: bool = False,
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_toggle: Callable[[bool], None] | None = None,
) -> SwitchRow:
    """A switch and its label."""
    made = SwitchRow(label=label, checked=checked, size=size, parent=parent)
    if on_toggle is not None:
        made.toggled.connect(on_toggle)
    return made


def toggle(
    text: str = "",
    pressed: bool = False,
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_toggle: Callable[[bool], None] | None = None,
    variant: str = "outline",
) -> Toggle:
    """A button that stays down, bordered at rest.

    A demo's toggles are `border border-border bg-background ... aria-pressed:bg-accent`
    upstream, so they read as controls before they are pressed; the ghost look belongs to a
    toggle inside a control, not to one standing alone on a page.
    """
    made = Toggle(text=text, pressed=pressed, size=size, variant=variant, parent=parent)
    if on_toggle is not None:
        made.toggled.connect(on_toggle)
    return made


def _hold_label(control: QtWidgets.QWidget) -> None:
    """Keep a select wide enough for its own longest label.

    `primitives/select.py` leaves the ring's room out of `sizeHint`, so a select at exactly its
    hint elides the value it was measured from.
    """
    slack = 8

    def fit(_theme: object = None) -> None:
        control.setMinimumWidth(control.sizeHint().width() + slack)

    watch_theme(control, fit)
    fit()


def overlay_scroll_area(parent: QtWidgets.QWidget | None = None) -> QtWidgets.QScrollArea:
    """A scroll area wearing the thin overlay scrollbars."""
    area = QtWidgets.QScrollArea(parent)
    area.setObjectName("scroll-area")
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    install_overlay_scrollbars(area)
    area.verticalScrollBar().setSingleStep(24)
    return area
