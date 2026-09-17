"""Port of `packages/core/test/field-types.test.ts`."""
from __future__ import annotations

from sg_widgets_core.field_types import (
    DATA_TYPES,
    OPERATORS_BY_TYPE,
    VALUE_SHAPE,
    is_filterable,
    operators_for,
    supports_operator,
)


class TestOperatorVocabularies:
    def test_match_what_the_api_printed_for_a_bogus_operator(self) -> None:
        assert operators_for("text") == (
            "contains", "not_contains", "is", "is_not", "starts_with", "ends_with", "in", "not_in",
        )
        assert operators_for("status_list") == ("is", "is_not", "in", "not_in")
        assert operators_for("checkbox") == ("is", "is_not")
        assert "name_contains" in operators_for("entity")
        assert operators_for("date") == operators_for("date_time")
        assert "greater_than_or_equal" not in operators_for("number")

    def test_marks_the_five_unfilterable_types(self) -> None:
        for t in ("url", "serializable", "calculated", "summary", "password"):
            assert is_filterable(t) is False
        assert is_filterable("text") is True

    def test_every_operator_of_every_type_has_a_value_shape(self) -> None:
        for t in DATA_TYPES:
            for op in OPERATORS_BY_TYPE[t]:
                assert VALUE_SHAPE.get(op) is not None

    def test_supports_operator_is_per_type(self) -> None:
        assert supports_operator("status_list", "contains") is False
        assert supports_operator("text", "contains") is True
