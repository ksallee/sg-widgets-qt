"""Port of `packages/core/test/client.test.ts`.

Every test that drives `RestClient` is skipped here: the REST implementation is not
ported, and the `shotgun_api3` adapter carries those behaviours.
"""
from __future__ import annotations

from typing import Any

import pytest

from sg_widgets_core.client import normalize_hierarchy_node

ADAPTER = "RestClient is not ported; the shotgun_api3 adapter covers this."


class TestTextSearchOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_sends_the_hash_content_type_with_a_hash_group_per_type_and_flattens_the_row(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_caps_the_page_size_at_25_which_is_the_cap_and_the_default(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_reads_a_row_that_links_to_nothing_as_two_empty_strings(self) -> None:
        pass


class TestTheHierarchyEndpointsOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_sends_plain_json_which_is_the_only_content_type_they_take(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_reads_both_ref_shapes_out_of_an_expand(self) -> None:
        pass


class TestStatusIconsOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_drops_an_image_icon_the_site_holds_with_an_empty_url(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_strips_the_newlines_an_image_icon_carries_in_its_data_url(self) -> None:
        pass


class TestNormalizeHierarchyNode:
    def test_keeps_one_child_when_expand_repeats_the_no_sequence_bucket_after_every_group(self) -> None:
        bucket = {
            "path": "/Project/91/Shot/sg_sequence/Sequence/__none__",
            "label": "Shots with no Sequence",
            "has_children": True,
            "ref": {"kind": "entity_type", "value": "Shot"},
        }

        def seq(id: int) -> dict[str, Any]:
            return {
                "path": f"/Project/91/Shot/sg_sequence/Sequence/{id}",
                "label": str(id),
                "has_children": True,
                "ref": {"kind": "entity", "value": {"type": "Sequence", "id": id}},
            }

        node = normalize_hierarchy_node(
            {
                "path": "/Project/91/Shot",
                "label": "Shots",
                "has_children": True,
                "ref": {"kind": "entity_type", "value": "Shot"},
                "children": [seq(41), bucket, seq(307), bucket, seq(1362), bucket],
            },
            "/Project/91/Shot",
        )
        assert [c.path for c in node.children] == [
            "/Project/91/Shot/sg_sequence/Sequence/41",
            "/Project/91/Shot/sg_sequence/Sequence/__none__",
            "/Project/91/Shot/sg_sequence/Sequence/307",
            "/Project/91/Shot/sg_sequence/Sequence/1362",
        ]


class TestANoteThreadOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_asks_for_one_path_widens_a_type_through_entity_fields_and_reads_the_author_from_two_keys(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_keeps_the_author_under_created_by_on_a_note_widened_with_user(self) -> None:
        pass


class TestOneFieldOfTheSchemaOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_answers_the_override_when_the_site_reads_the_field_as_data_null(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_refuses_a_data_null_answer_for_a_field_it_has_no_override_for(self) -> None:
        pass


class TestTheEventLogOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_narrows_on_the_filterable_fields_sorts_id_and_lifts_the_two_values_out_of_meta(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_sends_an_empty_group_when_nothing_narrows_it(self) -> None:
        pass


class TestFollowingOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_sends_the_two_filters_it_takes_and_reads_a_type_and_an_id_per_row(self) -> None:
        pass


class TestACreateOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_posts_plain_json_to_the_type_and_answers_the_row(self) -> None:
        pass


class TestAnUploadOnTheWire:
    @pytest.mark.skip(reason=ADAPTER)
    def test_takes_a_ticket_puts_the_bytes_with_no_auth_header_and_completes_without_parsing_the_reply(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_leaves_the_field_out_of_the_path_for_a_generic_attachment(self) -> None:
        pass

    @pytest.mark.skip(reason=ADAPTER)
    def test_calls_an_absolute_complete_upload_link_as_it_is(self) -> None:
        pass
