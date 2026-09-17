"""One project by server-side search: the listing rule, the row, the value and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_core.filter import EntityRef, to_api3_hash
from sg_widgets_core.picker import PickerRow
from sg_widgets_qt.widgets.project_picker import ProjectPicker

from .pickers import PROJECT, context_for, mount, settled, spin, window
from .test_picker_contract import PickerShape, check_contract


def build(qtbot, **props: Any) -> ProjectPicker:
    props.setdefault("thumbnail", False)
    context, client = context_for()
    root = window(qtbot)
    picker = ProjectPicker(context=context, parent=root, **props)
    picker.test_client = client
    return mount(qtbot, picker, root)


def conditions(picker: ProjectPicker) -> list:
    wire = to_api3_hash(picker.search._opts.filters)
    return list(wire.get("conditions", [])) if wire else []


def test_the_contract(qtbot):
    picker = build(qtbot)
    checked = check_contract(
        qtbot, picker, PickerShape(settle=lambda: settled(qtbot, picker, 600))
    )
    assert "press toggles" in checked and "pick" in checked


def test_archived_projects_are_hidden_unless_asked_for(qtbot):
    # `archived`, `is_template` and `is_demo` are the discriminators, not `sg_status`
    # (018_project_listing).
    picker = build(qtbot)
    assert any(one == ["archived", "is", False] for one in conditions(picker))
    picker.set_include_archived(True)
    assert not any(one == ["archived", "is", False] for one in conditions(picker))


def test_the_listing_rule_leaves_a_pre_filter_standing(qtbot):
    from sg_widgets_core.filter import condition, group

    own = group("and", [condition("is_template", "is", False)])
    picker = build(qtbot, filters=own)
    paths = [one[0] for one in conditions(picker) if isinstance(one, list)]
    assert "archived" in paths
    assert picker.filters is own
    assert any(isinstance(one, dict) for one in conditions(picker))


def test_the_status_and_the_archived_flag_are_read_and_the_status_is_the_sub_label(qtbot):
    picker = build(qtbot)
    assert set(["sg_status", "archived"]).issubset(set(picker.rows_model.fields))
    assert picker.rows_model.sub_label_field == "sg_status"
    picker.set_open(True)
    settled(qtbot, picker)
    row = picker.state.rows[0]
    assert row.values.get("sg_status")


def test_only_projects_are_searched(qtbot):
    picker = build(qtbot)
    assert picker.entity_types == ["Project"]
    picker.set_open(True)
    settled(qtbot, picker)
    assert {row.type for row in picker.state.rows} == {"Project"}


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
    assert ref.type == "Project"
    assert not picker.control.is_open


def test_hydration_resolves_a_bare_reference(qtbot):
    picker = build(qtbot, value=EntityRef(type="Project", id=PROJECT))
    spin(qtbot, 600)
    label = picker.control.labels[0]
    assert label and label != f"Project {PROJECT}"


def test_a_thumbnail_field_is_kept_by_default(qtbot):
    picker = build(qtbot, thumbnail="image")
    assert picker.thumbnail == "image"
    assert picker.control.row_delegate().thumbnail
