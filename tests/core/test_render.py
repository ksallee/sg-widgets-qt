"""Port of `packages/core/test/render.test.ts`."""
from __future__ import annotations

import math

from sg_widgets_core.edit import _as_finite_number as edit_as_finite_number
from sg_widgets_core.filter import _is_number as filter_is_number
from sg_widgets_core.mock import _is_number as mock_is_number
from sg_widgets_core.mock import _js_round as mock_js_round
from sg_widgets_core.render import (
    COLOR_SENTINEL,
    NAME_HUES,
    DateOptions,
    DurationOptions,
    FieldTextOptions,
    FloatOptions,
    LocalPaths,
    TimecodeOptions,
    UrlLinkInfo,
    _as_finite_number,
    _as_number,
    _js_round,
    field_text,
    file_href,
    file_name_from_url,
    format_currency,
    format_date,
    format_date_time,
    format_duration,
    format_float,
    format_percent,
    format_timecode,
    image_state,
    initials_of,
    is_empty_value,
    name_color_index,
    name_hue,
    render_kind_for,
    url_link,
)


class TestRenderKindFor:
    def test_collapses_the_numeric_family_and_keeps_the_link_families_apart(self) -> None:
        assert render_kind_for("number") == "number"
        assert render_kind_for("float") == "number"
        assert render_kind_for("percent") == "number"
        assert render_kind_for("duration") == "number"
        assert render_kind_for("timecode") == "number"
        assert render_kind_for("entity") == "entity"
        assert render_kind_for("multi_entity") == "multi_entity"
        assert render_kind_for("tag_list") == "multi_entity"

    def test_maps_the_display_only_types(self) -> None:
        assert render_kind_for("status_list") == "status"
        assert render_kind_for("list") == "list"
        assert render_kind_for("date") == "date"
        assert render_kind_for("date_time") == "datetime"
        assert render_kind_for("checkbox") == "checkbox"
        assert render_kind_for("image") == "image"
        assert render_kind_for("url") == "url"
        assert render_kind_for("color") == "color"

    def test_gives_pivot_column_the_empty_rendering_and_falls_back_to_text(self) -> None:
        # pivot_column reads null on every row over REST (field_types/pivot_column).
        assert render_kind_for("pivot_column") == "empty"
        assert render_kind_for("calculated") == "text"
        assert render_kind_for("sg_not_a_type") == "text"


class TestIsEmptyValue:
    def test_treats_zero_and_false_as_values_not_emptiness(self) -> None:
        assert is_empty_value(0) is False
        assert is_empty_value(False) is False
        assert is_empty_value("0") is False
        assert is_empty_value(None) is True
        assert is_empty_value("") is True
        assert is_empty_value([]) is True


class TestFormatDuration:
    def test_renders_whole_minutes_as_h_mm(self) -> None:
        assert format_duration(90) == "1:30"
        assert format_duration(0) == "0:00"
        assert format_duration(59) == "0:59"
        assert format_duration(600) == "10:00"
        assert format_duration(2400) == "40:00"
        assert format_duration(-90) == "-1:30"

    def test_renders_days_when_the_site_reports_hours_per_day(self) -> None:
        # GET /preferences on the probed site: hours_per_day 8.0, duration_units "days".
        assert format_duration(480, DurationOptions(hours_per_day=8)) == "1d"
        assert format_duration(720, DurationOptions(hours_per_day=8)) == "1.5d"
        assert format_duration(0, DurationOptions(hours_per_day=8)) == "0d"

    def test_is_empty_for_an_unset_field(self) -> None:
        assert format_duration(None) == ""


class TestFormatPercent:
    def test_appends_a_sign_to_the_stored_0_100_integer_and_clamps_nothing(self) -> None:
        assert format_percent(50) == "50%"
        assert format_percent(0) == "0%"
        assert format_percent(101) == "101%"
        assert format_percent(-1) == "-1%"
        assert format_percent(None) == ""


class TestFormatTimecode:
    def test_renders_milliseconds_as_hh_mm_ss(self) -> None:
        # group_name renderings recorded in field_types/timecode.
        assert format_timecode(3600000) == "01:00:00"
        assert format_timecode(1000) == "00:00:01"
        assert format_timecode(500) == "00:00:00"
        assert format_timecode(86400000) == "24:00:00"
        assert format_timecode(0) == "00:00:00"
        assert format_timecode(-3600000) == "-01:00:00"
        assert format_timecode(None) == ""

    def test_does_not_wrap_past_24_hours(self) -> None:
        assert format_timecode(2147483647) == "596:31:23"

    def test_adds_the_frame_digits_when_the_app_names_a_rate(self) -> None:
        # The server groups 500 as 00:00:00:12 and 3600000 as 01:00:00:00 (field_types/timecode).
        assert format_timecode(500, TimecodeOptions(frame_rate=23.976)) == "00:00:00:12"
        assert format_timecode(3600000, TimecodeOptions(frame_rate=23.976)) == "01:00:00:00"
        assert format_timecode(86400000, TimecodeOptions(frame_rate=23.976)) == "24:00:00:00"
        assert format_timecode(500, TimecodeOptions(frame_rate=0)) == "00:00:00"


class TestFormatFloat:
    def test_trims_the_quoted_decimal_the_api_returns(self) -> None:
        assert format_float("25.0") == "25"
        assert format_float("0.04") == "0.04"
        assert format_float("1.234568") == "1.234568"
        assert format_float("1.500") == "1.5"
        assert format_float("0.0") == "0"
        assert format_float("-1.50") == "-1.5"
        assert format_float(2.5) == "2.5"
        assert format_float(None) == ""

    def test_rounds_to_a_cap_when_asked(self) -> None:
        assert format_float("1.234568", FloatOptions(max_decimals=2)) == "1.23"
        assert format_float("1.999", FloatOptions(max_decimals=2)) == "2"

    def test_returns_an_unparseable_value_untouched(self) -> None:
        assert format_float("n/a") == "n/a"


class TestFormatDate:
    def test_formats_a_zoneless_day_without_shifting_it(self) -> None:
        assert format_date("2026-09-02", DateOptions(locale="en-US")) == "Sep 2, 2026"
        assert format_date("2026-01-01", DateOptions(locale="en-US")) == "Jan 1, 2026"

    def test_passes_anything_that_is_not_yyyy_mm_dd_straight_through(self) -> None:
        assert format_date("2026-09-02T15:58:21Z", DateOptions(locale="en-US")) == "2026-09-02T15:58:21Z"
        assert format_date(None) == ""


class TestFormatDateTime:
    def test_renders_the_stored_utc_instant_in_a_zone(self) -> None:
        assert (
            format_date_time("2026-09-02T15:58:21Z", DateOptions(locale="en-US", time_zone="UTC"))
            == "Sep 2, 2026, 3:58 PM"
        )
        assert (
            format_date_time("2026-09-02T15:58:21Z", DateOptions(locale="en-US", time_zone="Europe/Paris"))
            == "Sep 2, 2026, 5:58 PM"
        )

    def test_crosses_the_day_boundary_in_the_viewer_zone(self) -> None:
        assert (
            format_date_time("2026-09-02T23:30:00Z", DateOptions(locale="en-US", time_zone="Australia/Sydney"))
            == "Sep 3, 2026, 9:30 AM"
        )

    def test_returns_an_unparseable_value_untouched(self) -> None:
        assert format_date_time("never", DateOptions(locale="en-US")) == "never"
        assert format_date_time(None) == ""


class TestFileNameFromUrl:
    def test_takes_the_last_path_segment_and_drops_the_presigned_query(self) -> None:
        assert (
            file_name_from_url("https://s3-accelerate.amazonaws.com/abc/bunny.jpg?X-Amz-Signature=deadbeef")
            == "bunny.jpg"
        )
        assert file_name_from_url("/files/0000/0000/0001/original/my%20take.mov") == "my take.mov"
        assert file_name_from_url("C:\\shows\\seq01\\plate.exr") == "plate.exr"
        assert file_name_from_url(None) == ""


class TestUrlLink:
    def test_reads_the_upload_shape(self) -> None:
        assert url_link(
            {
                "url": "https://s3-accelerate.amazonaws.com/abc/bunny.jpg?X-Amz-Expires=900",
                "name": "bunny.jpg",
                "content_type": "image/jpeg",
                "link_type": "upload",
                "type": "Attachment",
                "id": 1430,
            }
        ) == UrlLinkInfo(href="https://s3-accelerate.amazonaws.com/abc/bunny.jpg?X-Amz-Expires=900", label="bunny.jpg")

    def test_reads_the_local_shape_which_carries_no_url_as_a_file_link(self) -> None:
        assert url_link(
            {
                "link_type": "local",
                "name": "plate.exr",
                "local_path_mac": "/Volumes/shows/seq01/plate.exr",
                "relative_path": "seq01/plate.exr",
            },
            "mac",
        ) == UrlLinkInfo(
            href="file:///Volumes/shows/seq01/plate.exr",
            label="plate.exr",
            local=LocalPaths(
                mac="/Volumes/shows/seq01/plate.exr", linux=None, windows=None, path="/Volumes/shows/seq01/plate.exr"
            ),
        )

    def test_reads_the_bare_string_shape(self) -> None:
        assert url_link("/page/media_center") == UrlLinkInfo(href="/page/media_center", label="media_center")

    def test_is_null_when_there_is_nothing_to_show(self) -> None:
        assert url_link(None) is None
        assert url_link({}) is None


class TestImageState:
    def test_reads_the_transient_prefix_rather_than_truthiness(self) -> None:
        assert image_state(None) == "none"
        assert image_state("") == "none"
        assert image_state("https://site.shotgunstudio.com/images/status/transient/thumbnail_pending.png") == "pending"
        assert image_state("https://s3-accelerate.amazonaws.com/deadbeef/image.jpg?X-Amz-Expires=900") == "ready"


class TestInitialsOf:
    def test_takes_the_first_and_last_word(self) -> None:
        assert initials_of("Ada Lovelace") == "AL"
        assert initials_of("Anna van der Meer") == "AM"
        assert initials_of("Madonna") == "M"
        assert initials_of("j.doe") == "JD"
        assert initials_of("  spaced   out  ") == "SO"
        assert initials_of("") == ""
        assert initials_of(None) == ""


class TestColorSentinel:
    def test_names_the_token_task_color_holds_instead_of_a_colour(self) -> None:
        assert COLOR_SENTINEL == "pipeline_step"


class TestLocalFileLinks:
    def test_resolves_the_path_for_the_platform_and_opens_it_through_file(self) -> None:
        value = {
            "link_type": "local",
            "name": "plate.exr",
            "local_path_mac": "/Volumes/shows/plate.exr",
            "local_path_windows": "P:\\shows\\plate.exr",
            "local_path_linux": "/mnt/shows/plate.exr",
        }
        mac = url_link(value, "mac")
        windows = url_link(value, "windows")
        linux = url_link(value, "linux")
        assert mac is not None and mac.href == "file:///Volumes/shows/plate.exr"
        assert windows is not None and windows.href == "file:///P%3A/shows/plate.exr"
        assert linux is not None and linux.local is not None and linux.local.path == "/mnt/shows/plate.exr"
        fallback = url_link({"link_type": "local", "name": "x", "local_path_mac": "/a b/x"}, "windows")
        assert fallback is not None and fallback.href == "file:///a%20b/x"
        assert file_href("/a/b c") == "file:///a/b%20c"


class TestFormatFloatDecimals:
    def test_fixes_the_precision_and_keeps_zeros(self) -> None:
        assert format_float("1.777778", FloatOptions(decimals=2)) == "1.78"
        assert format_float("25.0", FloatOptions(decimals=3)) == "25.000"
        assert format_float("25.0") == "25"


class TestNameColorIndex:
    def test_is_stable_bounded_and_spreads_names(self) -> None:
        assert name_color_index("Ada Lovelace") == name_color_index("Ada Lovelace")
        idx = [
            name_color_index(n)
            for n in ["Ada Lovelace", "Bo Chen", "Cleo Dias", "Grace Hopper", "Alan Turing", "Madonna"]
        ]
        assert all(0 <= i < 5 for i in idx)
        assert len(set(idx)) > 2
        assert name_color_index("") == 0
        assert name_hue("Ada Lovelace") in NAME_HUES
        assert name_hue("Ada Lovelace") == name_hue("Ada Lovelace")


class TestFormatCurrency:
    def test_prefixes_the_symbol_and_fixes_two_decimals(self) -> None:
        assert format_currency(12500) == "$12,500.00"
        assert format_currency("42.5", symbol="€") == "€42.50"
        assert format_currency(-3, symbol="£", decimals=0) == "-£3"
        assert format_currency(None) == ""


class TestFieldText:
    def test_names_a_linked_row_and_falls_back_to_type_and_id(self) -> None:
        assert field_text({"type": "Shot", "id": 862, "name": "sh010_0010"}, "entity") == "sh010_0010"
        assert field_text({"type": "Shot", "id": 862}, "entity") == "Shot #862"

    def test_joins_a_multi_entity_value(self) -> None:
        value = [
            {"type": "Asset", "id": 1, "name": "charAda"},
            {"type": "Asset", "id": 2, "name": "envForest"},
        ]
        assert field_text(value, "multi_entity") == "charAda, envForest"
        assert field_text(value, "multi_entity", FieldTextOptions(separator=" / ")) == "charAda / envForest"

    def test_labels_a_status_through_display_values_and_falls_back_to_the_code(self) -> None:
        assert field_text("ip", "status_list", FieldTextOptions(display_values={"ip": "In Progress"})) == "In Progress"
        assert field_text("ip", "status_list") == "ip"

    def test_formats_the_number_family_by_its_data_type(self) -> None:
        assert field_text(90, "duration") == "1:30"
        assert field_text(480, "duration", FieldTextOptions(hours_per_day=8)) == "1d"
        assert field_text(50, "percent") == "50%"
        assert field_text(3_661_000, "timecode") == "01:01:01"
        assert field_text("25.00", "float") == "25"
        assert field_text("42.5", "currency", FieldTextOptions(currency_symbol="€")) == "€42.50"

    def test_gives_a_timecode_its_frames_when_the_site_names_a_rate(self) -> None:
        assert field_text(3_661_500, "timecode", FieldTextOptions(frame_rate=23.976)) == "01:01:01:12"
        assert field_text(3_661_500, "timecode") == "01:01:01"

    def test_shows_a_date_time_in_the_zone_it_is_given(self) -> None:
        assert (
            field_text("2026-09-02T15:58:21Z", "date_time", FieldTextOptions(locale="en-US", time_zone="UTC"))
            == "Sep 2, 2026, 3:58 PM"
        )
        assert (
            field_text(
                "2026-09-02T15:58:21Z", "date_time", FieldTextOptions(locale="en-US", time_zone="Europe/Paris")
            )
            == "Sep 2, 2026, 5:58 PM"
        )

    def test_leaves_the_zone_to_the_runtime_when_none_is_given_and_keeps_a_date_zoneless(self) -> None:
        raw = "2026-09-02T15:58:21Z"
        assert field_text(raw, "date_time", FieldTextOptions(locale="en-US")) == format_date_time(
            raw, DateOptions(locale="en-US")
        )
        # A date has no time and no zone, so a zone must not move it (field_types/date).
        assert (
            field_text("2026-09-02", "date", FieldTextOptions(locale="en-US", time_zone="Australia/Sydney"))
            == "Sep 2, 2026"
        )

    def test_a_date_time_with_no_zone_named_is_rendered_in_the_runtime_zone(self) -> None:
        """No zone named means the runtime's own, as upstream's `Intl.DateTimeFormat` defaults."""
        from datetime import datetime, timezone

        local = datetime(2026, 9, 2, 15, 58, 21, tzinfo=timezone.utc).astimezone()
        expected = field_text(
            "2026-09-02T15:58:21Z", "date_time", FieldTextOptions(locale="en-US", time_zone=str(local.tzinfo))
        ) if str(local.tzinfo) in ("UTC",) else None
        rendered = field_text("2026-09-02T15:58:21Z", "date_time", FieldTextOptions(locale="en-US"))
        assert rendered.endswith(local.strftime("%-I:%M %p").replace("AM", "AM").replace("PM", "PM"))
        assert expected is None or rendered == expected

    def test_renders_a_checkbox_as_a_word_never_as_empty(self) -> None:
        assert field_text(False, "checkbox") == "No"
        assert field_text(True, "checkbox") == "Yes"

    def test_answers_empty_for_nothing_to_show(self) -> None:
        assert field_text(None, "text") == ""
        assert field_text([], "multi_entity") == ""
        assert field_text("anything", "pivot_column") == ""

    def test_keeps_zero_which_is_a_value(self) -> None:
        assert field_text(0, "number") == "0"

    def test_shows_the_colour_sentinel_as_the_step_it_stands_for(self) -> None:
        assert field_text("pipeline_step", "color") == "pipeline step"
        assert field_text("255,0,0", "color") == "255,0,0"

    def test_takes_the_label_of_a_url_and_the_file_name_of_an_image(self) -> None:
        assert field_text({"link_type": "web", "url": "https://example.com/a.mov", "name": "a.mov"}, "url") == "a.mov"
        assert field_text("https://example.com/x/thumb.jpg?sig=1", "image") == "thumb.jpg"


class TestTheNumberReadingsTheModulesShare:
    def test_reads_a_number_once_and_rounds_once(self) -> None:
        # One definition each, in the module that owns the reading.
        assert mock_js_round is _js_round
        assert mock_is_number is filter_is_number
        assert edit_as_finite_number is _as_finite_number

    def test_keeps_the_editors_reading_apart_from_the_renderers(self) -> None:
        assert _as_number("1e400") == math.inf
        assert _as_finite_number("1e400") is None
        assert _as_number(" 12 ") == 12.0
        assert _as_finite_number(" 12 ") == 12.0
