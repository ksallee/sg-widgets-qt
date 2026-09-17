"""Several entities by server-side search: the chip row, the checkboxes and what a pick does."""
from __future__ import annotations

from qtpy.QtWidgets import QWidget

from sg_widgets_core.filter import EntityRef
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.entity_multi_picker import EntityMultiPicker
from sg_widgets_qt.widgets.picker_control import CHIP_GAP, OVERFLOW_RESERVE

from .test_entity_picker import context_for, settled
from .test_picker_contract import PickerShape, check_contract, spin

#: Shots the fixtures always carry, in id order from the first one generated.
ALREADY_THERE = [EntityRef(type="Shot", id=862), EntityRef(type="Shot", id=863)]
ASSETS = [EntityRef(type="Asset", id=1226), EntityRef(type="Asset", id=1227)]


def build(qtbot, latency_ms: int = 20, width: int = 500, **props):
    """One multi picker on a themed window. The rows draw no thumbnail, so nothing is read."""
    props.setdefault("thumbnail", False)
    props.setdefault("entity_types", ["Asset"])
    context, client = context_for(latency_ms)
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(width + 20, 160)
    picker = EntityMultiPicker(context=context, parent=root, **props)
    picker.setGeometry(10, 10, width, 40)
    root.show()
    qtbot.waitExposed(root)
    picker.test_root = root
    picker.test_client = client
    return picker


def test_the_contract_as_a_token_field(qtbot):
    picker = build(qtbot, summary="chips", value=list(ASSETS))
    spin(qtbot, 400)
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(multiple=True, settle=lambda: settled(qtbot, picker, 600)),
    )
    assert "value keys" in checked
    assert "pick" in checked


def test_the_contract_as_a_summary_trigger(qtbot):
    picker = build(qtbot, summary="ellipsis", value=list(ASSETS))
    spin(qtbot, 400)
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(
            multiple=True, inline=False, settle=lambda: settled(qtbot, picker, 600)
        ),
    )
    assert "caret on open" in checked


def test_a_pick_keeps_the_list_open_and_ticks_the_row(qtbot):
    picker = build(qtbot)
    answers: list = []
    picker.value_changed.connect(lambda refs, rows: answers.append((refs, rows)))
    picker.set_open(True)
    settled(qtbot, picker)
    surface = picker.control.list_surface()
    surface.activate(0)
    spin(qtbot, 60)
    assert picker.control.is_open, "a pick keeps a multi picker open"
    refs, rows = answers[-1]
    assert len(refs) == 1 and len(rows) == 1
    surface.activate(1)
    spin(qtbot, 60)
    assert len(picker.value) == 2
    # A second press on a ticked row unticks it.
    surface.activate(1)
    spin(qtbot, 60)
    assert len(picker.value) == 1


def test_the_rows_carry_a_checkbox_in_the_indicator_column(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    settled(qtbot, picker)
    assert picker.control.row_delegate().indicator == "checkbox"
    model = picker.rows_model
    assert model.data(model.index(0, 0), Roles.CHECKED) in (True, False, None)
    picker.control.list_surface().activate(0)
    spin(qtbot, 60)
    assert model.data(model.index(0, 0), Roles.CHECKED) is True


def test_the_chip_row_hides_chips_into_a_pill_when_the_control_is_narrow(qtbot):
    five = [EntityRef(type="Asset", id=1226 + i) for i in range(5)]
    picker = build(qtbot, value=five, summary="ellipsis", width=600)
    spin(qtbot, 700)
    control = picker.control
    control._relayout()
    wide = control._shown_chips
    assert wide >= 1
    picker.setFixedWidth(200)
    control.setFixedWidth(200)
    control._relayout()
    assert control._shown_chips < wide
    assert control.overflow_pill().isVisibleTo(control)
    left, right, _pad = control._insets()
    room = control.width() - left - right
    drawn = [chip for chip in control.chips() if chip.isVisibleTo(control)]
    assert sum(chip.sizeHint().width() + CHIP_GAP for chip in drawn) <= room - OVERFLOW_RESERVE


def test_max_bounds_the_chips(qtbot):
    five = [EntityRef(type="Asset", id=1226 + i) for i in range(5)]
    picker = build(qtbot, value=five, summary="chips", max=2, width=900)
    spin(qtbot, 700)
    picker.control._relayout()
    assert picker.control._shown_chips == 2


def test_count_reads_how_many_are_selected(qtbot):
    picker = build(qtbot, value=list(ASSETS), summary="count")
    spin(qtbot, 500)
    assert picker.control._count_label == "2 selected"


def test_summary_moves_the_search_box_into_the_popup(qtbot):
    picker = build(qtbot, summary="chips")
    assert picker.control.inline
    picker.set_summary("ellipsis")
    assert not picker.control.inline
    picker.set_summary("chips")
    assert picker.control.inline


def test_hydration_resolves_bare_references(qtbot):
    picker = build(qtbot, entity_types=["Shot", "Asset"], value=[
        EntityRef(type="Shot", id=866), EntityRef(type="Asset", id=1226),
    ])
    spin(qtbot, 800)
    labels = picker.control.labels
    assert len(labels) == 2
    assert labels[0] != "Shot 866" and labels[1] != "Asset 1226"


def test_exclude_keeps_a_row_out_of_the_results(qtbot):
    picker = build(qtbot, entity_types=["Shot"], exclude=ALREADY_THERE, page_size=50)
    picker.set_open(True)
    settled(qtbot, picker)
    offered = {f"{row.type}:{row.id}" for row in picker.state.rows}
    assert offered, "the read answered nothing"
    assert "Shot:862" not in offered and "Shot:863" not in offered


def test_a_selected_row_stays_on_the_list_to_be_unticked(qtbot):
    picker = build(qtbot, entity_types=["Shot"], value=[EntityRef(type="Shot", id=862)])
    picker.set_open(True)
    settled(qtbot, picker)
    picker.control.set_query("zzzzzz")
    spin(qtbot, 700)
    assert picker.control.items == ["Shot:862"], "the selection is still there to be unticked"


def test_clearing_drops_every_chip(qtbot):
    picker = build(qtbot, value=list(ASSETS))
    spin(qtbot, 500)
    assert len(picker.control.labels) == 2
    picker.control.cleared.emit()
    spin(qtbot, 50)
    assert picker.value == []
    assert picker.control.labels == []
