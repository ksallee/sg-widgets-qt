"""A `date_time` field, shown local and stored UTC.

Ported from `packages/react/src/registry/sg/components/date-time-editor.tsx`.

    editor = DateTimeEditor(value="2026-03-04T13:06:07Z", time_zone="America/Los_Angeles")
    editor.committed.connect(write)

The store is UTC `YYYY-MM-DDTHH:MM:SSZ`: a written offset is normalised away and a zoneless string
is taken as UTC, not as site-local, so the wall-clock time typed here is converted before it is
emitted and converted back to show (field_types/date_time). The zone that conversion uses is named
under the trigger.

One anatomy everywhere: a trigger carrying the stored instant, over a popover holding the typed day,
the calendar and the time. `inline` only sizes the trigger to its value and drops the zone line.
"""
from __future__ import annotations

import datetime
from typing import Callable

from qtpy import QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.edit import (
    DateTimeOptions,
    from_api_date_time,
    time_zone_name,
    to_api_date_time,
)
from sg_widgets_core.schema import FieldSchema

from ..primitives.calendar import Calendar
from ..primitives.input import Input
from ..primitives.popover import Popover
from .date_editor import DateTrigger, date_popover_panel
from .editor_calendar import from_calendar_date, to_calendar_date
from .value_editor import EditorNote, ValueEditor, ValueSession, fade_disabled

__all__ = ["DateTimeEditor"]

#: What the time input takes, with and without the seconds the store keeps.
TIME_PLACEHOLDER = "HH:MM"
TIME_PLACEHOLDER_SECONDS = "HH:MM:SS"


class DateTimeEditor(ValueEditor):
    """A `date_time` field."""

    #: The calendar opened or closed.
    open_changed = Signal(bool)

    def __init__(
        self,
        value: str | None = None,
        field: FieldSchema | None = None,
        time_zone: str | None = None,
        show_seconds: bool = False,
        hint: bool = True,
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
            "date-time-editor",
            size=size,
            inline=inline,
            error_message=error_message,
            parent=parent,
        )
        self._time_zone = time_zone
        self._show_seconds = bool(show_seconds)
        self._hint = bool(hint)

        self.use_session(
            ValueSession(
                value,
                format=self._format,
                parse=self._parse,
                same=lambda a, b: a == b,
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

    # --- the two halves ------------------------------------------------------------------

    def _zone_options(self) -> DateTimeOptions:
        return DateTimeOptions(time_zone=self._time_zone)

    def _format(self, stored: str | None) -> dict:
        local = from_api_date_time(stored, self._zone_options())
        if local is None:
            return {"date": "", "time": ""}
        return {
            "date": local.date,
            "time": local.time_with_seconds if self._show_seconds else local.time,
        }

    def _parse(self, draft: dict):
        return to_api_date_time(
            str(draft.get("date", "")), str(draft.get("time", "")), self._zone_options()
        )

    # --- the parts -----------------------------------------------------------------------

    def _build(self) -> None:
        self._trigger = DateTrigger(size=self.size, parent=self)
        self._trigger.setObjectName("date-time-editor-trigger")
        self._trigger.clicked.connect(self.toggle)
        self.add_control(self._trigger)

        panel = date_popover_panel()
        self._day = Input(placeholder="YYYY-MM-DD", size=self.size, parent=panel)
        self._day.setObjectName("date-time-editor-date")
        self._session.bind(self._day, "date")
        panel.layout().addWidget(self._day)

        self._calendar = Calendar(surface="transparent", parent=panel)
        self._calendar.setObjectName("date-time-editor-calendar")
        self._calendar.grid().picked.connect(self._pick)
        panel.layout().addWidget(self._calendar)

        self._time = Input(placeholder=self._time_placeholder(), size=self.size, parent=panel)
        self._time.setObjectName("date-time-editor-time")
        self._session.bind(self._time, "time")
        panel.layout().addWidget(self._time)

        self._popover = Popover(self._trigger, panel, side="bottom", align="start")
        self._popover.opened.connect(self._on_opened)
        self._popover.closed.connect(lambda: self.open_changed.emit(False))

        self._zone_line = EditorNote("", parent=self)
        self._zone_line.setObjectName("date-time-editor-zone")
        self.add_control(self._zone_line)

        self._session.entered.connect(self._on_enter)
        self._session.escaped.connect(self._on_escape)
        self._session.committed.connect(lambda _value: self._refresh())
        self._session.draft_changed.connect(self._on_draft)

    def _time_placeholder(self) -> str:
        return TIME_PLACEHOLDER_SECONDS if self._show_seconds else TIME_PLACEHOLDER

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

    # A picked day leaves the popover open: the time is the other half of the value.
    def _pick(self, day: datetime.date) -> None:
        draft = dict(self._session.draft)
        draft["date"] = from_calendar_date(day)
        self._session.commit(draft)

    def _on_draft(self, draft: object) -> None:
        if isinstance(draft, dict):
            self._calendar.set_value(to_calendar_date(str(draft.get("date", ""))))

    # --- props ---------------------------------------------------------------------------

    @property
    def value(self) -> str | None:
        """The stored instant, UTC at second resolution (field_types/date_time)."""
        return self._session.value

    def set_value(self, value: str | None) -> None:
        self._session.set_value(value)
        self._refresh()

    @property
    def time_zone(self) -> str | None:
        """IANA zone the typed wall-clock time is read in."""
        return self._time_zone

    def set_time_zone(self, value: str | None) -> None:
        self._time_zone = value
        self._session.reset()
        self._refresh()

    @property
    def show_seconds(self) -> bool:
        """Seconds in the time input. The store keeps them; most fields do not need them."""
        return self._show_seconds

    def set_show_seconds(self, value: bool) -> None:
        self._show_seconds = bool(value)
        self._time.setPlaceholderText(self._time_placeholder())
        self._session.reset()
        self._refresh()

    @property
    def hint(self) -> bool:
        """Name the zone under the trigger."""
        return self._hint

    def set_hint(self, value: bool) -> None:
        self._hint = bool(value)
        self._refresh()

    @property
    def zone_name(self) -> str:
        """The zone the typed time is read in, as the line under the trigger names it."""
        return time_zone_name(self._time_zone)

    @property
    def trigger(self) -> DateTrigger:
        """The control the popover hangs off."""
        return self._trigger

    @property
    def date_input(self) -> Input:
        """The typed day inside the popover."""
        return self._day

    @property
    def time_input(self) -> Input:
        """The typed time inside the popover."""
        return self._time

    @property
    def calendar(self) -> Calendar:
        """The month grid inside the popover."""
        return self._calendar

    @property
    def label(self) -> str:
        """What the trigger shows: the stored instant in the zone, or the empty string."""
        local = from_api_date_time(self._session.value, self._zone_options())
        if local is None:
            return ""
        return f"{local.date} {local.time_with_seconds if self._show_seconds else local.time}"

    def _refresh(self) -> None:
        # The trigger reads the stored instant, so it answers a commit and never a draft.
        self._trigger.set_text(self.label)
        self._on_draft(self._session.draft)
        self._zone_line.set_text(
            "" if self.inline or not self._hint else f"Local time in {self.zone_name}, stored as UTC."
        )

    # --- hooks ---------------------------------------------------------------------------

    def _apply_size(self, size: str) -> None:
        self._trigger.set_size_step(size)
        self._day.set_size(size)
        self._time.set_size(size)

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
        for control in (self._day, self._time):
            control.setReadOnly(self.readonly)
            control.set_invalid(self.reads_invalid)
            fade_disabled(control)
        trigger.setAccessibleName(self.field_name() or "Pick a date and time")
        if self.readonly or not self.isEnabled():
            self.set_open(False)
