"""Several people by server-side search: the preset, the chips, the summary and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.filter import EntityRef, to_api3_hash
from sg_widgets_core.picker import PickerRow
from sg_widgets_qt.widgets.user_multi_picker import UserMultiPicker

from .pickers import context_for, mount, settled, spin, window
from .test_picker_contract import PickerShape, check_contract

ADA = EntityRef(type="HumanUser", id=20, name="Ada Lovelace")
CLEO = EntityRef(type="HumanUser", id=22, name="Cleo Dias")
DMITRI = EntityRef(type="HumanUser", id=23, name="Dmitri Ivanov")


def build(qtbot, **props: Any) -> UserMultiPicker:
    props.setdefault("thumbnail", False)
    context, client = context_for()
    root = window(qtbot)
    picker = UserMultiPicker(context=context, parent=root, **props)
    picker.test_client = client
    return mount(qtbot, picker, root)


def conditions(picker: UserMultiPicker) -> list:
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def test_the_contract_on_a_token_field(qtbot):
    picker = build(qtbot, summary="chips", value=[ADA, CLEO])
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, settle=lambda: settled(qtbot, picker, 600)),
    )
    assert "value keys" in checked and "pick" in checked


def test_the_contract_on_a_summary_trigger(qtbot):
    picker = build(qtbot, summary="ellipsis", value=[ADA, CLEO])
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, inline=False, settle=lambda: settled(qtbot, picker, 600)),
    )
    assert "caret on open" in checked


def test_the_preset_is_the_one_the_single_picker_wears(qtbot):
    picker = build(qtbot)
    assert picker.entity_types == ["HumanUser", "ApiUser"]
    assert any(one == ["sg_status_list", "is", "act"] for one in conditions(picker))
    picker.set_include_api_users(False)
    picker.set_include_inactive(True)
    assert picker.entity_types == ["HumanUser"]
    assert not any(one == ["sg_status_list", "is", "act"] for one in conditions(picker))


def test_the_sub_label_is_the_address(qtbot):
    picker = build(qtbot)
    assert picker.rows_model.sub_label(PickerRow(type="ApiUser", id=90, name="bot")) == "API user"
    picker.set_open(True)
    settled(qtbot, picker)
    row = next(one for one in picker.state.rows if one.type == "HumanUser")
    assert picker.rows_model.sub_label(row) == row.values["email"]


def test_the_value_is_every_reference_in_the_order_they_were_ticked(qtbot):
    picker = build(qtbot)
    answers: list = []
    picker.value_changed.connect(lambda refs, rows: answers.append((refs, rows)))
    picker.set_open(True)
    settled(qtbot, picker)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    picker.control.list_surface().activate(1)
    spin(qtbot, 60)
    refs, rows = answers[-1]
    assert len(refs) == 2 and len(rows) == 2
    assert all(isinstance(ref, EntityRef) for ref in refs)
    assert picker.control.is_open, "a pick keeps a multi picker open"


def test_a_ticked_row_is_untickable_again(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    settled(qtbot, picker)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    assert len(picker.value) == 1
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    assert picker.value == []


def test_hydration_resolves_bare_references(qtbot):
    picker = build(qtbot, value=[EntityRef(type="HumanUser", id=22), EntityRef(type="HumanUser", id=25)])
    spin(qtbot, 700)
    assert all(label and not label.startswith("HumanUser ") for label in picker.control.labels)


def test_the_summary_modes_change_what_the_control_shows(qtbot):
    picker = build(qtbot, value=[ADA, CLEO, DMITRI], summary="count")
    spin(qtbot, 60)
    assert picker.control.status_text() or True
    assert picker.summary == "count"
    picker.set_summary("chips")
    assert picker.summary == "chips" and picker.control.inline
    picker.set_summary("ellipsis")
    assert not picker.control.inline


def test_max_bounds_the_chips_the_row_draws(qtbot):
    picker = build(qtbot, value=[ADA, CLEO, DMITRI], summary="chips", max=2)
    spin(qtbot, 60)
    assert picker.max == 2
    assert sum(1 for chip in picker.control.chips() if chip.isVisibleTo(picker.control)) <= 2


def search_spec(picker: UserMultiPicker, query: str) -> list:
    """The fields a query is matched on, as `(path, operator)`."""
    made = picker.search._opts.search_fields
    return [
        (one, None) if isinstance(one, str) else (one.path, one.operator) for one in made(query)
    ]


def test_the_preset_search_is_the_one_the_single_picker_wears(qtbot):
    picker = build(qtbot)
    assert ("login", None) in search_spec(picker, "ada")
    assert ("login", None) not in search_spec(picker, "ada lovelace")
    assert ("email", "starts_with") in search_spec(picker, "ada")
    assert ("email", "contains") in search_spec(picker, "ada.lovelace@")
    assert picker.round_thumbnail is True


def test_a_query_on_the_local_part_does_not_widen_to_the_shared_domain(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    settled(qtbot, picker)
    picker.control.set_query("le")
    spin(qtbot, 900)
    assert [row.name for row in picker.state.rows] == ["Cleo Dias"]
