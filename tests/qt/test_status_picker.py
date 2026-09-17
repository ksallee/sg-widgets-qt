"""One status: the option set, the row, the badge, the mandatory field and the contract."""
from __future__ import annotations

from typing import Any

from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.widgets.status_badge import StatusBadge
from sg_widgets_qt.widgets.status_picker import StatusLeadDelegate, StatusPicker

from .pickers import OTHER_PROJECT, PROJECT, context_for, mount, spin, window
from .test_picker_contract import PickerShape, check_contract


def build(qtbot, **props: Any) -> StatusPicker:
    props.setdefault("entity_type", "Version")
    context, client = context_for()
    root = window(qtbot)
    picker = StatusPicker(context=context, parent=root, **props)
    picker.test_client = client
    mount(qtbot, picker, root)
    settled(qtbot, picker)
    return picker


def settled(qtbot, picker: StatusPicker, ms: int = 900) -> None:
    import time

    from qtpy.QtWidgets import QApplication

    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)
        if not picker.load.loading:
            return
    QApplication.processEvents()


def codes(picker: StatusPicker) -> list:
    return [one.code for one in picker.options]


def test_the_contract(qtbot):
    picker = build(qtbot, project_id=PROJECT)
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(inline=False, searchable=False, settle=lambda: settled(qtbot, picker, 400)),
    )
    assert "press toggles" in checked and "pick" in checked and "disabled" in checked


def test_the_options_are_valid_values_minus_the_projects_hidden_values(qtbot):
    # `valid_values` minus `hidden_values`, read with `project_id` (probe 009).
    picker = build(qtbot, project_id=PROJECT)
    assert "ip" in codes(picker)
    assert "pndad" not in codes(picker), "a code the project hides is not offered"


def test_several_projects_offer_their_intersection(qtbot):
    picker = build(qtbot, project_ids=[PROJECT, OTHER_PROJECT])
    both = set(codes(picker))
    picker.set_project_ids([OTHER_PROJECT])
    settled(qtbot, picker)
    one = set(codes(picker))
    assert both.issubset(one)
    assert "pndad" in one and "pndad" not in both


def test_a_row_is_the_glyph_the_name_and_the_code(qtbot):
    picker = build(qtbot, project_id=PROJECT, show_code=True)
    model = picker.rows_model
    at = next(
        row for row in range(model.rowCount()) if model.index(row, 0).data(Roles.LABEL) == "In Progress"
    )
    index = model.index(at, 0)
    assert index.data(Roles.SECONDARY) == "ip", "the code is the row's secondary, never a badge"
    # The delegate the list paints with, not the one the surface was built with: the base
    # keeps answering that one, so the anatomy is read off the view.
    delegate = picker.control.list_surface().itemDelegate()
    assert isinstance(delegate, StatusLeadDelegate), "the rows are drawn with the status row"
    assert delegate.thumbnail, "the glyph keeps the leading slot"
    source = delegate._source_for(index)
    assert source is not None and source.draws(True), "the row resolves a glyph of its own"


def test_every_option_resolves_a_glyph_and_an_unknown_code_takes_the_dot(qtbot):
    # The bundled sprite cells draw with no site access; a key with no cell and no site url
    # falls back to the neutral dot rather than to nothing (010_status_icons).
    picker = build(qtbot, project_id=PROJECT, value="zz_retired")
    kinds = {code: source.kind for code, source in picker._sources.items()}
    assert kinds["ip"] == "cell", "a shipped icon is a bundled sprite cell"
    assert kinds["custom"] == "image", "a site's own icon is its data url"
    assert kinds["vwd"] == "dot", "a shipped key with no bundled cell and no site takes the dot"
    assert kinds["zz_retired"] == "none", "a code with no Status row behind it resolves to nothing"
    assert all(picker._sources[code].draws(True) for code in kinds), (
        "a row always draws a mark: the dot stands where there is no picture"
    )


def test_the_chosen_value_is_a_badge_in_the_control(qtbot):
    picker = build(qtbot, project_id=PROJECT, value="ip")
    chips = picker.control.chips()
    assert chips and isinstance(chips[0], StatusBadge)
    assert chips[0].code == "ip"


def test_show_code_off_leaves_the_label_alone(qtbot):
    picker = build(qtbot, project_id=PROJECT, show_code=False)
    model = picker.rows_model
    assert all(
        model.index(row, 0).data(Roles.SECONDARY) == "" for row in range(model.rowCount())
    )


def test_a_mandatory_field_offers_no_clear(qtbot):
    picker = build(qtbot, entity_type="Note", value="opn")
    assert picker.load.field is not None and picker.load.field.mandatory
    assert not picker.control.clearable


def test_a_code_the_field_does_not_carry_still_renders(qtbot):
    # A row may legally hold a code outside the usable set (field_types/status_list).
    picker = build(qtbot, project_id=PROJECT, value="zz_retired")
    assert picker.control.labels == ["zz_retired"]


def test_the_value_reaches_the_signal(qtbot):
    picker = build(qtbot, project_id=PROJECT)
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_open(True)
    spin(qtbot, 60)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    assert answers and answers[-1] == codes(picker)[0]
    assert not picker.control.is_open


def test_switching_project_drops_a_status_the_new_one_hides(qtbot):
    picker = build(qtbot, project_id=OTHER_PROJECT, value="pndad")
    answers: list = []
    picker.value_changed.connect(answers.append)
    picker.set_project_id(PROJECT)
    settled(qtbot, picker)
    spin(qtbot, 60)
    assert answers == [None]
    assert picker.value is None


def test_a_secondary_of_the_callers_own_wins_over_the_code(qtbot):
    picker = build(qtbot, project_id=PROJECT, secondary=lambda option: option.code.upper())
    model = picker.rows_model
    assert model.index(0, 0).data(Roles.SECONDARY) == codes(picker)[0].upper()


def test_a_picker_taken_down_under_a_read_drops_the_answer(qtbot):
    """A table cell's editor closes, a demo is rebuilt: the read in flight has nowhere to land.

    The answer reaches the loader through a queued signal, and emitting on a loader Qt has
    deleted raises `RuntimeError` inside the event loop, which pytest-qt fails the test on and
    the showcase prints as a traceback. The loader drops what is in flight as it goes.
    """
    import time

    from qtpy.QtWidgets import QApplication

    from sg_widgets_qt.widgets.status_picker import StatusOptionsLoader

    context, _client = context_for(latency_ms=200)
    loader = StatusOptionsLoader()
    answers: list = []
    loader.settled.connect(answers.append)
    loader.reload(context, "Version", [PROJECT], None)
    spin(qtbot, 20)
    loader.deleteLater()
    del loader
    # The read is still on its pool thread; the loader goes under it.
    end = time.time() + 2.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(10)
    assert True, "the answer landed on a loader that had gone"
