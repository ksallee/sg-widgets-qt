"""Port of `packages/core/test/field-icons.test.ts`."""
from __future__ import annotations

import re

from sg_widgets_core.field_icons import DEFAULT_FIELD_ICON, FIELD_ICON_NAMES, icon_name_for
from sg_widgets_core.field_types import DATA_TYPES

_KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class TestIconNameFor:
    def test_names_a_lucide_icon_for_every_data_type(self) -> None:
        for data_type in DATA_TYPES:
            name = icon_name_for(data_type)
            assert _KEBAB.match(name), data_type
            assert name in FIELD_ICON_NAMES, data_type

    def test_gives_the_types_a_reader_recognises_their_own_glyph(self) -> None:
        assert icon_name_for("text") == "type"
        assert icon_name_for("date") == "calendar"
        assert icon_name_for("date_time") == "calendar-clock"
        assert icon_name_for("checkbox") == "square-check"
        assert icon_name_for("status_list") == "circle-dot"
        assert icon_name_for("image") == "image"
        assert icon_name_for("url") == "globe"

    def test_separates_a_single_link_from_a_multi_link(self) -> None:
        assert icon_name_for("entity") == "link"
        assert icon_name_for("multi_entity") == "link-2"
        assert icon_name_for("entity") != icon_name_for("multi_entity")

    def test_shares_one_glyph_across_the_numeric_types(self) -> None:
        assert icon_name_for("number") == icon_name_for("float")
        assert icon_name_for("duration") == icon_name_for("timecode")

    def test_falls_back_to_the_document_glyph_for_a_type_it_does_not_know(self) -> None:
        assert icon_name_for("sg_not_a_data_type") == DEFAULT_FIELD_ICON
        assert icon_name_for("") == DEFAULT_FIELD_ICON

    def test_lists_every_name_it_can_return_once_each(self) -> None:
        assert DEFAULT_FIELD_ICON in FIELD_ICON_NAMES
        assert len(set(FIELD_ICON_NAMES)) == len(FIELD_ICON_NAMES)
        for data_type in DATA_TYPES:
            assert icon_name_for(data_type) in FIELD_ICON_NAMES
