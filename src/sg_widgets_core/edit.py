"""Input parsing and write serialisation.

Pure functions that turn what a person typed into the value Flow Production
Tracking accepts on a write, or say why it cannot. Every accepted and rejected
shape here was measured against a live site; each rule cites its card in the
sg-groundtruth corpus (`findings/field_types/<type>.md`).

A parse either yields a value or an error. It never raises and never guesses: an
editor that gets an error emits nothing and shows the message.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Union

from .render import (
    COLOR_SENTINEL,
    DurationOptions,
    TimecodeOptions,
    _as_finite_number,
    format_duration,
    format_timecode,
    locale_marks,
    parse_instant,
    zone_of,
)

__all__ = [
    "DateTimeOptions",
    "DurationParseOptions",
    "EDITOR_KIND",
    "EditorKind",
    "EditorPlacement",
    "FLOAT_PRECISION",
    "FloatParseOptions",
    "INT32_MAX",
    "INT32_MIN",
    "IntegerOptions",
    "IsoDayParts",
    "LocalDateTime",
    "NumberInputFormat",
    "NumberShape",
    "NumberSteps",
    "NumberStepsOptions",
    "ParseError",
    "ParseResult",
    "ParseValue",
    "StepOptions",
    "UrlWriteValue",
    "color_to_hex",
    "editor_kind_for",
    "editor_needs_context",
    "editor_placement_for",
    "format_number_input",
    "format_timecode_frames",
    "from_api_date_time",
    "is_editable_type",
    "is_parse_error",
    "is_valid_list_value",
    "iso_day",
    "iso_day_parts",
    "number_digits",
    "number_draft",
    "number_steps",
    "number_wire",
    "parse_color_input",
    "parse_duration_input",
    "parse_float_input",
    "parse_integer",
    "parse_number_input",
    "parse_text_input",
    "parse_timecode_input",
    "parse_url_input",
    "settle_step",
    "step_number",
    "stored_number",
    "time_zone_name",
    "to_api_date",
    "to_api_date_time",
    "to_api_float",
    "unformat_number_input",
]


@dataclass
class ParseValue:
    """A parse that yielded a value."""

    value: Any = None


@dataclass
class ParseError:
    """A parse that refused the input, with the message an editor shows."""

    error: str = ""


ParseResult = Union[ParseValue, ParseError]


def is_parse_error(result: ParseResult) -> bool:
    return isinstance(result, ParseError)


#: The column behind `number`, `percent`, `duration` and `timecode` is a signed
#: 32-bit integer; one past either end is a 400 (field_types/number, percent, timecode).
INT32_MIN = -2147483648
INT32_MAX = 2147483647

#: Decimals a `float` keeps. Rounding happens on write, at 200 and without warning (field_types/float).
FLOAT_PRECISION = 6

_OUT_OF_RANGE = f"Out of range: whole numbers from {INT32_MIN} to {INT32_MAX}."

_MAX_SAFE_INTEGER = 2 ** 53 - 1

# --- text --------------------------------------------------------------------


def parse_text_input(raw: str) -> ParseResult:
    """Free text.

    Both ends are stripped on write and an empty string is stored as null, so there
    is no "set but blank" state to preserve (field_types/text).
    """
    trimmed = raw.strip()
    return ParseValue(None if len(trimmed) == 0 else trimmed)


# --- numbers -----------------------------------------------------------------


@dataclass
class IntegerOptions:
    min: int | None = None
    max: int | None = None


def parse_integer(raw: str, options: IntegerOptions | None = None) -> ParseResult:
    """A whole number for `number`, `percent` and `timecode`.

    A decimal is refused rather than rounded, matching the API: `number` and
    `percent` 400 on a Float and `timecode` takes `[Integer, NilClass]` alone
    (field_types/number, percent, timecode). Empty input clears the field.
    """
    o = options if options is not None else IntegerOptions()
    text = raw.strip()
    if len(text) == 0:
        return ParseValue(None)
    if not re.fullmatch(r"[+-]?\d+", text):
        return ParseError("Whole numbers only." if re.fullmatch(r"[+-]?\d*\.\d*", text) else "Not a number.")
    n = int(text)
    minimum = o.min if o.min is not None else INT32_MIN
    maximum = o.max if o.max is not None else INT32_MAX
    if abs(n) > _MAX_SAFE_INTEGER:
        return ParseError(_OUT_OF_RANGE)
    if n < minimum or n > maximum:
        if minimum == INT32_MIN and maximum == INT32_MAX:
            return ParseError(_OUT_OF_RANGE)
        return ParseError(f"Out of range: {minimum} to {maximum}.")
    return ParseValue(n)


@dataclass
class FloatParseOptions:
    #: Decimals to keep. Defaults to the six the store itself keeps (field_types/float).
    precision: int | None = None


def parse_float_input(raw: str, options: FloatParseOptions | None = None) -> ParseResult:
    """A decimal for `float`.

    The store rounds to six decimals on write, so the parse rounds too and the value
    a caller emits is the value that comes back (field_types/float). Empty input
    clears the field.
    """
    o = options if options is not None else FloatParseOptions()
    text = raw.strip()
    if len(text) == 0:
        return ParseValue(None)
    if not re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", text):
        return ParseError("Not a number.")
    try:
        n = float(text)
    except ValueError:
        return ParseError("Not a number.")
    if not math.isfinite(n):
        return ParseError("Not a number.")
    precision = o.precision if o.precision is not None else FLOAT_PRECISION
    return ParseValue(_round(n, precision))


def _round(n: float, decimals: int) -> float:
    factor = 10 ** decimals
    return math.floor(n * factor + 0.5) / factor


def to_api_float(value: float | None) -> str | None:
    """The wire form of a float.

    An Integer is refused on write and inside a filter, so a whole value has to
    carry a decimal point; JSON has no way to write one, so the value goes as the
    numeric string the API also accepts (field_types/float).
    """
    if value is None or not math.isfinite(value):
        return None
    text = _number_text(value)
    return text if ("." in text or "e" in text or "E" in text) else f"{text}.0"


def _number_text(value: float) -> str:
    """A number the way JavaScript spells it: no trailing `.0` on a whole value."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if math.isfinite(value) and float(value).is_integer() and abs(value) < 1e21:
        return str(int(value))
    return repr(float(value))


@dataclass
class DurationParseOptions:
    #: The site's `hours_per_day` from `GET /preferences`, for the `d` unit. Default 8.
    hours_per_day: float | None = None


_DURATION_PART = re.compile(
    r"([+-]?\d+(?:\.\d+)?)\s*(days?|d|hours?|hrs?|h|minutes?|mins?|m)(?![^\W\d_])",
    re.IGNORECASE | re.UNICODE,
)

_CLOCK = re.compile(r"^([+-]?)(\d+):([0-5]?\d)$")


def parse_duration_input(raw: str, options: DurationParseOptions | None = None) -> ParseResult:
    """A duration, in whole minutes.

    The stored integer is minutes and no schema names the unit, so the accepted
    spellings are the client's own: a bare number is minutes, `1h 30m`, `1.5h` and
    `2d` scale by the site's working day, and `1:30` is hours and minutes. The API
    itself takes only something that parses as a number, so `"1h 30m"` never leaves
    this function (field_types/duration).
    """
    o = options if options is not None else DurationParseOptions()
    text = raw.strip()
    if len(text) == 0:
        return ParseValue(None)
    hours_per_day = o.hours_per_day if o.hours_per_day is not None else 8

    clock = _CLOCK.match(text)
    if clock:
        sign = -1 if clock.group(1) == "-" else 1
        return _bounded(sign * (int(clock.group(2)) * 60 + int(clock.group(3))))

    if re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", text):
        return _bounded(math.floor(float(text) + 0.5))

    # Spacing is free: `1h 30m` and `1h30m` are the same input.
    compact = re.sub(r"\s+", "", text, flags=re.UNICODE)
    minutes = 0.0
    consumed = 0
    for m in _DURATION_PART.finditer(compact):
        amount = float(m.group(1))
        unit = m.group(2).lower()[0]
        minutes += amount * (60 * hours_per_day if unit == "d" else 60 if unit == "h" else 1)
        consumed += len(m.group(0))
    # Every character has to belong to a part, so `1h banana` is refused rather than read as 1h.
    if consumed == 0 or consumed != len(compact):
        return ParseError("Not a duration. Try 90, 1h 30m, 1.5h or 2d.")
    return _bounded(math.floor(minutes + 0.5))


def _bounded(minutes: int) -> ParseResult:
    if minutes < INT32_MIN or minutes > INT32_MAX:
        return ParseError(_OUT_OF_RANGE)
    return ParseValue(minutes)


_TIMECODE = re.compile(r"^([+-]?)(\d+):([0-5]\d):([0-5]\d)(?:[:;](\d+))?$")


def parse_timecode_input(raw: str, options: TimecodeOptions | None = None) -> ParseResult:
    """A timecode, in milliseconds.

    The stored integer is milliseconds: `1000` renders as one whole second in the
    server's own `_summarize` grouping. The field rejects every timecode string,
    including the drop-frame spelling, so the conversion is the client's
    (field_types/timecode). Empty input clears the field.
    """
    o = options if options is not None else TimecodeOptions()
    text = raw.strip()
    if len(text) == 0:
        return ParseValue(None)

    if re.fullmatch(r"[+-]?\d+", text):
        return parse_integer(text)

    m = _TIMECODE.match(text)
    if not m:
        return ParseError("Not a timecode. Try HH:MM:SS, HH:MM:SS:FF or milliseconds.")
    sign = -1 if m.group(1) == "-" else 1
    ms = (int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))) * 1000
    frames = m.group(5)
    if frames is not None:
        rate = o.frame_rate
        if rate is None or not rate > 0:
            return ParseError("Frames need a frame rate.")
        f = int(frames)
        if f >= rate:
            return ParseError(f"Frames run 0 to {math.ceil(rate) - 1} at {_number_text(rate)} fps.")
        ms += math.floor(f / rate * 1000 + 0.5)
    total = sign * ms
    if total < INT32_MIN or total > INT32_MAX:
        return ParseError(_OUT_OF_RANGE)
    return ParseValue(total)


def format_timecode_frames(ms: float, frame_rate: float) -> str:
    """Milliseconds as `HH:MM:SS:FF`, for putting a stored timecode back in an input."""
    return format_timecode(ms, TimecodeOptions(frame_rate=frame_rate))


# --- stepping ----------------------------------------------------------------


@dataclass
class NumberSteps:
    """The bounds and the amount one step moves, for one numeric data type."""

    step: float
    min: int | None = None
    max: int | None = None


@dataclass
class NumberStepsOptions:
    #: Frames per second. A timecode steps one frame when it is known, one second when it is not.
    frame_rate: float | None = None


def number_steps(data_type: str, options: NumberStepsOptions | None = None) -> NumberSteps:
    """The step and the bounds a numeric data type takes when the caller names none.

    A percent runs 0 to 100 because that is the scale it is read on; the column
    itself clamps nothing, so a caller with out-of-scale data widens the bounds
    (field_types/percent). A duration steps a quarter of an hour, a timecode one
    frame, and a float a tenth.
    """
    o = options if options is not None else NumberStepsOptions()
    if data_type == "percent":
        return NumberSteps(step=1, min=0, max=100)
    if data_type == "float":
        return NumberSteps(step=0.1)
    if data_type == "currency":
        return NumberSteps(step=1)
    if data_type == "duration":
        return NumberSteps(step=15, min=INT32_MIN, max=INT32_MAX)
    if data_type == "timecode":
        rate = o.frame_rate
        frame = max(1, math.floor(1000 / rate + 0.5)) if rate is not None and rate > 0 else 1000
        return NumberSteps(step=frame, min=INT32_MIN, max=INT32_MAX)
    return NumberSteps(step=1, min=INT32_MIN, max=INT32_MAX)


@dataclass
class StepOptions:
    step: float
    #: Steps taken at once: ten with Shift, a hundred with Page Up and Page Down.
    multiplier: float | None = None
    min: float | None = None
    max: float | None = None


def _decimals_of(n: float) -> int:
    """Decimals a number is written with, capped at the six a float keeps."""
    if not math.isfinite(n):
        return 0
    text = _number_text(n)
    if "e" in text or "E" in text:
        return FLOAT_PRECISION
    dot = text.find(".")
    return 0 if dot == -1 else min(FLOAT_PRECISION, len(text) - dot - 1)


def settle_step(from_value: float | None, to: float, options: StepOptions) -> float:
    """Where a step lands: rounded to the decimals the step and the starting value
    carry, then clamped. The rounding is what keeps a tenth-sized step off
    `0.30000000000000004`."""
    decimals = max(_decimals_of(options.step), 0 if from_value is None else _decimals_of(from_value))
    settled = _round(to, decimals)
    minimum = options.min if options.min is not None else -math.inf
    maximum = options.max if options.max is not None else math.inf
    return min(maximum, max(minimum, settled))


def step_number(from_value: float | None, direction: Literal[1, -1], options: StepOptions) -> float:
    """The value one step away. An empty field lands on zero first, then steps."""
    if from_value is None:
        return settle_step(None, 0, options)
    multiplier = options.multiplier if options.multiplier is not None else 1
    return settle_step(from_value, from_value + options.step * multiplier * direction, options)


# --- locale numbers ----------------------------------------------------------


@dataclass
class NumberInputFormat:
    locale: str | None = None
    #: Exactly this many decimals, zeros kept.
    decimals: int | None = None


def format_number_input(value: float, options: NumberInputFormat | None = None) -> str:
    """A number written the way the locale writes it, for putting a stored value back in an input."""
    o = options if options is not None else NumberInputFormat()
    if not math.isfinite(value):
        return ""
    group, decimal = locale_marks(o.locale)
    places = o.decimals if o.decimals is not None else FLOAT_PRECISION
    text = f"{abs(value):.{places}f}"
    if o.decimals is None and "." in text:
        text = text.rstrip("0").rstrip(".")
    whole, _, frac = text.partition(".")
    marked = f"{int(whole):,}".replace(",", group)
    body = f"{marked}{decimal}{frac}" if frac else marked
    return f"-{body}" if value < 0 else body


def unformat_number_input(raw: str, locale: str | None = None) -> str:
    """The digits behind a locale-formatted number.

    Spacing and group marks dropped, the decimal mark turned into a point, so the
    parsers above read back what the formatter wrote. A comma is a group mark in
    every locale that does not spell its decimal with one.
    """
    group, decimal = locale_marks(locale)
    text = re.sub(r"[\s  ]", "", raw, flags=re.UNICODE)
    text = text.replace(group, "")
    if decimal != ",":
        text = text.replace(",", "")
    if decimal != ".":
        text = text.replace(decimal, ".")
    return text


# --- the numeric family ------------------------------------------------------


@dataclass
class NumberShape:
    """What the six numeric data types need beyond the type's own name: the site
    preferences a duration and a timecode read in, the decimals a float keeps, the
    bounds an integer is held to, and the locale a plain number is written in."""

    #: The site's `hours_per_day` from `GET /preferences`, for the `d` unit (field_types/duration).
    hours_per_day: float | None = None
    #: Frames per second, for the `HH:MM:SS:FF` form and the one-frame step (field_types/timecode).
    frame_rate: float | None = None
    #: Decimals kept on a float. The store itself keeps six (field_types/float).
    precision: int | None = None
    min: int | None = None
    max: int | None = None
    #: Locale the value is written in. Defaults to `en-US`.
    locale: str | None = None


#: The types whose input is a plain number, and so is written in the locale's marks.
_LOCALE_TYPES = ("number", "float", "percent", "currency")


def number_draft(value: Any, data_type: str, shape: NumberShape | None = None) -> str:
    """The stored value as the string an input shows. Each type round-trips through its own parse."""
    s = shape if shape is not None else NumberShape()
    if value is None or value == "":
        return ""
    n = _as_finite_number(value)
    if data_type in ("float", "currency"):
        if n is None:
            return str(value)
        return format_number_input(n, NumberInputFormat(locale=s.locale, decimals=s.precision))
    if data_type == "duration":
        # Hours and minutes, never days: a day rendering rounds and would not survive a
        # round trip through the parse. The working day is a parse unit only.
        return format_duration(n, DurationOptions())
    if data_type == "timecode":
        if s.frame_rate is None:
            return format_timecode(n)
        return format_timecode_frames(n, s.frame_rate)
    if n is None:
        return str(value)
    return format_number_input(n, NumberInputFormat(locale=s.locale))


def number_digits(raw: str, data_type: str, shape: NumberShape | None = None) -> str:
    """What the numeric parses read: the locale's group and decimal marks are undone first."""
    s = shape if shape is not None else NumberShape()
    if data_type not in _LOCALE_TYPES:
        return raw
    return unformat_number_input(raw, s.locale)


def parse_number_input(raw: str, data_type: str, shape: NumberShape | None = None) -> ParseResult:
    """One numeric input, through the parse its data type calls for."""
    s = shape if shape is not None else NumberShape()
    text = number_digits(raw, data_type, s)
    if data_type in ("float", "currency"):
        return parse_float_input(text, FloatParseOptions(precision=s.precision))
    if data_type == "duration":
        return parse_duration_input(text, DurationParseOptions(hours_per_day=s.hours_per_day))
    if data_type == "timecode":
        return parse_timecode_input(text, TimecodeOptions(frame_rate=s.frame_rate))
    return parse_integer(text, IntegerOptions(min=s.min, max=s.max))


def number_wire(parsed: float | None, data_type: str) -> float | str | None:
    """The wire value.

    A `float` goes as a decimal string because an Integer is refused on write and
    JSON cannot spell `2.0`; every other type is a bare number (field_types/float,
    number, percent, duration, timecode).
    """
    if parsed is None:
        return None
    return to_api_float(parsed) if data_type == "float" else parsed


def stored_number(value: float | str | None) -> float | None:
    """The stored value as the number the steppers and the spinbutton role work on."""
    if value is None or (isinstance(value, str) and value == ""):
        return None
    return _as_finite_number(value)


# --- dates -------------------------------------------------------------------

_DATE_ONLY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_TIME_ONLY = re.compile(r"^(\d{1,2}):([0-5]\d)(?::([0-5]\d))?$")


def to_api_date(raw: str) -> ParseResult:
    """A calendar date as `YYYY-MM-DD`, with no time and no zone.

    The API validates the date rather than only parsing it, and refuses every
    timestamp (field_types/date). Empty input clears the field.
    """
    text = raw.strip()
    if len(text) == 0:
        return ParseValue(None)
    m = _DATE_ONLY.match(text)
    if not m:
        return ParseError("Not a date. Use YYYY-MM-DD.")
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        datetime(year, month, day)
    except ValueError:
        return ParseError("No such day.")
    return ParseValue(text)


@dataclass
class IsoDayParts:
    """A calendar day, as the three numbers a calendar widget is built from."""

    year: int
    month: int
    day: int


def iso_day_parts(value: str | None) -> IsoDayParts | None:
    """`YYYY-MM-DD` as its three numbers, or None when the string is not one.

    The shape a calendar takes differs per toolkit, so only the split is shared.
    """
    m = _DATE_ONLY.match(str(value if value is not None else "").strip())
    if not m:
        return None
    return IsoDayParts(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))


def iso_day(parts: IsoDayParts) -> str:
    """The three numbers back as `YYYY-MM-DD`, zero-padded."""
    return f"{parts.year:04d}-{parts.month:02d}-{parts.day:02d}"


@dataclass
class DateTimeOptions:
    #: IANA zone the typed wall-clock time is read in. Defaults to UTC.
    time_zone: str | None = None


def to_api_date_time(date: str, time: str, options: DateTimeOptions | None = None) -> ParseResult:
    """A local wall-clock date and time as the UTC `YYYY-MM-DDTHH:MM:SSZ` the field stores.

    A written offset is normalised away and a zoneless string is taken as UTC, so
    the conversion has to happen here or the instant is wrong (field_types/date_time).
    Both parts empty clears the field; a date with no time is midnight local.
    """
    o = options if options is not None else DateTimeOptions()
    day = date.strip()
    clock = time.strip()
    if len(day) == 0 and len(clock) == 0:
        return ParseValue(None)
    parsed_day = to_api_date(day)
    if isinstance(parsed_day, ParseError):
        return parsed_day
    if parsed_day.value is None:
        return ParseError("A time needs a date.")

    hours = minutes = seconds = 0
    if len(clock) > 0:
        m = _TIME_ONLY.match(clock)
        if not m:
            return ParseError("Not a time. Use HH:MM.")
        hours = int(m.group(1))
        minutes = int(m.group(2))
        seconds = 0 if m.group(3) is None else int(m.group(3))
        if hours > 23:
            return ParseError("Not a time. Use HH:MM.")
    parts = iso_day_parts(parsed_day.value)
    if parts is None:
        return ParseError("Not a date. Use YYYY-MM-DD.")
    local = datetime(
        parts.year, parts.month, parts.day, hours, minutes, seconds, tzinfo=zone_of(o.time_zone)
    )
    utc = local.astimezone(timezone.utc)
    return ParseValue(utc.strftime("%Y-%m-%dT%H:%M:%SZ"))


@dataclass
class LocalDateTime:
    #: `YYYY-MM-DD` in the given zone.
    date: str
    #: `HH:MM` in the given zone.
    time: str
    #: `HH:MM:SS` in the given zone, for a value whose seconds matter.
    time_with_seconds: str


def from_api_date_time(value: str | None, options: DateTimeOptions | None = None) -> LocalDateTime | None:
    """The stored UTC instant as local wall-clock parts, for putting back in a date
    and a time input. The store is second-resolution UTC with a literal `Z`
    (field_types/date_time)."""
    o = options if options is not None else DateTimeOptions()
    if value is None or len(str(value).strip()) == 0:
        return None
    instant = parse_instant(str(value))
    if instant is None:
        return None
    local = instant.astimezone(zone_of(o.time_zone))
    return LocalDateTime(
        date=f"{local.year:04d}-{local.month:02d}-{local.day:02d}",
        time=f"{local.hour:02d}:{local.minute:02d}",
        time_with_seconds=f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}",
    )


def time_zone_name(time_zone: str | None = None) -> str:
    """The zone a wall-clock input is read in, named for the line under a date-time field.

    With no zone named it is the running process's own zone, which the standard
    library spells as an abbreviation rather than an IANA name.
    """
    if time_zone is not None:
        return time_zone
    try:
        name = datetime.now().astimezone().tzname()
    except Exception:
        return "UTC"
    return name if name else "UTC"


# --- list --------------------------------------------------------------------


def is_valid_list_value(valid_values: list[str] | tuple[str, ...] | None, value: str) -> bool:
    """A value is legal only if it is in `valid_values`, byte for byte.

    A write is case-sensitive and a trailing space is a 400, while a filter on the
    same string matches (field_types/list).
    """
    return value in (valid_values if valid_values is not None else ())


# --- url ---------------------------------------------------------------------


@dataclass
class UrlWriteValue:
    """The web-link write shape: a map holding `url`, optionally `name` (field_types/url)."""

    url: str
    name: str | None = None


def parse_url_input(url: str, name: str = "") -> ParseResult:
    """A web link for a `url` field.

    The only accepted input is a map holding `url`: a bare string 400s, `{}` 400s,
    and the url itself is validated, a raw space being the one character measured to
    fail. With no `name` the field reads back the whole url as its name
    (field_types/url).
    """
    href = url.strip()
    label = name.strip()
    if len(href) == 0:
        return ParseValue(None) if len(label) == 0 else ParseError("A name needs a link.")
    if re.search(r"\s", href, flags=re.UNICODE):
        return ParseError("No spaces in a link. Percent-encode them.")
    return ParseValue(UrlWriteValue(url=href) if len(label) == 0 else UrlWriteValue(url=href, name=label))


# --- colour ------------------------------------------------------------------

_HEX = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$", re.IGNORECASE)
_TRIPLE = re.compile(r"^(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})$")


def parse_color_input(raw: str) -> ParseResult:
    """A colour as the decimal `r,g,b` the field stores, with no spaces and no `#`.

    Hex is rejected on write, so it is converted here; spaces inside the triple are
    rejected too, so they are stripped (field_types/color). The pipeline-step token
    passes through.
    """
    text = raw.strip()
    if len(text) == 0:
        return ParseValue(None)
    if text.lower() == COLOR_SENTINEL:
        return ParseValue(COLOR_SENTINEL)

    hex_match = _HEX.match(text)
    if hex_match:
        digits = hex_match.group(1)
        full = "".join(d + d for d in digits) if len(digits) == 3 else digits
        channels = [int(full[i:i + 2], 16) for i in (0, 2, 4)]
        return ParseValue(",".join(str(c) for c in channels))

    triple = _TRIPLE.match(text)
    if not triple:
        return ParseError("Not a colour. Use r,g,b or a hex code.")
    channels = [int(triple.group(i)) for i in (1, 2, 3)]
    if any(c > 255 for c in channels):
        return ParseError("Each channel runs 0 to 255.")
    return ParseValue(",".join(str(c) for c in channels))


def color_to_hex(value: str | None) -> str | None:
    """A stored `r,g,b` as `#rrggbb`, for a colour input. None for the sentinel and for anything else."""
    if not value or value == COLOR_SENTINEL:
        return None
    triple = _TRIPLE.match(str(value).strip())
    if not triple:
        return None
    channels = [int(triple.group(i)) for i in (1, 2, 3)]
    if any(c > 255 for c in channels):
        return None
    return "#" + "".join(f"{c:02x}" for c in channels)


# --- dispatch ----------------------------------------------------------------

EditorKind = Literal[
    "text", "number", "checkbox", "date", "date_time", "list",
    "url", "color", "status_list", "entity", "multi_entity", "none",
]

EDITOR_KIND: dict[str, EditorKind] = {
    "text": "text",
    "entity_type": "text",
    "uuid": "text",
    "number": "number",
    "float": "number",
    "percent": "number",
    "duration": "number",
    "timecode": "number",
    "currency": "number",
    "footage": "number",
    "checkbox": "checkbox",
    "date": "date",
    "date_time": "date_time",
    "list": "list",
    "url": "url",
    "color": "color",
    "status_list": "status_list",
    "entity": "entity",
    "multi_entity": "multi_entity",
}


def editor_kind_for(data_type: str) -> EditorKind:
    """The editor for a data type.

    The read-only types and the ones REST cannot write have no editor at all
    (field_types/calculated, summary, pivot_column).
    """
    return EDITOR_KIND.get(data_type, "none")


#: The three kinds a picker widget owns; each needs a context to read through.
_PICKER_KINDS = frozenset(("status_list", "entity", "multi_entity"))


def editor_needs_context(data_type: str) -> bool:
    """True when the editor for a data type reads the API, so the caller has to hand it a context.

    A status picker reads the schema and the Status table; an entity picker searches.
    """
    return editor_kind_for(data_type) in _PICKER_KINDS


def is_editable_type(data_type: str) -> bool:
    """True when a data type can be edited by one of these widgets."""
    return editor_kind_for(data_type) != "none"


EditorPlacement = Literal["inline", "popover"]

#: Kinds that stay in the cell. A checkbox is one press, and a status, a list or a
#: single entity opens a popup of its own, so a second surface around them adds nothing.
_INLINE_KINDS = frozenset(("checkbox", "none"))


def editor_placement_for(data_type: str) -> EditorPlacement:
    """Where the editor for a data type opens when the caller names no placement.

    Every editor takes the room a popover has; a checkbox is one press and stays in
    the cell.
    """
    return "inline" if editor_kind_for(data_type) in _INLINE_KINDS else "popover"
