"""Several statuses: the option set, the rows, the badges, the summary and the contract."""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.status_badge import StatusBadge
from sg_widgets_qt.widgets.status_multi_picker import StatusMultiPicker

from .pickers import OTHER_PROJECT, PROJECT, context_for, mount, spin, window
from .test_picker_contract import PickerShape, check_contract


def settled(qtbot, picker: StatusMultiPicker, ms: int = 900) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)
        if not picker.load.loading:
            return
    QApplication.processEvents()


def build(qtbot, **props: Any) -> StatusMultiPicker:
    props.setdefault("entity_type", "Version")
    context, client = context_for()
    root = window(qtbot)
    picker = StatusMultiPicker(context=context, parent=root, **props)
    picker.test_client = client
    mount(qtbot, picker, root)
    settled(qtbot, picker)
    return picker


def codes(picker: StatusMultiPicker) -> list:
    return [one.code for one in picker.options]


def test_the_contract_on_a_summary_trigger(qtbot):
    picker = build(qtbot, project_id=PROJECT, value=["ip", "apr"])
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, inline=False, settle=lambda: settled(qtbot, picker, 400)),
    )
    assert "caret on open" in checked and "value keys" in checked


def test_the_contract_on_a_token_field(qtbot):
    picker = build(qtbot, project_id=PROJECT, value=["ip", "apr"], summary="chips")
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, settle=lambda: settled(qtbot, picker, 400)),
    )
    assert "pick" in checked


def test_the_options_are_valid_values_minus_the_projects_hidden_values(qtbot):
    picker = build(qtbot, project_id=PROJECT)
    assert "ip" in codes(picker) and "pndad" not in codes(picker)


def test_several_projects_offer_their_intersection(qtbot):
    picker = build(qtbot, project_ids=[PROJECT, OTHER_PROJECT])
    assert "pndad" not in codes(picker), "a code either project hides is not offered"
    assert "ip" in codes(picker)


def test_a_row_is_the_glyph_the_name_and_the_code_after_its_checkbox(qtbot):
    picker = build(qtbot, project_id=PROJECT, value=["ip"])
    model = picker.rows_model
    at = next(
        row
        for row in range(model.rowCount())
        if model.index(row, 0).data(Roles.LABEL) == "In Progress"
    )
    index = model.index(at, 0)
    assert index.data(Roles.SECONDARY) == "ip"
    assert index.data(Roles.CHECKED) is True
    assert picker.control.row_delegate().indicator == "checkbox"


def test_every_chosen_code_is_a_badge_in_the_control(qtbot):
    picker = build(qtbot, project_id=PROJECT, value=["ip", "apr"], summary="chips")
    spin(qtbot, 60)
    chips = picker.control.chips()
    assert [chip.code for chip in chips if isinstance(chip, StatusBadge)] == ["ip", "apr"]


def test_a_code_the_option_set_does_not_carry_is_never_dropped(qtbot):
    picker = build(qtbot, project_id=PROJECT, value=["zz_retired", "rev"])
    assert picker.value == ["zz_retired", "rev"]
    assert "zz_retired" in [one.code for one in picker.list_picker.shown]


def test_the_search_box_narrows_the_vocabulary_here(qtbot):
    # A status list has no substring operator (field_types/status_list).
    picker = build(qtbot, project_id=PROJECT)
    picker.set_open(True)
    picker.control.set_query("progress")
    spin(qtbot, 60)
    assert [one.label for one in picker.list_picker.shown] == ["In Progress"]


def test_the_value_is_the_whole_list_and_a_pick_keeps_the_list_open(qtbot):
    picker = build(qtbot, project_id=PROJECT)
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_open(True)
    spin(qtbot, 60)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    picker.control.list_surface().activate(1)
    spin(qtbot, 60)
    assert answers[-1] == codes(picker)[:2]
    assert picker.control.is_open


def test_a_mandatory_field_offers_no_clear(qtbot):
    picker = build(qtbot, entity_type="Note", value=["opn"])
    assert picker.load.field is not None and picker.load.field.mandatory
    assert not picker.control.clearable


def test_a_bare_icon_badge_doubles_the_cap(qtbot):
    picker = build(qtbot, project_id=PROJECT, value=["ip", "apr"], max=1)
    assert picker.list_picker.max == 1
    picker.set_badge("icon")
    assert picker.list_picker.max == 2
