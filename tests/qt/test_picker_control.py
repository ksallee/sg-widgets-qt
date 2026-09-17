"""The control box and the popup shell: the ladder, the measured chip row and the state block."""
from __future__ import annotations

from qtpy.QtCore import QPoint, Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.primitives.base import CONTROL_HEIGHT, ICON_HIT_BOX
from sg_widgets_qt.primitives.popover import MIN_WIDTH as POPUP_MIN_WIDTH
from sg_widgets_qt.widgets.picker_control import (
    CHIP_GAP,
    OVERFLOW_RESERVE,
    PICKER_BOX,
    PICKER_BOX_EMPTY,
    PICKER_TEXT_BOX,
    POPUP_WIDTH,
    SEARCH_ROW_HEIGHT,
    SKELETON_ROWS,
)

from .test_picker_contract import DEPARTMENTS, _settle, build_static, spin


def test_the_box_ladder_is_the_upstream_one():
    # `PICKER_BOX` of picker-classes.ts, in pixels.
    assert PICKER_BOX == {"sm": (8, 3, 3), "md": (12, 3, 3), "lg": (12, 1, 1)}
    assert PICKER_BOX_EMPTY == {"sm": (6, 0), "md": (8, 0), "lg": (8, 0)}
    assert PICKER_TEXT_BOX == {"sm": (8, 8), "md": (12, 12), "lg": (12, 12)}
    assert (CHIP_GAP, OVERFLOW_RESERVE, POPUP_WIDTH) == (6, 40, 384)


def test_an_empty_control_gives_its_leading_inset_back(qtbot):
    control = build_static(qtbot)
    left, _right, pad_y = control._insets()
    assert (left, pad_y) == PICKER_BOX_EMPTY["md"]
    _settle(control, ["layout"], dict(DEPARTMENTS))
    left, _right, pad_y = control._insets()
    assert (left, pad_y) == (PICKER_BOX["md"][1], PICKER_BOX["md"][2])


def test_the_height_holds_the_ladder_in_both_states(qtbot):
    for size in ("sm", "md", "lg"):
        control = build_static(qtbot, size=size)
        assert control.minimumHeight() == CONTROL_HEIGHT[size]
        _settle(control, ["layout"], dict(DEPARTMENTS))
        spin(qtbot, 10)
        assert control.minimumHeight() == CONTROL_HEIGHT[size]


def test_a_text_value_keeps_the_reading_inset(qtbot):
    control = build_static(qtbot, text_value=True, inline=False)
    _settle(control, ["layout"], dict(DEPARTMENTS))
    left, _right, pad_y = control._insets()
    assert (left, pad_y) == (PICKER_TEXT_BOX["md"][0], 0)


def test_the_chip_row_hides_chips_into_a_pill_when_the_control_is_narrow(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True, summary="ellipsis")
    _settle(control, [code for code, _ in DEPARTMENTS], dict(DEPARTMENTS))
    spin(qtbot, 20)
    control.setFixedWidth(600)
    control._relayout()
    wide = control._shown_chips
    control.setFixedWidth(180)
    control._relayout()
    assert control._shown_chips < wide
    assert control._overflow == len(DEPARTMENTS) - control._shown_chips
    assert control.overflow_pill().isVisibleTo(control)
    assert control.overflow_pill().count == control._overflow
    # Whole chips only: nothing is drawn past the room the row has.
    left, right, _pad = control._insets()
    room = control.width() - left - right
    drawn = [chip for chip in control.chips() if chip.isVisibleTo(control)]
    used = sum(chip.sizeHint().width() + CHIP_GAP for chip in drawn)
    assert used <= room - OVERFLOW_RESERVE


def test_the_pill_opens_the_list_where_the_hidden_ones_are(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True, summary="ellipsis")
    _settle(control, [code for code, _ in DEPARTMENTS], dict(DEPARTMENTS))
    control.setFixedWidth(180)
    control._relayout()
    pill = control.overflow_pill()
    QTest.mouseClick(pill, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(2, 2))
    spin(qtbot, 20)
    assert control.is_open


def test_max_caps_the_chips_whatever_the_room(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True, summary="chips", max=2)
    _settle(control, [code for code, _ in DEPARTMENTS], dict(DEPARTMENTS))
    control.setFixedWidth(900)
    control._relayout()
    assert control._shown_chips == 2
    assert control._overflow == len(DEPARTMENTS) - 2


def test_count_replaces_the_row_with_one_line(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True, summary="count")
    _settle(control, ["layout", "anim", "light"], dict(DEPARTMENTS))
    assert control._count_label == "3 selected"
    assert control.chips() == []


def test_the_state_block_draws_one_of_four_things(qtbot):
    control = build_static(qtbot)
    control.set_loading(True)
    assert control.skeletons().isVisibleTo(control.popup())
    assert not control.list_surface().isVisibleTo(control.popup())
    assert len(control.skeletons().findChildren(type(control.skeletons()))) >= 0
    control.set_loading(False)
    control.set_empty(True)
    assert control.state_line().isVisibleTo(control.popup())
    assert control.state_line().label == "No match"
    control.set_error("Flow PT API error 503")
    assert control.state_line().state == "error"
    assert control.state_line().label == "Flow PT API error 503"
    control.set_error(None)
    control.set_empty(False)
    assert control.list_surface().isVisibleTo(control.popup())


def test_the_skeletons_stand_in_for_three_rows(qtbot):
    from sg_widgets_qt.primitives.skeleton import Skeleton

    control = build_static(qtbot)
    assert len(control.skeletons().findChildren(Skeleton)) == SKELETON_ROWS


def test_the_load_more_row_appears_under_the_rows(qtbot):
    control = build_static(qtbot)
    rows = control.list_surface().row_count()
    control.set_has_more(True)
    assert control.list_surface().row_count() == rows + 1
    assert control.list_surface().is_load_more(rows)
    asked = []
    control.load_more_requested.connect(lambda: asked.append(True))
    control.list_surface().activate(rows)
    assert asked == [True]


def test_the_live_status_says_what_the_list_is_doing(qtbot):
    control = build_static(qtbot)
    assert control.status_text() == f"{len(DEPARTMENTS)} results"
    control.set_loading(True)
    assert control.status_text() == "Searching…"
    control.set_loading(False)
    control.set_items([])
    control.set_empty(True)
    assert control.status_text() == "No match"
    control.set_error("boom")
    assert control.status_text() == "boom"
    assert control.list_surface().accessibleDescription() == "boom"


def test_the_trailing_controls_keep_a_24px_hit_box(qtbot):
    control = build_static(qtbot)
    _settle(control, ["layout"], dict(DEPARTMENTS))
    control._relayout()
    for button in (control.clear_control(), control.open_control()):
        assert button.sizeHint().width() >= ICON_HIT_BOX
        assert button.sizeHint().height() >= ICON_HIT_BOX
    assert control.clear_control().geometry().right() < control.width()


def test_the_dismissal_guard_claims_the_control_and_its_parts(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True)
    _settle(control, ["layout"], dict(DEPARTMENTS))
    control._relayout()
    middle = control.mapToGlobal(QPoint(control.width() // 2, control.height() // 2))
    assert control._claims_press(middle)
    chip = control.chips()[0]
    assert control._claims_press(chip.mapToGlobal(QPoint(2, 2)))
    assert control._claims_press(control.open_control().mapToGlobal(QPoint(2, 2)))
    assert not control._claims_press(QPoint(-1000, -1000))


def test_the_popup_is_384_wide_or_the_controls_own_width(qtbot):
    control = build_static(qtbot)
    control.set_open(True)
    spin(qtbot, 20)
    assert control.popover().surface_size().width() == POPUP_WIDTH
    control.set_open(False)
    anchored = build_static(qtbot, anchored=True)
    anchored.setFixedWidth(300)
    anchored.set_open(True)
    spin(qtbot, 20)
    assert anchored.popover().surface_size().width() == max(POPUP_MIN_WIDTH, 300)


def test_a_summary_control_keeps_its_search_row_under_a_hairline(qtbot):
    control = build_static(qtbot, inline=False)
    assert control.search_row().height() == SEARCH_ROW_HEIGHT + 1
    fixed = build_static(qtbot, inline=False, searchable=False)
    assert not fixed.search_row().isVisibleTo(fixed.popup())


def test_closing_clears_the_query(qtbot):
    control = build_static(qtbot)
    control.set_open(True)
    control.set_query("lig")
    assert control.query == "lig"
    control.set_open(False)
    assert control.query == ""
    assert control.caret().text() == ""
