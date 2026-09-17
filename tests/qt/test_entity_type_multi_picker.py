"""Several entity types: the derived list, the checkbox rows, the summary and the contract."""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.entity_type_multi_picker import EntityTypeMultiPicker

from .pickers import context_for, mount, spin, window
from .test_picker_contract import PickerShape, check_contract

PRODUCTION = ["Project", "Sequence", "Shot", "Asset", "Version", "Task"]


def settled(qtbot, picker: EntityTypeMultiPicker, ms: int = 900) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)
        if picker.control.items:
            return
    QApplication.processEvents()


def build(qtbot, **props: Any) -> EntityTypeMultiPicker:
    context, client = context_for()
    root = window(qtbot)
    picker = EntityTypeMultiPicker(context=context, parent=root, **props)
    picker.test_client = client
    mount(qtbot, picker, root)
    settled(qtbot, picker)
    return picker


def test_the_contract_on_a_summary_trigger(qtbot):
    picker = build(qtbot, value=["Shot", "Asset"])
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, inline=False, settle=lambda: settled(qtbot, picker, 400)),
    )
    assert "caret on open" in checked and "value keys" in checked


def test_the_contract_on_a_token_field(qtbot):
    picker = build(qtbot, value=["Shot", "Asset"], summary="chips")
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, settle=lambda: settled(qtbot, picker, 400)),
    )
    assert "pick" in checked


def test_deny_narrows_the_derived_list_rather_than_the_read(qtbot):
    picker = build(qtbot, deny=["HumanUser", "ApiUser"])
    before = picker.test_client.reads.get("entity_types", 0)
    names = [one.name for one in picker.types]
    assert "HumanUser" not in names and "Shot" in names
    picker.set_deny(None)
    assert "HumanUser" in [one.name for one in picker.types]
    assert picker.test_client.reads.get("entity_types", 0) == before


def test_every_row_carries_a_checkbox_that_follows_the_value(qtbot):
    picker = build(qtbot, allow=PRODUCTION, value=["Shot"])
    model = picker.rows_model
    checked = {
        model.index(row, 0).data(Roles.LABEL): model.index(row, 0).data(Roles.CHECKED)
        for row in range(model.rowCount())
    }
    assert checked["Shot"] is True and checked["Asset"] is False
    assert picker.control.row_delegate().indicator == "checkbox"


def test_the_row_shows_the_code_and_the_glyph(qtbot):
    picker = build(qtbot, allow=["HumanUser"])
    index = picker.rows_model.index(0, 0)
    assert index.data(Roles.LABEL) == "Person"
    assert index.data(Roles.CODE) == "HumanUser"
    assert index.data(Roles.GLYPH) == "user"


def test_the_value_is_the_whole_list_and_a_pick_keeps_the_list_open(qtbot):
    picker = build(qtbot, allow=PRODUCTION)
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_open(True)
    spin(qtbot, 60)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    picker.control.list_surface().activate(1)
    spin(qtbot, 60)
    assert answers[-1] == PRODUCTION[:2]
    assert picker.control.is_open


def test_a_chip_is_removed_by_its_index(qtbot):
    picker = build(qtbot, allow=PRODUCTION, value=["Shot", "Asset", "Task"], summary="chips")
    spin(qtbot, 60)
    picker.control.remove_requested.emit(1)
    spin(qtbot, 60)
    assert picker.value == ["Shot", "Task"]


def test_the_summary_modes_change_what_the_control_shows(qtbot):
    picker = build(qtbot, allow=PRODUCTION, value=list(PRODUCTION), summary="chips")
    spin(qtbot, 60)
    assert picker.control.inline
    picker.set_summary("count")
    spin(qtbot, 60)
    assert not picker.control.inline and picker.summary == "count"


def test_the_query_narrows_the_list_here(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    picker.control.set_query("ver")
    spin(qtbot, 60)
    assert "Version" in [one.name for one in picker.shown]
    assert len(picker.shown) < len(picker.types)
