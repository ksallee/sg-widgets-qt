"""Several values of a list field: the vocabulary, the chips, the value and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.list_multi_picker import ListMultiPicker

from .pickers import list_field, mount, spin, window
from .test_picker_contract import PickerShape, check_contract


def build(qtbot, **props: Any) -> ListMultiPicker:
    props.setdefault("field", list_field())
    root = window(qtbot)
    picker = ListMultiPicker(parent=root, **props)
    return mount(qtbot, picker, root)


def test_the_contract_on_a_summary_trigger(qtbot):
    picker = build(qtbot, value=["VFX", "2D"])
    checked = check_contract(
        qtbot, picker, PickerShape(multiple=True, inline=False, searchable=False)
    )
    assert "value keys" in checked and "pick" in checked


def test_the_contract_on_a_token_field(qtbot):
    picker = build(qtbot, value=["VFX", "2D"], summary="chips")
    checked = check_contract(
        qtbot, picker, PickerShape(multiple=True, inline=True, searchable=False)
    )
    assert "caret on open" in checked


def test_the_vocabulary_is_the_fields_valid_values(qtbot):
    picker = build(qtbot)
    assert [one.code for one in picker.options] == [
        "VFX", "2D", "Full CG", "Trailer", "Marketing", "Look Dev",
    ]


def test_a_project_id_subtracts_the_hidden_values(qtbot):
    picker = build(qtbot, project_id=63)
    assert [one.code for one in picker.options] == ["VFX", "2D", "Full CG", "Look Dev"]


def test_a_chosen_value_outside_the_set_keeps_a_row_of_its_own(qtbot):
    picker = build(qtbot, project_id=63, value=["Marketing", "VFX"])
    assert "Marketing" in [one.code for one in picker.shown]
    assert picker.control.labels == ["Marketing", "VFX"]


def test_every_row_carries_a_checkbox_that_follows_the_value(qtbot):
    picker = build(qtbot, value=["2D"])
    model = picker.rows_model
    checked = {
        model.index(row, 0).data(Roles.LABEL): model.index(row, 0).data(Roles.CHECKED)
        for row in range(model.rowCount())
    }
    assert checked["Two D"] is True and checked["VFX"] is False
    assert picker.control.row_delegate().indicator == "checkbox"


def test_a_pick_keeps_the_list_open_and_the_value_is_the_whole_list(qtbot):
    picker = build(qtbot)
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_open(True)
    spin(qtbot, 40)
    picker.control.list_surface().activate(0)
    spin(qtbot, 40)
    picker.control.list_surface().activate(1)
    spin(qtbot, 40)
    assert answers == [["VFX"], ["VFX", "2D"]]
    assert picker.control.is_open


def test_a_chip_is_removed_by_its_index(qtbot):
    picker = build(qtbot, value=["VFX", "2D", "Full CG"], summary="chips")
    spin(qtbot, 40)
    picker.control.remove_requested.emit(1)
    spin(qtbot, 40)
    assert picker.value == ["VFX", "Full CG"]


def test_the_clear_control_is_off_on_a_mandatory_field(qtbot):
    picker = build(qtbot, field=list_field(mandatory=True), value=["VFX"])
    spin(qtbot, 20)
    assert not picker.control.clearable


def test_the_alias_module_re_exports_the_picker(qtbot):
    from sg_widgets_qt.widgets.list_multi_select import ListMultiSelect

    assert ListMultiSelect is ListMultiPicker


def test_the_list_opens_with_the_cursor_on_the_first_value_it_holds(qtbot):
    # Upstream's combobox highlights the first of the chosen values on open.
    picker = build(qtbot, value=["Full CG", "VFX"])
    picker.set_open(True)
    spin(qtbot, 60)
    surface = picker.control.list_surface()
    assert [one.code for one in picker.shown][surface.highlighted()] == "Full CG"
