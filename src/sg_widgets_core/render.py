"""Display formatting.

Pure functions that turn a raw Flow Production Tracking attribute value into the
string a widget shows. No framework, no Qt, no locale guessing beyond `LOCALES`.

Every value shape here is what the API actually returns, taken from the
sg-groundtruth corpus (`findings/field_types/<type>.md`); each rule cites its card.

`Intl.DateTimeFormat` and `Intl.NumberFormat` have no equal in the standard
library, so `LOCALES` holds the medium date pattern, the short time pattern and
the decimal and group marks of the five locales this port carries. A locale
outside the table formats as `en-US`. `time_zone` resolves through `zoneinfo`; on
a system with no tz database every zone resolves to UTC.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import quote, unquote

try:  # A build without the tz database resolves every zone to UTC.
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - 3.9 without the backport
    ZoneInfo = None  # type: ignore[assignment]

__all__ = [
    "COLOR_SENTINEL",
    "DEFAULT_LOCALE",
    "DateOptions",
    "DurationOptions",
    "FieldTextOptions",
    "FloatOptions",
    "LOCALES",
    "Locale",
    "LocalPaths",
    "LocalPlatform",
    "NAME_HUES",
    "RENDER_KIND",
    "RenderKind",
    "THUMBNAIL_PENDING_PATH",
    "TimecodeOptions",
    "UrlLinkInfo",
    "UrlValue",
    "current_platform",
    "field_text",
    "file_href",
    "file_name_from_url",
    "format_currency",
    "format_date",
    "format_date_time",
    "format_duration",
    "format_float",
    "format_percent",
    "format_timecode",
    "image_state",
    "initials_of",
    "is_empty_value",
    "locale_for",
    "locale_marks",
    "name_color_index",
    "name_hue",
    "render_kind_for",
    "url_link",
    "zone_of",
]

RenderKind = Literal[
    "text", "number", "date", "datetime", "entity", "multi_entity",
    "status", "image", "checkbox", "url", "color", "list", "empty",
]

RENDER_KIND: dict[str, RenderKind] = {
    # A plain string in the row; "" is never stored, so null is the only empty (field_types/text).
    "text": "text",
    # Bare integers and decimal strings; `float` arrives quoted (field_types/number, float).
    "number": "number",
    "float": "number",
    "percent": "number",
    "duration": "number",
    "timecode": "number",
    "currency": "number",
    "footage": "number",
    # Two-state, never null (field_types/checkbox).
    "checkbox": "checkbox",
    # "YYYY-MM-DD" with no zone; "YYYY-MM-DDTHH:MM:SSZ" always UTC (field_types/date, date_time).
    "date": "date",
    "date_time": "datetime",
    # One bare string out of `valid_values` (field_types/list).
    "list": "list",
    # A bare code; the label lives in `display_values` (field_types/status_list).
    "status_list": "status",
    # A bare schema type name (field_types/entity_type).
    "entity_type": "text",
    # Decimal "r,g,b", or the sentinel `pipeline_step` (field_types/color).
    "color": "color",
    "uuid": "text",
    # `{type, id, name}`, `name` being `cached_display_name` (field_types/entity).
    "entity": "entity",
    # A list of those, never null (field_types/multi_entity).
    "multi_entity": "multi_entity",
    "tag_list": "multi_entity",
    # A presigned URL string, re-signed on every read (field_types/image).
    "image": "image",
    # A map whose keys depend on `link_type`, or a bare string (field_types/url).
    "url": "url",
    "jsonb": "text",
    "serializable": "text",
    # Live rollups: whatever the site computed, shown as text (field_types/calculated, summary).
    "calculated": "text",
    "summary": "text",
    # A seven-asterisk mask on every row; show it as the text it is (field_types/password).
    "password": "text",
    # No REST implementation at all: null on every row (field_types/pivot_column).
    "pivot_column": "empty",
}


def render_kind_for(data_type: str) -> RenderKind:
    """The rendering a data type needs. Unknown types fall back to text."""
    return RENDER_KIND.get(data_type, "text")


# --- locales -----------------------------------------------------------------

_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTHS_FR = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)


@dataclass(frozen=True)
class Locale:
    """One locale's patterns and number marks.

    `date` is the `dateStyle: 'medium'` pattern and `time` the `timeStyle: 'short'`
    one, in the tokens `YYYY`, `MMM`, `MM`, `DD`, `D`, `HH`, `H`, `hh`, `h`, `mm`
    and `A`. `date_time` joins the two through `{date}` and `{time}`.
    """

    date: str
    time: str
    date_time: str
    decimal: str
    group: str
    months: tuple[str, ...] = _MONTHS_EN


DEFAULT_LOCALE = "en-US"

LOCALES: dict[str, Locale] = {
    "en-US": Locale(date="MMM D, YYYY", time="h:mm A", date_time="{date}, {time}", decimal=".", group=","),
    "en-GB": Locale(date="D MMM YYYY", time="HH:mm", date_time="{date}, {time}", decimal=".", group=","),
    "fr-FR": Locale(
        date="D MMM YYYY", time="HH:mm", date_time="{date}, {time}",
        decimal=",", group=" ", months=_MONTHS_FR,
    ),
    "de-DE": Locale(date="DD.MM.YYYY", time="HH:mm", date_time="{date}, {time}", decimal=",", group="."),
    "ja-JP": Locale(date="YYYY/MM/DD", time="H:mm", date_time="{date} {time}", decimal=".", group=","),
}


def locale_for(locale: str | None) -> Locale:
    """The patterns of a locale. A locale outside the table formats as `en-US`."""
    return LOCALES.get(locale or DEFAULT_LOCALE, LOCALES[DEFAULT_LOCALE])


def locale_marks(locale: str | None) -> tuple[str, str]:
    """The group and decimal marks a locale writes numbers with."""
    loc = locale_for(locale)
    return loc.group, loc.decimal


def zone_of(time_zone: str | None) -> tzinfo:
    """An IANA zone; the runtime's own zone when unnamed, as `Intl` defaults; UTC for a name the tz database lacks."""
    if time_zone is None:
        return datetime.now().astimezone().tzinfo or timezone.utc
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(time_zone)
    except Exception:
        return timezone.utc


_TOKEN = re.compile(r"YYYY|MMM|MM|DD|D|HH|H|hh|h|mm|A")


def _render_pattern(pattern: str, moment: datetime, loc: Locale) -> str:
    hour12 = moment.hour % 12 or 12
    values = {
        "YYYY": f"{moment.year:04d}",
        "MMM": loc.months[moment.month - 1],
        "MM": f"{moment.month:02d}",
        "DD": f"{moment.day:02d}",
        "D": str(moment.day),
        "HH": f"{moment.hour:02d}",
        "H": str(moment.hour),
        "hh": f"{hour12:02d}",
        "h": str(hour12),
        "mm": f"{moment.minute:02d}",
        "A": "AM" if moment.hour < 12 else "PM",
    }
    return _TOKEN.sub(lambda m: values[m.group(0)], pattern)


# --- field text --------------------------------------------------------------


@dataclass
class FieldTextOptions:
    #: The site's `hours_per_day`; a duration then renders in days (field_types/duration).
    hours_per_day: float | None = None
    locale: str | None = None
    #: IANA zone a `date_time` is shown in. Defaults to UTC, which is what the store holds.
    time_zone: str | None = None
    #: Frames a second, for a timecode. Given, a timecode gains its frame digits (field_types/timecode).
    frame_rate: float | None = None
    #: Decimals kept on a float or a currency.
    decimals: int | None = None
    currency_symbol: str | None = None
    #: The status field's `display_values`, the only source of a status label (field_types/status_list).
    display_values: dict[str, str] | None = None
    #: Between the names of a multi_entity value.
    separator: str | None = None


def field_text(value: Any, data_type: str, options: FieldTextOptions | None = None) -> str:
    """Any value as one line of text.

    The renderings a widget usually draws with a control of its own, a status
    badge, a thumbnail, a chip, come back as their plain label, so a compact
    surface can show them as text and a caller can copy or export them.
    """
    o = options if options is not None else FieldTextOptions()
    kind = render_kind_for(data_type)
    if kind == "checkbox":
        return "Yes" if value is True else "No"
    if kind == "empty" or is_empty_value(value):
        return ""
    if kind == "number":
        return _number_text(value, data_type, o)
    if kind == "date":
        return format_date(str(value), DateOptions(locale=o.locale))
    if kind == "datetime":
        return format_date_time(str(value), DateOptions(locale=o.locale, time_zone=o.time_zone))
    if kind == "entity":
        return _entity_text(value)
    if kind == "multi_entity":
        return (o.separator if o.separator is not None else ", ").join(_entity_text(v) for v in value)
    if kind == "status":
        return (o.display_values or {}).get(str(value), str(value))
    if kind == "image":
        return file_name_from_url(str(value))
    if kind == "url":
        link = url_link(value)
        return link.label if link is not None else ""
    if kind == "color":
        return "pipeline step" if str(value) == COLOR_SENTINEL else str(value)
    return str(value)


def _entity_text(ref: Any) -> str:
    """The shape an entity link reads back as: `{type, id, name}` (field_types/entity)."""
    name = ref.get("name") if isinstance(ref, dict) else getattr(ref, "name", None)
    if isinstance(name, str) and len(name) > 0:
        return name
    type_ = ref.get("type") if isinstance(ref, dict) else getattr(ref, "type", None)
    id_ = ref.get("id") if isinstance(ref, dict) else getattr(ref, "id", None)
    return f"{type_} #{id_}"


def _number_text(value: Any, data_type: str, o: FieldTextOptions) -> str:
    if data_type == "duration":
        return format_duration(_as_number(value), DurationOptions(hours_per_day=o.hours_per_day))
    if data_type == "percent":
        return format_percent(value)
    if data_type == "timecode":
        return format_timecode(_as_number(value), TimecodeOptions(frame_rate=o.frame_rate))
    if data_type == "currency":
        return format_currency(value, symbol=o.currency_symbol, decimals=o.decimals, locale=o.locale)
    if data_type == "float":
        return format_float(value, FloatOptions(decimals=o.decimals))
    return str(value)


def is_empty_value(value: Any) -> bool:
    """True when there is nothing to show.

    `0`, `False` and `"0"` are values, not emptiness: a `number` holding 0 is
    `is_not None` on the server too (field_types/number, percent, duration).
    """
    if value is None:
        return True
    if isinstance(value, str):
        return len(value) == 0
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return False


# --- numbers -----------------------------------------------------------------


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_fixed(n: float, decimals: int) -> str:
    """A number at exactly `decimals` places, ties away from zero."""
    try:
        quantum = Decimal(1).scaleb(-decimals)
        return str(Decimal(n).quantize(quantum, rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, OverflowError):
        return str(n)


@dataclass
class DurationOptions:
    #: The site's `hours_per_day` from `GET /preferences`. Given, the duration is
    #: rendered in days, which is what a site with `duration_units: "days"` expects.
    #: The field schema names no unit; only the site does (field_types/duration).
    hours_per_day: float | None = None


def format_duration(minutes: float | None, options: DurationOptions | None = None) -> str:
    """A stored duration is a whole number of minutes (field_types/duration)."""
    o = options if options is not None else DurationOptions()
    if minutes is None or not math.isfinite(minutes):
        return ""
    sign = "-" if minutes < 0 else ""
    abs_minutes = abs(minutes)
    hours_per_day = o.hours_per_day
    if hours_per_day is not None and hours_per_day > 0:
        return f"{sign}{_trim_decimals(_to_fixed(abs_minutes / (60 * hours_per_day), 2))}d"
    hours = math.floor(abs_minutes / 60)
    rest = _js_round(abs_minutes % 60)
    return f"{sign}{hours}:{rest:02d}"


def format_percent(value: float | str | None) -> str:
    """A percent is a bare integer on a 0-100 scale, and nothing is clamped: -1 and
    1000 both store at 200, so render what is there (field_types/percent)."""
    if is_empty_value(value):
        return ""
    n = _as_number(value)
    if n is None or not math.isfinite(n):
        return f"{value}"
    return f"{_trim_decimals(_number_string(n))}%"


@dataclass
class TimecodeOptions:
    #: Frames a second, for the `HH:MM:SS:FF` form. No schema property and no
    #: preference names the rate, so it comes from the app; solving it out of a
    #: `_summarize` grouping gives 23.976 on the probed site (field_types/timecode).
    frame_rate: float | None = None


def format_timecode(ms: float | None, options: TimecodeOptions | None = None) -> str:
    """A timecode is milliseconds in a signed 32-bit integer.

    Nothing wraps at 24 hours and negatives are stored, so hours are not clamped
    either (field_types/timecode). Without a frame rate the frame digits are left
    off; with one they are the sub-second remainder rounded to the nearest frame,
    which is how the server renders it.
    """
    o = options if options is not None else TimecodeOptions()
    if ms is None or not math.isfinite(ms):
        return ""
    sign = "-" if ms < 0 else ""
    abs_ms = abs(ms)
    total = math.floor(abs_ms / 1000)
    parts = [math.floor(total / 3600), math.floor((total % 3600) / 60), total % 60]
    rate = o.frame_rate
    if rate is not None and rate > 0:
        parts.append(min(math.ceil(rate) - 1, _js_round((abs_ms % 1000) / 1000 * rate)))
    return sign + ":".join(f"{int(p):02d}" for p in parts)


@dataclass
class FloatOptions:
    #: Decimals to keep at most; trailing zeros are dropped. The store itself rounds to 6 (field_types/float).
    max_decimals: int | None = None
    #: Exactly this many decimals, zeros kept. Wins over `max_decimals`.
    decimals: int | None = None


def format_currency(
    value: float | str | None,
    symbol: str | None = None,
    decimals: int | None = None,
    locale: str | None = None,
) -> str:
    """A currency amount with its symbol.

    There is no corpus card for `currency`; the read shape is treated as a decimal
    number and the symbol is the caller's.
    """
    if is_empty_value(value):
        return ""
    n = _as_number(value)
    if n is None or not math.isfinite(n):
        return f"{value}"
    places = decimals if decimals is not None else 2
    amount = _grouped(abs(n), places, places, locale)
    mark = symbol if symbol is not None else "$"
    return f"-{mark}{amount}" if n < 0 else f"{mark}{amount}"


def format_float(value: float | str | None, options: FloatOptions | None = None) -> str:
    """A float reads back as a JSON *string* rounded to 6 decimals ("25.0"), never a
    JSON number, so it is formatted from the string to avoid a needless round trip
    through binary (field_types/float)."""
    o = options if options is not None else FloatOptions()
    if is_empty_value(value):
        return ""
    raw = _number_string(value) if isinstance(value, (int, float)) else str(value).strip()
    if o.decimals is not None:
        n = _as_number(raw)
        return _to_fixed(n, o.decimals) if n is not None and math.isfinite(n) else raw
    max_decimals = o.max_decimals
    if re.fullmatch(r"-?\d+(\.\d+)?", raw):
        return _trim_decimals(raw if max_decimals is None else _fixed(raw, max_decimals))
    n = _as_number(raw)
    if n is None or not math.isfinite(n):
        return raw
    return _trim_decimals(_number_string(n) if max_decimals is None else _to_fixed(n, max_decimals))


def _fixed(raw: str, decimals: int) -> str:
    n = _as_number(raw)
    return _to_fixed(n, decimals) if n is not None and math.isfinite(n) else raw


def _trim_decimals(raw: str) -> str:
    """"25.00" -> "25", "1.500" -> "1.5". Leaves an integer alone."""
    if "." not in raw:
        return raw
    return re.sub(r"\.?0+$", "", raw) or "0"


def _number_string(value: float) -> str:
    """A number the way JavaScript spells it: no trailing `.0` on a whole value."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if math.isfinite(value) and float(value).is_integer() and abs(value) < 1e21:
        return str(int(value))
    return repr(float(value))


def _js_round(n: float) -> int:
    """Half up, towards positive infinity, as `Math.round` is."""
    return math.floor(n + 0.5)


def _grouped(n: float, min_decimals: int, max_decimals: int, locale: str | None) -> str:
    """A non-negative number with the locale's group and decimal marks."""
    group, decimal = locale_marks(locale)
    text = _to_fixed(n, max_decimals)
    if max_decimals > min_decimals and "." in text:
        text = re.sub(r"0+$", "", text)
        whole, _, frac = text.partition(".")
        while len(frac) < min_decimals:
            frac += "0"
        text = f"{whole}.{frac}" if frac else whole
    whole, _, frac = text.partition(".")
    marked = f"{int(whole):,}".replace(",", group)
    return f"{marked}{decimal}{frac}" if frac else marked


# --- dates -------------------------------------------------------------------


@dataclass
class DateOptions:
    locale: str | None = None
    #: IANA zone. Defaults to UTC, which is the zone the store itself holds.
    time_zone: str | None = None


_DATE_ONLY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def format_date(value: str | None, options: DateOptions | None = None) -> str:
    """A `date` is exactly "YYYY-MM-DD": no time, no zone (field_types/date).

    It is therefore formatted in UTC whatever the viewer's zone, because shifting a
    zoneless day into a local zone moves it to the wrong day.
    """
    o = options if options is not None else DateOptions()
    if is_empty_value(value):
        return ""
    raw = str(value)
    m = _DATE_ONLY.match(raw)
    if not m:
        return raw
    loc = locale_for(o.locale)
    day = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    return _normalize_spaces(_render_pattern(loc.date, day, loc))


def format_date_time(value: str | None, options: DateOptions | None = None) -> str:
    """A `date_time` is always UTC "YYYY-MM-DDTHH:MM:SSZ" at second resolution
    (field_types/date_time). It is shown in the zone the caller names, UTC when it
    names none; keep the raw string beside it so the stored instant stays readable.
    """
    o = options if options is not None else DateOptions()
    if is_empty_value(value):
        return ""
    raw = str(value)
    instant = parse_instant(raw)
    if instant is None:
        return raw
    loc = locale_for(o.locale)
    local = instant.astimezone(zone_of(o.time_zone))
    return _normalize_spaces(
        loc.date_time.format(date=_render_pattern(loc.date, local, loc), time=_render_pattern(loc.time, local, loc))
    )


def parse_instant(raw: str) -> datetime | None:
    """A stored `YYYY-MM-DDTHH:MM:SSZ` as an aware datetime. A zoneless string is UTC."""
    text = str(raw).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _normalize_spaces(text: str) -> str:
    """Narrow no-break spaces around a day period collapse, so output is copyable and stable."""
    return re.sub(r"[    ]", " ", text)


# --- urls, images, colours ---------------------------------------------------


@dataclass
class UrlValue:
    """The `upload`/`web` and `local` shapes of a `url` field (field_types/url)."""

    url: str | None = None
    name: str | None = None
    content_type: str | None = None
    link_type: str | None = None
    local_path_mac: str | None = None
    local_path_linux: str | None = None
    local_path_windows: str | None = None
    relative_path: str | None = None
    type: str | None = None
    id: int | None = None


def file_name_from_url(url: str | None) -> str:
    """The last path segment of a URL or path, percent-decoded, with the query dropped.

    A presigned attachment URL carries the signature in the query and the content
    hash in the path, so the query is never part of a file name (field_types/url,
    field_types/image).
    """
    if is_empty_value(url):
        return ""
    raw = re.split(r"[?#]", str(url))[0]
    segments = [s for s in re.split(r"[\\/]", raw) if s]
    segment = segments[-1] if segments else ""
    return unquote(segment)


LocalPlatform = Literal["mac", "linux", "windows"]


def current_platform() -> LocalPlatform:
    """The platform this process runs on, for choosing which local path to open."""
    import sys

    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def file_href(path: str) -> str:
    """`file:` URL for a local path: a Windows drive path gains a third slash, and every segment is encoded."""
    win = re.match(r"^[a-zA-Z]:[\\/]", path) is not None
    normalized = path.replace("\\", "/") if win else path
    encoded = "/".join(quote(seg, safe="") for seg in normalized.split("/"))
    if win:
        return f"file:///{encoded}"
    return f"file://{'' if encoded.startswith('/') else '/'}{encoded}"


@dataclass
class LocalPaths:
    """The path of a `local` link per platform, and the one for the current platform."""

    mac: str | None = None
    linux: str | None = None
    windows: str | None = None
    path: str | None = None


@dataclass
class UrlLinkInfo:
    #: Where to open, or None when nothing can be opened. A local link opens through `file:`.
    href: str | None
    label: str
    #: Present on a `local` link.
    local: LocalPaths | None = None


def _url_field(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def url_link(value: Any, platform: LocalPlatform | None = None) -> UrlLinkInfo | None:
    """A displayable link out of a `url` value.

    Three shapes exist and no fourth: `upload`/`web` (has `url` and `name`), `local`
    (paths, no `url`), and a bare string (field_types/url). A local link resolves to
    a `file:` href for the current platform; an app that opens paths another way
    rewrites it with its own scheme.
    """
    if is_empty_value(value):
        return None
    if isinstance(value, str):
        return UrlLinkInfo(href=value, label=file_name_from_url(value) or value)
    if not isinstance(value, (dict, UrlValue)):
        return None
    where = platform if platform is not None else current_platform()
    if _url_field(value, "link_type") == "local":
        mac = _url_field(value, "local_path_mac")
        linux = _url_field(value, "local_path_linux")
        windows = _url_field(value, "local_path_windows")
        own = mac if where == "mac" else windows if where == "windows" else linux
        path = own if own is not None else (mac if mac is not None else (linux if linux is not None else windows))
        name = _url_field(value, "name")
        label = name if name is not None else file_name_from_url(path)
        if not label and not path:
            return None
        return UrlLinkInfo(
            href=file_href(path) if path else None,
            label=label or file_name_from_url(path),
            local=LocalPaths(mac=mac, linux=linux, windows=windows, path=path),
        )
    url = _url_field(value, "url")
    href = url if isinstance(url, str) and len(url) > 0 else None
    path = None
    for key in ("local_path_mac", "local_path_linux", "local_path_windows", "relative_path"):
        candidate = _url_field(value, key)
        if candidate is not None:
            path = candidate
            break
    name = _url_field(value, "name")
    label = name if name is not None else file_name_from_url(href if href else path)
    if not label and not href:
        return None
    return UrlLinkInfo(href=href, label=label or file_name_from_url(href))


#: The prefix Flow PT serves while a thumbnail is still transcoding (field_types/image).
THUMBNAIL_PENDING_PATH = "/images/status/transient/"


def image_state(value: str | None) -> Literal["none", "pending", "ready"]:
    """An `image` value is the only state marker there is: test the transient prefix,
    never truthiness (field_types/image)."""
    if is_empty_value(value):
        return "none"
    return "pending" if THUMBNAIL_PENDING_PATH in str(value) else "ready"


#: `Task.color` holds this token instead of a colour, meaning "use the colour of my
#: Pipeline Step". Resolve it with a dotted `step.Step.color` read in the same call
#: and keep a client default (field_types/color).
COLOR_SENTINEL = "pipeline_step"


def name_color_index(name: str | None, count: int = 5) -> int:
    """A stable index in `[0, count)` for a name, so the same person always gets the same tint.

    FNV-1a over the code points; the name alone, so a login and a display name of
    one person may differ.
    """
    if is_empty_value(name) or count <= 0:
        return 0
    h = 0x811C9DC5
    for ch in str(name):
        h = (h ^ ord(ch)) & 0xFFFFFFFF
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h % count


#: Eight hues far enough apart to tell neighbours apart, skipping the muddy yellows.
NAME_HUES: tuple[int, ...] = (15, 45, 95, 150, 195, 240, 285, 330)


def name_hue(name: str | None) -> int:
    """A stable hue for a name, for tinting initials independently of the theme."""
    return NAME_HUES[name_color_index(name, len(NAME_HUES))]


def initials_of(name: str | None, max_letters: int = 2) -> str:
    """Initials for an avatar fallback, from a person's display name.

    Takes the first letter of the first and last word, so "Ada Lovelace" is AL and
    "Anna van der Meer" is AM. A single word gives one letter; a `login` such as
    `j.doe` is split on its punctuation too.
    """
    if is_empty_value(name):
        return ""
    words = [w for w in (w.strip() for w in re.split(r"[\s._\-,]+", str(name))) if w]
    if not words:
        return ""
    first = words[0]
    letters = [first] if len(words) == 1 or max_letters < 2 else [first, words[-1]]
    return "".join(w[0] for w in letters if w).upper()[:max_letters]
