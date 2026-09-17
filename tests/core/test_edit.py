"""Port of `packages/core/test/edit.test.ts`."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.edit import (
    INT32_MAX,
    INT32_MIN,
    DateTimeOptions,
    DurationParseOptions,
    FloatParseOptions,
    IntegerOptions,
    IsoDayParts,
    LocalDateTime,
    NumberInputFormat,
    NumberShape,
    NumberSteps,
    NumberStepsOptions,
    ParseResult,
    StepOptions,
    UrlWriteValue,
    color_to_hex,
    editor_kind_for,
    editor_needs_context,
    editor_placement_for,
    format_number_input,
    format_timecode_frames,
    from_api_date_time,
    is_editable_type,
    is_parse_error,
    is_valid_list_value,
    iso_day,
    iso_day_parts,
    number_digits,
    number_draft,
    number_steps,
    number_wire,
    parse_color_input,
    parse_duration_input,
    parse_float_input,
    parse_integer,
    parse_number_input,
    parse_text_input,
    parse_timecode_input,
    parse_url_input,
    settle_step,
    step_number,
    stored_number,
    time_zone_name,
    to_api_date,
    to_api_date_time,
    to_api_float,
    unformat_number_input,
)
from sg_widgets_core.render import TimecodeOptions


def ok(result: ParseResult) -> Any:
    """The value of a parse that must have succeeded."""
    if is_parse_error(result):
        raise AssertionError(f"expected a value, got {result.error}")
    return result.value


def err(result: ParseResult) -> str:
    if not is_parse_error(result):
        raise AssertionError(f"expected an error, got {result.value!r}")
    return result.error


class TestParseTextInput:
    def test_strips_both_ends_and_stores_an_empty_string_as_null(self) -> None:
        # '  padded  ' reads back 'padded' and '   ' reads back None (field_types/text).
        assert ok(parse_text_input("  padded  ")) == "padded"
        assert ok(parse_text_input("   ")) is None
        assert ok(parse_text_input("")) is None

    def test_keeps_newlines_and_non_ascii(self) -> None:
        assert ok(parse_text_input("line1\nline2")) == "line1\nline2"
        assert ok(parse_text_input("héllo ✨ 漢字")) == "héllo ✨ 漢字"


class TestParseInteger:
    def test_takes_a_whole_number_and_clears_on_empty(self) -> None:
        assert ok(parse_integer("42")) == 42
        assert ok(parse_integer("-7")) == -7
        assert ok(parse_integer("0")) == 0
        assert ok(parse_integer("")) is None

    def test_refuses_a_decimal_rather_than_rounding_it(self) -> None:
        # 3.7 is a 400 with no truncation and no rounding (field_types/number).
        assert err(parse_integer("3.7")) == "Whole numbers only."
        assert err(parse_integer("42abc")) == "Not a number."

    def test_holds_the_signed_32_bit_ceiling(self) -> None:
        # 2**31-1 stores; 2**31 is 400 "integer out of range" (field_types/number).
        assert ok(parse_integer(str(INT32_MAX))) == INT32_MAX
        assert ok(parse_integer(str(INT32_MIN))) == INT32_MIN
        assert "Out of range" in err(parse_integer("2147483648"))
        assert "Out of range" in err(parse_integer("-2147483649"))

    def test_takes_an_explicit_range_for_a_percent(self) -> None:
        # The 0-100 range is a convention, not a constraint: 101 stores at 200 (field_types/percent).
        assert ok(parse_integer("50", IntegerOptions(min=0, max=100))) == 50
        assert err(parse_integer("101", IntegerOptions(min=0, max=100))) == "Out of range: 0 to 100."


class TestParseFloatInput:
    def test_rounds_to_the_six_decimals_the_store_keeps(self) -> None:
        # 1.23456789012345 reads back "1.234568", rounded not truncated (field_types/float).
        assert ok(parse_float_input("1.23456789012345")) == 1.234568
        assert ok(parse_float_input("2.5")) == 2.5
        assert ok(parse_float_input(" 4.5 ")) == 4.5
        assert ok(parse_float_input("-1.5")) == -1.5

    def test_underflows_to_zero_the_way_the_store_does(self) -> None:
        # 1e-09 stores as "0.0" (field_types/float).
        assert ok(parse_float_input("1e-09")) == 0

    def test_refuses_what_the_api_refuses_and_clears_on_empty(self) -> None:
        assert err(parse_float_input("abc")) == "Not a number."
        assert ok(parse_float_input("")) is None

    def test_honours_a_tighter_precision(self) -> None:
        assert ok(parse_float_input("1.777778", FloatParseOptions(precision=2))) == 1.78


class TestToApiFloat:
    def test_always_carries_a_decimal_point(self) -> None:
        # An Integer is refused on write and inside a filter (field_types/float).
        assert to_api_float(2) == "2.0"
        assert to_api_float(2.5) == "2.5"
        assert to_api_float(0) == "0.0"
        assert to_api_float(None) is None


class TestParseDurationInput:
    def test_reads_a_bare_number_as_minutes(self) -> None:
        # The stored integer is minutes; the stock field is named est_in_mins (field_types/duration).
        assert ok(parse_duration_input("90")) == 90
        assert ok(parse_duration_input("0")) == 0
        assert ok(parse_duration_input("-30")) == -30

    def test_reads_hours_and_minutes(self) -> None:
        assert ok(parse_duration_input("1h 30m")) == 90
        assert ok(parse_duration_input("1h30m")) == 90
        assert ok(parse_duration_input("1.5h")) == 90
        assert ok(parse_duration_input("2 hours")) == 120
        assert ok(parse_duration_input("45min")) == 45
        assert ok(parse_duration_input("1:30")) == 90

    def test_scales_days_by_the_site_working_day(self) -> None:
        # hours_per_day comes from GET /preferences; the probed site holds 8.0 (field_types/duration).
        assert ok(parse_duration_input("2d", DurationParseOptions(hours_per_day=8))) == 960
        assert ok(parse_duration_input("1d", DurationParseOptions(hours_per_day=10))) == 600
        assert ok(parse_duration_input("1d 2h", DurationParseOptions(hours_per_day=8))) == 600

    def test_rounds_to_a_whole_minute(self) -> None:
        # A Float truncates toward zero at 200, so the client rounds first (field_types/duration).
        assert ok(parse_duration_input("90.6")) == 91

    def test_refuses_what_it_cannot_read_whole_and_clears_on_empty(self) -> None:
        assert "Not a duration" in err(parse_duration_input("1h banana"))
        assert "Not a duration" in err(parse_duration_input("banana"))
        assert ok(parse_duration_input("")) is None


class TestParseTimecodeInput:
    def test_reads_a_bare_number_as_milliseconds(self) -> None:
        # 1000 renders as one whole second in the server's own grouping (field_types/timecode).
        assert ok(parse_timecode_input("3600000")) == 3600000
        assert ok(parse_timecode_input("0")) == 0

    def test_converts_hh_mm_ss(self) -> None:
        assert ok(parse_timecode_input("01:00:00")) == 3600000
        assert ok(parse_timecode_input("24:00:00")) == 86400000
        assert ok(parse_timecode_input("-01:00:00")) == -3600000

    def test_converts_frames_at_a_given_rate(self) -> None:
        # The rate is on neither the schema nor the preferences; solve it per site (field_types/timecode).
        assert ok(parse_timecode_input("00:00:01:00", TimecodeOptions(frame_rate=23.976))) == 1000
        assert ok(parse_timecode_input("00:00:00:12", TimecodeOptions(frame_rate=23.976))) == 501
        assert err(parse_timecode_input("00:00:00:12")) == "Frames need a frame rate."
        assert "Frames run 0 to" in err(parse_timecode_input("00:00:00:24", TimecodeOptions(frame_rate=23.976)))

    def test_refuses_anything_else_and_clears_on_empty(self) -> None:
        assert "Not a timecode" in err(parse_timecode_input("banana"))
        assert "Not a timecode" in err(parse_timecode_input("01:00:00;00 extra"))
        assert ok(parse_timecode_input("")) is None

    def test_holds_the_signed_32_bit_ceiling(self) -> None:
        assert ok(parse_timecode_input(str(INT32_MAX))) == INT32_MAX
        assert "Out of range" in err(parse_timecode_input("2147483648"))


class TestFormatTimecodeFrames:
    def test_renders_milliseconds_the_way_the_server_groups_them(self) -> None:
        # 500 groups as 00:00:00:12 and 3600000 as 01:00:00:00 (field_types/timecode).
        assert format_timecode_frames(500, 23.976) == "00:00:00:12"
        assert format_timecode_frames(3600000, 23.976) == "01:00:00:00"
        assert format_timecode_frames(86400000, 23.976) == "24:00:00:00"


class TestToApiDate:
    def test_takes_yyyy_mm_dd_and_nothing_else(self) -> None:
        # A timestamp is a 400 on write and as a filter value (field_types/date).
        assert ok(to_api_date("2026-09-02")) == "2026-09-02"
        assert err(to_api_date("2026-09-02T13:45:06Z")) == "Not a date. Use YYYY-MM-DD."
        assert err(to_api_date("09/07/2026")) == "Not a date. Use YYYY-MM-DD."
        assert err(to_api_date("2026-9-8")) == "Not a date. Use YYYY-MM-DD."

    def test_validates_the_day_not_just_the_shape(self) -> None:
        # 2026-02-30 is rejected by the same message as 'tomorrow' (field_types/date).
        assert err(to_api_date("2026-02-30")) == "No such day."
        assert ok(to_api_date("2024-02-29")) == "2024-02-29"

    def test_clears_on_empty(self) -> None:
        assert ok(to_api_date("")) is None


class TestIsoDayPartsAndIsoDay:
    def test_splits_a_calendar_day_and_puts_it_back(self) -> None:
        assert iso_day_parts("2026-09-02") == IsoDayParts(year=2026, month=9, day=2)
        assert iso_day(IsoDayParts(year=2026, month=9, day=2)) == "2026-09-02"

    def test_pads_every_part(self) -> None:
        assert iso_day(IsoDayParts(year=7, month=1, day=3)) == "0007-01-03"

    def test_answers_nothing_for_anything_that_is_not_a_calendar_day(self) -> None:
        assert iso_day_parts("2026-09-02T13:45:06Z") is None
        assert iso_day_parts("2026-9-2") is None
        assert iso_day_parts(None) is None

    def test_ignores_the_space_around_it_as_a_typed_day_carries(self) -> None:
        assert iso_day_parts("  2026-09-02 ") == IsoDayParts(year=2026, month=9, day=2)


class TestToApiDateTime:
    def test_converts_local_wall_clock_to_the_stored_utc_string(self) -> None:
        # The store is UTC YYYY-MM-DDTHH:MM:SSZ at second resolution (field_types/date_time).
        assert ok(to_api_date_time("2026-03-04", "05:06", DateTimeOptions(time_zone="UTC"))) == "2026-03-04T05:06:00Z"
        assert (
            ok(to_api_date_time("2026-03-04", "05:06:07", DateTimeOptions(time_zone="UTC")))
            == "2026-03-04T05:06:07Z"
        )
        # A written offset is not preserved: 05:06:07+05:00 reads back 00:06:07Z (field_types/date_time).
        assert (
            ok(to_api_date_time("2026-03-04", "05:06:07", DateTimeOptions(time_zone="Asia/Karachi")))
            == "2026-03-04T00:06:07Z"
        )
        assert (
            ok(to_api_date_time("2026-03-04", "05:06:07", DateTimeOptions(time_zone="America/Los_Angeles")))
            == "2026-03-04T13:06:07Z"
        )

    def test_reads_a_date_with_no_time_as_midnight_local(self) -> None:
        assert ok(to_api_date_time("2026-03-04", "", DateTimeOptions(time_zone="UTC"))) == "2026-03-04T00:00:00Z"
        assert (
            ok(to_api_date_time("2026-03-04", "", DateTimeOptions(time_zone="Asia/Karachi")))
            == "2026-03-03T19:00:00Z"
        )

    def test_clears_when_both_parts_are_empty_and_refuses_a_lone_time(self) -> None:
        # Only null clears a date_time; "" is a 400 (field_types/date_time).
        assert ok(to_api_date_time("", "", DateTimeOptions(time_zone="UTC"))) is None
        assert err(to_api_date_time("", "05:06", DateTimeOptions(time_zone="UTC"))) == "A time needs a date."
        assert (
            err(to_api_date_time("2026-03-04", "25:00", DateTimeOptions(time_zone="UTC")))
            == "Not a time. Use HH:MM."
        )


class TestFromApiDateTime:
    def test_splits_the_stored_instant_into_local_parts(self) -> None:
        assert from_api_date_time("2026-03-04T05:06:07Z", DateTimeOptions(time_zone="UTC")) == LocalDateTime(
            date="2026-03-04", time="05:06", time_with_seconds="05:06:07"
        )
        assert from_api_date_time(
            "2026-03-04T00:06:07Z", DateTimeOptions(time_zone="Asia/Karachi")
        ) == LocalDateTime(date="2026-03-04", time="05:06", time_with_seconds="05:06:07")

    def test_round_trips_through_to_api_date_time(self) -> None:
        local = from_api_date_time("2026-03-04T13:06:07Z", DateTimeOptions(time_zone="America/Los_Angeles"))
        assert local is not None
        back = to_api_date_time(local.date, local.time_with_seconds, DateTimeOptions(time_zone="America/Los_Angeles"))
        assert ok(back) == "2026-03-04T13:06:07Z"

    def test_gives_null_for_an_empty_or_unreadable_value(self) -> None:
        assert from_api_date_time(None) is None
        assert from_api_date_time("") is None
        assert from_api_date_time("not-a-time") is None


class TestTimeZoneName:
    def test_names_the_zone_a_wall_clock_input_is_read_in(self) -> None:
        assert time_zone_name("Europe/Paris") == "Europe/Paris"
        assert len(time_zone_name()) > 0


class TestIsValidListValue:
    def test_is_case_sensitive_as_the_write_is(self) -> None:
        # 'type a' and 'Type A ' are both 400 on write (field_types/list).
        valid = ["Type A", "Type B", "Type C"]
        assert is_valid_list_value(valid, "Type A") is True
        assert is_valid_list_value(valid, "type a") is False
        assert is_valid_list_value(valid, "Type A ") is False
        assert is_valid_list_value(None, "Type A") is False


class TestParseUrlInput:
    def test_builds_the_object_write_shape(self) -> None:
        # The only accepted input is an object holding url; a bare string 400s (field_types/url).
        assert ok(parse_url_input("https://example.com/plate.mov")) == UrlWriteValue(
            url="https://example.com/plate.mov"
        )
        assert ok(parse_url_input("https://example.com/plate.mov", "plate.mov")) == UrlWriteValue(
            url="https://example.com/plate.mov", name="plate.mov"
        )

    def test_refuses_a_raw_space(self) -> None:
        # A raw space is the one character measured to fail; percent-encode it (field_types/url).
        assert (
            err(parse_url_input("https://example.com/a folder/plate.exr"))
            == "No spaces in a link. Percent-encode them."
        )
        assert ok(parse_url_input("https://example.com/a%20folder/plate.exr")) == UrlWriteValue(
            url="https://example.com/a%20folder/plate.exr"
        )

    def test_clears_on_empty_and_refuses_a_name_with_no_link(self) -> None:
        assert ok(parse_url_input("", "")) is None
        assert err(parse_url_input("", "plate.mov")) == "A name needs a link."


class TestParseColorInput:
    def test_keeps_a_decimal_triple_and_drops_the_spaces_the_api_refuses(self) -> None:
        # "255, 128, 0" is a 400; decimal r,g,b with no spaces is the stored form (field_types/color).
        assert ok(parse_color_input("255,128,0")) == "255,128,0"
        assert ok(parse_color_input("255, 128, 0")) == "255,128,0"

    def test_converts_hex_which_the_api_rejects(self) -> None:
        assert ok(parse_color_input("#ff8000")) == "255,128,0"
        assert ok(parse_color_input("ff8000")) == "255,128,0"
        assert ok(parse_color_input("#f80")) == "255,136,0"

    def test_passes_the_pipeline_step_token_through(self) -> None:
        # Writing the token is the only way to un-set Task.color; null is a 400 (field_types/color).
        assert ok(parse_color_input("pipeline_step")) == "pipeline_step"

    def test_refuses_an_out_of_range_channel_and_anything_unreadable(self) -> None:
        assert err(parse_color_input("300,0,0")) == "Each channel runs 0 to 255."
        assert err(parse_color_input("255,128")) == "Not a colour. Use r,g,b or a hex code."
        assert err(parse_color_input("255,128,0,255")) == "Not a colour. Use r,g,b or a hex code."
        assert ok(parse_color_input("")) is None


class TestColorToHex:
    def test_renders_a_stored_triple_for_a_colour_input(self) -> None:
        assert color_to_hex("255,128,0") == "#ff8000"
        assert color_to_hex("253,94,99") == "#fd5e63"

    def test_gives_null_for_the_sentinel_and_for_anything_unreadable(self) -> None:
        assert color_to_hex("pipeline_step") is None
        assert color_to_hex(None) is None
        assert color_to_hex("300,0,0") is None


class TestEditorKindFor:
    def test_groups_the_numeric_family_under_one_editor(self) -> None:
        for data_type in ["number", "float", "percent", "duration", "timecode", "currency"]:
            assert editor_kind_for(data_type) == "number"

    def test_keeps_the_rest_apart(self) -> None:
        assert editor_kind_for("text") == "text"
        assert editor_kind_for("checkbox") == "checkbox"
        assert editor_kind_for("date") == "date"
        assert editor_kind_for("date_time") == "date_time"
        assert editor_kind_for("list") == "list"
        assert editor_kind_for("url") == "url"
        assert editor_kind_for("color") == "color"

    def test_gives_the_three_picker_types_an_editor_of_their_own(self) -> None:
        assert editor_kind_for("status_list") == "status_list"
        assert editor_kind_for("entity") == "entity"
        assert editor_kind_for("multi_entity") == "multi_entity"
        for data_type in ["status_list", "entity", "multi_entity"]:
            assert is_editable_type(data_type) is True
            assert editor_needs_context(data_type) is True

    def test_leaves_the_read_only_types_with_no_editor(self) -> None:
        for data_type in ["image", "calculated", "summary", "pivot_column", "tag_list", "jsonb"]:
            assert editor_kind_for(data_type) == "none"
            assert is_editable_type(data_type) is False
        assert is_editable_type("text") is True

    def test_keeps_the_checkbox_in_the_cell_and_gives_every_other_editor_a_popover(self) -> None:
        assert editor_placement_for("checkbox") == "inline"
        for data_type in [
            "status_list", "entity", "list", "text", "number", "float", "percent", "currency",
            "duration", "timecode", "date", "date_time", "multi_entity", "color", "url",
        ]:
            assert editor_placement_for(data_type) == "popover"

    def test_leaves_a_type_with_no_editor_in_the_cell(self) -> None:
        assert editor_placement_for("image") == "inline"
        assert editor_placement_for("calculated") == "inline"

    def test_asks_for_a_context_only_where_the_editor_reads_the_api(self) -> None:
        for data_type in ["text", "number", "date", "list", "url", "color", "checkbox", "calculated"]:
            assert editor_needs_context(data_type) is False


class TestNumberSteps:
    def test_gives_each_numeric_type_the_step_its_unit_reads_in(self) -> None:
        assert number_steps("number") == NumberSteps(step=1, min=INT32_MIN, max=INT32_MAX)
        assert number_steps("currency") == NumberSteps(step=1)
        assert number_steps("float") == NumberSteps(step=0.1)
        assert number_steps("percent") == NumberSteps(step=1, min=0, max=100)
        assert number_steps("duration") == NumberSteps(step=15, min=INT32_MIN, max=INT32_MAX)

    def test_steps_a_timecode_one_frame_when_the_rate_is_known_one_second_when_it_is_not(self) -> None:
        assert number_steps("timecode", NumberStepsOptions(frame_rate=25)).step == 40
        assert number_steps("timecode", NumberStepsOptions(frame_rate=23.976)).step == 42
        assert number_steps("timecode").step == 1000


class TestStepNumber:
    def test_moves_one_step_and_ten_or_a_hundred_with_a_multiplier(self) -> None:
        assert step_number(480, 1, StepOptions(step=15)) == 495
        assert step_number(480, -1, StepOptions(step=15)) == 465
        assert step_number(480, 1, StepOptions(step=15, multiplier=10)) == 630
        assert step_number(480, -1, StepOptions(step=15, multiplier=100)) == -1020

    def test_keeps_a_tenth_sized_step_off_binary_noise(self) -> None:
        assert step_number(0.2, 1, StepOptions(step=0.1)) == 0.3
        assert step_number(1.23456, 1, StepOptions(step=0.1)) == 1.33456

    def test_clamps_at_both_bounds(self) -> None:
        assert step_number(100, 1, StepOptions(step=1, min=0, max=100)) == 100
        assert step_number(0, -1, StepOptions(step=1, min=0, max=100)) == 0
        assert step_number(95, 1, StepOptions(step=1, min=0, max=100, multiplier=10)) == 100

    def test_lands_an_empty_field_on_zero_before_it_steps(self) -> None:
        assert step_number(None, 1, StepOptions(step=15)) == 0
        assert step_number(None, -1, StepOptions(step=1, min=0, max=100)) == 0


class TestSettleStep:
    def test_rounds_where_a_step_landed_and_clamps_it(self) -> None:
        assert settle_step(0.2, 0.30000000000000004, StepOptions(step=0.1)) == 0.3
        assert settle_step(50, 150, StepOptions(step=1, min=0, max=100)) == 100
        assert settle_step(None, 0, StepOptions(step=1)) == 0


class TestFormatAndUnformatNumberInput:
    def test_round_trips_a_grouped_number_back_through_the_parsers(self) -> None:
        assert format_number_input(12500.5, NumberInputFormat(locale="en-US", decimals=2)) == "12,500.50"
        assert unformat_number_input("12,500.50", "en-US") == "12500.50"
        assert ok(parse_float_input(unformat_number_input("12,500.50", "en-US"))) == 12500.5

    def test_reads_the_marks_the_locale_writes(self) -> None:
        assert format_number_input(1001, NumberInputFormat(locale="de-DE")) == "1.001"
        assert unformat_number_input("1.234,5", "de-DE") == "1234.5"
        assert unformat_number_input("1 234,5", "fr-FR") == "1234.5"

    def test_drops_a_comma_wherever_the_locale_spells_its_decimal_with_a_point(self) -> None:
        assert unformat_number_input("1,001", "en-GB") == "1001"
        assert ok(parse_integer(unformat_number_input("1,001", "en-US"))) == 1001


class TestTheNumericFamily:
    def test_writes_each_type_the_way_its_own_input_shows_it(self) -> None:
        assert number_draft(1500, "number", NumberShape(locale="en-US")) == "1,500"
        assert number_draft("2.5", "float", NumberShape(locale="en-US", precision=2)) == "2.50"
        assert number_draft(90, "duration") == "1:30"
        assert number_draft(3600000, "timecode") == "01:00:00"
        assert number_draft(3600000, "timecode", NumberShape(frame_rate=24)) == "01:00:00:00"
        assert number_draft(None, "number") == ""
        assert number_draft("", "number") == ""

    def test_reads_each_type_back_through_the_parse_it_calls_for(self) -> None:
        assert ok(parse_number_input("1,500", "number", NumberShape(locale="en-US"))) == 1500
        assert ok(parse_number_input("1h 30m", "duration")) == 90
        assert ok(parse_number_input("1d", "duration", NumberShape(hours_per_day=8))) == 480
        assert ok(parse_number_input("01:00:00:00", "timecode", NumberShape(frame_rate=24))) == 3600000
        assert ok(parse_number_input("", "number")) is None
        assert err(parse_number_input("nope", "number"))

    def test_holds_an_integer_to_the_bounds_it_was_given(self) -> None:
        assert err(parse_number_input("120", "percent", NumberShape(min=0, max=100)))
        assert ok(parse_number_input("100", "percent", NumberShape(min=0, max=100))) == 100

    def test_undoes_the_locale_marks_only_for_the_types_written_in_them(self) -> None:
        assert number_digits("1,500", "number", NumberShape(locale="en-US")) == "1500"
        assert number_digits("1h 30m", "duration", NumberShape(locale="en-US")) == "1h 30m"
        assert number_digits("01:00:00:00", "timecode", NumberShape(locale="en-US")) == "01:00:00:00"

    def test_sends_a_float_as_a_decimal_string_and_everything_else_as_a_number(self) -> None:
        assert number_wire(2, "float") == "2.0"
        assert number_wire(2, "number") == 2
        assert number_wire(None, "float") is None

    def test_reads_a_stored_value_as_the_number_the_steppers_work_on(self) -> None:
        assert stored_number("2.5") == 2.5
        assert stored_number(0) == 0
        assert stored_number("") is None
        assert stored_number(None) is None
        assert stored_number("nope") is None

    def test_round_trips_every_type_through_its_draft_and_its_parse(self) -> None:
        cases: list[tuple[int, str, NumberShape]] = [
            (1500, "number", NumberShape()),
            (90, "duration", NumberShape()),
            (3600000, "timecode", NumberShape(frame_rate=24)),
            (42, "percent", NumberShape()),
        ]
        for stored, data_type, shape in cases:
            assert ok(parse_number_input(number_draft(stored, data_type, shape), data_type, shape)) == stored
