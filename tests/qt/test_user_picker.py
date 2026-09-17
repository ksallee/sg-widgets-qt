"""One person by server-side search: the preset, the row, the value and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.filter import EntityRef, to_api3_hash
from sg_widgets_core.picker import PickerRow
from sg_widgets_qt.widgets.user_picker import UserPicker

from .pickers import context_for, mount, settled, spin, window
from .test_picker_contract import PickerShape, check_contract

#: People the fixtures always carry: one active, one whose status is `dis`.
ADA = 20
BO = 21


def build(qtbot, **props: Any) -> UserPicker:
    """One user picker on a themed window. The fixtures' pictures are never read here."""
    props.setdefault("thumbnail", False)
    context, client = context_for()
    root = window(qtbot)
    picker = UserPicker(context=context, parent=root, **props)
    picker.test_client = client
    return mount(qtbot, picker, root)


def conditions(picker: UserPicker) -> list:
    """The pre-filter as the wire shape, so a condition can be looked for by path."""
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def test_the_contract(qtbot):
    picker = build(qtbot)
    checked = check_contract(
        qtbot, picker, PickerShape(settle=lambda: settled(qtbot, picker, 600))
    )
    assert "press toggles" in checked and "pick" in checked and "disabled" in checked


def test_the_preset_searches_people_and_script_accounts(qtbot):
    picker = build(qtbot)
    assert picker.entity_types == ["HumanUser", "ApiUser"]
    picker.set_include_api_users(False)
    assert picker.entity_types == ["HumanUser"]


def test_active_only_is_the_status_condition_and_inactive_drops_it(qtbot):
    # `sg_status_list` on HumanUser is `act` and `dis`, `act` the default
    # (entity_types/HumanUser).
    picker = build(qtbot)
    assert any(one == ["sg_status_list", "is", "act"] for one in conditions(picker))
    picker.set_include_inactive(True)
    assert not any(one == ["sg_status_list", "is", "act"] for one in conditions(picker))


def test_the_active_condition_leaves_a_pre_filter_standing(qtbot):
    from sg_widgets_core.filter import condition, group

    own = group("and", [condition("login", "starts_with", "a")])
    picker = build(qtbot, filters=own)
    paths = [one[0] for one in conditions(picker) if isinstance(one, list)]
    nested = [one for one in conditions(picker) if isinstance(one, dict)]
    assert "sg_status_list" in paths
    assert nested, "the caller's own group survived the merge"
    assert picker.filters is own


def test_the_login_and_the_email_are_read_and_the_sub_label_is_the_address(qtbot):
    picker = build(qtbot)
    assert set(["login", "email", "sg_status_list"]).issubset(set(picker.rows_model.fields))
    picker.set_open(True)
    settled(qtbot, picker)
    row = next(one for one in picker.state.rows if one.type == "HumanUser")
    assert picker.rows_model.sub_label(row) == row.values["email"]


def test_a_script_account_reads_as_an_api_user(qtbot):
    picker = build(qtbot)
    assert picker.rows_model.sub_label(PickerRow(type="ApiUser", id=90, name="bot")) == "API user"


def test_hydration_resolves_a_bare_reference(qtbot):
    picker = build(qtbot, value=EntityRef(type="HumanUser", id=ADA))
    spin(qtbot, 600)
    label = picker.control.labels[0]
    assert label and label != f"HumanUser {ADA}"


def test_the_value_and_its_row_reach_the_signal(qtbot):
    picker = build(qtbot)
    answers: list = []
    picker.value_changed.connect(lambda ref, row: answers.append((ref, row)))
    picker.set_open(True)
    settled(qtbot, picker)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    ref, row = answers[-1]
    assert isinstance(ref, EntityRef) and isinstance(row, PickerRow)
    assert ref.type == row.type and ref.id == row.id
    assert not picker.control.is_open, "a pick closes a single picker"


def test_extra_fields_are_added_to_the_preset_rather_than_replacing_it(qtbot):
    picker = build(qtbot, fields=["department"])
    assert picker.fields == ["department"]
    assert "login" in picker.rows_model.fields and "department" in picker.rows_model.fields


def test_an_inactive_person_is_out_of_the_list_until_asked_for(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    settled(qtbot, picker)
    assert all(row.values.get("sg_status_list") != "dis" for row in picker.state.rows)
    picker.set_include_inactive(True)
    picker.control.set_query("bo")
    spin(qtbot, 700)
    assert any(row.id == BO for row in picker.state.rows)
