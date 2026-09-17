"""The floating primitives: the popover window, the hover card, the dialog, the menu and more."""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QPoint, QRect, QSize, Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.primitives.dialog import Dialog
from sg_widgets_qt.primitives.dropdown_menu import DropdownMenu
from sg_widgets_qt.primitives.hover_card import HoverCard, HoverCardContent
from sg_widgets_qt.primitives.popover import (
    MIN_WIDTH,
    SIDE_OFFSET,
    Popover,
    PopoverContent,
    anchor_rect,
    available_rect,
    place,
)
from sg_widgets_qt.primitives.select import Select
from sg_widgets_qt.primitives.tooltip import Tooltip
from sg_widgets_qt.theme import apply_theme, theme_for

#: Long enough for a 100ms open or close to land, and well under the 1.5s ceiling.
SETTLE_MS = 300


class Host(QtWidgets.QWidget):
    """A themed window with an anchor and a second widget to press outside on."""

    def __init__(self) -> None:
        super().__init__()
        apply_theme(self, theme_for("default"))
        self.resize(640, 480)
        # No layout: the two widgets stand far enough apart that a press on one is nowhere
        # near the surface hanging off the other.
        self.anchor = QtWidgets.QLineEdit(self)
        self.anchor.setGeometry(16, 16, 240, 32)
        self.outside = QtWidgets.QLineEdit(self)
        self.outside.setGeometry(360, 400, 240, 32)


@pytest.fixture
def host(qtbot):
    widget = Host()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    widget.anchor.setFocus()
    return widget


def settle(qtbot) -> None:
    """Let an open or a close animation finish."""
    qtbot.wait(SETTLE_MS)


# --- placement ---------------------------------------------------------------------------


def test_place_puts_the_surface_below_the_anchor_at_the_side_offset():
    rect, side = place(
        QRect(100, 100, 240, 32), QSize(288, 120), "bottom", "start", SIDE_OFFSET, QRect(0, 0, 800, 800)
    )
    assert side == "bottom"
    assert rect.top() == 100 + 32 + SIDE_OFFSET
    assert rect.left() == 100


def test_place_flips_above_when_the_anchor_sits_at_the_foot_of_the_screen():
    screen = QRect(0, 0, 800, 800)
    rect, side = place(QRect(100, 740, 240, 32), QSize(288, 200), "bottom", "start", SIDE_OFFSET, screen)
    assert side == "top"
    assert rect.bottom() + 1 == 740 - SIDE_OFFSET


def test_place_aligns_center_and_end_on_the_other_axis():
    screen = QRect(0, 0, 800, 800)
    centred, _ = place(QRect(100, 100, 240, 32), QSize(100, 40), "bottom", "center", 4, screen)
    ended, _ = place(QRect(100, 100, 240, 32), QSize(100, 40), "bottom", "end", 4, screen)
    assert centred.left() == 100 + (240 - 100) // 2
    assert ended.left() == 100 + 240 - 100


def test_place_flips_a_side_popover_to_the_other_side():
    screen = QRect(0, 0, 800, 800)
    rect, side = place(QRect(10, 100, 40, 32), QSize(200, 120), "left", "start", 4, screen)
    assert side == "right"
    assert rect.left() == 10 + 40 + 4


# --- the popover window ------------------------------------------------------------------


def test_a_popover_opens_below_its_anchor_aligned_start(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"), side="bottom", align="start")
    popover.open()
    settle(qtbot)
    surface = popover.surface_geometry()
    anchor = anchor_rect(host.anchor)
    assert popover.is_open
    assert popover.placed_side == "bottom"
    assert surface.top() == anchor.bottom() + 1 + SIDE_OFFSET
    assert surface.left() == anchor.left()


def test_a_popover_flips_above_an_anchor_at_the_foot_of_the_screen(host, qtbot):
    screen = available_rect(host.anchor)
    host.move(screen.left(), max(screen.top(), screen.bottom() - host.height() + 1))
    host.anchor.setFixedHeight(32)
    qtbot.wait(50)
    tall = QtWidgets.QWidget()
    tall.setFixedSize(288, 260)
    popover = Popover(host.anchor, tall, side="bottom", align="start")
    popover.set_anchor_rect_provider(
        lambda: QRect(screen.left() + 20, screen.bottom() - 40, 240, 32)
    )
    popover.open()
    settle(qtbot)
    assert popover.placed_side == "top"
    assert popover.surface_geometry().bottom() + 1 == screen.bottom() - 40 - SIDE_OFFSET


def test_a_popover_matches_the_anchor_width(host, qtbot):
    host.anchor.setFixedWidth(320)
    qtbot.wait(20)
    popover = Popover(host.anchor, QtWidgets.QWidget(), match_anchor_width=True)
    popover.open()
    settle(qtbot)
    assert popover.surface_geometry().width() == 320


def test_a_matched_popover_never_goes_under_the_minimum_width(host, qtbot):
    host.anchor.setFixedWidth(80)
    qtbot.wait(20)
    popover = Popover(host.anchor, QtWidgets.QWidget(), match_anchor_width=True)
    popover.open()
    settle(qtbot)
    assert popover.surface_geometry().width() == MIN_WIDTH


def test_a_popover_closes_on_a_press_outside_it_and_says_it_was_dismissed(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.open()
    settle(qtbot)
    with qtbot.waitSignal(popover.dismissed, timeout=1000):
        QTest.mousePress(host.outside, Qt.MouseButton.LeftButton)
    assert not popover.is_open
    settle(qtbot)
    assert not popover.isVisible()


def test_a_press_the_guard_claims_does_not_dismiss_a_popover(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.set_dismiss_guard(lambda point: anchor_rect(host.outside).contains(point))
    popover.open()
    settle(qtbot)
    QTest.mousePress(host.outside, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert popover.is_open


def test_a_press_on_the_anchor_is_the_anchors_own_business(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.open()
    settle(qtbot)
    QTest.mousePress(host.anchor, Qt.MouseButton.LeftButton)
    qtbot.wait(50)
    assert popover.is_open


def test_the_anchor_keeps_the_keyboard_while_a_popover_is_open(host, qtbot):
    assert host.anchor.window().focusWidget() is host.anchor
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.open()
    settle(qtbot)
    assert host.anchor.window().focusWidget() is host.anchor
    assert popover.focusWidget() is None
    assert popover.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_escape_through_handle_key_dismisses_a_popover(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.open()
    settle(qtbot)
    with qtbot.waitSignal(popover.dismissed, timeout=1000):
        assert popover.handle_key(_key_event(Qt.Key.Key_Escape))
    assert not popover.is_open


def test_a_popover_follows_the_anchors_window(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.open()
    settle(qtbot)
    before = popover.surface_geometry().topLeft()
    host.move(host.x() + 40, host.y() + 30)
    qtbot.wait(80)
    after = popover.surface_geometry().topLeft()
    assert popover.is_open
    assert after - before == QPoint(40, 30)


def test_toggle_opens_and_closes(host, qtbot):
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.toggle()
    assert popover.is_open
    popover.toggle()
    assert not popover.is_open


# --- the hover card ----------------------------------------------------------------------


def test_a_hover_card_opens_after_its_delay(host, qtbot):
    card = HoverCard(
        host.anchor, HoverCardContent("Ada Lovelace", "Rigging"), open_delay=120, close_delay=120
    )
    QTest.mouseMove(host.anchor, QPoint(10, 10))
    QtWidgets.QApplication.sendEvent(host.anchor, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    qtbot.wait(40)
    assert not card.is_open
    qtbot.wait(200)
    assert card.is_open
    assert card.popover.surface_geometry().width() == 256


def test_a_hover_card_closes_once_the_pointer_leaves(host, qtbot):
    card = HoverCard(host.anchor, HoverCardContent("Ada Lovelace"), open_delay=40, close_delay=60)
    QtWidgets.QApplication.sendEvent(host.anchor, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    qtbot.wait(150)
    assert card.is_open
    QtWidgets.QApplication.sendEvent(host.anchor, QtCore.QEvent(QtCore.QEvent.Type.Leave))
    qtbot.wait(300)
    assert not card.is_open


# --- the select --------------------------------------------------------------------------


def test_a_select_changes_its_value_on_enter_after_down(host, qtbot):
    select = Select([("hold", "On hold"), ("ip", "In progress"), ("fin", "Final")], parent=host)
    select.show()
    select.setFocus()
    qtbot.wait(20)
    QTest.keyClick(select, Qt.Key.Key_Down)
    settle(qtbot)
    assert select.is_open
    QTest.keyClick(select, Qt.Key.Key_Down)
    with qtbot.waitSignal(select.value_changed, timeout=1000) as caught:
        QTest.keyClick(select, Qt.Key.Key_Return)
    assert caught.args == ["ip"]
    assert select.value == "ip"
    assert select.label == "In progress"
    assert not select.is_open


def test_a_select_reads_its_placeholder_until_a_value_lands(host, qtbot):
    select = Select([("a", "Alpha")], placeholder="Pick one", parent=host)
    assert select.label == "Pick one"
    select.set_value("a")
    assert select.label == "Alpha"


def test_a_select_list_is_as_wide_as_the_control(host, qtbot):
    select = Select([("a", "Alpha"), ("b", "Beta")], parent=host)
    select.setFixedWidth(300)
    select.show()
    qtbot.wait(20)
    select.open()
    settle(qtbot)
    assert select.popover.surface_geometry().width() == 300


def test_escape_closes_a_select_and_keeps_its_value(host, qtbot):
    select = Select([("a", "Alpha"), ("b", "Beta")], value="a", parent=host)
    select.show()
    select.setFocus()
    qtbot.wait(20)
    select.open()
    settle(qtbot)
    QTest.keyClick(select, Qt.Key.Key_Escape)
    qtbot.wait(50)
    assert not select.is_open
    assert select.value == "a"


def test_a_readonly_select_does_not_open(host, qtbot):
    select = Select([("a", "Alpha")], readonly=True, parent=host)
    select.show()
    qtbot.wait(20)
    select.open()
    assert not select.is_open


def test_a_select_takes_groups_with_headings(host, qtbot):
    select = Select(parent=host)
    select.set_groups([("Live", [("a", "Alpha")]), ("Held", [("b", "Beta")])])
    kinds = [entry.kind for entry in select.list.entries]
    assert kinds == ["label", "item", "separator", "label", "item"]
    assert select.items == [("a", "Alpha"), ("b", "Beta")]


def test_a_select_walks_its_rows_with_typeahead(host, qtbot):
    select = Select([("a", "Alpha"), ("b", "Beta"), ("g", "Gamma")], parent=host)
    select.show()
    select.setFocus()
    qtbot.wait(20)
    select.open()
    settle(qtbot)
    QTest.keyClicks(select, "g")
    assert select.list.entries[select.list.highlight].text == "Gamma"


# --- the dropdown menu -------------------------------------------------------------------


def test_a_dropdown_activates_an_item_on_enter(host, qtbot):
    fired: list[str] = []
    menu = DropdownMenu(host.anchor)
    menu.add_label("Actions")
    menu.add_item("Duplicate", on_activate=lambda: fired.append("duplicate"))
    menu.add_separator()
    menu.add_item("Delete", destructive=True, on_activate=lambda: fired.append("delete"))
    QTest.keyClick(host.anchor, Qt.Key.Key_Down)
    settle(qtbot)
    assert menu.is_open
    QTest.keyClick(host.anchor, Qt.Key.Key_Down)
    QTest.keyClick(host.anchor, Qt.Key.Key_Return)
    assert fired == ["delete"]
    assert not menu.is_open


def test_a_dropdown_skips_the_rows_the_keyboard_cannot_land_on(host, qtbot):
    menu = DropdownMenu(host.anchor)
    menu.add_label("Actions")
    menu.add_item("One")
    menu.add_separator()
    menu.add_item("Two", disabled=True)
    menu.add_item("Three")
    menu.open(from_keyboard=True)
    settle(qtbot)
    assert menu.list.entries[menu.list.highlight].text == "One"
    menu.list.step(1)
    assert menu.list.entries[menu.list.highlight].text == "Three"


def test_a_dropdown_checkbox_item_toggles_and_stays_open(host, qtbot):
    seen: list[bool] = []
    menu = DropdownMenu(host.anchor)
    entry = menu.add_checkbox_item("Show codes", checked=False, on_toggle=seen.append)
    menu.open(from_keyboard=True)
    settle(qtbot)
    QTest.keyClick(host.anchor, Qt.Key.Key_Return)
    assert seen == [True]
    assert entry.checked is True
    assert menu.is_open


def test_a_dropdown_radio_group_keeps_one_tick(host, qtbot):
    chosen: list[str] = []
    menu = DropdownMenu(host.anchor)
    entries = menu.add_radio_group([("a", "Alpha"), ("b", "Beta")], value="a", on_change=chosen.append)
    menu.open(from_keyboard=True)
    settle(qtbot)
    menu.list.set_highlight(1)
    QTest.keyClick(host.anchor, Qt.Key.Key_Return)
    assert chosen == ["b"]
    assert [entry.checked for entry in entries] == [False, True]


def test_a_dropdown_walks_with_typeahead(host, qtbot):
    menu = DropdownMenu(host.anchor)
    menu.add_item("Alpha")
    menu.add_item("Beta")
    menu.add_item("Gamma")
    menu.open(from_keyboard=True)
    settle(qtbot)
    QTest.keyClicks(host.anchor, "b")
    assert menu.list.entries[menu.list.highlight].text == "Beta"


def test_a_dropdown_row_stands_on_the_control_ladder(host, qtbot):
    menu = DropdownMenu(host.anchor)
    menu.add_item("Alpha")
    assert menu.list.row_rect(0).height() == 32


# --- the dialog --------------------------------------------------------------------------


def test_a_dialog_closes_on_escape_and_its_scrim_goes(host, qtbot):
    dialog = Dialog(host, title="Delete the shot", description="This cannot be undone.")
    qtbot.addWidget(dialog)
    dialog.open()
    settle(qtbot)
    assert dialog.isVisible()
    assert dialog.scrim is not None and dialog.scrim.isVisible()
    with qtbot.waitSignal(dialog.dismissed, timeout=1000):
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
    settle(qtbot)
    assert not dialog.isVisible()
    assert not dialog.scrim.isVisible()


def test_a_dialog_is_modal_and_no_wider_than_the_ladder(host, qtbot):
    dialog = Dialog(host, title="A title", description="A description.")
    qtbot.addWidget(dialog)
    dialog.open()
    settle(qtbot)
    assert dialog.isModal()
    assert dialog.surface_rect().width() <= 512
    dialog.close()
    settle(qtbot)


def test_a_dialog_footer_holds_its_buttons(host, qtbot):
    from sg_widgets_qt.primitives.button import Button

    dialog = Dialog(host, title="A title")
    qtbot.addWidget(dialog)
    assert dialog._footer.is_empty
    dialog.footer.add_button(Button("Cancel", variant="outline"))
    assert not dialog._footer.is_empty


# --- the tooltip -------------------------------------------------------------------------


def test_a_tooltip_appears_on_hover(host, qtbot):
    tip = Tooltip.attach(host.anchor, "Copy the id", delay=80)
    QtWidgets.QApplication.sendEvent(host.anchor, QtCore.QEvent(QtCore.QEvent.Type.Enter))
    qtbot.wait(30)
    assert not tip.is_open
    qtbot.wait(200)
    assert tip.is_open
    assert tip.popover.surface_geometry().height() > 0
    QtWidgets.QApplication.sendEvent(host.anchor, QtCore.QEvent(QtCore.QEvent.Type.Leave))
    settle(qtbot)
    assert not tip.is_open


def test_attaching_a_tooltip_twice_changes_its_text(host, qtbot):
    first = Tooltip.attach(host.anchor, "One")
    second = Tooltip.attach(host.anchor, "Two")
    assert first is second
    assert second.text == "Two"


# --- reduced motion ----------------------------------------------------------------------


def test_reduced_motion_still_opens_and_closes_a_popover(host, qtbot):
    apply_theme(host, theme_for("default", reduced_motion=True))
    popover = Popover(host.anchor, PopoverContent(title="Filters"))
    popover.open()
    settle(qtbot)
    assert popover.is_open
    assert popover.content().isVisible()
    popover.close()
    settle(qtbot)
    assert not popover.isVisible()


def _key_event(key, text: str = "") -> QtCore.QEvent:
    from qtpy.QtGui import QKeyEvent

    return QKeyEvent(QtCore.QEvent.Type.KeyPress, int(key), Qt.KeyboardModifier.NoModifier, text)
