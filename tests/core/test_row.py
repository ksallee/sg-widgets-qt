"""Port of `packages/core/test/row.test.ts`."""
from __future__ import annotations

from sg_widgets_core.client import EntityRow
from sg_widgets_core.collection import CollectionColumn
from sg_widgets_core.row import (
    RowAnatomy,
    path_of,
    row_code,
    row_fields,
    row_secondary,
    row_sub_label,
    row_thumbnail,
    secondary_type,
    thumbnail_field,
)

column = CollectionColumn(
    path="sg_status_list",
    header="Status",
    data_type="status_list",
    editable=True,
    align="left",
    sortable=True,
    field=None,
)


class TestPathOf:
    def test_takes_a_bare_path_or_a_resolved_column(self) -> None:
        assert path_of("code") == "code"
        assert path_of(column) == "sg_status_list"

    def test_answers_an_empty_path_for_nothing(self) -> None:
        assert path_of(None) == ""


class TestThumbnailField:
    def test_defaults_to_image_and_is_off_on_false(self) -> None:
        assert thumbnail_field(RowAnatomy()) == "image"
        assert thumbnail_field(RowAnatomy(thumbnail="sg_uploaded_movie_image")) == "sg_uploaded_movie_image"
        assert thumbnail_field(RowAnatomy(thumbnail=False)) is None


class TestRowFields:
    def test_asks_for_every_part_of_the_anatomy_once_base_first(self) -> None:
        assert row_fields(
            RowAnatomy(
                label_field="code",
                sub_label_field="description",
                secondary_field=column,
                show_code=True,
                fields=["code", "sg_cut_in"],
            ),
            ["id", "type", "code"],
        ) == ["id", "type", "code", "description", "sg_status_list", "image", "sg_cut_in"]

    def test_leaves_the_image_out_when_the_thumbnail_is_off(self) -> None:
        assert row_fields(RowAnatomy(thumbnail=False), ["id"]) == ["id"]

    def test_asks_for_code_only_when_the_code_is_shown(self) -> None:
        assert row_fields(RowAnatomy(thumbnail=False)) == []
        assert row_fields(RowAnatomy(thumbnail=False, show_code=True)) == ["code"]


class TestRowThumbnail:
    def test_reads_the_named_field_and_ignores_anything_that_is_not_a_url(self) -> None:
        assert row_thumbnail({"image": "https://x/y.jpg"}, RowAnatomy()) == "https://x/y.jpg"
        assert row_thumbnail({"image": None}, RowAnatomy()) is None
        assert row_thumbnail({"image": ""}, RowAnatomy()) is None
        assert row_thumbnail({"image": "https://x/y.jpg"}, RowAnatomy(thumbnail=False)) is None


class TestRowSubLabel:
    def test_is_empty_without_a_field(self) -> None:
        assert row_sub_label({"description": "a shot"}, RowAnatomy()) == ""

    def test_reads_a_scalar_and_a_relationship_alike(self) -> None:
        assert row_sub_label({"description": "a shot"}, RowAnatomy(sub_label_field="description")) == "a shot"
        assert row_sub_label({"sg_cut_in": 1001}, RowAnatomy(sub_label_field="sg_cut_in")) == "1001"
        assert row_sub_label(
            {"project": {"type": "Project", "id": 70, "name": "Blue Moon"}},
            RowAnatomy(sub_label_field="project"),
        ) == "Blue Moon"

    def test_is_empty_on_a_blank_value(self) -> None:
        assert row_sub_label({"description": None}, RowAnatomy(sub_label_field="description")) == ""
        assert row_sub_label({"project": None}, RowAnatomy(sub_label_field="project")) == ""

    def test_takes_a_resolved_column_as_well_as_a_path(self) -> None:
        assert row_sub_label({"sg_status_list": "ip"}, RowAnatomy(sub_label_field=column)) == "ip"


class TestRowCode:
    def test_shows_the_code_only_when_it_says_something_the_label_does_not(self) -> None:
        assert row_code({"code": "sh010"}, "Shot sh010", True) == "sh010"
        assert row_code({"code": "sh010"}, "sh010", True) == ""
        assert row_code({"code": "sh010"}, "Shot sh010", False) == ""
        assert row_code({}, "Shot sh010", True) == ""


class TestRowSecondary:
    def test_answers_the_id_off_the_reference_not_the_attributes(self) -> None:
        row = EntityRow(type="Version", id=862, values={})
        assert row_secondary(row, RowAnatomy(secondary_field="id")) == 862

    def test_reads_any_other_field_off_the_values(self) -> None:
        row = EntityRow(type="Version", id=862, values={"sg_status_list": "ip"})
        assert row_secondary(row, RowAnatomy(secondary_field=column)) == "ip"
        assert row_secondary(EntityRow(type="Version", id=862, values={}), RowAnatomy()) is None


class TestSecondaryType:
    def test_prefers_the_resolved_column_then_the_schema_then_text(self) -> None:
        assert secondary_type(RowAnatomy(secondary_field=column)) == "status_list"
        assert secondary_type(RowAnatomy(secondary_field="sg_status_list"), "status_list") == "status_list"
        assert secondary_type(RowAnatomy(secondary_field="description")) == "text"

    def test_renders_an_id_as_a_number_which_is_the_mono_treatment(self) -> None:
        assert secondary_type(RowAnatomy(secondary_field="id")) == "number"
