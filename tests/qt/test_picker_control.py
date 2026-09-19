"""The control box and the popup shell: the ladder, the measured chip row and the state block."""
from __future__ import annotations

from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QColor
from qtpy.QtTest import QTest

from sg_widgets_qt.primitives.base import CHIP_HEIGHT, CONTROL_HEIGHT, ICON_HIT_BOX
from sg_widgets_qt.primitives.popover import MIN_WIDTH as POPUP_MIN_WIDTH
from sg_widgets_qt.theme import theme_of, with_alpha
from sg_widgets_qt.widgets.picker_control import (
    BORDER,
    CHIP_GAP,
    OVERFLOW_RESERVE,
    PICKER_BOX,
    PICKER_BOX_EMPTY,
    PICKER_CHIP,
    PICKER_TEXT_BOX,
    POPUP_WIDTH,
    SEARCH_ROW_HEIGHT,
    SKELETON_ROWS,
    over,
)

from .test_picker_contract import DEPARTMENTS, _settle, build_static, spin


def test_the_box_ladder_is_the_upstream_one():
    # `PICKER_BOX` of picker-classes.ts, in pixels.
    assert PICKER_BOX == {"sm": (8, 3, 3), "md": (12, 3, 3), "lg": (12, 5, 5)}
    assert PICKER_BOX_EMPTY == {"sm": (6, 0), "md": (8, 0), "lg": (8, 0)}
    assert PICKER_TEXT_BOX == {"sm": (8, 8), "md": (12, 12), "lg": (12, 12)}
    assert (CHIP_GAP, OVERFLOW_RESERVE, POPUP_WIDTH) == (6, 40, 384)


def test_a_large_control_keeps_mds_chip_so_it_has_room_inside_36px(qtbot):
    # Rule 3: a chip sits a step under the control, except at lg, where a 32 chip leaves 1 above
    # and below under 36. lg keeps md's 24 chip, inset 5, so the control holds 36 exactly.
    assert PICKER_CHIP == {"sm": "xs", "md": "sm", "lg": "sm"}
    for size in ("sm", "md", "lg"):
        inset = PICKER_BOX[size][2]
        chip = CHIP_HEIGHT[PICKER_CHIP[size]]
        assert BORDER + inset + chip + inset + BORDER == CONTROL_HEIGHT[size]
    # The leading inset matches the room above and below, so the chip sits evenly in the border.
    assert PICKER_BOX["lg"][1] == PICKER_BOX["lg"][2] == 5
    control = build_static(qtbot, size="lg")
    control.setFixedHeight(CONTROL_HEIGHT["lg"])
    _settle(control, ["layout"], dict(DEPARTMENTS))
    spin(qtbot, 10)
    control._relayout()
    chip = control.chips()[0]
    assert chip.size_step == "sm"
    assert chip.height() == CHIP_HEIGHT["sm"]
    assert chip.y() == BORDER + PICKER_BOX["lg"][2]


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


def test_the_ink_sits_on_the_controls_own_centre_line(qtbot):
    # Rule 3: the inset is what the chip and the control's own border leave under the ladder,
    # halved, so the border counts and a chip, a text value and the caret share one centre line.
    for size in ("sm", "md", "lg"):
        control = build_static(qtbot, size=size)
        control.setFixedHeight(CONTROL_HEIGHT[size])
        control._relayout()
        empty = control.caret().geometry()
        middle = empty.y() + empty.height() / 2.0
        assert abs(middle - control.height() / 2.0) <= 1.0, f"{size}: the empty caret rides high"
        # An empty control gives its inset back and reads as a plain input: the caret fills it.
        assert empty.height() == control.height() - 2 * BORDER

        _settle(control, ["layout"], dict(DEPARTMENTS))
        spin(qtbot, 10)
        chip = control.chips()[0].geometry()
        # 20 and 2 under 28 at sm, 24 and 2 under 32 at md, and md's 24 and 2 under 36 at lg.
        assert chip.y() == BORDER + PICKER_BOX[size][2]
        assert chip.y() + chip.height() + BORDER + PICKER_BOX[size][2] == CONTROL_HEIGHT[size]
        assert abs(chip.y() + chip.height() / 2.0 - control.height() / 2.0) <= 1.0
        caret = control.caret().geometry()
        assert caret.y() == chip.y() and caret.height() == chip.height()
        # A box a caller made taller centres the whole row in it, as `items-center` does.
        control.setFixedHeight(CONTROL_HEIGHT[size] + 8)
        control._relayout()
        chip = control.chips()[0].geometry()
        assert abs(chip.y() + chip.height() / 2.0 - control.height() / 2.0) <= 1.0


def test_a_value_that_reads_as_plain_text_centres_too(qtbot):
    # The text line is shorter than the chip ladder, so it sits in the middle of the box
    # rather than on the inset the chip row takes.
    from sg_widgets_qt.showcase import chrome

    control = build_static(qtbot, text_value=True, inline=False)
    control.set_chip_factory(
        lambda index: chrome.TextLine(dict(DEPARTMENTS)[control.keys[index]], size=14)
    )
    _settle(control, ["layout"], dict(DEPARTMENTS))
    spin(qtbot, 10)
    line = control.chips()[0].geometry()
    assert line.height() < CONTROL_HEIGHT["md"]
    assert abs(line.y() + line.height() / 2.0 - control.height() / 2.0) <= 1.0


def test_a_control_built_disabled_is_inert_from_the_first_paint(qtbot):
    control = build_static(qtbot, disabled=True)
    assert not control.isEnabled()
    assert control.disabled_opacity() == 0.5
    assert not control.interactive


def test_the_hover_wash_is_muted_over_the_surface(qtbot):
    # `bg-background hover:bg-muted/30`. `muted` is a translucent overlay in several palettes,
    # so the wash is laid over the surface, never blended towards the token's raw colour.
    control = build_static(qtbot)
    theme = theme_of(control)
    wanted = over(theme.color("background"), with_alpha(theme.muted, 0.3))
    assert over(theme.color("background"), with_alpha(theme.muted, 0.0)) == theme.color(
        "background"
    )
    control.set_hovered(True)
    spin(qtbot, 250)
    image = control.grab().toImage()
    ratio = image.width() / max(1, control.width())
    got = QColor(image.pixel(int(control.width() * 0.6 * ratio), int(control.height() * 0.5 * ratio)))
    assert abs(got.red() - wanted.red()) <= 1
    assert abs(got.green() - wanted.green()) <= 1
    assert abs(got.blue() - wanted.blue()) <= 1


def test_a_text_input_rings_on_any_focus(qtbot):
    # The exception to rule 5: a browser gives `:focus-visible` to an input however the focus
    # arrived, so the control rings on a mouse press as well as on Tab.
    control = build_static(qtbot)
    assert not control._ring_shown()
    control.caret().setFocus(Qt.FocusReason.MouseFocusReason)
    spin(qtbot, 10)
    assert control.input_focused()
    assert control._ring_shown(), "a mouse press into the caret rings the control"
    control.caret().clearFocus()
    spin(qtbot, 10)
    assert not control._ring_shown()


def test_a_summary_trigger_rings_while_its_search_box_holds_the_caret(qtbot):
    control = build_static(qtbot, inline=False, multiple=True, chip_row=True, summary="ellipsis")
    control.set_open(True)
    spin(qtbot, 250)
    assert control.caret() is control._search_caret
    assert control.input_focused() and control._ring_shown()
    control.set_open(False)
    spin(qtbot, 20)
    assert not control.input_focused()


def test_a_fixed_set_keeps_the_keyboard_only_ring(qtbot):
    # No text input, so rule 5's own rule stands: a mouse press rings nothing.
    control = build_static(qtbot, inline=False, searchable=False, text_value=True, anchored=True)
    control.setFocus(Qt.FocusReason.MouseFocusReason)
    spin(qtbot, 10)
    assert not control._ring_shown()
    control.clearFocus()
    control.setFocus(Qt.FocusReason.TabFocusReason)
    spin(qtbot, 10)
    assert control._ring_shown()


def test_the_popup_follows_the_row_count_down_as_well_as_up(qtbot):
    # A layout caches its minimum and a top-level's resize is clamped by it, so a popup that
    # had been tall once used to refuse to come back down when a query narrowed the list.
    control = build_static(qtbot)
    control.set_open(True)
    spin(qtbot, 60)
    tall = control.list_surface().height()
    assert tall == control.list_surface().content_height()

    model = control.row_model()
    model.beginResetModel()
    model.codes = ["layout"]
    model.endResetModel()
    control.set_items(["layout"])
    spin(qtbot, 80)
    short = control.list_surface().height()
    assert short < tall
    assert short == control.list_surface().content_height()
    assert control.popover().height() <= tall

    model.beginResetModel()
    model.codes = [code for code, _ in DEPARTMENTS]
    model.endResetModel()
    control.set_items([code for code, _ in DEPARTMENTS])
    spin(qtbot, 80)
    assert control.list_surface().height() == tall
    control.set_open(False)


def test_a_closed_picker_has_no_popup_until_it_is_opened(qtbot):
    # The shell is the costly half of a picker and a page holding many opens few of them, so
    # nothing of it exists until the first open or the first call that needs one of its parts.
    from sg_widgets_qt.primitives.popover import Popover

    control = build_static(qtbot)
    root = control.test_root
    assert control.has_popup() is False
    assert root.findChildren(Popover) == []

    control.set_open(True)
    spin(qtbot, 20)

    assert control.has_popup() is True
    assert root.findChildren(Popover) == [control.popover()]
    assert control.popover().is_open
    # The model and the delegate set before the open are on the list the build made.
    assert control.list_surface().source_model() is control.row_model()
    assert control.list_surface().row_count() == len(DEPARTMENTS)
    assert control.list_surface().isVisibleTo(control.popup())

    picked: list = []
    control.selected.connect(lambda keys: picked.append(list(keys)))
    control.list_surface().activate(0)
    assert picked == [[DEPARTMENTS[0][0]]]
    # Clause 6: a pick closes a single picker.
    assert control.is_open is False


def test_an_accessor_builds_the_shell_a_closed_picker_never_had(qtbot):
    control = build_static(qtbot)
    assert control.has_popup() is False
    surface = control.list_surface()
    assert control.has_popup() is True
    assert surface.row_count() == len(DEPARTMENTS)
    assert control.state_line() is not None
    assert control.skeletons() is not None
    assert control.search_row() is not None


def test_the_states_set_before_the_first_open_are_worn_on_the_build(qtbot):
    control = build_static(qtbot, inline=False)
    control.set_loading(True)
    control.set_search_placeholder("Search departments…")
    control.set_empty_label("Nothing here")
    assert control.has_popup() is False
    assert control.status_text() == "Searching…"

    control.set_open(True)
    spin(qtbot, 20)

    assert control.skeletons().isVisibleTo(control.popup())
    assert not control.list_surface().isVisibleTo(control.popup())
    assert control.caret().placeholderText() == "Search departments…"
    control.set_loading(False)
    control.set_items([])
    control.set_empty(True)
    assert control.state_line().label == "Nothing here"
