"""The menu a button drops, and the painted row list every popup list in this package draws.

A menu hangs off an anchor on a `Popover`, so it never takes the anchor's focus and never uses
`Qt.Popup`. The anchor forwards its keys to `DropdownMenu.handle_key`, which is how the caret
stays where the user put it while the list walks under the arrows.

    menu = DropdownMenu(button)
    menu.add_item("Duplicate", icon="copy", on_activate=duplicate)
    menu.add_separator()
    menu.add_item("Delete", icon="trash", destructive=True, on_activate=delete)
    button.clicked.connect(menu.toggle)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal

from ..icons import paint_icon
from ..theme import with_alpha
from .base import ThemedWidget, elide
from .popover import Popover
from .scrollbar import install_overlay_scrollbars

__all__ = [
    "MENU_LIST_PAD",
    "MENU_MAX_HEIGHT",
    "MENU_MIN_WIDTH",
    "MENU_ROW_HEIGHT",
    "DropdownMenu",
    "MenuEntry",
    "MenuList",
    "MenuPanel",
]

#: A row stands 32 high, the `md` rung of the control ladder. `px-2 py-1.5` is its inset.
MENU_ROW_HEIGHT = 32
MENU_ROW_PAD = 8

#: `p-1` around the rows, inside the surface.
MENU_LIST_PAD = 4

#: `max-h-72` of the popup list, and `min-w-32` of a menu.
MENU_MAX_HEIGHT = 288
MENU_MIN_WIDTH = 128

#: A heading row and the rule between two groups: `px-1.5 py-1 text-xs` and `my-1 h-px`.
MENU_LABEL_HEIGHT = 24
MENU_SEPARATOR_HEIGHT = 9

#: Between a glyph and its label, and before the trailing indicator.
GLYPH_GAP = 6
TRAILING_GAP = 8
GLYPH_SIZE = 16

#: Typeahead forgets what was typed after this pause.
TYPEAHEAD_MS = 1000


@dataclass
class MenuEntry:
    """One row of a menu or a select list."""

    kind: str = "item"
    text: str = ""
    icon: str | None = None
    shortcut: str | None = None
    on_activate: Callable[[], None] | None = None
    destructive: bool = False
    disabled: bool = False
    checked: bool | None = None
    submenu: bool = False
    value: Any = None
    group: int | None = None
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def selectable(self) -> bool:
        """True on a row the keyboard may land on."""
        return self.kind == "item" and not self.disabled

    def height(self) -> int:
        """The room the row takes."""
        if self.kind == "separator":
            return MENU_SEPARATOR_HEIGHT
        if self.kind == "label":
            return MENU_LABEL_HEIGHT
        return MENU_ROW_HEIGHT


class MenuList(ThemedWidget):
    """The painted rows of a popup list: the highlight, the glyphs, the keyboard and typeahead.

    The highlight and the selection share one colour, `accent` behind `accent_foreground`, which
    is rule 5 of `docs/design-rules.md`. Nothing here is a `QListWidget`: every row is drawn.
    """

    activated = Signal(int)
    highlight_changed = Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[MenuEntry] = []
        self._highlight = -1
        self._typed = ""
        self._typed_at = QtCore.QElapsedTimer()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

    # --- rows ---------------------------------------------------------------------------

    @property
    def entries(self) -> list[MenuEntry]:
        """The rows, in the order they are drawn."""
        return self._entries

    def set_entries(self, entries: list[MenuEntry]) -> None:
        """Replace every row and drop the highlight."""
        self._entries = list(entries)
        self._highlight = -1
        self.updateGeometry()
        self.update()

    def add(self, entry: MenuEntry) -> MenuEntry:
        """Append one row."""
        self._entries.append(entry)
        self.updateGeometry()
        self.update()
        return entry

    def clear(self) -> None:
        """Drop every row."""
        self.set_entries([])

    # --- the highlight ------------------------------------------------------------------

    @property
    def highlight(self) -> int:
        """The row the keyboard is on, or -1."""
        return self._highlight

    def set_highlight(self, index: int) -> None:
        """Put the keyboard cursor on a row and keep it in view."""
        if index != -1 and not (0 <= index < len(self._entries)):
            return
        if index != -1 and not self._entries[index].selectable:
            return
        if index == self._highlight:
            return
        self._highlight = index
        self._scroll_into_view(index)
        self.highlight_changed.emit(index)
        self.update()

    def step(self, delta: int) -> None:
        """Move the highlight to the next selectable row in that direction, wrapping."""
        rows = [i for i, entry in enumerate(self._entries) if entry.selectable]
        if not rows:
            return
        if self._highlight not in rows:
            self.set_highlight(rows[0] if delta > 0 else rows[-1])
            return
        at = rows.index(self._highlight)
        self.set_highlight(rows[(at + delta) % len(rows)])

    def first(self) -> None:
        """Put the highlight on the first selectable row."""
        for index, entry in enumerate(self._entries):
            if entry.selectable:
                self.set_highlight(index)
                return

    def last(self) -> None:
        """Put the highlight on the last selectable row."""
        for index in range(len(self._entries) - 1, -1, -1):
            if self._entries[index].selectable:
                self.set_highlight(index)
                return

    def activate(self, index: int | None = None) -> bool:
        """Fire the row under the highlight, or the one asked for."""
        at = self._highlight if index is None else index
        if not (0 <= at < len(self._entries)):
            return False
        entry = self._entries[at]
        if not entry.selectable:
            return False
        if entry.on_activate is not None:
            entry.on_activate()
        self.activated.emit(at)
        return True

    # --- geometry -----------------------------------------------------------------------

    def row_rect(self, index: int) -> QRect:
        """Where a row is drawn, in this widget's coordinates."""
        top = MENU_LIST_PAD
        for at, entry in enumerate(self._entries):
            if at == index:
                return QRect(MENU_LIST_PAD, top, max(0, self.width() - 2 * MENU_LIST_PAD), entry.height())
            top += entry.height()
        return QRect()

    def row_at(self, point: QPoint) -> int:
        """The row under a point, or -1."""
        top = MENU_LIST_PAD
        for index, entry in enumerate(self._entries):
            if top <= point.y() < top + entry.height():
                return index
            top += entry.height()
        return -1

    def sizeHint(self) -> QSize:  # noqa: N802
        height = 2 * MENU_LIST_PAD + sum(entry.height() for entry in self._entries)
        return QSize(max(MENU_MIN_WIDTH, self._natural_width()), height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(MENU_MIN_WIDTH, self.sizeHint().height())

    def _natural_width(self) -> int:
        theme = self.theme
        metrics = QtGui.QFontMetrics(theme.font(14))
        small = QtGui.QFontMetrics(theme.font(12))
        widest = 0
        for entry in self._entries:
            if entry.kind == "separator":
                continue
            width = 2 * MENU_ROW_PAD
            if entry.kind == "label":
                widest = max(widest, width + small.horizontalAdvance(entry.text))
                continue
            width += metrics.horizontalAdvance(entry.text)
            if entry.icon is not None:
                width += GLYPH_SIZE + GLYPH_GAP
            if entry.shortcut:
                width += TRAILING_GAP + small.horizontalAdvance(entry.shortcut)
            if entry.checked is not None or entry.submenu:
                width += TRAILING_GAP + GLYPH_SIZE
            widest = max(widest, width)
        return widest + 2 * MENU_LIST_PAD

    def _scroll_into_view(self, index: int) -> None:
        area = self._scroll_area()
        if area is None or index < 0:
            return
        rect = self.row_rect(index)
        bar = area.verticalScrollBar()
        value = bar.value()
        top, bottom = rect.top() - MENU_LIST_PAD, rect.bottom() + MENU_LIST_PAD
        height = area.viewport().height()
        if top < value:
            bar.setValue(top)
        elif bottom > value + height:
            bar.setValue(bottom - height)

    def _scroll_area(self) -> QtWidgets.QAbstractScrollArea | None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QtWidgets.QAbstractScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    # --- the keyboard -------------------------------------------------------------------

    def handle_key(self, event: QtGui.QKeyEvent) -> bool:
        """Take a key the anchor forwarded. True when the list used it."""
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self.step(1 if key == Qt.Key.Key_Down else -1)
            return True
        if key == Qt.Key.Key_Home:
            self.first()
            return True
        if key == Qt.Key.Key_End:
            self.last()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self.activate()
        text = event.text()
        if text and text.isprintable() and not text.isspace():
            return self._typeahead(text)
        return False

    def _typeahead(self, text: str) -> bool:
        if self._typed_at.isValid() and self._typed_at.elapsed() > TYPEAHEAD_MS:
            self._typed = ""
        self._typed += text.lower()
        self._typed_at.restart()
        order = list(range(self._highlight + 1, len(self._entries))) + list(
            range(0, max(0, self._highlight + 1))
        )
        for index in order:
            entry = self._entries[index]
            if entry.selectable and entry.text.lower().startswith(self._typed):
                self.set_highlight(index)
                return True
        return False

    # --- the mouse ----------------------------------------------------------------------

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        index = self.row_at(_local_pos(event))
        if index >= 0 and self._entries[index].selectable:
            self.set_highlight(index)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        index = self.row_at(_local_pos(event))
        if index >= 0:
            self.activate(index)

    # --- painting -----------------------------------------------------------------------

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        theme = self.theme
        for index, entry in enumerate(self._entries):
            rect = self.row_rect(index)
            if entry.kind == "separator":
                line = QRect(rect.left(), rect.center().y(), rect.width(), 1)
                painter.fillRect(line, theme.color("border"))
                continue
            if entry.kind == "label":
                painter.setFont(theme.font(12))
                painter.setPen(theme.color("muted_foreground"))
                painter.drawText(
                    rect.adjusted(MENU_ROW_PAD, 0, -MENU_ROW_PAD, 0),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    elide(painter, entry.text, rect.width() - 2 * MENU_ROW_PAD),
                )
                continue
            self._paint_item(painter, rect, entry, index == self._highlight)
        painter.end()

    def _paint_item(
        self, painter: QtGui.QPainter, rect: QRect, entry: MenuEntry, highlighted: bool
    ) -> None:
        theme = self.theme
        radius = float(theme.radius_px("md"))
        ink = theme.color("popover_foreground")
        if entry.destructive:
            ink = theme.color("destructive")
        if highlighted:
            if entry.destructive:
                painter.setBrush(with_alpha(theme.color("destructive"), 0.10))
            else:
                painter.setBrush(theme.color("accent"))
                ink = theme.color("accent_foreground")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QtCore.QRectF(rect), radius, radius)
        painter.setOpacity(0.5 if entry.disabled else 1.0)

        left = rect.left() + MENU_ROW_PAD
        right = rect.right() + 1 - MENU_ROW_PAD
        if entry.checked is not None or entry.submenu:
            box = QRect(right - GLYPH_SIZE, rect.center().y() - GLYPH_SIZE // 2 + 1, GLYPH_SIZE, GLYPH_SIZE)
            if entry.submenu:
                paint_icon(painter, box, "chevron-right", ink)
            elif entry.checked:
                paint_icon(painter, box, "check", ink)
            right -= GLYPH_SIZE + TRAILING_GAP
        if entry.shortcut:
            painter.setFont(theme.font(12))
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(entry.shortcut)
            painter.setPen(
                theme.color("accent_foreground") if highlighted else theme.color("muted_foreground")
            )
            painter.drawText(
                QRect(right - width, rect.top(), width, rect.height()),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                entry.shortcut,
            )
            right -= width + TRAILING_GAP
        if entry.icon is not None:
            box = QRect(left, rect.center().y() - GLYPH_SIZE // 2 + 1, GLYPH_SIZE, GLYPH_SIZE)
            paint_icon(painter, box, entry.icon, ink)
            left += GLYPH_SIZE + GLYPH_GAP
        painter.setFont(theme.font(14))
        painter.setPen(ink)
        painter.drawText(
            QRect(left, rect.top(), max(0, right - left), rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(painter, entry.text, right - left),
        )
        painter.setOpacity(1.0)


def _local_pos(event: QtGui.QMouseEvent) -> QPoint:
    getter = getattr(event, "position", None)
    return getter().toPoint() if getter is not None else event.pos()


class MenuPanel(QtWidgets.QScrollArea):
    """A `MenuList` that scrolls once it passes `max_height`, on the thin overlay bars."""

    def __init__(
        self,
        list_widget: MenuList,
        max_height: int = MENU_MAX_HEIGHT,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._list = list_widget
        self._max_height = int(max_height)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setWidget(list_widget)
        self.viewport().setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        install_overlay_scrollbars(self)

    @property
    def list(self) -> MenuList:
        """The rows inside."""
        return self._list

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = self._list.sizeHint()
        return QSize(hint.width(), min(self._max_height, hint.height()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(MENU_MIN_WIDTH, min(self._max_height, self._list.sizeHint().height()))


class DropdownMenu(QtCore.QObject):
    """A menu hanging off an anchor, walked with the arrows and closed with Escape.

    It is drawn on a `Popover`, so the anchor keeps its focus; the anchor's keys reach the rows
    through the event filter this installs, and a press or Down on the anchor opens it.
    """

    activated = Signal(int)
    opened = Signal()
    closed = Signal()

    def __init__(self, anchor: QtWidgets.QWidget, side: str = "bottom", align: str = "start") -> None:
        super().__init__(anchor)
        self._anchor = anchor
        self._list = MenuList()
        self._panel = MenuPanel(self._list)
        self._popover = Popover(anchor, self._panel, side=side, align=align)
        self._popover.set_key_handler(self._on_key)
        self._popover.opened.connect(self.opened.emit)
        self._popover.closed.connect(self._on_closed)
        self._list.activated.connect(self._on_activated)
        self._list.highlight_changed.connect(self._on_highlight)
        self._submenus: dict[int, DropdownMenu] = {}
        self._radio_state: dict[int, Any] = {}
        self._radio_change: dict[int, Callable[[Any], None] | None] = {}
        anchor.installEventFilter(self)

    # --- rows ---------------------------------------------------------------------------

    def add_item(
        self,
        text: str,
        icon: str | None = None,
        shortcut: str | None = None,
        on_activate: Callable[[], None] | None = None,
        destructive: bool = False,
        disabled: bool = False,
    ) -> MenuEntry:
        """A row that runs `on_activate` and closes the menu."""
        return self._list.add(
            MenuEntry(
                kind="item",
                text=text,
                icon=icon,
                shortcut=shortcut,
                on_activate=on_activate,
                destructive=destructive,
                disabled=disabled,
            )
        )

    def add_checkbox_item(
        self,
        text: str,
        checked: bool = False,
        on_toggle: Callable[[bool], None] | None = None,
        disabled: bool = False,
    ) -> MenuEntry:
        """A row carrying a tick, which toggles and stays open."""
        entry = MenuEntry(kind="item", text=text, checked=bool(checked), disabled=disabled)

        def toggle() -> None:
            entry.checked = not entry.checked
            self._list.update()
            if on_toggle is not None:
                on_toggle(bool(entry.checked))

        entry.on_activate = toggle
        return self._list.add(entry)

    def add_radio_group(
        self,
        items: list[tuple[Any, str]],
        value: Any = None,
        on_change: Callable[[Any], None] | None = None,
    ) -> list[MenuEntry]:
        """One tick across a set of rows."""
        group = len(self._radio_state)
        self._radio_state[group] = value
        self._radio_change[group] = on_change
        made: list[MenuEntry] = []
        for item_value, label in items:
            entry = MenuEntry(
                kind="item", text=label, checked=item_value == value, value=item_value, group=group
            )
            entry.on_activate = self._radio_setter(group, item_value)
            made.append(self._list.add(entry))
        return made

    def _radio_setter(self, group: int, value: Any) -> Callable[[], None]:
        def choose() -> None:
            self._radio_state[group] = value
            for entry in self._list.entries:
                if entry.group == group:
                    entry.checked = entry.value == value
            self._list.update()
            handler = self._radio_change.get(group)
            if handler is not None:
                handler(value)

        return choose

    def add_separator(self) -> MenuEntry:
        """A rule between two groups of rows."""
        return self._list.add(MenuEntry(kind="separator"))

    def add_label(self, text: str) -> MenuEntry:
        """A heading naming the rows under it."""
        return self._list.add(MenuEntry(kind="label", text=text))

    def add_submenu(self, text: str) -> DropdownMenu:
        """A row that opens a menu of its own beside it."""
        entry = MenuEntry(kind="item", text=text, submenu=True)
        index = len(self._list.entries)
        self._list.add(entry)
        submenu = DropdownMenu(self._list, side="right", align="start")
        submenu.popover.set_anchor_rect_provider(self._row_rect_provider(index))
        submenu.popover.set_side("right")
        self._popover.add_pass_through(submenu.popover)
        self._submenus[index] = submenu
        entry.on_activate = submenu.open
        return submenu

    def _row_rect_provider(self, index: int) -> Callable[[], QRect]:
        def provider() -> QRect:
            rect = self._list.row_rect(index)
            return QRect(self._list.mapToGlobal(rect.topLeft()), rect.size())

        return provider

    def clear(self) -> None:
        """Drop every row."""
        self._list.clear()
        self._submenus.clear()

    # --- opening and closing ------------------------------------------------------------

    @property
    def popover(self) -> Popover:
        """The window the rows are drawn on."""
        return self._popover

    @property
    def list(self) -> MenuList:
        """The rows."""
        return self._list

    @property
    def is_open(self) -> bool:
        """True while the menu is up."""
        return self._popover.is_open

    def open(self, from_keyboard: bool = False) -> None:
        """Show the menu. Opened from the keyboard, the highlight starts on the first row."""
        self._popover.open()
        if from_keyboard:
            self._list.first()

    def close(self) -> None:
        """Hide the menu."""
        self._popover.close()

    def toggle(self) -> None:
        """Open a closed menu, close an open one."""
        if self.is_open:
            self.close()
        else:
            self.open()

    def handle_key(self, event: QtGui.QKeyEvent) -> bool:
        """Take a key the anchor forwarded."""
        if not self.is_open:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.open(from_keyboard=True)
                return True
            return False
        return self._popover.handle_key(event)

    def _on_key(self, event: QtGui.QKeyEvent) -> bool:
        for submenu in self._submenus.values():
            if submenu.is_open and submenu.handle_key(event):
                return True
        return self._list.handle_key(event)

    def _on_activated(self, index: int) -> None:
        entry = self._list.entries[index]
        self.activated.emit(index)
        if entry.checked is None and not entry.submenu:
            self.close()

    def _on_highlight(self, index: int) -> None:
        for at, submenu in self._submenus.items():
            if at != index and submenu.is_open:
                submenu.close()

    def _on_closed(self) -> None:
        for submenu in self._submenus.values():
            submenu.close()
        self._list.set_highlight(-1)
        self.closed.emit()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self._anchor and event.type() == QEvent.Type.KeyPress:
            if self.handle_key(event):
                return True
        return False
