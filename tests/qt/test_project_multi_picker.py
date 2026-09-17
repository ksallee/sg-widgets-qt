"""Several projects by server-side search: the listing rule, the chips and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.filter import EntityRef, to_api3_hash
from sg_widgets_qt.widgets.project_multi_picker import ProjectMultiPicker

from .pickers import OTHER_PROJECT, PROJECT, context_for, mount, settled, spin, window
from .test_picker_contract import PickerShape, check_contract

BLUE = EntityRef(type="Project", id=70, name="Blue Moon Rising")
HARBOUR = EntityRef(type="Project", id=71, name="Harbour Lights")
FERRY = EntityRef(type="Project", id=72, name="Night Ferry")


def build(qtbot, **props: Any) -> ProjectMultiPicker:
    props.setdefault("thumbnail", False)
    context, client = context_for()
    root = window(qtbot)
    picker = ProjectMultiPicker(context=context, parent=root, **props)
    picker.test_client = client
    return mount(qtbot, picker, root)


def conditions(picker: ProjectMultiPicker) -> list:
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def test_the_contract_on_a_token_field(qtbot):
    picker = build(qtbot, summary="chips", value=[BLUE, HARBOUR])
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, settle=lambda: settled(qtbot, picker, 600)),
    )
    assert "value keys" in checked and "pick" in checked


def test_the_contract_on_a_summary_trigger(qtbot):
    picker = build(qtbot, value=[BLUE, HARBOUR])
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, inline=False, settle=lambda: settled(qtbot, picker, 600)),
    )
    assert "caret on open" in checked


def test_archived_projects_are_hidden_unless_asked_for(qtbot):
    picker = build(qtbot)
    assert any(one == ["archived", "is", False] for one in conditions(picker))
    picker.set_include_archived(True)
    assert not any(one == ["archived", "is", False] for one in conditions(picker))


def test_the_status_is_the_sub_label_and_both_preset_fields_are_read(qtbot):
    picker = build(qtbot)
    assert picker.rows_model.sub_label_field == "sg_status"
    assert set(["sg_status", "archived"]).issubset(set(picker.rows_model.fields))


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
    assert [ref.type for ref in refs] == ["Project", "Project"]
    assert len(rows) == 2
    assert picker.control.is_open


def test_hydration_resolves_bare_references(qtbot):
    picker = build(
        qtbot,
        value=[EntityRef(type="Project", id=PROJECT), EntityRef(type="Project", id=OTHER_PROJECT)],
    )
    spin(qtbot, 700)
    assert all(label and not label.startswith("Project ") for label in picker.control.labels)


def test_a_chip_is_removed_by_its_index(qtbot):
    picker = build(qtbot, summary="chips", value=[BLUE, HARBOUR, FERRY])
    spin(qtbot, 60)
    picker.control.remove_requested.emit(1)
    spin(qtbot, 60)
    assert [ref.id for ref in picker.value] == [70, 72]


def test_the_summary_modes_change_what_the_control_shows(qtbot):
    picker = build(qtbot, value=[BLUE, HARBOUR, FERRY], summary="chips")
    spin(qtbot, 60)
    assert picker.control.inline
    picker.set_summary("count")
    spin(qtbot, 60)
    assert not picker.control.inline and picker.summary == "count"
