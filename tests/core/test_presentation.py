"""Port of `packages/core/test/presentation.test.ts`."""
from __future__ import annotations

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.presentation import (
    PathLabelOptions,
    entity_detail_url,
    normalize_site_url,
    path_label,
)
from sg_widgets_core.schema_service import create_schema_service

from .fake_client import FakeClient

SITE = "https://example.shotgunstudio.com"


class TestEntityDetailUrl:
    def test_addresses_a_row_on_the_web_app(self) -> None:
        assert entity_detail_url(SITE, EntityRef(type="Shot", id=862)) == f"{SITE}/detail/Shot/862"

    def test_drops_trailing_slashes_on_the_site(self) -> None:
        assert entity_detail_url(f"{SITE}//", EntityRef(type="Task", id=5700)) == f"{SITE}/detail/Task/5700"

    def test_answers_none_without_a_site_or_a_row(self) -> None:
        assert entity_detail_url("", EntityRef(type="Shot", id=862)) is None
        assert entity_detail_url(None, EntityRef(type="Shot", id=862)) is None
        assert entity_detail_url(SITE, None) is None
        assert entity_detail_url(SITE, EntityRef(type="", id=1)) is None

    def test_takes_the_name_a_chip_carries_without_putting_it_in_the_url(self) -> None:
        ref = EntityRef(type="Shot", id=1, name="sh010_0010")
        assert entity_detail_url(SITE, ref) == f"{SITE}/detail/Shot/1"


class TestNormalizeSiteUrl:
    def test_trims_space_and_trailing_slashes_and_answers_empty_for_nothing(self) -> None:
        assert normalize_site_url(f"  {SITE}/ ") == SITE
        assert normalize_site_url(None) == ""


class TestPathLabel:
    schema = create_schema_service(FakeClient())

    def test_names_a_plain_field_by_its_display_name(self) -> None:
        assert path_label(self.schema.resolve_path("Task", "sg_status_list")) == "Status"

    def test_leaves_the_type_out_when_the_hop_links_one_type(self) -> None:
        assert path_label(self.schema.resolve_path("Version", "sg_task.Task.sg_status_list")) == "Task › Status"

    def test_names_the_type_when_the_hop_links_several(self) -> None:
        label = path_label(self.schema.resolve_path("Version", "entity.Shot.sg_sequence"))
        assert label == "Link › Shot › Sequence"

    def test_names_every_ambiguous_hop_of_a_longer_path(self) -> None:
        label = path_label(self.schema.resolve_path("Version", "entity.Shot.sg_sequence.Sequence.code"))
        assert label == "Link › Shot › Sequence › Sequence Name"

    def test_drops_the_type_on_request(self) -> None:
        segments = self.schema.resolve_path("Version", "entity.Shot.sg_sequence")
        assert path_label(segments, PathLabelOptions(type_when_ambiguous=False)) == "Link › Sequence"

    def test_shows_a_type_by_its_display_name_when_one_is_given(self) -> None:
        segments = self.schema.resolve_path("Version", "entity.Shot.sg_sequence")
        assert path_label(segments, PathLabelOptions(type_labels={"Shot": "Plan"})) == "Link › Plan › Sequence"

    def test_takes_a_separator(self) -> None:
        segments = self.schema.resolve_path("Version", "sg_task.Task.sg_status_list")
        assert path_label(segments, PathLabelOptions(separator=" / ")) == "Task / Status"


class TestTheContextSiteUrl:
    def test_carries_the_site_every_widget_links_into(self) -> None:
        sg = create_sg_context(FakeClient(), SgContextOptions(site_url=f"{SITE}/"))
        assert sg.site_url == SITE
        assert entity_detail_url(sg.site_url, EntityRef(type="Asset", id=1226)) == f"{SITE}/detail/Asset/1226"

    def test_is_empty_when_the_app_named_none(self) -> None:
        assert create_sg_context(FakeClient()).site_url == ""
