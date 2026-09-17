"""The control box and popup shell every picker in this package is built on.

Ported from `packages/react/src/registry/sg/components/picker-control.tsx` and its Svelte twin,
on the ladders of `picker-classes.ts`. One module holds the box and its states, the press rule (a
press anywhere on the control toggles the list, the caret included), the dismissal guard, where
the caret lands on open, the keyboard model of core's `picker_key_intent`, the inline token field
against the summary trigger with its measured chip row, and the popup shell: the search row, the
list, the empty, loading and error block, and the load-more row.

A picker supplies four things and nothing else: its query, its rows as a model, the delegate that
draws a row, and a factory that builds one chip.

    control = PickerControl(slot="entity-picker", picker="entity", multiple=True)
    control.set_row_model(model)
    control.set_chip_factory(chip_for)
    control.query_changed.connect(search)
    control.selected.connect(choose)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.list_chrome import ListStatusState, list_status
from sg_widgets_core.picker import ChipRow, summarise_selection
from sg_widgets_core.picker_keys import PickerKeyState, picker_key_intent
from sg_widgets_core.state import NO_MATCH_LABEL, StateLabels, state_line

from ..icons import paint_icon
from ..primitives.base import (
    CHIP_HEIGHT,
    CONTROL_HEIGHT,
    DURATION,
    FOCUS_RING_WIDTH,
    ICON_HIT_BOX,
    ThemedWidget,
    elide,
    fill_round_rect,
    painter_for,
    text_width,
)
from ..primitives.list_view import LIST_PAD, ListSurface
from ..primitives.popover import MIN_WIDTH as POPUP_MIN_WIDTH
from ..primitives.popover import Popover
from ..primitives.row_delegate import RowDelegate
from ..primitives.skeleton import Skeleton
from ..theme import mix, with_alpha
from .state_line import StateLine

__all__ = [
    "BORDER",
    "CHIP_GAP",
    "OVERFLOW_RESERVE",
    "PICKER_BOX",
    "PICKER_CHIP",
    "PICKER_GLYPH",
    "PICKER_SIZE_VALUES",
    "PICKER_TEXT_BOX",
    "POPUP_WIDTH",
    "SEARCH_ROW_HEIGHT",
    "SKELETON_ROWS",
    "PickerControl",
]

PICKER_SIZE_VALUES: tuple[str, ...] = ("sm", "md", "lg")

#: `PICKER_BOX` in pixels: the trailing, leading and vertical inset a filled control takes. The
#: leading inset matches the room above and below the chip, so the chip sits evenly in the border.
PICKER_BOX: dict[str, tuple[int, int, int]] = {
    "sm": (8, 3, 3),
    "md": (12, 3, 3),
    "lg": (12, 1, 1),
}

#: `data-empty`: an empty control gives that inset back and reads as a plain input.
PICKER_BOX_EMPTY: dict[str, tuple[int, int]] = {"sm": (6, 0), "md": (8, 0), "lg": (8, 0)}

#: `PICKER_TEXT_BOX`: a control whose filled value is plain text keeps the reading inset.
PICKER_TEXT_BOX: dict[str, tuple[int, int]] = {"sm": (8, 8), "md": (12, 12), "lg": (12, 12)}
PICKER_TEXT_BOX_EMPTY: dict[str, int] = {"sm": 6, "md": 8, "lg": 8}

#: The trailing inset held as reserve for the clear control and the chevron.
TRAILING_READONLY = 12
TRAILING_OPEN = 32
TRAILING_CLEAR = 56

#: A chip or a badge sits inside the control, so it takes the step below it.
PICKER_CHIP: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: The glyphs inside a control.
PICKER_GLYPH: dict[str, int] = {"sm": 16, "md": 16, "lg": 20}

#: The control's own border, which the vertical inset is measured from the inside of.
BORDER = 1

#: The chip row's gap, carried by every measured width.
CHIP_GAP = 6

#: Room the `+n` pill needs beside the chips, so it is never the thing that overflows.
OVERFLOW_RESERVE = 40

#: `w-96`: the popup a control does not lend its width to.
POPUP_WIDTH = 384

#: The search row a summary trigger keeps in its popup: `h-8` under a 1px border, inset `px-3`.
SEARCH_ROW_HEIGHT = 32
SEARCH_ROW_PAD = 12

#: The `+n` pill and the load-more row, on the metadata step.
PILL_TEXT = 12

#: Skeletons a read stands behind, shaped like the rows they replace.
SKELETON_ROWS = 3
SKELETON_HEIGHT = 20
SKELETON_PAD_X = 8
SKELETON_PAD_Y = 6

#: The narrowest the caret gets before the chips have to give room back.
CARET_MIN_WIDTH = 32
TOKEN_CARET_MIN_WIDTH = 16

#: The body step of rule 6.
TEXT_SIZE = 14

#: `disabled:opacity-50`, on the ink Qt draws itself, which no painter opacity reaches.
DISABLED_INK = 0.5

#: The row a press on the last row of a page carries, rather than an item key.
LOAD_MORE = "__load-more"

_LOAD_MORE_LABEL = "Load more"


def over(base: QtGui.QColor, top: QtGui.QColor) -> QtGui.QColor:
    """`top` composited over an opaque `base`, which is what a CSS background does.

    A token may be a translucent overlay of its own — `muted` is `#00000008` in several
    palettes — so `hover:bg-muted/30` is that alpha taken down to 30% of itself and laid over
    the surface, never a blend towards the token's raw colour, which would read as a grey.
    """
    share = top.alphaF()
    return QtGui.QColor(
        round(base.red() + (top.red() - base.red()) * share),
        round(base.green() + (top.green() - base.green()) * share),
        round(base.blue() + (top.blue() - base.blue()) * share),
        base.alpha(),
    )


def _retire(popover: Popover) -> None:
    """Close a popover and let Qt delete it, ignoring one that has already gone."""
    try:
        popover.close()
        popover.deleteLater()
    except RuntimeError:
        pass


def _key_name(event: QtGui.QKeyEvent) -> str:
    """A key event as the name core's keyboard model is written against."""
    key = event.key()
    named = {
        Qt.Key.Key_Escape: "Escape",
        Qt.Key.Key_Left: "ArrowLeft",
        Qt.Key.Key_Right: "ArrowRight",
        Qt.Key.Key_Up: "ArrowUp",
        Qt.Key.Key_Down: "ArrowDown",
        Qt.Key.Key_Backspace: "Backspace",
        Qt.Key.Key_Delete: "Delete",
        Qt.Key.Key_Return: "Enter",
        Qt.Key.Key_Enter: "Enter",
        Qt.Key.Key_Tab: "Tab",
        Qt.Key.Key_Space: " ",
    }
    if key in named:
        return named[key]
    text = event.text()
    return text if len(text) == 1 and text.isprintable() else ""


class _Caret(QtWidgets.QLineEdit):
    """The control's own input, with no box of its own: it borrows the control's."""

    def __init__(
        self,
        on_key: Callable[[QtGui.QKeyEvent], bool],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_key = on_key
        self._keyboard_focus = False
        self._theme: Any = None
        self.setFrame(False)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)
        self.setTextMargins(0, 0, 0, 0)

    @property
    def keyboard_focus(self) -> bool:
        """True while the focus arrived from the keyboard, which is when the ring is painted."""
        return self._keyboard_focus

    def apply_theme(self, theme: Any) -> None:
        """Wear the tokens Qt's own text drawing reads.

        A painter's opacity never reaches the text Qt draws itself, so the inert step of rule 5
        is applied to the ink here.
        """
        self._theme = theme
        step = 1.0 if self.isEnabled() else DISABLED_INK
        palette = self.palette()
        role = QtGui.QPalette.ColorRole
        palette.setColor(role.Base, QtGui.QColor(Qt.GlobalColor.transparent))
        palette.setColor(role.Window, QtGui.QColor(Qt.GlobalColor.transparent))
        palette.setColor(role.Text, with_alpha(theme.foreground, step))
        palette.setColor(role.WindowText, with_alpha(theme.foreground, step))
        palette.setColor(role.Highlight, theme.color("accent"))
        palette.setColor(role.HighlightedText, theme.color("accent_foreground"))
        placeholder = getattr(role, "PlaceholderText", None)
        if placeholder is not None:
            palette.setColor(placeholder, with_alpha(theme.muted_foreground, step))
        self.setPalette(palette)
        self.setFont(theme.font(TEXT_SIZE))

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.EnabledChange and self._theme is not None:
            self.apply_theme(self._theme)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusInEvent(event)
        self._keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self._keyboard_focus = False

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._on_key(event):
            event.accept()
            return
        super().keyPressEvent(event)


class _IconButton(ThemedWidget):
    """The clear control and the chevron: a glyph at its own size in a 24px hit box."""

    pressed_signal = Signal()

    def __init__(
        self,
        glyph: str,
        label: str = "",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._glyph = glyph
        self.set_size_step(size if size in PICKER_GLYPH else "md")
        self._hover = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAccessibleName(label)
        self.setToolTip(label)

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in PICKER_GLYPH else "md")
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        side = max(ICON_HIT_BOX, PICKER_GLYPH[self.size_step])
        return QtCore.QSize(side, side)

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        box = self.rect()
        if self.pressed and not theme.reduced_motion:
            centre = QtCore.QPointF(box.center())
            painter.translate(centre)
            painter.scale(0.98, 0.98)
            painter.translate(-centre)
        amount = self._hover.value
        ink = mix(theme.foreground, theme.accent_foreground, amount)
        if amount > 0:
            fill_round_rect(
                painter,
                box,
                float(theme.radius_px("sm")),
                with_alpha(theme.accent, amount),
            )
        glyph = PICKER_GLYPH[self.size_step]
        slot = QtCore.QRect(0, 0, glyph, glyph)
        slot.moveCenter(box.center())
        paint_icon(painter, slot, self._glyph, with_alpha(ink, 0.7 + 0.3 * amount))
        if self.keyboard_focus:
            self.paint_focus_ring(painter, box, float(theme.radius_px("sm")))
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self.pressed and event.button() == Qt.MouseButton.LeftButton:
            self.set_pressed(False)
            if self.rect().contains(event.pos()):
                self.pressed_signal.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.pressed_signal.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _OverflowPill(ThemedWidget):
    """The `+n` pill. A press on it opens the list, where the hidden ones are."""

    pressed_signal = Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = 0
        self._hover = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

    @property
    def count(self) -> int:
        return self._count

    def set_count(self, value: int) -> None:
        self._count = max(0, int(value))
        self.updateGeometry()
        self.update()

    def _label(self) -> str:
        return f"+{self._count}"

    def _font(self) -> QtGui.QFont:
        return self.theme.font(PILL_TEXT, tabular=True)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self._font())
        return QtCore.QSize(text_width(metrics, self._label()) + 4, metrics.height())

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        painter.setFont(self._font())
        painter.setPen(mix(theme.muted_foreground, theme.foreground, self._hover.value))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter),
            self._label(),
        )
        painter.end()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.pressed_signal.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _ArmedRing(ThemedWidget):
    """The inset ring the chip holding the caret wears, drawn over the chip so its fill cannot
    cover it, and inset so the control's edge cannot cut it."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        inset = FOCUS_RING_WIDTH / 2.0
        radius = max(0.0, float(theme.radius_px("md")) - inset)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(theme.color("ring"), FOCUS_RING_WIDTH))
        painter.drawRoundedRect(
            QtCore.QRectF(self.rect()).adjusted(inset, inset, -inset, -inset), radius, radius
        )
        painter.end()


class _SearchRow(ThemedWidget):
    """The search box a summary trigger keeps at the top of its popup, under a 1px border."""

    def __init__(self, caret: _Caret, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._caret = caret
        caret.setParent(self)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setFixedHeight(SEARCH_ROW_HEIGHT + 1)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(POPUP_MIN_WIDTH, SEARCH_ROW_HEIGHT + 1)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        glyph = PICKER_GLYPH["md"]
        left = SEARCH_ROW_PAD + glyph + CHIP_GAP
        self._caret.setGeometry(
            left, 0, max(0, self.width() - left - SEARCH_ROW_PAD), SEARCH_ROW_HEIGHT
        )

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        glyph = PICKER_GLYPH["md"]
        slot = QtCore.QRect(SEARCH_ROW_PAD, (SEARCH_ROW_HEIGHT - glyph) // 2, glyph, glyph)
        paint_icon(painter, slot, "search", with_alpha(theme.foreground, 0.5))
        painter.fillRect(
            QtCore.QRect(0, SEARCH_ROW_HEIGHT, self.width(), 1), theme.color("border")
        )
        painter.end()


class _Skeletons(QtWidgets.QWidget):
    """The three rows a read stands behind, at the inset and the height of a row."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(LIST_PAD, LIST_PAD, LIST_PAD, LIST_PAD)
        column.setSpacing(0)
        for _ in range(SKELETON_ROWS):
            row = QtWidgets.QWidget(self)
            inner = QtWidgets.QHBoxLayout(row)
            inner.setContentsMargins(
                SKELETON_PAD_X, SKELETON_PAD_Y, SKELETON_PAD_X, SKELETON_PAD_Y
            )
            inner.setSpacing(0)
            inner.addWidget(Skeleton(height=SKELETON_HEIGHT, parent=row))
            column.addWidget(row)


class _Popup(QtWidgets.QWidget):
    """What the popover holds: the search row, the list, and the block that replaces it."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(0)

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        self._column.addWidget(widget)


class PickerControl(ThemedWidget):
    """The control and the popup every picker in this package wears.

    A picker hands it four things: `query_changed` to answer, a row model, the delegate that
    draws a row, and a factory that builds one chip. Everything else here is fixed: the box and
    its states, the press rule, the dismissal guard, the keyboard model, the measured chip row
    and the popup shell.
    """

    #: The keys the control has settled on, in order.
    selected = Signal(list)
    #: The popup opened or closed.
    open_changed = Signal(bool)
    #: What the caret holds.
    query_changed = Signal(str)
    #: Remove the chip at this index. Backspace walks the row through it.
    remove_requested = Signal(int)
    #: The clear control was pressed.
    cleared = Signal()
    #: The last row of the page was pressed.
    load_more_requested = Signal()

    def __init__(
        self,
        slot: str = "picker",
        picker: str = "picker",
        multiple: bool = False,
        keys: Sequence[str] = (),
        labels: Sequence[str] = (),
        items: Sequence[str] = (),
        summary: str = "chips",
        max: int = 0,
        chip_row: bool = False,
        inline: bool = True,
        token_input: bool = True,
        input_placeholder: str | None = None,
        searchable: bool = True,
        text_value: bool = False,
        size: str = "md",
        disabled: bool = False,
        inert: bool | None = None,
        readonly: bool = False,
        invalid: bool = False,
        clearable: bool = True,
        placeholder: str = "",
        search_placeholder: str = "Search…",
        open: bool = False,
        query: str = "",
        anchored: bool = False,
        highlight_on_open: bool = False,
        loading: bool = False,
        error: str | None = None,
        empty: bool = False,
        empty_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        has_more: bool = False,
        clear_label: str = "Clear the selection",
        trigger_label: str = "Show the options",
        overflow_label: str | None = None,
        chip_factory: Callable[[int], QtWidgets.QWidget] | None = None,
        row_model: QtCore.QAbstractItemModel | None = None,
        row_delegate: RowDelegate | None = None,
        on_select: Callable[[list], None] | None = None,
        on_open_change: Callable[[bool], None] | None = None,
        on_query_change: Callable[[str], None] | None = None,
        on_remove_at: Callable[[int], None] | None = None,
        on_clear: Callable[[], None] | None = None,
        on_load_more: Callable[[], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slot = slot
        self._picker = picker
        self._multiple = bool(multiple)
        self._keys = list(keys)
        self._labels = list(labels)
        self._items = list(items)
        self._summary = summary if summary in ("chips", "ellipsis", "count") else "chips"
        self._max = int(max)
        self._chip_row = bool(chip_row)
        self._inline = bool(inline)
        self._token_input = bool(token_input)
        self._input_placeholder = input_placeholder
        self._searchable = bool(searchable)
        self._text_value = bool(text_value)
        self._disabled = bool(disabled)
        self._inert = bool(disabled if inert is None else inert)
        self._readonly = bool(readonly)
        self._invalid = bool(invalid)
        self._clearable = bool(clearable)
        self._placeholder = placeholder
        self._search_placeholder = search_placeholder
        self._anchored = bool(anchored)
        self._highlight_on_open = bool(highlight_on_open)
        self._loading = bool(loading)
        self._error = error
        self._empty = bool(empty)
        self._labels_state = StateLabels(
            empty_label=empty_label, loading_label=loading_label, error_label=error_label
        )
        self._has_more = bool(has_more)
        self._clear_label = clear_label
        self._trigger_label = trigger_label
        self._overflow_label = overflow_label
        self._chip_factory = chip_factory
        self._on_select = on_select
        self._on_open_change = on_open_change
        self._on_query_change = on_query_change
        self._on_remove_at = on_remove_at
        self._on_clear = on_clear
        self._on_load_more = on_load_more

        self._open = False
        self._query = query
        self._armed: int | None = None
        self._chips: list[QtWidgets.QWidget] = []
        self._shown_chips = 0
        self._overflow = 0
        self._title = ""
        self._count_label = ""
        self._one_line = False

        self.set_size_step(size if size in PICKER_SIZE_VALUES else "md")
        self.setObjectName(f"{slot}-control")
        # `disabled` handed in is the same state `set_disabled` puts the control in, so the
        # inert step of rule 5 is worn from the first paint rather than only after a setter.
        self.setEnabled(not self._disabled)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self._hover = self.animated(DURATION["hover"])

        #: Coalesces the popup's measuring, which one answer would otherwise ask for five times.
        self._sync_timer = QtCore.QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(lambda: self._resize_popup(now=True))

        self._caret = _Caret(self._on_key, self)
        self._caret.setObjectName(f"{slot}-input")
        self._caret.textEdited.connect(self._on_typed)
        self._caret.installEventFilter(self)

        self._pill = _OverflowPill(self)
        self._pill.setObjectName(f"{slot}-overflow")
        self._pill.pressed_signal.connect(lambda: self.set_open(True))
        self._pill.hide()

        self._ring = _ArmedRing(self)

        self._clear = _IconButton("x", clear_label, self.size_step, self)
        self._clear.setObjectName(f"{slot}-clear")
        self._clear.pressed_signal.connect(self._clear_pressed)
        self._trigger = _IconButton("chevron-down", trigger_label, self.size_step, self)
        self._trigger.setObjectName(f"{slot}-trigger")
        self._trigger.pressed_signal.connect(self._toggle_from_trigger)

        self._build_popup(row_model, row_delegate)
        self._apply_shape()
        self._apply_theme()
        self._sync_query()
        self.set_items(items)
        if row_model is not None:
            self.set_row_model(row_model)
        self.set_labels(labels)
        if open:
            self.set_open(True)

    # --- the popup ------------------------------------------------------------------------

    def _build_popup(
        self,
        row_model: QtCore.QAbstractItemModel | None,
        row_delegate: RowDelegate | None,
    ) -> None:
        self._popup = _Popup()
        self._popup.setObjectName(f"{self._slot}-content")
        self._popup.setProperty("data_picker", self._picker)

        self._search_caret = _Caret(self._on_key, None)
        self._search_caret.setObjectName(f"{self._slot}-search-input")
        self._search_caret.textEdited.connect(self._on_typed)
        self._search_caret.installEventFilter(self)
        self._search_row = _SearchRow(self._search_caret, self._popup)
        self._search_row.setObjectName(f"{self._slot}-search")
        self._popup.add_widget(self._search_row)

        self._list = ListSurface(
            self._popup, size=self.size_step, delegate=row_delegate
        )
        self._list.setObjectName(f"{self._slot}-list")
        # A picker's load-more row is `text-xs`, the metadata step, where a search widget's is
        # the body one; the shared delegate is told which this is.
        self._list.row_delegate().set_load_more_text(PILL_TEXT)
        self._list.activated.connect(self._on_activated)
        self._list.load_more_requested.connect(self._on_load_more_row)
        self._popup.add_widget(self._list)

        self._skeletons = _Skeletons(self._popup)
        self._skeletons.setObjectName(f"{self._slot}-loading")
        self._popup.add_widget(self._skeletons)

        self._state_line = StateLine(
            state="empty", slot_name=f"{self._slot}-empty", parent=self._popup
        )
        self._popup.add_widget(self._state_line)

        self._popover = Popover(
            self,
            self._popup,
            side="bottom",
            align="start",
            match_anchor_width=self._anchored,
            width=None if self._anchored else POPUP_WIDTH,
        )
        # The popover is a top-level of its own, parented to the anchor's window, so it has to
        # go when the control does rather than when the window does.
        popover_ref = self._popover
        self.destroyed.connect(lambda *_: _retire(popover_ref))
        self._popover.set_dismiss_guard(self._claims_press)
        self._popover.set_key_handler(self._on_key)
        self._popover.dismissed.connect(lambda: self.set_open(False))
        if row_model is None:
            self._list.setModel(QtGui.QStandardItemModel(0, 1, self._list))

    def _claims_press(self, point: QtCore.QPoint) -> bool:
        """A press on the control, its chips or its trailing controls is never a dismissal."""
        local = self.mapFromGlobal(point)
        if self.rect().contains(local):
            return True
        for widget in (*self._chips, self._pill, self._clear, self._trigger, self._caret):
            try:
                if widget.isVisible() and widget.rect().contains(widget.mapFromGlobal(point)):
                    return True
            except RuntimeError:
                continue
        return False

    # --- props ----------------------------------------------------------------------------

    @property
    def slot(self) -> str:
        """The object-name prefix every part of this picker carries."""
        return self._slot

    def set_slot(self, value: str) -> None:
        self._slot = value
        self.setObjectName(f"{value}-control")

    @property
    def picker(self) -> str:
        """What the popup says it is."""
        return self._picker

    def set_picker(self, value: str) -> None:
        self._picker = value
        self._popup.setProperty("data_picker", value)

    @property
    def multiple(self) -> bool:
        return self._multiple

    def set_multiple(self, value: bool) -> None:
        self._multiple = bool(value)
        self._relayout()

    @property
    def keys(self) -> list[str]:
        """The chosen keys, in order."""
        return list(self._keys)

    def set_keys(self, value: Sequence[str]) -> None:
        self._keys = list(value)

    @property
    def labels(self) -> list[str]:
        """One label per chosen key: the summary, the title and the measured row read it."""
        return list(self._labels)

    def set_labels(self, value: Sequence[str]) -> None:
        # The chips are rebuilt only when the selection reads differently, so a read that
        # answers the same names leaves the chips, and their pictures, where they are.
        same = list(value) == self._labels and len(self._chips) > 0
        self._labels = list(value)
        if self._armed is not None and self._armed >= len(self._labels):
            self._armed = None
        if same:
            self._relayout()
            return
        self.rebuild_chips()

    @property
    def items(self) -> list[str]:
        """The item keys the list offers, in order."""
        return list(self._items)

    def set_items(self, value: Sequence[str]) -> None:
        self._items = list(value)
        self._sync_popup()

    @property
    def summary(self) -> str:
        return self._summary

    def set_summary(self, value: str) -> None:
        self._summary = value if value in ("chips", "ellipsis", "count") else "chips"
        self._relayout()

    @property
    def max(self) -> int:
        """Chips drawn before the rest becomes `+n`. Zero lets the row fit what it can."""
        return self._max

    def set_max(self, value: int) -> None:
        self._max = int(value)
        self._relayout()

    @property
    def chip_row(self) -> bool:
        """The value is a measured row of chips rather than the one chip of a single picker."""
        return self._chip_row

    def set_chip_row(self, value: bool) -> None:
        self._chip_row = bool(value)
        self._relayout()

    @property
    def inline(self) -> bool:
        """The control holds the caret. A summary control keeps it in the popup instead."""
        return self._inline

    def set_inline(self, value: bool) -> None:
        self._inline = bool(value)
        self._apply_shape()
        self._relayout()

    @property
    def token_input(self) -> bool:
        """The caret gives its room to the chips."""
        return self._token_input

    def set_token_input(self, value: bool) -> None:
        self._token_input = bool(value)
        self._relayout()

    @property
    def input_placeholder(self) -> str | None:
        return self._input_placeholder

    def set_input_placeholder(self, value: str | None) -> None:
        self._input_placeholder = value
        self._sync_placeholder()

    @property
    def searchable(self) -> bool:
        """A summary control keeps a search row. A fixed set has nothing to search."""
        return self._searchable

    def set_searchable(self, value: bool) -> None:
        self._searchable = bool(value)
        self._apply_shape()

    @property
    def text_value(self) -> bool:
        """The filled value is plain text, so the control keeps the reading inset."""
        return self._text_value

    def set_text_value(self, value: bool) -> None:
        self._text_value = bool(value)
        self._relayout()

    @property
    def size(self) -> str:
        return self.size_step

    def set_size(self, value: str) -> None:
        self.set_size_step(value if value in PICKER_SIZE_VALUES else "md")
        self._clear.set_size(self.size_step)
        self._trigger.set_size(self.size_step)
        self._list.row_delegate().set_size(self.size_step)
        self.rebuild_chips()

    @property
    def disabled(self) -> bool:
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self._inert = self._disabled
        self.setEnabled(not self._disabled)
        if self._disabled:
            self.set_open(False)
        self._apply_shape()
        self._relayout()

    @property
    def inert(self) -> bool:
        """The control takes no input. Wider than `disabled`: a loading picker is inert too."""
        return self._inert

    def set_inert(self, value: bool) -> None:
        self._inert = bool(value)
        self._apply_shape()

    @property
    def readonly(self) -> bool:
        return self._readonly

    def set_readonly(self, value: bool) -> None:
        self._readonly = bool(value)
        if self._readonly:
            self.set_open(False)
        self._apply_shape()
        self._relayout()

    @property
    def invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        self.update()

    @property
    def clearable(self) -> bool:
        return self._clearable

    def set_clearable(self, value: bool) -> None:
        self._clearable = bool(value)
        self._relayout()

    @property
    def placeholder(self) -> str:
        return self._placeholder

    def set_placeholder(self, value: str) -> None:
        self._placeholder = value
        self._sync_placeholder()
        self.update()

    @property
    def search_placeholder(self) -> str:
        return self._search_placeholder

    def set_search_placeholder(self, value: str) -> None:
        self._search_placeholder = value
        self._sync_placeholder()

    @property
    def anchored(self) -> bool:
        """The popup is as wide as the control it hangs off."""
        return self._anchored

    def set_anchored(self, value: bool) -> None:
        self._anchored = bool(value)
        self._popover._match_anchor_width = self._anchored
        self._popover._width = None if self._anchored else POPUP_WIDTH
        if self._open:
            self._popover.reposition()

    @property
    def highlight_on_open(self) -> bool:
        """Whether opening the list puts the cursor on the first row.

        Upstream's combobox does not: it opens with nothing highlighted and the first `Down`
        takes the first row, which is what `tools/drives/upstream/entity-picker-query.js`
        reads off the page. A picker that opens on a value of its own passes `True`.
        """
        return self._highlight_on_open

    def set_highlight_on_open(self, value: bool) -> None:
        self._highlight_on_open = bool(value)

    @property
    def loading(self) -> bool:
        return self._loading

    def set_loading(self, value: bool) -> None:
        self._loading = bool(value)
        self._sync_popup()

    @property
    def error(self) -> str | None:
        return self._error

    def set_error(self, value: str | None) -> None:
        self._error = value
        self._sync_popup()

    @property
    def empty(self) -> bool:
        return self._empty

    def set_empty(self, value: bool) -> None:
        self._empty = bool(value)
        self._sync_popup()

    @property
    def empty_label(self) -> str:
        return self._labels_state.empty_label or NO_MATCH_LABEL

    def set_empty_label(self, value: str) -> None:
        self._labels_state.empty_label = value
        self._sync_popup()

    @property
    def loading_label(self) -> str | None:
        return self._labels_state.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._labels_state.loading_label = value
        self._sync_popup()

    @property
    def error_label(self) -> str | None:
        return self._labels_state.error_label

    def set_error_label(self, value: str | None) -> None:
        self._labels_state.error_label = value
        self._sync_popup()

    @property
    def has_more(self) -> bool:
        """A further page is there to be read."""
        return self._has_more

    def set_has_more(self, value: bool) -> None:
        self._has_more = bool(value)
        self._sync_popup()

    @property
    def clear_label(self) -> str:
        return self._clear_label

    def set_clear_label(self, value: str) -> None:
        self._clear_label = value
        self._clear.setAccessibleName(value)
        self._clear.setToolTip(value)

    @property
    def trigger_label(self) -> str:
        return self._trigger_label

    def set_trigger_label(self, value: str) -> None:
        self._trigger_label = value
        self._trigger.setAccessibleName(value)
        self._trigger.setToolTip(value)

    @property
    def overflow_label(self) -> str | None:
        return self._overflow_label

    def set_overflow_label(self, value: str | None) -> None:
        self._overflow_label = value
        self._relayout()

    # --- the hooks a picker supplies ------------------------------------------------------

    def set_chip_factory(self, factory: Callable[[int], QtWidgets.QWidget] | None) -> None:
        """Build the chip for one chosen index. The control owns where it sits and its ring."""
        self._chip_factory = factory
        self.rebuild_chips()

    def set_row_model(self, model: QtCore.QAbstractItemModel | None) -> None:
        """The rows the list draws, one per item key, in the same order."""
        self._list.setModel(model if model is not None else QtGui.QStandardItemModel(0, 1))
        self._sync_popup()

    def row_model(self) -> QtCore.QAbstractItemModel | None:
        """The model the list draws."""
        return self._list.source_model()

    def set_row_delegate(self, delegate: RowDelegate) -> None:
        """The delegate that draws a row."""
        delegate.set_load_more_text(PILL_TEXT)
        self._list.setItemDelegate(delegate)

    def row_delegate(self) -> RowDelegate:
        return self._list.row_delegate()

    def caret(self) -> _Caret:
        """The input the keys reach: the control's own, or the popup's search box."""
        return self._caret if self._inline else self._search_caret

    def chips(self) -> list:
        """The chip widgets, in order, hidden ones included."""
        return list(self._chips)

    def overflow_pill(self) -> QtWidgets.QWidget:
        """The `+n` pill, shown only while the row hides something."""
        return self._pill

    def clear_control(self) -> QtWidgets.QWidget:
        """The clear control on the trailing edge."""
        return self._clear

    def open_control(self) -> QtWidgets.QWidget:
        """The chevron on the trailing edge."""
        return self._trigger

    def search_row(self) -> QtWidgets.QWidget:
        """The search row a summary trigger keeps at the top of its popup."""
        return self._search_row

    def state_line(self) -> StateLine:
        """The empty or error line the list is replaced by."""
        return self._state_line

    def skeletons(self) -> QtWidgets.QWidget:
        """The rows a read stands behind."""
        return self._skeletons

    def popup(self) -> QtWidgets.QWidget:
        """What the popover holds."""
        return self._popup

    def list_surface(self) -> ListSurface:
        """The list itself, for a picker that wants its highlight."""
        return self._list

    def popover(self) -> Popover:
        """The popup, which never takes focus."""
        return self._popover

    # --- the callback keywords ------------------------------------------------------------

    def set_on_select(self, value: Callable[[list], None] | None) -> None:
        self._on_select = value

    def set_on_open_change(self, value: Callable[[bool], None] | None) -> None:
        self._on_open_change = value

    def set_on_query_change(self, value: Callable[[str], None] | None) -> None:
        self._on_query_change = value

    def set_on_remove_at(self, value: Callable[[int], None] | None) -> None:
        self._on_remove_at = value

    def set_on_clear(self, value: Callable[[], None] | None) -> None:
        self._on_clear = value

    def set_on_load_more(self, value: Callable[[], None] | None) -> None:
        self._on_load_more = value

    # --- open, query and the selection ----------------------------------------------------

    @property
    def interactive(self) -> bool:
        """True while the control takes a press and a key."""
        return not self._readonly and not self._inert and self.isEnabled()

    @property
    def is_open(self) -> bool:
        return self._open

    def set_open(self, value: bool) -> None:
        """Show or hide the list. Closing clears the query, per clause 3 of the contract."""
        wanted = bool(value) and self.interactive
        if wanted == self._open:
            return
        self._open = wanted
        if not wanted:
            self.set_query("")
            self._popover.close()
        else:
            self._sync_popup()
            self._resize_popup(now=True)
            self._popover.open()
            self._focus_caret()
            if self._highlight_on_open:
                self._list.highlight_first()
        self.update()
        if self._on_open_change is not None:
            self._on_open_change(wanted)
        self.open_changed.emit(wanted)

    def toggle(self) -> None:
        self.set_open(not self._open)

    @property
    def query(self) -> str:
        return self._query

    def set_query(self, value: str) -> None:
        """Put text in the caret and tell the picker about it."""
        text = str(value)
        if text == self._query:
            return
        self._query = text
        self._sync_query()
        if self._on_query_change is not None:
            self._on_query_change(text)
        self.query_changed.emit(text)

    def status_text(self) -> str:
        """The one line the list's live region carries."""
        return list_status(
            ListStatusState(
                loading=self._loading,
                count=len(self._items),
                error=self._error,
                asked=True,
            ),
            self._labels_state,
        )

    @property
    def armed(self) -> int | None:
        """The chip holding the caret, or None while the input holds it."""
        return self._armed

    def arm(self, index: int | None) -> None:
        """Put the caret on a chip, or back in the input."""
        if index is not None and not 0 <= index < len(self._labels):
            index = None
        self._armed = index
        if index is None:
            self._ring.hide()
        self._place_ring()
        self.update()

    # --- the press rule -------------------------------------------------------------------

    def _press(self, on_caret: bool) -> None:
        """A press anywhere on the control toggles the list, the caret included."""
        if not self.interactive:
            return
        self.arm(None)
        if self._inline and not on_caret:
            self._caret.setFocus(Qt.FocusReason.MouseFocusReason)
        self.set_open(not self._open)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._press(on_caret=False)
        event.accept()

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self._caret and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._press(on_caret=True)
        return False

    def _toggle_from_trigger(self) -> None:
        if not self.interactive:
            return
        self.arm(None)
        if self._inline:
            self._caret.setFocus(Qt.FocusReason.MouseFocusReason)
        self.set_open(not self._open)

    def _clear_pressed(self) -> None:
        if self._on_clear is not None:
            self._on_clear()
        self.cleared.emit()
        if self._inline:
            self._caret.setFocus(Qt.FocusReason.MouseFocusReason)

    def _focus_caret(self) -> None:
        """Clause 2: the caret lands in the control's own input, or in the popup's search box.

        A fixed set has no search row, so the control itself holds the keys.
        """
        if self._inline:
            self._caret.setFocus(Qt.FocusReason.OtherFocusReason)
        elif self._searchable:
            self._search_caret.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # --- the keyboard ---------------------------------------------------------------------

    def _on_key(self, event: QtGui.QKeyEvent) -> bool:
        """Every intent core's `picker_key_intent` names, and the ones the list owns."""
        name = _key_name(event)
        intent = picker_key_intent(
            name,
            PickerKeyState(
                open=self._open,
                query=self._query,
                count=len(self._labels),
                focused=self._armed,
                editable=self.interactive,
                multiple=self._multiple,
            ),
        )
        kind = intent.kind
        if kind == "dismiss":
            self.arm(None)
            self._focus_caret()
            self.set_open(False)
            return True
        if kind == "focus":
            self.arm(intent.index)
            if intent.index is None:
                self._focus_caret()
            return True
        if kind == "remove":
            self.arm(intent.then)
            if intent.then is None:
                self._focus_caret()
            if self._on_remove_at is not None:
                self._on_remove_at(intent.index or 0)
            self.remove_requested.emit(intent.index or 0)
            return True
        if kind == "type":
            self.arm(None)
            self._focus_caret()
            self.set_query(self._query + (intent.key or ""))
            self.set_open(True)
            return True
        if kind == "open":
            self.arm(None)
            self._focus_caret()
            self.set_open(True)
            return True
        if kind == "follow":
            return self._list.handle_key(event)
        if self._open:
            return self._list.handle_key(event)
        return False

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._on_key(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_typed(self, text: str) -> None:
        self._query = text
        self._sync_query()
        if self._on_query_change is not None:
            self._on_query_change(text)
        self.query_changed.emit(text)
        if self.interactive and not self._open:
            self.set_open(True)

    # --- choosing -------------------------------------------------------------------------

    def _on_activated(self, row: int) -> None:
        if not 0 <= row < len(self._items):
            return
        key = self._items[row]
        if self._multiple:
            keys = list(self._keys)
            if key in keys:
                keys.remove(key)
            else:
                keys.append(key)
        else:
            keys = [key]
        self._emit_select(keys)
        # A pick keeps a multi picker open and closes a single one.
        if not self._multiple:
            self.set_open(False)
        self.arm(None)
        self._focus_caret()

    def _emit_select(self, keys: list) -> None:
        if self._on_select is not None:
            self._on_select(keys)
        self.selected.emit(keys)

    def _on_load_more_row(self) -> None:
        if self._on_load_more is not None:
            self._on_load_more()
        self.load_more_requested.emit()

    # --- the shape ------------------------------------------------------------------------

    def _apply_shape(self) -> None:
        """Which caret exists, and who takes the focus."""
        self._caret.setVisible(self._inline)
        self._search_row.setVisible(not self._inline and self._searchable)
        self.setFocusPolicy(
            Qt.FocusPolicy.NoFocus if self._inline else Qt.FocusPolicy.StrongFocus
        )
        self._caret.setReadOnly(self._readonly or not self.interactive)
        self._search_caret.setReadOnly(not self.interactive)
        self._sync_placeholder()

    def _sync_placeholder(self) -> None:
        shown = self._input_placeholder
        if shown is None:
            shown = "" if self._labels else self._placeholder
        self._caret.setPlaceholderText(shown)
        self._caret.setAccessibleName(self._placeholder)
        self._search_caret.setPlaceholderText(self._search_placeholder)
        self._search_caret.setAccessibleName(self._search_placeholder)

    def _sync_query(self) -> None:
        for caret in (self._caret, self._search_caret):
            if caret.text() != self._query:
                blocked = caret.blockSignals(True)
                caret.setText(self._query)
                caret.blockSignals(blocked)

    def _sync_popup(self) -> None:
        """One of four things: the error line, the skeletons, the empty line, or the rows."""
        failed = self._error is not None and self._error != ""
        if failed:
            self._state_line.apply_state("error", self._labels_state, self._error)
            self._state_line.set_icon("triangle-alert")
            self._state_line.set_slot_name(f"{self._slot}-error")
        elif not self._loading and self._empty:
            self._state_line.apply_state("empty", self._labels_state)
            self._state_line.set_icon("search-x")
            self._state_line.set_slot_name(f"{self._slot}-empty")
        blocked = failed or (not self._loading and self._empty)
        self._state_line.setVisible(blocked)
        self._skeletons.setVisible(self._loading and not failed)
        self._list.setVisible(not blocked and not (self._loading and not failed))
        self._list.set_load_more(
            self._has_more and not blocked,
            state_line("loading", self._labels_state) if self._loading else _LOAD_MORE_LABEL,
        )
        self._list.setAccessibleDescription(self.status_text())
        self.setAccessibleDescription(self.status_text())
        if self._open:
            # The rows of an open list land after it opened, so a picker that opens on a row
            # takes it as the rows arrive rather than only when the list was already full.
            if self._highlight_on_open and self._list.highlighted() < 0:
                self._list.highlight_first()
        self._resize_popup()

    def _resize_popup(self, now: bool = False) -> None:
        """Size the popup to its content and put it back against the control.

        One answer walks the whole shell — the rows, the keys, the loading flag, the error, the
        empty flag and the page flag — and each of those syncs the popup. Measuring the list
        costs a size hint per row, so the measuring is coalesced onto the next turn of the loop
        and five calls in one answer become one.
        """
        if now or not self._open:
            self._sync_timer.stop()
            self._popup.adjustSize()
            if self._open:
                self._popover.reposition()
            return
        if not self._sync_timer.isActive():
            self._sync_timer.start(0)

    # --- the chips ------------------------------------------------------------------------

    def _chip_step(self) -> str:
        return PICKER_CHIP[self.size_step]

    def rebuild_chips(self) -> None:
        """Build every chip again, for a change the labels alone do not show."""
        for chip in self._chips:
            chip.setParent(None)
            chip.deleteLater()
        self._chips = []
        if self._chip_factory is not None and self._summary != "count":
            wanted = len(self._labels) if self._chip_row else min(1, len(self._labels))
            for index in range(wanted):
                chip = self._chip_factory(index)
                if chip is None:
                    continue
                chip.setParent(self)
                chip.show()
                remove = getattr(chip, "removed", None)
                if remove is not None and self._chip_row:
                    # A chip's own remove signal may carry what it removed, or nothing.
                    remove.connect(lambda *_ignored, i=index: self._remove_at(i))
                self._chips.append(chip)
        self._sync_placeholder()
        self._relayout()

    def _remove_at(self, index: int) -> None:
        if self._on_remove_at is not None:
            self._on_remove_at(index)
        self.remove_requested.emit(index)

    def _insets(self) -> tuple[int, int, int]:
        """The leading, trailing and vertical inset the box takes in its current state."""
        filled = len(self._labels) > 0
        if self._text_value:
            left, _right = PICKER_TEXT_BOX[self.size_step]
            if not filled:
                left = PICKER_TEXT_BOX_EMPTY[self.size_step]
            pad_y = 0
        else:
            _right, left, pad_y = PICKER_BOX[self.size_step]
            if not filled:
                left, pad_y = PICKER_BOX_EMPTY[self.size_step]
        if self._readonly:
            right = TRAILING_READONLY
        elif self._show_clear():
            right = TRAILING_CLEAR
        else:
            right = TRAILING_OPEN
        return left, right, pad_y

    def _show_clear(self) -> bool:
        return self._clearable and len(self._labels) > 0 and not self._readonly and not self._disabled

    def _plan(self) -> Any:
        """What the control draws for the selection, from core's `summarise_selection`."""
        fit = None
        if self._chip_row and self._multiple and self._summary == "ellipsis" and self._chips:
            left, right, _pad = self._insets()
            widths = [float(chip.sizeHint().width() + CHIP_GAP) for chip in self._chips]
            fit = ChipRow(
                widths=widths,
                available=float(max(0, self.width() - left - right)),
                reserve=float(OVERFLOW_RESERVE),
            )
        return summarise_selection(
            self._labels,
            lambda label: label,
            summary=self._summary,
            max=self._max,
            fit=fit,
        )

    # --- geometry -------------------------------------------------------------------------

    def _line_height(self) -> int:
        if self._chips:
            return self._chips[0].sizeHint().height()
        return CHIP_HEIGHT[self._chip_step()]

    def _relayout(self) -> None:
        plan = self._plan()
        self._shown_chips = len(plan.shown)
        self._overflow = plan.overflow
        self._title = plan.title
        self._count_label = plan.count_label
        self._one_line = plan.one_line
        self.setToolTip(self._title or self._placeholder)
        self._pill.set_count(self._overflow)
        # What each part should show, not what Qt says it shows: a control whose window is not
        # up yet reports every child hidden, and the geometry still has to be right.
        show_pill = self._overflow > 0 and self._summary != "count"
        self._pill.setVisible(show_pill)
        if self._overflow_label is not None:
            self._pill.setToolTip(self._overflow_label)
        else:
            self._pill.setToolTip(f"Show all {len(self._labels)} selected")

        left, right, pad_y = self._insets()
        room = max(0, self.width() - left - right)
        line = max(1, self._line_height())
        ladder = CONTROL_HEIGHT[self.size_step]
        # The inset is what the chip and the control's own border leave under the ladder,
        # halved, so the border counts: 20 and 2 under 28 at sm, 24 and 2 under 32 at md.
        x, y = left, BORDER + pad_y
        rows = 1
        placed: list[tuple[QtWidgets.QWidget, QtCore.QRect]] = []
        for index, chip in enumerate(self._chips):
            shown_chip = index < self._shown_chips
            chip.setVisible(shown_chip)
            if not shown_chip:
                continue
            width = chip.sizeHint().width()
            if not self._one_line and x > left and x + width > left + room:
                x = left
                y += line + CHIP_GAP
                rows += 1
            placed.append((chip, QtCore.QRect(x, y, min(width, max(0, room)), line)))
            x += width + CHIP_GAP
        if show_pill:
            width = self._pill.sizeHint().width()
            placed.append((self._pill, QtCore.QRect(x, y, width, line)))
            x += width + CHIP_GAP

        natural = 2 * (BORDER + pad_y) + rows * line + (rows - 1) * CHIP_GAP
        height = max(ladder, natural)
        # `items-center`: the value sits in the middle of the box it is in, whether that is the
        # ladder or a box a caller made taller, so a chip, a value that reads as plain text and
        # the caret's own text share one centre line.
        box = max(self.height(), height)
        shift = max(0, (box - natural) // 2)
        for widget, rect in placed:
            widget.setGeometry(rect.translated(0, shift))

        if self._inline:
            floor = TOKEN_CARET_MIN_WIDTH if self._token_input else CARET_MIN_WIDTH
            width = max(floor, self.width() - right - x)
            if placed:
                self._caret.setGeometry(x, y + shift, width, line)
            else:
                # An empty control gives its inset back and reads as a plain input, so the
                # caret fills the box and centres its text on the box's own centre line.
                self._caret.setGeometry(x, BORDER, width, max(1, box - 2 * BORDER))

        if height != self.minimumHeight():
            self.setMinimumHeight(height)
            self.updateGeometry()

        show_clear = self._show_clear()
        show_trigger = not self._readonly
        self._clear.setVisible(show_clear)
        self._trigger.setVisible(show_trigger)
        edge = self.width() - 8
        # `PICKER_TRAILING`: each takes the ladder, so the pair centres on a control that holds
        # one line and stays with the first row when the value wraps below it.
        lane = (box - ladder) // 2 if rows == 1 else 0
        for control, shown in ((self._trigger, show_trigger), (self._clear, show_clear)):
            if not shown:
                continue
            hint = control.sizeHint()
            edge -= hint.width()
            control.setGeometry(
                edge, lane + (ladder - hint.height()) // 2, hint.width(), hint.height()
            )
            edge -= 4
        self._place_ring()
        self.update()

    def _place_ring(self) -> None:
        if self._armed is None or self._armed >= min(len(self._chips), self._shown_chips):
            self._ring.hide()
            return
        chip = self._chips[self._armed]
        self._ring.setGeometry(chip.geometry())
        self._ring.raise_()
        self._ring.show()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(240, max(CONTROL_HEIGHT[self.size_step], self.minimumHeight()))

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, max(CONTROL_HEIGHT[self.size_step], self.minimumHeight()))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    # --- the theme and the box ------------------------------------------------------------

    def _apply_theme(self) -> None:
        theme = self.theme
        self._caret.apply_theme(theme)
        self._search_caret.apply_theme(theme)

    def _on_theme(self, theme: object) -> None:
        self._apply_theme()
        self._relayout()
        super()._on_theme(theme)

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def _ring_shown(self) -> bool:
        return self._caret.keyboard_focus if self._inline else self.keyboard_focus

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        painter.setOpacity(self.disabled_opacity())
        box = self.rect()
        radius = float(theme.radius_px("lg"))
        # `bg-background hover:bg-muted/30`: the wash is laid over the surface, not blended in.
        surface = over(
            theme.color("background"), with_alpha(theme.muted, 0.3 * self._hover.value)
        )
        border = theme.color("destructive") if self._invalid else theme.color("input")
        fill_round_rect(painter, box, radius, surface, border)

        if self._invalid:
            wash = with_alpha(theme.destructive, 0.4 if theme.dark else 0.2)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(wash, 2))
            painter.drawRoundedRect(
                QtCore.QRectF(box).adjusted(2.0, 2.0, -2.0, -2.0), radius - 2.0, radius - 2.0
            )

        left, right, _pad = self._insets()
        room = max(0, self.width() - left - right)
        font = theme.font(TEXT_SIZE)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        text = ""
        token = "muted_foreground"
        if self._summary == "count" and self._chip_row and self._multiple and self._labels:
            text, token = self._count_label, "foreground"
        elif not self._labels and not self._inline:
            text = self._placeholder
        if text:
            painter.setPen(theme.color(token))
            # One line, so the text centres on the box rather than on the ladder inside it.
            painter.drawText(
                QtCore.QRect(left, 0, room, self.height()),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                elide(metrics, text, room),
            )

        if self._ring_shown():
            self.paint_focus_ring(painter, box, radius)
        painter.end()
