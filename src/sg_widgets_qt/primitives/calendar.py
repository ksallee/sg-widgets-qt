"""The month grid of `calendar.tsx`.

A caption holding a month and a year select between two ghost step buttons, a row of weekday
headings, and six weeks of 32px day cells drawn by one `paintEvent`. Today is outlined, the
chosen day is filled in `primary`, and the days between the ends of a range wear `accent`.

Dates cross the boundary as ISO strings (`YYYY-MM-DD`), which is what the API sends and what
core reads; a `date` is taken too and is given back as its ISO string.
"""
from __future__ import annotations

import datetime
from typing import Union

from qtpy.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal
from qtpy.QtGui import QFont, QKeyEvent, QPainter
from qtpy.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ..theme import with_alpha
from .base import DURATION, ThemedWidget, fill_round_rect
from .input_group import IconButton
from .select import Select

__all__ = [
    "CELL",
    "MONTH_NAMES",
    "WEEKDAY_LETTERS",
    "Calendar",
    "MonthGrid",
]

#: A day cell, and the weekday heading over it.
CELL = 32
HEADING_HEIGHT = 20

#: Six weeks, so the grid keeps one height whatever month it shows.
WEEKS = 6
COLUMNS = 7

#: The step buttons beside the caption.
NAV_SIZE = 28

#: Month names, and the weekday letters in Monday-first order.
MONTH_NAMES: tuple[str, ...] = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
WEEKDAY_LETTERS: tuple[str, ...] = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")

#: Years the year select offers around the one on show.
YEAR_SPAN = 10

DateLike = Union[str, datetime.date, None]


def as_date(value: DateLike) -> datetime.date | None:
    """A `date`, an ISO string or None as a `date`. An unreadable string reads as None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def iso(value: datetime.date | None) -> str | None:
    """A `date` as the ISO string the API sends."""
    return None if value is None else value.isoformat()


def _monday_first(locale: str) -> bool:
    """Every locale but `en-US` starts its week on Monday."""
    return (locale or "").lower() != "en-us"


class MonthGrid(ThemedWidget):
    """Six weeks of day cells, drawn and walked without a child widget per day."""

    picked = Signal(object)
    cursor_moved = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        locale: str = "en-US",
    ) -> None:
        super().__init__(parent)
        today = datetime.date.today()
        self._locale = locale
        self._year = today.year
        self._month = today.month
        self._cursor = today
        self._hover: datetime.date | None = None
        self._selected: datetime.date | None = None
        self._start: datetime.date | None = None
        self._end: datetime.date | None = None
        self._min: datetime.date | None = None
        self._max: datetime.date | None = None
        self._mode = "single"
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._wash = self.animated(DURATION["hover"])

    # --- what it shows -------------------------------------------------------------------

    def set_month(self, year: int, month: int) -> None:
        """Show that month."""
        self._year, self._month = int(year), int(month)
        self.update()

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def set_locale(self, locale: str) -> None:
        self._locale = locale
        self.update()

    def set_bounds(self, low: datetime.date | None, high: datetime.date | None) -> None:
        self._min, self._max = low, high
        self.update()

    def set_selection(
        self,
        selected: datetime.date | None,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> None:
        self._selected, self._start, self._end = selected, start, end
        self.update()

    @property
    def cursor(self) -> datetime.date:
        """The day the keyboard is on."""
        return self._cursor

    def set_cursor(self, day: datetime.date, follow: bool = True) -> None:
        """Put the keyboard cursor on a day, and turn the page to its month."""
        self._cursor = day
        if follow and (day.year, day.month) != (self._year, self._month):
            self.set_month(day.year, day.month)
        self.cursor_moved.emit(day)
        self.update()

    # --- the grid ------------------------------------------------------------------------

    def first_cell(self) -> datetime.date:
        """The day in the top left cell, which may be in the month before."""
        first = datetime.date(self._year, self._month, 1)
        weekday = first.weekday() if _monday_first(self._locale) else (first.weekday() + 1) % 7
        return first - datetime.timedelta(days=weekday)

    def headings(self) -> list[str]:
        """The weekday letters in the order this locale reads them."""
        if _monday_first(self._locale):
            return list(WEEKDAY_LETTERS)
        return [WEEKDAY_LETTERS[6], *WEEKDAY_LETTERS[:6]]

    def cell_rect(self, column: int, week: int) -> QRect:
        top = HEADING_HEIGHT + 4 + week * CELL
        return QRect(column * CELL, top, CELL, CELL)

    def date_at(self, point: QPoint) -> datetime.date | None:
        """The day under a point, or None where the point is off the grid."""
        top = HEADING_HEIGHT + 4
        if point.y() < top:
            return None
        column = point.x() // CELL
        week = (point.y() - top) // CELL
        if not (0 <= column < COLUMNS and 0 <= week < WEEKS):
            return None
        return self.first_cell() + datetime.timedelta(days=int(week * COLUMNS + column))

    def enabled_day(self, day: datetime.date) -> bool:
        """True while a day is inside the bounds the caller set."""
        if self._min is not None and day < self._min:
            return False
        return not (self._max is not None and day > self._max)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(COLUMNS * CELL, HEADING_HEIGHT + 4 + WEEKS * CELL)

    # --- painting ------------------------------------------------------------------------

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        painter.setFont(theme.font(12))
        painter.setPen(theme.color("muted_foreground"))
        for column, letter in enumerate(self.headings()):
            box = QRect(column * CELL, 0, CELL, HEADING_HEIGHT)
            painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), letter)

        radius = float(theme.radius_px("md"))
        today = datetime.date.today()
        first = self.first_cell()
        for slot in range(WEEKS * COLUMNS):
            day = first + datetime.timedelta(days=slot)
            box = self.cell_rect(slot % COLUMNS, slot // COLUMNS)
            self._paint_day(painter, box, day, today, radius)
        painter.end()

    def _paint_day(  # noqa: C901
        self,
        painter: QPainter,
        box: QRect,
        day: datetime.date,
        today: datetime.date,
        radius: float,
    ) -> None:
        theme = self.theme
        outside = day.month != self._month
        enabled = self.enabled_day(day)
        in_range = self._in_range(day)
        is_end = self._is_range_end(day)
        chosen = self._selected == day or is_end

        ink = theme.color("foreground")
        if outside or not enabled:
            ink = theme.color("muted_foreground")

        if in_range:
            # The band runs edge to edge, so a week of range days reads as one strip.
            painter.fillRect(box, theme.color("accent"))
            ink = theme.color("accent_foreground")
        elif is_end and self._start is not None and self._end is not None and self._start != self._end:
            # Half a band under an end, towards the middle, so the strip meets the pill.
            half = QRect(box.left() if day == self._end else box.center().x(), box.top(),
                         box.width() // 2, box.height())
            painter.fillRect(half, theme.color("accent"))

        if chosen:
            fill_round_rect(painter, box, radius, theme.color("primary"))
            ink = theme.color("primary_foreground")
        elif self._hover == day and enabled:
            fill_round_rect(painter, box, radius, with_alpha(theme.accent, 0.5))
            ink = theme.color("accent_foreground")
        elif day == today:
            fill_round_rect(painter, box, radius, None, theme.color("primary"))

        if self.hasFocus() and day == self._cursor:
            self.paint_focus_ring(painter, box, radius)

        painter.setOpacity(1.0 if enabled else 0.5)
        painter.setFont(theme.font(14, QFont.Weight.Medium if chosen else QFont.Weight.Normal))
        painter.setPen(ink)
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), str(day.day))
        painter.setOpacity(1.0)

    def _in_range(self, day: datetime.date) -> bool:
        if self._mode != "range" or self._start is None or self._end is None:
            return False
        return self._start < day < self._end

    def _is_range_end(self, day: datetime.date) -> bool:
        return self._mode == "range" and day in (self._start, self._end) and day is not None

    # --- the pointer and the keys --------------------------------------------------------

    def mouseMoveEvent(self, event: QEvent) -> None:  # noqa: N802
        day = self.date_at(_point(event))
        if day != self._hover:
            self._hover = day
            self.update()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        super().leaveEvent(event)
        self._hover = None
        self.update()

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        day = self.date_at(_point(event))
        if day is not None and self.enabled_day(day):
            self.set_cursor(day)
            self.picked.emit(day)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self.handle_key(event):
            super().keyPressEvent(event)

    def handle_key(self, event: QKeyEvent) -> bool:  # noqa: C901
        """Take one key. Arrows walk the days, PageUp and PageDown the months."""
        key = event.key()
        day = self._cursor
        if key == Qt.Key.Key_Left:
            self.set_cursor(day - datetime.timedelta(days=1))
        elif key == Qt.Key.Key_Right:
            self.set_cursor(day + datetime.timedelta(days=1))
        elif key == Qt.Key.Key_Up:
            self.set_cursor(day - datetime.timedelta(days=7))
        elif key == Qt.Key.Key_Down:
            self.set_cursor(day + datetime.timedelta(days=7))
        elif key == Qt.Key.Key_PageUp:
            self.set_cursor(_add_months(day, -1))
        elif key == Qt.Key.Key_PageDown:
            self.set_cursor(_add_months(day, 1))
        elif key == Qt.Key.Key_Home:
            offset = day.weekday() if _monday_first(self._locale) else (day.weekday() + 1) % 7
            self.set_cursor(day - datetime.timedelta(days=offset))
        elif key == Qt.Key.Key_End:
            offset = day.weekday() if _monday_first(self._locale) else (day.weekday() + 1) % 7
            self.set_cursor(day + datetime.timedelta(days=6 - offset))
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self.enabled_day(day):
                self.picked.emit(day)
        else:
            return False
        return True


class Calendar(ThemedWidget):
    """A month of days a person picks from.

    `mode` of `single` keeps one day and `range` keeps two. `value` and `value_changed` carry
    ISO strings: one string in `single`, a `(start, end)` pair in `range`, either end None while
    it is unset. `surface` of `transparent` drops the `background` fill, for a calendar sitting
    in a popover that has painted one already.
    """

    value_changed = Signal(object)
    month_changed = Signal(int, int)

    def __init__(
        self,
        value: DateLike | tuple[DateLike, DateLike] = None,
        mode: str = "single",
        min: DateLike = None,  # noqa: A002
        max: DateLike = None,  # noqa: A002
        locale: str = "en-US",
        surface: str = "background",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode if mode in ("single", "range") else "single"
        self._surface = surface
        self._locale = locale
        self._min = as_date(min)
        self._max = as_date(max)
        self._selected: datetime.date | None = None
        self._start: datetime.date | None = None
        self._end: datetime.date | None = None
        self._pending = False

        self._prev = IconButton("chevron-left", self, side=NAV_SIZE, glyph=16, tooltip="Previous month")
        self._next = IconButton("chevron-right", self, side=NAV_SIZE, glyph=16, tooltip="Next month")
        self._month_select = Select(parent=self, size="sm", placeholder="Month")
        self._year_select = Select(parent=self, size="sm", placeholder="Year")
        self._month_select.setMinimumWidth(124)
        self._year_select.setMinimumWidth(96)
        self._grid = MonthGrid(self, locale=locale)
        self._grid.set_mode(self._mode)
        self._grid.set_bounds(self._min, self._max)

        column = QVBoxLayout(self)
        column.setContentsMargins(8, 8, 8, 8)
        column.setSpacing(12)
        caption = QHBoxLayout()
        caption.setContentsMargins(0, 0, 0, 0)
        caption.setSpacing(6)
        caption.addWidget(self._prev)
        caption.addStretch(1)
        caption.addWidget(self._month_select)
        caption.addWidget(self._year_select)
        caption.addStretch(1)
        caption.addWidget(self._next)
        column.addLayout(caption)
        column.addWidget(self._grid, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._prev.clicked.connect(lambda: self.step_month(-1))
        self._next.clicked.connect(lambda: self.step_month(1))
        self._month_select.value_changed.connect(self._on_month_pick)
        self._year_select.value_changed.connect(self._on_year_pick)
        self._grid.picked.connect(self._on_picked)
        self.setFocusProxy(self._grid)

        self.set_value(value)

    # --- the value -----------------------------------------------------------------------

    @property
    def value(self) -> object:
        """The ISO string in `single`, or the `(start, end)` pair in `range`."""
        if self._mode == "range":
            return (iso(self._start), iso(self._end))
        return iso(self._selected)

    def set_value(self, value: DateLike | tuple[DateLike, DateLike]) -> None:
        """Take a value without emitting `value_changed`."""
        if self._mode == "range":
            pair = value if isinstance(value, tuple) else (value, None)
            self._start, self._end = as_date(pair[0]), as_date(pair[1])
            self._pending = self._start is not None and self._end is None
            anchor = self._start or self._end or datetime.date.today()
        else:
            self._selected = as_date(value if not isinstance(value, tuple) else value[0])
            anchor = self._selected or datetime.date.today()
        self._grid.set_selection(self._selected, self._start, self._end)
        self._grid.set_cursor(anchor)
        self.set_month(anchor.year, anchor.month)

    @property
    def mode(self) -> str:
        """`single` or `range`."""
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode if mode in ("single", "range") else "single"
        self._grid.set_mode(self._mode)

    def set_bounds(self, min: DateLike = None, max: DateLike = None) -> None:  # noqa: A002
        """The first and the last day a person may pick."""
        self._min, self._max = as_date(min), as_date(max)
        self._grid.set_bounds(self._min, self._max)

    def set_locale(self, locale: str) -> None:
        """Which day a week starts on: Monday everywhere but `en-US`."""
        self._locale = locale
        self._grid.set_locale(locale)

    # --- the month -----------------------------------------------------------------------

    def set_month(self, year: int, month: int) -> None:
        """Turn to a month."""
        self._grid.set_month(year, month)
        self._rebuild_caption()
        self.month_changed.emit(year, month)

    def step_month(self, delta: int) -> None:
        """A month forward or back."""
        moved = _add_months(datetime.date(self._grid.year, self._grid.month, 1), delta)
        self.set_month(moved.year, moved.month)

    def grid(self) -> MonthGrid:
        """The day grid, which holds the keyboard cursor."""
        return self._grid

    def _rebuild_caption(self) -> None:
        year, month = self._grid.year, self._grid.month
        self._month_select.blockSignals(True)
        self._year_select.blockSignals(True)
        self._month_select.set_items([(i + 1, name) for i, name in enumerate(MONTH_NAMES)])
        self._month_select.set_value(month)
        self._year_select.set_items(
            [(y, str(y)) for y in range(year - YEAR_SPAN, year + YEAR_SPAN + 1)]
        )
        self._year_select.set_value(year)
        self._month_select.blockSignals(False)
        self._year_select.blockSignals(False)

    def _on_month_pick(self, value: object) -> None:
        if value is not None:
            self.set_month(self._grid.year, int(value))

    def _on_year_pick(self, value: object) -> None:
        if value is not None:
            self.set_month(int(value), self._grid.month)

    # --- picking -------------------------------------------------------------------------

    def _on_picked(self, day: datetime.date) -> None:
        if self._mode == "range":
            if not self._pending or self._start is None:
                self._start, self._end, self._pending = day, None, True
            else:
                self._start, self._end = sorted((self._start, day))
                self._pending = False
            self._grid.set_selection(None, self._start, self._end)
        else:
            self._selected = day
            self._grid.set_selection(day, None, None)
        self.value_changed.emit(self.value)

    def handle_key(self, event: QKeyEvent) -> bool:
        """Take one key from a widget holding the focus above this one."""
        return self._grid.handle_key(event)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        if self._surface == "transparent":
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.theme.color("background"))
        painter.end()


def _add_months(day: datetime.date, delta: int) -> datetime.date:
    """The same day of the month `delta` months away, cut back to the month's last day."""
    total = (day.year * 12 + day.month - 1) + delta
    year, month = divmod(total, 12)
    month += 1
    last = _days_in(year, month)
    return datetime.date(year, month, min(day.day, last))


def _days_in(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day


def _point(event: QEvent) -> QPoint:
    """A mouse event's position, on either binding."""
    return event.position().toPoint() if hasattr(event, "position") else event.pos()
