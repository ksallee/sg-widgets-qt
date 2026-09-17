"""The calendar day the two date editors hand the Calendar primitive.

Ported from `packages/react/src/registry/sg/components/editor-calendar.ts`. The split and the
padding are core's; only the shape the primitive takes lives here, which is why this is not in
core: `primitives/calendar.py` picks a `datetime.date`, the API stores `YYYY-MM-DD`.

    calendar.set_value(to_calendar_date(value))
    day = from_calendar_date(picked)
"""
from __future__ import annotations

import datetime

from sg_widgets_core.edit import IsoDayParts, iso_day, iso_day_parts

__all__ = ["from_calendar_date", "to_calendar_date"]


def to_calendar_date(value: str | None) -> datetime.date | None:
    """`YYYY-MM-DD` as a calendar day, or None when the string is not one (field_types/date)."""
    parts = iso_day_parts(value)
    if parts is None:
        return None
    try:
        return datetime.date(parts.year, parts.month, parts.day)
    except ValueError:  # `2026-02-30` splits cleanly and is no day.
        return None


def from_calendar_date(value: datetime.date | None) -> str:
    """The picked day back as `YYYY-MM-DD`, or the empty string when nothing is picked."""
    if value is None:
        return ""
    return iso_day(IsoDayParts(year=value.year, month=value.month, day=value.day))
