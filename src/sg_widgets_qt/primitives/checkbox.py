"""The four controls that carry a boolean: a checkbox, a switch, a toggle and a group of toggles.

Ported from `packages/react/src/components/ui/checkbox.tsx`, `switch.tsx`, `toggle.tsx` and
`toggle-group.tsx`. Upstream's `pressed` prop on a toggle is `checked` here, because `pressed` is
the mouse state every painted leaf already keeps.

    box = Checkbox("Only mine")
    box.toggled.connect(reload)
    group = ToggleGroup([("list", "List"), ("grid", "Grid")], value="list")
"""
from __future__ import annotations

from collections.abc import Sequence

from qtpy import QtCore, QtGui, QtWidgets

from ..icons import paint_icon
from ..theme import mix, with_alpha
from .accessible import AccessibleControl
from .base import (
    CONTROL_HEIGHT,
    DURATION,
    FOCUS_RING_OFFSET,
    FOCUS_RING_WIDTH,
    ThemedWidget,
    fill_round_rect,
    painter_for,
    text_width,
)

__all__ = ["TOGGLE_VARIANT_VALUES", "Checkbox", "Switch", "Toggle", "ToggleGroup"]

#: The two looks of `toggleVariants`: transparent, or a bordered box of its own.
TOGGLE_VARIANT_VALUES: tuple[str, ...] = ("default", "outline")

#: `size-4` of `checkbox.tsx`, and the 24px hit box rule 3 gives it, which is also the ring's room.
CHECKBOX_SIZE = 16
CHECKBOX_SLOT = 24

#: Between the control and its label, rule 2.
LABEL_GAP = 8
LABEL_SIZE = 14

#: `dark:bg-input/30` of `checkbox.tsx`: the wash an unticked box wears on a dark page. The
#: `input` token carries its own alpha, so the fraction is of that, as it is for a field.
REST_WASH_DARK = 0.3

#: The wash the pointer lays over it, which the upstream checkbox has no class for and the
#: Qt port gives every control: `muted` at a share of itself.
HOVER_WASH = 0.6

#: The two steps of `switch.tsx`: the track, then the thumb that slides inside it.
#: `data-[size=default]` is 32 by 18.4 with a `size-4` thumb, `data-[size=sm]` 24 by 14 with a
#: `size-3` one. A step the table does not name wears the default, as `SWITCH` upstream does.
SWITCH_SIZE_VALUES: tuple[str, ...] = ("sm", "default")
SWITCH_TRACK: dict[str, tuple[int, int]] = {"sm": (24, 14), "default": (32, 18)}
SWITCH_THUMB_SIZE: dict[str, int] = {"sm": 12, "default": 16}

#: The default step on its own, which is the track a value reads as rather than edits.
SWITCH_WIDTH, SWITCH_HEIGHT = SWITCH_TRACK["default"]
SWITCH_THUMB = SWITCH_THUMB_SIZE["default"]

#: The 1px transparent border the track carries, which is what the thumb sits in from.
SWITCH_INSET = 1
RING_ROOM = FOCUS_RING_WIDTH + FOCUS_RING_OFFSET

#: `h-8 min-w-8 px-2.5` of `toggle.tsx`, on the control ladder.
TOGGLE_PAD = 10
TOGGLE_GAP = 4
TOGGLE_GLYPH = 16

#: `data-spacing=2`, which is the 8 of rule 2.
TOGGLE_GROUP_SPACING = 8


class Checkbox(AccessibleControl, ThemedWidget):
    """A 16px rounded square in `input`, filled `primary` with a tick when it is on."""

    toggled = QtCore.Signal(bool)
    state_changed = QtCore.Signal(int)

    def __init__(
        self,
        text: str = "",
        tri_state: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._tri_state = bool(tri_state)
        self._state = 0
        self._fill = self.animated(DURATION["hover"])
        self._hover_wash = self.animated(DURATION["hover"])
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.name_after_label()

    # --- accessibility ---

    accessible_role = "checkbox"

    def accessible_states(self) -> dict[str, bool]:
        return {
            "checkable": True,
            "checked": self._state == 2,
            "checkStateMixed": self._state == 1,
            "pressed": self.pressed,
        }

    # --- props ---

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.name_after_label()
        self.updateGeometry()
        self.update()

    @property
    def tri_state(self) -> bool:
        return self._tri_state

    def set_tri_state(self, value: bool) -> None:
        self._tri_state = bool(value)
        if not self._tri_state and self._state == 1:
            self.set_check_state(2)

    @property
    def checked(self) -> bool:
        return self._state == 2

    def set_checked(self, value: bool) -> None:
        self.set_check_state(2 if value else 0)

    @property
    def check_state(self) -> int:
        """0 off, 1 partial, 2 on, the numbers `Qt.CheckState` carries."""
        return self._state

    def set_check_state(self, value: int) -> None:
        value = int(value)
        if value == self._state:
            return
        self._state = value
        self._fill.set(0.0 if value == 0 else 1.0)
        self.state_changed.emit(value)
        self.toggled.emit(value == 2)
        self.update()

    def toggle(self) -> None:
        """Off to on, on to off, and through partial when the box is tri state."""
        if self._tri_state:
            order = {0: 2, 2: 1, 1: 0}
        else:
            order = {0: 2, 1: 2, 2: 0}
        self.set_check_state(order[self._state])

    # --- geometry ---

    def _font(self) -> QtGui.QFont:
        return self.theme.font(LABEL_SIZE)

    def _box(self) -> QtCore.QRect:
        rect = QtCore.QRect(0, 0, CHECKBOX_SIZE, CHECKBOX_SIZE)
        rect.moveCenter(QtCore.QPoint(CHECKBOX_SLOT // 2, self.height() // 2))
        return rect

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        width = CHECKBOX_SLOT
        if self._text:
            width += LABEL_GAP + text_width(QtGui.QFontMetrics(self._font()), self._text)
        return QtCore.QSize(width, CHECKBOX_SLOT)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(CHECKBOX_SLOT, CHECKBOX_SLOT)

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        box = self._box()
        radius = float(theme.radius_px("sm"))
        amount = self._fill.value

        # `checkbox.tsx` carries no ground of its own on a light page and `dark:bg-input/30` on
        # a dark one, then `data-checked:bg-primary` over it. Each is laid on the surface the
        # box stands on rather than blended into `background`, so a checkbox in a dark popover
        # or card is that surface lifted and not a hole of the page's own colour.
        washes = (
            with_alpha(theme.input, REST_WASH_DARK) if theme.dark else None,
            with_alpha(theme.muted, HOVER_WASH * self._hover_wash.value),
            with_alpha(theme.primary, amount),
        )
        for wash in washes:
            if wash is not None and wash.alpha():
                fill_round_rect(painter, box, radius, wash)
        fill_round_rect(painter, box, radius, border=mix(theme.input, theme.primary, amount))

        if amount > 0.0:
            glyph = QtCore.QRect(0, 0, CHECKBOX_SIZE - 3, CHECKBOX_SIZE - 3)
            glyph.moveCenter(box.center())
            name = "minus" if self._state == 1 else "check"
            paint_icon(painter, glyph, name, with_alpha(theme.primary_foreground, amount))

        if self._text:
            painter.setFont(self._font())
            painter.setPen(theme.color("foreground"))
            x = CHECKBOX_SLOT + LABEL_GAP
            width = max(0, self.width() - x)
            label = self.elide(QtGui.QFontMetrics(self._font()), self._text, width)
            self.set_elide_tooltip(self._text, label == self._text)
            painter.drawText(
                QtCore.QRect(x, 0, width, self.height()),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                label,
            )

        if self.keyboard_focus:
            ring = box.adjusted(-RING_ROOM, -RING_ROOM, RING_ROOM, RING_ROOM)
            self.paint_focus_ring(painter, ring, radius + RING_ROOM)
        painter.end()

    # --- interaction ---

    def on_hover_changed(self, value: bool) -> None:
        self._hover_wash.set(1.0 if value else 0.0)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.rect().contains(event.pos()):
                self.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.key() == QtCore.Qt.Key.Key_Space:
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)


class Switch(AccessibleControl, ThemedWidget):
    """A track in `input` off and `primary` on, with a thumb that slides over 150ms.

    Two steps, as `switch.tsx` has: 32 by 18 with a 16 thumb, and 24 by 14 with a 12 one.
    """

    toggled = QtCore.Signal(bool)

    def __init__(
        self,
        checked: bool = False,
        parent: QtWidgets.QWidget | None = None,
        size: str = "default",
    ) -> None:
        super().__init__(parent)
        self._checked = bool(checked)
        self._size = size if size in SWITCH_SIZE_VALUES else "default"
        self._slide = self.animated(DURATION["hover"], value=1.0 if checked else 0.0)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    # --- accessibility ---

    #: A switch has no role of its own in Qt: it reports the check box it behaves as.
    accessible_role = "checkbox"

    def accessible_states(self) -> dict[str, bool]:
        return {"checkable": True, "checked": self._checked, "pressed": self.pressed}

    @property
    def size(self) -> str:
        """Which step of `switch.tsx` the track wears: `sm` or `default`."""
        return self._size

    def set_size(self, value: str) -> None:
        value = value if value in SWITCH_SIZE_VALUES else "default"
        if value == self._size:
            return
        self._size = value
        self.updateGeometry()
        self.update()

    @property
    def checked(self) -> bool:
        return self._checked

    def set_checked(self, value: bool) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        self._slide.set(1.0 if value else 0.0)
        self.toggled.emit(value)
        self.update()

    def toggle(self) -> None:
        self.set_checked(not self._checked)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        width, height = SWITCH_TRACK[self._size]
        return QtCore.QSize(width + RING_ROOM * 2, height + RING_ROOM * 2)

    def _track(self) -> QtCore.QRect:
        width, height = SWITCH_TRACK[self._size]
        rect = QtCore.QRect(0, 0, width, height)
        rect.moveCenter(self.rect().center())
        return rect

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        track = self._track()
        radius = track.height() / 2.0
        off = with_alpha(theme.input, 0.8) if theme.dark else theme.color("input")
        fill_round_rect(painter, track, radius, mix(off, theme.primary, self._slide.value))

        side = SWITCH_THUMB_SIZE[self._size]
        travel = track.width() - side - SWITCH_INSET * 2
        x = track.x() + SWITCH_INSET + travel * self._slide.value
        thumb = QtCore.QRectF(x, track.y() + SWITCH_INSET, side, side)
        if theme.dark:
            ink = mix(theme.foreground, theme.primary_foreground, self._slide.value)
        else:
            ink = theme.color("background")
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawEllipse(thumb)

        if self.keyboard_focus:
            ring = track.adjusted(-RING_ROOM, -RING_ROOM, RING_ROOM, RING_ROOM)
            self.paint_focus_ring(painter, ring, radius + RING_ROOM)
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.rect().contains(event.pos()):
                self.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.key() == QtCore.Qt.Key.Key_Space:
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)


class Toggle(AccessibleControl, ThemedWidget):
    """A button that stays down: ghost until it is on, `accent` once it is.

    `variant='outline'` is `toggleVariants`' second look: a `border-input` box of its own, which
    is what a pair standing as one control wears — the filter editor's All and Any, the sort
    picker's ascending and descending.
    """

    toggled = QtCore.Signal(bool)

    def __init__(
        self,
        text: str = "",
        icon: str | None = None,
        pressed: bool = False,
        size: str = "md",
        variant: str = "default",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self._variant = variant if variant in TOGGLE_VARIANT_VALUES else "default"
        self._checked = bool(pressed)
        self._hover = self.animated(DURATION["hover"])
        self._fill = self.animated(DURATION["hover"], value=1.0 if pressed else 0.0)
        self.set_size_step(size if size in CONTROL_HEIGHT else "md")
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.name_after_label()

    # --- accessibility ---

    #: Upstream's `aria-pressed` button: a button that stays down is a checkable one here.
    accessible_role = "button"

    def accessible_states(self) -> dict[str, bool]:
        return {"checkable": True, "checked": self._checked, "pressed": self.pressed}

    # --- props ---

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value
        self.name_after_label()
        self.updateGeometry()
        self.update()

    @property
    def icon(self) -> str | None:
        return self._icon

    def set_icon(self, name: str | None) -> None:
        self._icon = name
        self.updateGeometry()
        self.update()

    @property
    def variant(self) -> str:
        """`default` or `outline`, which draws the toggle its own border."""
        return self._variant

    def set_variant(self, value: str) -> None:
        self._variant = value if value in TOGGLE_VARIANT_VALUES else "default"
        self.update()

    @property
    def checked(self) -> bool:
        """Upstream's `pressed`: the toggle is down."""
        return self._checked

    def set_checked(self, value: bool) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        self._fill.set(1.0 if value else 0.0)
        self.toggled.emit(value)
        self.update()

    def toggle(self) -> None:
        self.set_checked(not self._checked)

    # --- geometry ---

    def _font(self) -> QtGui.QFont:
        return self.theme.font(LABEL_SIZE, QtGui.QFont.Weight.Medium)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        height = CONTROL_HEIGHT[self.size_step]
        width = TOGGLE_PAD * 2
        parts = 0
        if self._icon is not None:
            width += TOGGLE_GLYPH
            parts += 1
        if self._text:
            width += text_width(QtGui.QFontMetrics(self._font()), self._text)
            parts += 1
        width += TOGGLE_GAP * max(0, parts - 1)
        return QtCore.QSize(max(height, width), height)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        height = CONTROL_HEIGHT[self.size_step]
        return QtCore.QSize(height, height)

    # --- painting ---

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        theme = self.theme
        box = QtCore.QRect(0, 0, self.width(), min(self.height(), CONTROL_HEIGHT[self.size_step]))
        box.moveCenter(self.rect().center())
        radius = float(theme.radius_px("lg"))

        hover = with_alpha(theme.muted, 0.5) if theme.dark else theme.color("muted")
        surface = mix(with_alpha(theme.muted, 0.0), hover, self._hover.value)
        surface = mix(surface, theme.accent, self._fill.value)
        ink = mix(theme.color("foreground"), theme.color("accent_foreground"), self._fill.value)
        border = theme.color("input") if self._variant == "outline" else None
        fill_round_rect(painter, box, radius, surface, border)

        font = self._font()
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        content = self.sizeHint().width() - TOGGLE_PAD * 2
        x = box.x() + (box.width() - content) // 2
        if self._icon is not None:
            glyph = QtCore.QRect(0, 0, TOGGLE_GLYPH, TOGGLE_GLYPH)
            glyph.moveCenter(QtCore.QPoint(x + TOGGLE_GLYPH // 2, box.center().y()))
            paint_icon(painter, glyph, self._icon, ink)
            x += TOGGLE_GLYPH + (TOGGLE_GAP if self._text else 0)
        if self._text:
            width = max(0, box.right() + 1 - TOGGLE_PAD - x)
            label = self.elide(metrics, self._text, width)
            self.set_elide_tooltip(self._text, label == self._text)
            painter.setPen(ink)
            painter.drawText(
                QtCore.QRect(x, box.y(), width, box.height()),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                label,
            )

        if self.keyboard_focus:
            self.paint_focus_ring(painter, box, radius)
        painter.end()

    # --- interaction ---

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            self.set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == QtCore.Qt.MouseButton.LeftButton:
            was = self.pressed
            self.set_pressed(False)
            if was and self.rect().contains(event.pos()):
                self.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter)
        if self.isEnabled() and event.key() in keys:
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)


class ToggleGroup(ThemedWidget):
    """A row of toggles holding one value, or several when `multiple` is on.

    `items` are `value`, `(value, label)` or `(value, label, icon)`. The arrows walk the row and,
    on a single group, pick as they go.
    """

    value_changed = QtCore.Signal(object)

    def __init__(
        self,
        items: Sequence[object] = (),
        value: object = None,
        multiple: bool = False,
        size: str = "md",
        variant: str = "default",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._multiple = bool(multiple)
        self._variant = variant if variant in TOGGLE_VARIANT_VALUES else "default"
        self._toggles: list[Toggle] = []
        self._values: list[str] = []
        self._names: dict[str, str] = {}
        self.set_size_step(size if size in CONTROL_HEIGHT else "md")

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TOGGLE_GROUP_SPACING)
        self._row = row
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.set_items(items)
        self.set_value(value)

    # --- props ---

    @property
    def items(self) -> list[str]:
        return list(self._values)

    def set_items(self, items: Sequence[object]) -> None:
        for toggle in self._toggles:
            self._row.removeWidget(toggle)
            toggle.setParent(None)
            toggle.deleteLater()
        self._toggles = []
        self._values = []
        for item in items:
            value, label, icon = self._split(item)
            toggle = Toggle(
                label, icon=icon, size=self.size_step, variant=self._variant, parent=self
            )
            toggle.toggled.connect(self._on_toggled)
            if value in self._names:
                toggle.setAccessibleName(self._names[value])
            self._row.addWidget(toggle)
            self._toggles.append(toggle)
            self._values.append(value)
        self.updateGeometry()

    def set_accessible_names(self, names: dict[str, str]) -> None:
        """Name each toggle by its value, for a row of glyphs that reads as nothing.

        The names outlive a new `items`, so a group rebuilt from its values keeps them.
        """
        self._names = dict(names)
        for value, toggle in zip(self._values, self._toggles):
            if value in self._names:
                toggle.setAccessibleName(self._names[value])

    @staticmethod
    def _split(item: object) -> tuple[str, str, str | None]:
        if isinstance(item, str):
            return item, item, None
        parts = list(item)  # type: ignore[call-overload]
        value = str(parts[0])
        label = str(parts[1]) if len(parts) > 1 else value
        icon = str(parts[2]) if len(parts) > 2 and parts[2] else None
        return value, label, icon

    @property
    def variant(self) -> str:
        """The look every toggle in the row wears."""
        return self._variant

    @property
    def multiple(self) -> bool:
        return self._multiple

    @property
    def value(self) -> object:
        """The chosen value, or the list of them on a group that takes several."""
        chosen = [v for v, t in zip(self._values, self._toggles) if t.checked]
        if self._multiple:
            return chosen
        return chosen[0] if chosen else None

    def set_value(self, value: object) -> None:
        wanted = set(value) if isinstance(value, (list, tuple, set)) else ({value} if value else set())
        for name, toggle in zip(self._values, self._toggles):
            toggle.blockSignals(True)
            toggle.set_checked(name in wanted)
            toggle.blockSignals(False)
        self.update()

    def toggles(self) -> list[Toggle]:
        """The row's toggles, in order."""
        return list(self._toggles)

    # --- behaviour ---

    def _on_toggled(self, on: bool) -> None:
        sender = self.sender()
        if not isinstance(sender, Toggle):
            return
        if not self._multiple and on:
            for toggle in self._toggles:
                if toggle is not sender and toggle.checked:
                    toggle.blockSignals(True)
                    toggle.set_checked(False)
                    toggle.blockSignals(False)
        if not self._multiple and not on:
            # A single group always holds a value: pressing the chosen one again keeps it.
            sender.blockSignals(True)
            sender.set_checked(True)
            sender.blockSignals(False)
            return
        self.value_changed.emit(self.value)

    def _step(self, delta: int) -> None:
        if not self._toggles:
            return
        current = 0
        for index, toggle in enumerate(self._toggles):
            if toggle.hasFocus():
                current = index
                break
        target = (current + delta) % len(self._toggles)
        self._toggles[target].setFocus(QtCore.Qt.FocusReason.TabFocusReason)
        if not self._multiple:
            self._toggles[target].set_checked(True)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        back = (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Up)
        forward = (QtCore.Qt.Key.Key_Right, QtCore.Qt.Key.Key_Down)
        if event.key() in back:
            self._step(-1)
            event.accept()
            return
        if event.key() in forward:
            self._step(1)
            event.accept()
            return
        super().keyPressEvent(event)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        height = CONTROL_HEIGHT[self.size_step]
        width = sum(t.sizeHint().width() for t in self._toggles)
        width += TOGGLE_GROUP_SPACING * max(0, len(self._toggles) - 1)
        return QtCore.QSize(width, height)
