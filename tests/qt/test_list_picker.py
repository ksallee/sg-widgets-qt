"""One value of a list field: the vocabulary, the row, the value and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.list_picker import ListOption, ListPicker

from .pickers import list_field, mount, spin, window
from .test_picker_contract import PickerShape, check_contract


def build(qtbot, **props: Any) -> ListPicker:
    props.setdefault("field", list_field())
    root = window(qtbot)
    picker = ListPicker(parent=root, **props)
    return mount(qtbot, picker, root)


def labels_of(picker: ListPicker) -> list:
    model = picker.rows_model
    return [model.index(row, 0).data(Roles.LABEL) for row in range(model.rowCount())]


def test_the_contract(qtbot):
    picker = build(qtbot)
    checked = check_contract(qtbot, picker, PickerShape(inline=False, searchable=False))
    assert "outside press" in checked and "pick" in checked and "readonly" in checked


def test_the_contract_with_a_search_box(qtbot):
    picker = build(qtbot, searchable=True)
    checked = check_contract(qtbot, picker, PickerShape(inline=False, searchable=True))
    assert "caret on open" in checked


def test_the_vocabulary_is_the_fields_valid_values(qtbot):
    picker = build(qtbot)
    assert [one.code for one in picker.options] == [
        "VFX", "2D", "Full CG", "Trailer", "Marketing", "Look Dev",
    ]
    # `display_values` is the only other source of a label (field_types/list).
    assert labels_of(picker) == ["VFX", "Two D", "Full CG", "Trailer", "Marketing", "Lookdev"]


def test_a_project_id_subtracts_the_hidden_values(qtbot):
    # REST does not enforce `hidden_values` on write, so the subtraction is the client's
    # (probe 009).
    picker = build(qtbot, project_id=63)
    assert [one.code for one in picker.options] == ["VFX", "2D", "Full CG", "Look Dev"]


def test_a_stored_value_outside_the_set_keeps_a_row_of_its_own(qtbot):
    picker = build(qtbot, project_id=63, value="Marketing")
    assert "Marketing" in [one.code for one in picker.shown]
    assert picker.control.labels == ["Marketing"]


def test_the_row_shows_the_code_only_where_it_says_more(qtbot):
    picker = build(qtbot, show_code=True)
    model = picker.rows_model
    by_code = {
        model.index(row, 0).data(Roles.LABEL): model.index(row, 0).data(Roles.SECONDARY)
        for row in range(model.rowCount())
    }
    assert by_code["Two D"] == "2D"
    assert by_code["VFX"] == ""


def test_the_value_reaches_the_signal_and_the_list_closes(qtbot):
    picker = build(qtbot)
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_open(True)
    spin(qtbot, 40)
    picker.control.list_surface().activate(1)
    spin(qtbot, 40)
    assert answers == ["2D"]
    assert picker.value == "2D"
    assert not picker.control.is_open


def test_the_clear_control_is_off_on_a_mandatory_field(qtbot):
    picker = build(qtbot, field=list_field(mandatory=True), value="VFX")
    spin(qtbot, 20)
    assert not picker.control.clearable
    assert not picker.control.clear_control().isVisibleTo(picker.control)


def test_a_search_box_narrows_the_set_here(qtbot):
    picker = build(qtbot, searchable=True)
    picker.set_open(True)
    picker.control.set_query("cg")
    spin(qtbot, 40)
    assert [one.code for one in picker.shown] == ["Full CG"]


def test_a_callers_own_options_win_over_the_field(qtbot):
    picker = build(qtbot, options=[ListOption(code="a", label="Alpha")])
    assert [one.code for one in picker.options] == ["a"]
    assert labels_of(picker) == ["Alpha"]


def test_the_message_under_the_control_clears_on_a_pick(qtbot):
    picker = build(qtbot, error="Not a valid value.")
    seen: list = []
    picker.error_changed.connect(seen.append)
    assert picker.error == "Not a valid value."
    picker.set_open(True)
    spin(qtbot, 40)
    picker.control.list_surface().activate(0)
    spin(qtbot, 40)
    assert picker.error is None and seen == [None]


def test_the_alias_module_re_exports_the_picker(qtbot):
    from sg_widgets_qt.widgets.list_select import ListSelect

    assert ListSelect is ListPicker


def test_the_list_opens_with_the_cursor_on_the_value_it_holds(qtbot):
    # Upstream's combobox opens on the row it holds, so the reader sees where the value sits.
    picker = build(qtbot, value="Full CG")
    picker.set_open(True)
    spin(qtbot, 60)
    surface = picker.control.list_surface()
    assert [one.code for one in picker.shown][surface.highlighted()] == "Full CG"


def test_a_picker_holding_nothing_opens_with_nothing_highlighted(qtbot):
    # Nothing held, nothing under the cursor: the first Down takes the first row, as the base says.
    picker = build(qtbot)
    picker.set_open(True)
    spin(qtbot, 60)
    assert picker.control.list_surface().highlighted() < 0
