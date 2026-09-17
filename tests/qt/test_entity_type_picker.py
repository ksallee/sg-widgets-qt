"""One entity type: the derived list, the row, the value and the contract."""
from __future__ import annotations

import time
from typing import Any

from qtpy.QtWidgets import QApplication

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.entity_type_picker import EntityTypePicker

from .pickers import context_for, mount, spin, window
from .test_picker_contract import PickerShape, check_contract

PRODUCTION = ["Project", "Sequence", "Shot", "Asset", "Version", "Task"]


def settled(qtbot, picker: EntityTypePicker, ms: int = 900) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)
        if picker.control.items:
            return
    QApplication.processEvents()


def build(qtbot, **props: Any) -> EntityTypePicker:
    context, client = context_for()
    root = window(qtbot)
    picker = EntityTypePicker(context=context, parent=root, **props)
    picker.test_client = client
    mount(qtbot, picker, root)
    settled(qtbot, picker)
    return picker


def test_the_contract(qtbot):
    picker = build(qtbot)
    checked = check_contract(
        qtbot, picker, PickerShape(settle=lambda: settled(qtbot, picker, 400))
    )
    assert "press toggles" in checked and "pick" in checked and "readonly" in checked


def test_the_list_is_every_enabled_type(qtbot):
    # `/schema` is 12KB and holds every enabled type, custom slots included (probe 002).
    picker = build(qtbot)
    assert len(picker.types) > 6
    assert "Shot" in [one.name for one in picker.types]


def test_allow_and_deny_narrow_the_derived_list_rather_than_the_read(qtbot):
    picker = build(qtbot, allow=PRODUCTION)
    before = picker.test_client.reads.get("entity_types", 0)
    assert [one.name for one in picker.types] == PRODUCTION
    picker.set_deny(["Task"])
    assert "Task" not in [one.name for one in picker.types]
    picker.set_allow(None)
    assert len(picker.types) > len(PRODUCTION)
    assert picker.test_client.reads.get("entity_types", 0) == before, "no second read"


def test_the_query_narrows_the_list_here(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    picker.control.set_query("ver")
    spin(qtbot, 60)
    codes = [one.name for one in picker.shown]
    assert codes and "Version" in codes
    assert len(codes) < len(picker.types)


def test_a_row_carries_its_glyph_and_its_code_beside_the_display_name(qtbot):
    picker = build(qtbot, allow=["HumanUser"])
    model = picker.rows_model
    index = model.index(0, 0)
    assert index.data(Roles.LABEL) == "Person"
    assert index.data(Roles.CODE) == "HumanUser"
    assert index.data(Roles.GLYPH) == "user"


def test_show_code_off_drops_the_code(qtbot):
    picker = build(qtbot, allow=["HumanUser"], show_code=False)
    assert picker.rows_model.index(0, 0).data(Roles.CODE) == ""


def test_the_code_reaches_the_signal_and_a_pick_closes_the_list(qtbot):
    picker = build(qtbot, allow=PRODUCTION)
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_open(True)
    spin(qtbot, 60)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    assert answers and answers[-1] in PRODUCTION
    assert picker.value == answers[-1]
    assert not picker.control.is_open


def test_the_clear_control_emits_none(qtbot):
    picker = build(qtbot, allow=PRODUCTION, value="Shot")
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.control.cleared.emit()
    spin(qtbot, 40)
    assert answers == [None] and picker.value is None


def test_the_control_is_a_token_field_with_the_caret_in_it(qtbot):
    picker = build(qtbot, value="Shot")
    assert picker.control.inline, "typing narrows the list from the control itself"
    assert picker.control.labels == ["Shot"]
