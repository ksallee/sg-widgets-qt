"""A value chosen from a list, drawn as a control with a popup list under it.

The trigger stands on the control ladder and carries the chosen label or the placeholder and a
`chevrons-up-down` glyph. The list hangs off it on a `Popover` as wide as the control, one row
ticked, walked with the arrows and with typeahead.

    select = Select([("hold", "On hold"), ("ip", "In progress")], value="ip")
    select.value_changed.connect(print)
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QRect, QSize, Qt, Signal

from ..icons import paint_icon
from ..theme import with_alpha
from .base import CONTROL_GLYPH, CONTROL_HEIGHT, CONTROL_PAD, DURATION, ThemedWidget, elide
from .dropdown_menu import MenuEntry, MenuList, MenuPanel
from .popover import Popover

__all__ = ["SELECT_TRAILING_PAD", "Select"]

#: `pr-2` of the trigger: the chevron sits closer to the edge than the label does.
SELECT_TRAILING_PAD = 8

#: The gap between the label and the chevron.
SELECT_GAP = 6

#: `dark:bg-input/30` and `dark:hover:bg-input/50` of `select.tsx`: the wash the trigger wears
#: on a dark page at rest and under the pointer. The `input` token carries its own alpha, so the
#: fraction is of that, as it is for a field.
REST_WASH_DARK = 0.3
HOVER_WASH_DARK = 0.5

#: The trigger carries no ground at all on a light page, where `bg-transparent` leaves the card,
#: the popover or the page under it showing through; the pointer washes it with `muted/30`.
HOVER_WASH = 0.3


class Select(ThemedWidget):
    """A control that opens a list and keeps one value.

    `items` is `[(value, label), ...]`; `set_groups` takes `[(heading, items), ...]` instead.
    `size` is a rung of the control ladder, and `invalid`, `readonly` and `setEnabled` are the
    states of `docs/design-rules.md` rule 5, in that order of precedence.
    """

    value_changed = Signal(object)
    opened = Signal()
    closed = Signal()

    def __init__(
        self,
        items: list[tuple[Any, str]] | None = None,
        value: Any = None,
        placeholder: str = "Select",
        size: str = "md",
        invalid: bool = False,
        readonly: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size_step=size if size in CONTROL_HEIGHT else "md")
        self._groups: list[tuple[str | None, list[tuple[Any, str]]]] = [(None, list(items or []))]
        self._value = value
        self._placeholder = placeholder
        self._invalid = bool(invalid)
        self._readonly = bool(readonly)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self._hover = self.animated(DURATION["hover"])

        self._list = MenuList()
        self._panel = MenuPanel(self._list)
        self._popover = Popover(self, self._panel, side="bottom", align="start", match_anchor_width=True)
        self._popover.set_key_handler(self._list.handle_key)
        self._popover.opened.connect(self.opened.emit)
        self._popover.closed.connect(self._on_closed)
        self._list.activated.connect(self._on_activated)
        self._rebuild()

    # --- props --------------------------------------------------------------------------

    @property
    def items(self) -> list[tuple[Any, str]]:
        """Every `(value, label)` pair, the headings left out."""
        return [pair for _heading, pairs in self._groups for pair in pairs]

    def set_items(self, items: list[tuple[Any, str]]) -> None:
        """Replace the list with one ungrouped run of rows."""
        self._groups = [(None, list(items))]
        self._rebuild()

    def set_groups(self, groups: list[tuple[str, list[tuple[Any, str]]]]) -> None:
        """Replace the list with runs of rows under headings."""
        self._groups = [(heading, list(pairs)) for heading, pairs in groups]
        self._rebuild()

    @property
    def value(self) -> Any:
        """The chosen value, or `None`."""
        return self._value

    def set_value(self, value: Any) -> None:
        """Choose a value without emitting `value_changed`."""
        if value == self._value:
            return
        self._value = value
        self._rebuild()
        self.update()

    @property
    def placeholder(self) -> str:
        """What the control reads while nothing is chosen."""
        return self._placeholder

    def set_placeholder(self, text: str) -> None:
        """Change the empty reading."""
        self._placeholder = text
        self.update()

    @property
    def invalid(self) -> bool:
        """True while the value fails the caller's rule."""
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        """Put the border and the ring in `destructive`."""
        self._invalid = bool(value)
        self.update()

    @property
    def readonly(self) -> bool:
        """True while the control keeps its contrast and drops its affordances."""
        return self._readonly

    def set_readonly(self, value: bool) -> None:
        """Keep the value readable and take the chevron and the list away."""
        self._readonly = bool(value)
        if self._readonly and self._popover.is_open:
            self._popover.close()
        self.setCursor(
            Qt.CursorShape.ArrowCursor if self._readonly else Qt.CursorShape.PointingHandCursor
        )
        self.update()

    @property
    def label(self) -> str:
        """The label of the chosen value, or the placeholder."""
        for value, text in self.items:
            if value == self._value:
                return text
        return self._placeholder

    @property
    def is_open(self) -> bool:
        """True while the list is up."""
        return self._popover.is_open

    @property
    def popover(self) -> Popover:
        """The window the list is drawn on."""
        return self._popover

    @property
    def list(self) -> MenuList:
        """The rows."""
        return self._list

    # --- the list -----------------------------------------------------------------------

    def _rebuild(self) -> None:
        entries: list[MenuEntry] = []
        for heading, pairs in self._groups:
            if heading:
                if entries:
                    entries.append(MenuEntry(kind="separator"))
                entries.append(MenuEntry(kind="label", text=heading))
            for value, text in pairs:
                entries.append(
                    MenuEntry(kind="item", text=text, value=value, checked=value == self._value)
                )
        self._list.set_entries(entries)

    def open(self) -> None:
        """Show the list with the highlight on the chosen row."""
        if self._readonly or not self.isEnabled():
            return
        self._popover.open()
        for index, entry in enumerate(self._list.entries):
            if entry.selectable and entry.value == self._value:
                self._list.set_highlight(index)
                return
        self._list.first()

    def close(self) -> None:
        """Hide the list."""
        self._popover.close()

    def toggle(self) -> None:
        """Open a closed list, close an open one."""
        if self._popover.is_open:
            self.close()
        else:
            self.open()

    def _on_activated(self, index: int) -> None:
        entry = self._list.entries[index]
        self.close()
        if entry.value != self._value:
            self._value = entry.value
            self._rebuild()
            self.update()
            self.value_changed.emit(entry.value)

    def _on_closed(self) -> None:
        self._list.set_highlight(-1)
        self.closed.emit()
        self.update()

    # --- the keyboard and the mouse -----------------------------------------------------

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._readonly or not self.isEnabled():
            super().keyPressEvent(event)
            return
        if self._popover.is_open:
            if self._popover.handle_key(event):
                event.accept()
                return
            super().keyPressEvent(event)
            return
        if event.key() in (
            Qt.Key.Key_Down,
            Qt.Key.Key_Up,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.open()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._readonly or not self.isEnabled():
            return
        self.set_pressed(True)
        self.toggle()
        event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        self.set_pressed(False)
        event.accept()

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    # --- geometry and painting ----------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self.theme.font(14))
        widest = metrics.horizontalAdvance(self._placeholder)
        for _value, text in self.items:
            widest = max(widest, metrics.horizontalAdvance(text))
        pad = CONTROL_PAD[self.size_step]
        glyph = CONTROL_GLYPH[self.size_step]
        return QSize(
            pad + widest + SELECT_GAP + glyph + SELECT_TRAILING_PAD,
            CONTROL_HEIGHT[self.size_step],
        )

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(CONTROL_HEIGHT[self.size_step] * 2, CONTROL_HEIGHT[self.size_step])

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setOpacity(self.disabled_opacity())

        radius = float(theme.radius_px("lg"))
        # The chrome fills the whole box, as a button's and an input's do, and the focus ring
        # is drawn inward over it: the trigger stands at the control height of its step, `h-8`
        # at md, level with the controls beside it.
        box = QRect(0, 0, self.width(), self.height())
        border = theme.color("destructive") if self._invalid else theme.color("input")
        # `bg-transparent dark:bg-input/30 dark:hover:bg-input/50`: a wash laid on the surface
        # the trigger stands on, never a ground of its own, so a select inside a card or a
        # popover shows that surface through it and a dark page lifts it.
        if theme.dark:
            share = REST_WASH_DARK + (HOVER_WASH_DARK - REST_WASH_DARK) * self._hover.value
            fill = with_alpha(theme.color("input"), share)
        else:
            fill = with_alpha(theme.color("muted"), HOVER_WASH * self._hover.value)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(QtCore.QRectF(box), radius, radius)
        pen = QtGui.QPen(border, 1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        painter.drawRoundedRect(
            QtCore.QRectF(box).adjusted(0.5, 0.5, -0.5, -0.5), radius - 0.5, radius - 0.5
        )
        if self._invalid:
            # `aria-invalid:ring-3 ring-destructive/20`, drawn inside the border as the input does.
            painter.setPen(QtGui.QPen(with_alpha(theme.color("destructive"), 0.2), 2.0))
            painter.drawRoundedRect(QtCore.QRectF(box).adjusted(2, 2, -2, -2), radius - 2, radius - 2)
        if self.keyboard_focus and not self._invalid:
            self.paint_focus_ring(painter, box, radius)

        pad = CONTROL_PAD[self.size_step]
        glyph = CONTROL_GLYPH[self.size_step]
        right = box.right() + 1 - SELECT_TRAILING_PAD
        if not self._readonly:
            spot = QRect(right - glyph, box.center().y() - glyph // 2 + 1, glyph, glyph)
            paint_icon(painter, spot, "chevrons-up-down", theme.color("muted_foreground"))
            right -= glyph + SELECT_GAP

        chosen = any(value == self._value for value, _text in self.items)
        painter.setFont(theme.font(14))
        painter.setPen(
            theme.color("foreground") if chosen else theme.color("muted_foreground")
        )
        text_rect = QRect(box.left() + pad, box.top(), max(0, right - box.left() - pad), box.height())
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(painter, self.label, text_rect.width()),
        )
        painter.end()
