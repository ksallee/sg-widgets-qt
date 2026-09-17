"""A `date` field, as a trigger over a typed day and a calendar.

Ported from `packages/react/src/registry/sg/components/date-editor.tsx`.

    editor = DateEditor(value="2026-09-02")
    editor.committed.connect(write)

The value is exactly `YYYY-MM-DD`: no time, no zone, and the API validates the day rather than only
parsing it, so `2026-02-30` is refused here too. A timestamp is never a date on this type
(field_types/date).

One anatomy everywhere: a trigger carrying the stored day, over a popover holding the typed day and
the calendar. `inline` only sizes the trigger to its value.
"""
from __future__ import annotations

import datetime
from typing import Callable

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QRect, QSize, Qt, Signal

from sg_widgets_core.edit import to_api_date
from sg_widgets_core.schema import FieldSchema

from ..icons import paint_icon
from ..primitives.base import (
    CONTROL_GLYPH,
    CONTROL_HEIGHT,
    CONTROL_PAD,
    DURATION,
    ThemedWidget,
    elide,
)
from ..primitives.calendar import Calendar
from ..primitives.input import Input
from ..primitives.popover import Popover
from ..theme import with_alpha
from .editor_calendar import from_calendar_date, to_calendar_date
from .value_editor import ValueEditor, ValueSession, fade_disabled

__all__ = ["POPOVER_PAD", "DateEditor", "DateTrigger", "date_popover_panel"]

#: `p-3` and `gap-3` of the popover the two date editors open.
POPOVER_PAD = 12

#: Between the glyph and the value on the trigger.
TRIGGER_GAP = 6

#: The widest value a trigger has to hold: a day and a clock with seconds.
_WIDEST = "2026-09-02 00:00:00"


class DateTrigger(ThemedWidget):
    """The control a date editor opens from: a calendar glyph, then the value or the placeholder.

    It stands on the control ladder and wears the states of `docs/design-rules.md` rule 5: readonly
    keeps full contrast and drops the press, disabled is inert, invalid puts the border and the ring
    in `destructive`.
    """

    clicked = Signal()

    def __init__(
        self,
        text: str = "",
        placeholder: str = "",
        size: str = "md",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size_step=size if size in CONTROL_HEIGHT else "md")
        self._text = text
        self._placeholder = placeholder
        self._invalid = False
        self._readonly = False
        self._hover = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    # --- props ---------------------------------------------------------------------------

    @property
    def text(self) -> str:
        """The value on the trigger, or the empty string while the field is unset."""
        return self._text

    def set_text(self, value: str) -> None:
        self._text = value or ""
        self.setToolTip(self._text)
        self.update()

    @property
    def placeholder(self) -> str:
        return self._placeholder

    def set_placeholder(self, value: str) -> None:
        self._placeholder = value or ""
        self.update()

    @property
    def invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        self.update()

    @property
    def readonly(self) -> bool:
        return self._readonly

    def set_readonly(self, value: bool) -> None:
        self._readonly = bool(value)
        self.setCursor(
            Qt.CursorShape.ArrowCursor if self._readonly else Qt.CursorShape.PointingHandCursor
        )
        self.update()

    # --- geometry ------------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self.theme.font(14, tabular=True))
        widest = max(
            metrics.horizontalAdvance(self._text or _WIDEST),
            metrics.horizontalAdvance(self._placeholder),
        )
        pad = CONTROL_PAD[self.size_step]
        glyph = CONTROL_GLYPH[self.size_step]
        return QSize(pad * 2 + glyph + TRIGGER_GAP + widest, CONTROL_HEIGHT[self.size_step])

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(CONTROL_HEIGHT[self.size_step], CONTROL_HEIGHT[self.size_step])

    # --- painting ------------------------------------------------------------------------

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value and not self._readonly else 0.0)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setOpacity(self.disabled_opacity())

        # The trigger stands on the control ladder, so its box is the widget's own rect: the
        # border rides the rim and the focus ring is painted inward, as every field does.
        radius = float(theme.radius_px("lg"))
        box = QRect(0, 0, self.width(), self.height())
        inner = box
        border = theme.color("destructive") if self._invalid else theme.color("input")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(theme.muted, 0.3 * self._hover.value))
        painter.drawRoundedRect(QtCore.QRectF(inner), radius, radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QtGui.QPen(border, 1.0))
        painter.drawRoundedRect(
            QtCore.QRectF(inner).adjusted(0.5, 0.5, -0.5, -0.5), radius - 0.5, radius - 0.5
        )
        if self._invalid:
            ring = with_alpha(theme.destructive, 0.4 if theme.dark else 0.2)
            painter.setPen(QtGui.QPen(ring, 2.0))
            painter.drawRoundedRect(
                QtCore.QRectF(box).adjusted(2, 2, -2, -2), radius - 2.0, radius - 2.0
            )
        elif self.keyboard_focus:
            self.paint_focus_ring(painter, box, radius)

        pad = CONTROL_PAD[self.size_step]
        glyph = CONTROL_GLYPH[self.size_step]
        spot = QRect(inner.left() + pad, inner.center().y() - glyph // 2 + 1, glyph, glyph)
        paint_icon(painter, spot, "calendar", theme.color("muted_foreground"))

        left = spot.right() + 1 + TRIGGER_GAP
        width = max(0, inner.right() + 1 - pad - left)
        painter.setFont(theme.font(14, tabular=True))
        painter.setPen(theme.color("foreground" if self._text else "muted_foreground"))
        label = self._text or self._placeholder
        painter.drawText(
            QRect(left, inner.top(), width, inner.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(painter, label, width),
        )
        painter.end()

    # --- the press -----------------------------------------------------------------------

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.set_pressed(True)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        was = self.pressed
        self.set_pressed(False)
        if was and self.isEnabled() and not self._readonly:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
        if event.key() in keys and self.isEnabled() and not self._readonly:
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def date_popover_panel(parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The surface the two date editors stack their parts on: 12 of padding, 12 between them."""
    panel = QtWidgets.QWidget(parent)
    panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    column = QtWidgets.QVBoxLayout(panel)
    column.setContentsMargins(POPOVER_PAD, POPOVER_PAD, POPOVER_PAD, POPOVER_PAD)
    column.setSpacing(POPOVER_PAD)
    return panel


class DateEditor(ValueEditor):
    """A `date` field."""

    #: The calendar opened or closed.
    open_changed = Signal(bool)

    def __init__(
        self,
        value: str | None = None,
        field: FieldSchema | None = None,
        inline: bool = False,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "YYYY-MM-DD",
        open: bool = False,  # noqa: A002
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        on_value_change: Callable[[str | None], None] | None = None,
        on_error_change: Callable[[str | None], None] | None = None,
        on_open_change: Callable[[bool], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            "date-editor", size=size, inline=inline, error_message=error_message, parent=parent
        )
        self.use_session(
            ValueSession(
                value,
                format=lambda stored: stored if stored else "",
                parse=to_api_date,
                error=error,
                invalid=invalid,
                parent=self,
            )
        )
        self._build()

        self.set_placeholder(placeholder)
        self.set_field(field)
        self.set_invalid(invalid)
        self.set_readonly(readonly)
        self.set_disabled(disabled)
        self.connect_callbacks(on_value_change, on_error_change)
        if on_open_change is not None:
            self.open_changed.connect(on_open_change)
        self._refresh()
        if open:
            self.set_open(True)

    # --- the parts -----------------------------------------------------------------------

    def _build(self) -> None:
        self._trigger = DateTrigger(size=self.size, parent=self)
        self._trigger.setObjectName("date-editor-trigger")
        self._trigger.clicked.connect(self.toggle)
        self.add_control(self._trigger)

        panel = date_popover_panel()
        self._day = Input(placeholder="YYYY-MM-DD", size=self.size, parent=panel)
        self._day.setObjectName("date-editor-day")
        self._session.bind(self._day)
        panel.layout().addWidget(self._day)

        self._calendar = Calendar(surface="transparent", parent=panel)
        self._calendar.setObjectName("date-editor-calendar")
        self._calendar.grid().picked.connect(self._pick)
        panel.layout().addWidget(self._calendar)

        self._popover = Popover(self._trigger, panel, side="bottom", align="start")
        self._popover.opened.connect(self._on_opened)
        self._popover.closed.connect(lambda: self.open_changed.emit(False))

        self._session.entered.connect(self._on_enter)
        self._session.escaped.connect(self._on_escape)
        self._session.committed.connect(lambda _value: self._refresh())

    # --- the popover ---------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Whether the calendar popover is showing."""
        return self._popover.is_open

    def set_open(self, value: bool) -> None:
        """Open or close the calendar. Readonly and disabled never open."""
        wanted = bool(value) and not self.readonly and self.isEnabled()
        if wanted == self._popover.is_open:
            return
        if wanted:
            self._popover.open()
        else:
            self._popover.close()

    def toggle(self) -> None:
        """A press on the trigger."""
        self.set_open(not self.is_open)

    def _on_opened(self) -> None:
        self._calendar.set_value(to_calendar_date(self._session.value))
        self._popover.raise_()
        self._popover.activateWindow()
        self._day.setFocus(Qt.FocusReason.OtherFocusReason)
        self.open_changed.emit(True)

    def _on_enter(self, committed: bool) -> None:
        if not committed:
            return
        self._session.set_editing(False)
        self.set_open(False)

    def _on_escape(self) -> None:
        self._session.set_editing(False)
        self.set_open(False)

    def _pick(self, day: datetime.date) -> None:
        self._session.set_editing(False)
        self.set_open(False)
        self._session.apply(from_calendar_date(day) or None)

    # --- props ---------------------------------------------------------------------------

    @property
    def value(self) -> str | None:
        """The stored day, exactly `YYYY-MM-DD` (field_types/date)."""
        return self._session.value

    def set_value(self, value: str | None) -> None:
        self._session.set_value(value)
        self._refresh()

    @property
    def trigger(self) -> DateTrigger:
        """The control the popover hangs off."""
        return self._trigger

    @property
    def day_input(self) -> Input:
        """The typed day inside the popover."""
        return self._day

    @property
    def calendar(self) -> Calendar:
        """The month grid inside the popover."""
        return self._calendar

    def _refresh(self) -> None:
        stored = self._session.value
        self._trigger.set_text(stored if stored else "")
        self._calendar.set_value(to_calendar_date(stored))

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        self._trigger.set_size_step(size)
        self._day.set_size(size)

    def _apply_placeholder(self, placeholder: str) -> None:
        self._trigger.set_placeholder(placeholder)
        self._day.setPlaceholderText(placeholder)
        super()._apply_placeholder(placeholder)

    def _apply_state(self) -> None:
        trigger = getattr(self, "_trigger", None)
        if trigger is None:
            return
        trigger.set_readonly(self.readonly)
        trigger.set_invalid(self.reads_invalid)
        trigger.setFocusPolicy(
            Qt.FocusPolicy.NoFocus if self.readonly else Qt.FocusPolicy.StrongFocus
        )
        self._day.setReadOnly(self.readonly)
        self._day.set_invalid(self.reads_invalid)
        fade_disabled(self._day)
        name = self.field_name() or "Pick a date"
        trigger.setAccessibleName(name)
        if self.readonly or not self.isEnabled():
            self.set_open(False)
