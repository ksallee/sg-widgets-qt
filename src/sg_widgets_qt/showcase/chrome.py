"""The shell's own controls, painted from the tokens.

The sidebar, the header and a stage's toolbar are drawn by this repo like every widget is: no
`QPushButton`, no `QComboBox`, no `QCheckBox` wearing the host style. `primitives/` owns these
controls once it carries them; until then this module is what the shell wears, and `button`,
`select` and `switch` answer the primitive where there is one.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from qtpy import QtCore, QtGui, QtWidgets

from .. import icons
from ..theme import Theme, mix, theme_of, watch_theme, with_alpha

__all__ = [
    "HEIGHTS",
    "ChromeButton",
    "ChromeSelect",
    "ChromeSwitch",
    "SearchField",
    "button",
    "overlay_scroll_area",
    "primitive",
    "select",
    "switch",
]

#: The height ladder: `sm`, `md`, `lg`.
HEIGHTS: dict[str, int] = {"sm": 28, "md": 32, "lg": 36}

#: How long a hover or press takes to settle.
FEEDBACK_MS = 150


def primitive(name: str) -> Any:
    """The primitive of that name, or `None` while `primitives/` does not carry it."""
    try:
        module = __import__("sg_widgets_qt.primitives", fromlist=[name])
    except Exception:
        return None
    return getattr(module, name, None)


class _Painted(QtWidgets.QWidget):
    """A control that paints itself from the theme and follows hover, press and keyboard focus."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, size: str = "md") -> None:
        super().__init__(parent)
        self._size = size
        self._hover = 0.0
        self._pressed = False
        self._ring = False
        self._animation: QtGui.QColor | None = None
        self._fade: QtCore.QVariantAnimation | None = None
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(HEIGHTS.get(size, HEIGHTS["md"]))
        watch_theme(self, lambda _theme: self.update())

    @property
    def theme(self) -> Theme:
        return theme_of(self)

    def set_size(self, size: str) -> None:
        self._size = size
        self.setFixedHeight(HEIGHTS.get(size, HEIGHTS["md"]))
        self.updateGeometry()
        self.update()

    # --- state ------------------------------------------------------------------------------

    def _to_hover(self, target: float) -> None:
        if self.theme.reduced_motion:
            self._hover = target
            self.update()
            return
        if self._fade is not None:
            self._fade.stop()
        fade = QtCore.QVariantAnimation(self)
        fade.setStartValue(float(self._hover))
        fade.setEndValue(float(target))
        fade.setDuration(FEEDBACK_MS)
        fade.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        fade.valueChanged.connect(self._on_fade)
        fade.start(QtCore.QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade = fade

    def _on_fade(self, value: object) -> None:
        self._hover = float(value)  # type: ignore[arg-type]
        self.update()

    def enterEvent(self, event: object) -> None:  # noqa: N802
        if self.isEnabled():
            self._to_hover(1.0)
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        self._to_hover(0.0)
        super().leaveEvent(event)  # type: ignore[arg-type]

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        was, self._pressed = self._pressed, False
        self.update()
        if was and self.rect().contains(event.pos()) and self.isEnabled():
            self.activate()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() in (
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
            QtCore.Qt.Key.Key_Space,
        ):
            self.activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        self._ring = event.reason() in (
            QtCore.Qt.FocusReason.TabFocusReason,
            QtCore.Qt.FocusReason.BacktabFocusReason,
            QtCore.Qt.FocusReason.ShortcutFocusReason,
        )
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        self._ring = False
        self.update()
        super().focusOutEvent(event)

    def activate(self) -> None:
        """What a click or Enter does. Overridden by the control."""

    # --- painting ---------------------------------------------------------------------------

    def _body(self) -> QtCore.QRectF:
        box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._pressed:
            dx = box.width() * 0.01
            dy = box.height() * 0.01
            box = box.adjusted(dx, dy, -dx, -dy)
        return box

    def _paint_ring(self, painter: QtGui.QPainter, radius: float) -> None:
        if not self._ring:
            return
        theme = self.theme
        box = QtCore.QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        pen = QtGui.QPen(theme.color("ring"), 2.0)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box, radius, radius)


class ChromeButton(_Painted):
    """A button in the shadcn variants, painted from the tokens."""

    clicked = QtCore.Signal()
    toggled = QtCore.Signal(bool)

    VARIANTS = ("default", "secondary", "outline", "ghost", "destructive")

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
        size: str = "md",
        glyph: str = "",
        checkable: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size)
        self._text = text
        self._variant = variant if variant in self.VARIANTS else "default"
        self._glyph = glyph
        self._checkable = checkable
        self._checked = False
        self.setObjectName("button")

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.updateGeometry()
        self.update()

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> None:
        if self._checked == bool(checked):
            return
        self._checked = bool(checked)
        self.update()
        self.toggled.emit(self._checked)

    def activate(self) -> None:
        if self._checkable:
            self.set_checked(not self._checked)
        self.clicked.emit()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        width = metrics.horizontalAdvance(self._text) + 24
        if self._glyph:
            width += 22
        return QtCore.QSize(width, self.height())

    def _font(self) -> QtGui.QFont:
        weight = (
            QtGui.QFont.Weight.Medium
            if self._checked or self._variant == "default"
            else QtGui.QFont.Weight.Normal
        )
        return self.theme.font(14 if self._size != "sm" else 13, weight)

    def _colors(self, theme: Theme) -> tuple[QtGui.QColor, QtGui.QColor, QtGui.QColor | None]:
        ground = theme.color("background")
        if self._checked:
            return theme.color("accent"), theme.color("accent_foreground"), None
        if self._variant == "default":
            return theme.color("primary"), theme.color("primary_foreground"), None
        if self._variant == "secondary":
            return theme.color("secondary"), theme.color("secondary_foreground"), None
        if self._variant == "destructive":
            return theme.color("destructive"), theme.color("destructive_foreground"), None
        if self._variant == "outline":
            return ground, theme.color("foreground"), theme.color("border")
        return QtGui.QColor(0, 0, 0, 0), theme.color("foreground"), None

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(1.0 if self.isEnabled() else 0.5)
        fill, ink, border = self._colors(theme)
        radius = float(theme.radius_px("md"))
        if self._hover > 0.0:
            if self._variant in ("ghost", "outline") and not self._checked:
                fill = mix(fill, theme.color("accent"), self._hover)
                ink = mix(ink, theme.color("accent_foreground"), self._hover)
            else:
                fill = mix(fill, theme.color("background"), 0.1 * self._hover)
        box = self._body()
        painter.setPen(
            QtGui.QPen(border, 1.0) if border is not None else QtCore.Qt.PenStyle.NoPen
        )
        painter.setBrush(fill)
        painter.drawRoundedRect(box, radius, radius)

        painter.setFont(self._font())
        text_box = box.adjusted(12, 0, -12, 0)
        if self._glyph:
            glyph_box = QtCore.QRect(int(box.left()) + 8, 0, 16, self.height())
            icons.paint_icon(painter, glyph_box, self._glyph, ink)
            text_box = text_box.adjusted(16, 0, 0, 0)
        painter.setPen(ink)
        painter.drawText(
            text_box,
            int(QtCore.Qt.AlignmentFlag.AlignCenter),
            self._text,
        )
        self._paint_ring(painter, radius + 1.0)
        painter.end()


class ChromeSwitch(_Painted):
    """A two-state switch: a pill with a knob, and its label beside it."""

    toggled = QtCore.Signal(bool)

    def __init__(
        self,
        label: str = "",
        checked: bool = False,
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size)
        self._label = label
        self._checked = bool(checked)
        self.setObjectName("switch")

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool) -> None:
        if self._checked == bool(checked):
            return
        self._checked = bool(checked)
        self.update()
        self.toggled.emit(self._checked)

    def activate(self) -> None:
        self.set_checked(not self._checked)

    def _track(self) -> QtCore.QRectF:
        height = 20.0 if self._size != "lg" else 24.0
        width = height * 1.8
        top = (self.height() - height) / 2.0
        return QtCore.QRectF(0.5, top, width, height)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        width = int(self._track().width()) + 2
        if self._label:
            metrics = QtGui.QFontMetrics(self.theme.font(13))
            width += 8 + metrics.horizontalAdvance(self._label)
        return QtCore.QSize(width, self.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(1.0 if self.isEnabled() else 0.5)
        track = self._track()
        fill = theme.color("primary") if self._checked else theme.color("input")
        if self._hover > 0.0:
            fill = mix(fill, theme.color("foreground"), 0.08 * self._hover)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        radius = track.height() / 2.0
        painter.drawRoundedRect(track, radius, radius)
        knob = track.height() - 4.0
        x = track.right() - knob - 2.0 if self._checked else track.left() + 2.0
        painter.setBrush(theme.color("background" if not self._checked else "primary_foreground"))
        painter.drawEllipse(QtCore.QRectF(x, track.top() + 2.0, knob, knob))
        if self._label:
            painter.setFont(theme.font(13))
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                QtCore.QRectF(track.right() + 8.0, 0.0, self.width() - track.right() - 8.0, float(self.height())),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                self._label,
            )
        self._paint_ring(painter, radius + 1.0)
        painter.end()


class ChromeSelect(_Painted):
    """A select: the value, a chevron, and a menu of the options."""

    picked = QtCore.Signal(str)

    def __init__(
        self,
        options: Sequence[tuple[str, str]],
        value: str = "",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size)
        self._options = list(options)
        self._value = value or (self._options[0][0] if self._options else "")
        self.setObjectName("select")

    def value(self) -> str:
        return self._value

    def set_value(self, value: str, notify: bool = False) -> None:
        if value == self._value or value not in [name for name, _ in self._options]:
            return
        self._value = value
        self.updateGeometry()
        self.update()
        if notify:
            self.picked.emit(value)

    def set_options(self, options: Sequence[tuple[str, str]]) -> None:
        self._options = list(options)
        self.update()

    def label(self) -> str:
        for name, text in self._options:
            if name == self._value:
                return text
        return self._value

    def activate(self) -> None:
        if not self.isEnabled() or not self._options:
            return
        menu = QtWidgets.QMenu(self)
        menu.setFont(self.theme.font(13))
        for name, text in self._options:
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(name == self._value)
            action.triggered.connect(lambda _checked=False, value=name: self._pick(value))
        menu.exec_(self.mapToGlobal(QtCore.QPoint(0, self.height() + 4)))

    def _pick(self, value: str) -> None:
        if value == self._value:
            return
        self._value = value
        self.updateGeometry()
        self.update()
        self.picked.emit(value)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self.theme.font(13))
        widest = max(
            [metrics.horizontalAdvance(text) for _name, text in self._options] or [40]
        )
        return QtCore.QSize(widest + 40, self.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(1.0 if self.isEnabled() else 0.5)
        box = self._body()
        radius = float(theme.radius_px("md"))
        fill = theme.color("background")
        ink = theme.color("foreground")
        if self._hover > 0.0:
            fill = mix(fill, theme.color("accent"), self._hover)
            ink = mix(ink, theme.color("accent_foreground"), self._hover)
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.setBrush(fill)
        painter.drawRoundedRect(box, radius, radius)
        painter.setFont(theme.font(13))
        painter.setPen(ink)
        text_box = box.adjusted(10, 0, -26, 0)
        metrics = QtGui.QFontMetrics(painter.font())
        painter.drawText(
            text_box,
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(self.label(), QtCore.Qt.TextElideMode.ElideRight, int(text_box.width())),
        )
        icons.paint_icon(
            painter,
            QtCore.QRect(int(box.right()) - 22, 0, 16, self.height()),
            "chevron-down",
            ink,
        )
        self._paint_ring(painter, radius + 1.0)
        painter.end()


class SearchField(QtWidgets.QWidget):
    """A search box: the glyph, the input, and the surface they stand on."""

    text_changed = QtCore.Signal(str)

    def __init__(
        self,
        placeholder: str = "Search",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("search-field")
        self._size = size
        self.setFixedHeight(HEIGHTS.get(size, HEIGHTS["md"]))
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 8, 0)
        layout.setSpacing(0)
        self.input = QtWidgets.QLineEdit(self)
        self.input.setObjectName("search-input")
        self.input.setFrame(False)
        self.input.setPlaceholderText(placeholder)
        self.input.textChanged.connect(self.text_changed)
        layout.addWidget(self.input)
        watch_theme(self, self._restyle)
        self._restyle(theme_of(self))

    def text(self) -> str:
        return self.input.text()

    def set_text(self, text: str) -> None:
        self.input.setText(text)

    def _restyle(self, theme: Theme) -> None:
        self.input.setFont(theme.font(13))
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        box = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = float(theme.radius_px("md"))
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.setBrush(theme.color("background"))
        painter.drawRoundedRect(box, radius, radius)
        icons.paint_icon(
            painter,
            QtCore.QRect(8, 0, 16, self.height()),
            "search",
            with_alpha(theme.color("muted_foreground"), 0.9),
        )
        if self.input.hasFocus():
            pen = QtGui.QPen(theme.color("ring"), 2.0)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QtCore.QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0), radius + 1.0, radius + 1.0
            )
        painter.end()


# --- what the shell asks for -------------------------------------------------------------------


def button(
    text: str = "",
    variant: str = "default",
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_click: Callable[[], None] | None = None,
    **extra: Any,
) -> QtWidgets.QWidget:
    """A button: the primitive where `primitives/button.py` carries one, else the painted one."""
    made = _from_primitive("Button", text=text, variant=variant, size=size, parent=parent, **extra)
    if made is None:
        made = ChromeButton(text=text, variant=variant, size=size, parent=parent, **extra)
    if on_click is not None:
        signal = getattr(made, "clicked", None)
        if signal is not None:
            signal.connect(lambda *_args: on_click())
    return made


def select(
    options: Sequence[tuple[str, str]],
    value: str = "",
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_pick: Callable[[str], None] | None = None,
) -> QtWidgets.QWidget:
    """A select: the primitive where there is one, else the painted one."""
    made = _from_primitive("Select", options=options, value=value, size=size, parent=parent)
    if made is None:
        made = ChromeSelect(options, value=value, size=size, parent=parent)
    if on_pick is not None:
        for name in ("picked", "value_changed", "currentTextChanged"):
            signal = getattr(made, name, None)
            if signal is not None:
                signal.connect(on_pick)
                break
    return made


def switch(
    label: str = "",
    checked: bool = False,
    size: str = "md",
    parent: QtWidgets.QWidget | None = None,
    on_toggle: Callable[[bool], None] | None = None,
) -> QtWidgets.QWidget:
    """A switch: the primitive where there is one, else the painted one."""
    made = _from_primitive("Switch", label=label, checked=checked, size=size, parent=parent)
    if made is None:
        made = _from_primitive("Toggle", label=label, checked=checked, size=size, parent=parent)
    if made is None:
        made = ChromeSwitch(label=label, checked=checked, size=size, parent=parent)
    if on_toggle is not None:
        signal = getattr(made, "toggled", None)
        if signal is not None:
            signal.connect(on_toggle)
    return made


def _from_primitive(name: str, **kwargs: Any) -> QtWidgets.QWidget | None:
    """Build a primitive, or answer `None` where it is absent or takes other keywords."""
    factory = primitive(name)
    if factory is None:
        return None
    try:
        return factory(**kwargs)
    except TypeError:
        return None


def overlay_scroll_area(parent: QtWidgets.QWidget | None = None) -> QtWidgets.QScrollArea:
    """A scroll area wearing the overlay scrollbar."""
    area = QtWidgets.QScrollArea(parent)
    area.setObjectName("scroll-area")
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    bar = primitive("OverlayScrollBar")
    if bar is not None:
        try:
            area.setVerticalScrollBar(bar(QtCore.Qt.Orientation.Vertical, area))
        except TypeError:
            try:
                area.setVerticalScrollBar(bar(area))
            except TypeError:
                pass
    area.verticalScrollBar().setSingleStep(24)
    return area
