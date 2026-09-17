"""Nothing on a dark page is drawn in an ink or on a ground the reader cannot see.

The defect these hold down is one class with two halves, and a popup built on its first open
meets both.

Qt rebuilds a widget's palette when it polishes it, and a stylesheet rule naming the widget's
class makes it rebuild that palette from the *application's* rather than from the widget's own.
The generated stylesheet names `QLineEdit`, so every field in this package is inked, then shown,
and the show throws the ink away: the application's black, on the dark surface a popover painted.

The other half is a part built before it joined a themed tree. `watch_theme` only hears a theme
that lands while the widget is already under the root it lands on, so a field built on the first
open of a popup read the host's theme and kept it.

A ground drifts the same way: `QScrollArea.setWidget` turns the scrolled widget's auto-fill on,
and Qt fills it from the application's palette, which is a light grey whatever the theme says.

`tools/drives/_ink.py` reads the same thing off a running showcase, and the walks call it.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_qt.primitives.input import Input, Textarea
from sg_widgets_qt.primitives.input_group import InputGroupInput
from sg_widgets_qt.primitives.popover import Popover, PopoverContent
from sg_widgets_qt.theme import apply_theme, contrast_ratio, generate_qss, theme_for

#: Long enough for a 100ms open to land.
SETTLE_MS = 300

DARK = theme_for("default", dark=True)

ACTIVE = QtGui.QPalette.ColorGroup.Active
INACTIVE = QtGui.QPalette.ColorGroup.Inactive
DISABLED = QtGui.QPalette.ColorGroup.Disabled
TEXT = QtGui.QPalette.ColorRole.Text


def ink(widget: QtWidgets.QWidget, group=ACTIVE) -> str:
    return widget.palette().color(group, TEXT).name()


@pytest.fixture
def dark_host(qtbot):
    """A dark window with an anchor to hang a popover off."""
    widget = QtWidgets.QWidget()
    apply_theme(widget, DARK)
    qtbot.addWidget(widget)
    widget.resize(520, 400)
    widget.anchor = QtWidgets.QLineEdit(widget)
    widget.anchor.setGeometry(16, 16, 240, 32)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


# --- the ink Qt draws itself ---------------------------------------------------------------


def test_a_field_shown_under_a_stylesheet_keeps_the_theme_ink(dark_host, qtbot):
    """The show is what polishes a field, and a polish rebuilds the palette the ink is in."""
    field = Input(parent=dark_host)
    field.setGeometry(16, 80, 240, 32)
    field.show()
    qtbot.waitExposed(field)
    assert ink(field) == DARK.foreground
    assert ink(field, INACTIVE) == DARK.foreground
    # The inert step of rule 5 is a colour, because no painter opacity reaches Qt's own drawing.
    assert field.palette().color(DISABLED, TEXT).alpha() == 128
    # The box is ours, so Qt fills nothing behind the text it draws.
    assert field.palette().color(ACTIVE, QtGui.QPalette.ColorRole.Base).alpha() == 0


def test_a_field_keeps_its_ink_when_the_root_is_dressed_again(dark_host, qtbot):
    """A restyle repolishes the whole subtree; the ink has to come back with it."""
    field = Input(parent=dark_host)
    field.show()
    qtbot.waitExposed(field)
    dark_host.setStyleSheet(generate_qss(DARK))
    qtbot.wait(50)
    assert ink(field) == DARK.foreground


def test_a_field_built_before_it_joined_a_dark_tree_reads_the_theme_on_arrival(dark_host, qtbot):
    """A popup built on its first open never hears a theme land. It reads one when it arrives."""
    for field in (Input(), InputGroupInput(), Textarea()):
        assert ink(field) != DARK.foreground, "the host's theme is not the dark one"
        field.setParent(dark_host)
        field.show()
        qtbot.waitExposed(field)
        assert ink(field) == DARK.foreground, type(field).__name__


def test_a_field_keeps_its_whole_dressing_and_not_only_the_ink(dark_host, qtbot):
    """A field wears a type step as well, and the re-read has to put that back with the colour.

    `apply_field_ink` leaves a keeper that writes the ink alone; a field whose dressing is more
    than the ink registers its own after that one, and the order is what this holds down.
    """
    field = InputGroupInput()
    field.setParent(dark_host)
    field.show()
    qtbot.waitExposed(field)
    dark_host.setStyleSheet(generate_qss(DARK))
    qtbot.wait(50)
    assert ink(field) == DARK.foreground
    assert field.font().family() == DARK.font_sans
    assert field.font().pixelSize() == 14


def test_a_field_opened_inside_a_dark_popover_draws_in_the_theme_ink(dark_host, qtbot):
    """The whole path: a field built into a popover's content, then shown with the popover."""
    content = PopoverContent()
    field = Input()
    area = Textarea()
    content.add_widget(field)
    content.add_widget(area)
    popover = Popover(dark_host.anchor, content, takes_focus=True)
    qtbot.addWidget(popover)
    popover.open()
    qtbot.wait(SETTLE_MS)
    assert ink(field) == DARK.foreground
    assert ink(area) == DARK.foreground
    assert ink(area.viewport()) == DARK.foreground
    assert contrast_ratio(ink(field), DARK.popover) > 4.5
    popover.close()
    qtbot.wait(SETTLE_MS)


def test_the_search_box_of_a_picker_opened_in_dark_draws_in_the_theme_ink(dark_host, qtbot):
    """The whole path a reader takes: the popup is built on the first open, then shown.

    A summary control types into the popup's own search box, and that box is built at the moment
    the list first opens, after the theme landed on the page, and it is polished by the show that
    follows. The ink in it has to be the theme's, or the query typed into it cannot be seen.
    """
    from sg_widgets_qt.widgets.picker_control import PickerControl

    control = PickerControl(slot="department-picker", parent=dark_host, inline=False)
    control.setGeometry(16, 80, 380, 32)
    control.show()
    qtbot.waitExposed(control)
    control.set_open(True)
    qtbot.wait(SETTLE_MS)
    caret = control.caret()
    assert caret is not None
    assert ink(caret) == DARK.foreground
    assert contrast_ratio(ink(caret), DARK.popover) > 4.5
    control.set_open(False)
    qtbot.wait(SETTLE_MS)


# --- the ground Qt fills itself -------------------------------------------------------------


def test_a_popover_names_its_own_surface_in_the_stylesheet_it_wears(dark_host, qtbot):
    """A popover's stylesheet grounds and inks are the surface it painted, not the page's."""
    popover = Popover(dark_host.anchor, PopoverContent())
    qtbot.addWidget(popover)
    popover.open()
    qtbot.wait(SETTLE_MS)
    assert popover.styleSheet() == generate_qss(DARK, "popover")
    assert popover.styleSheet() != generate_qss(DARK)
    popover.close()
    qtbot.wait(SETTLE_MS)


def test_the_stylesheet_leaves_a_scroll_area_s_scrolled_widget_transparent():
    """`QScrollArea.setWidget` turns auto-fill on, and Qt would fill from the host's own grey."""
    rule = "QAbstractScrollArea > QWidget#qt_scrollarea_viewport > QWidget"
    qss = generate_qss(DARK)
    assert rule in qss
    assert qss.split(rule, 1)[1].split("}", 1)[0].strip().startswith("{")
    assert "transparent" in qss.split(rule, 1)[1].split("}", 1)[0]


def test_a_section_inside_a_dark_popover_stands_on_the_popover_surface(dark_host, qtbot):
    """The recents block of the context panel is this shape: a scroll area holding a column."""
    content = PopoverContent()
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QScrollArea.Shape.NoFrame)
    area.setWidget(QtWidgets.QWidget())
    area.setMinimumHeight(60)
    content.add_widget(area)

    popover = Popover(dark_host.anchor, content, width=240)
    qtbot.addWidget(popover)
    popover.open()
    qtbot.wait(SETTLE_MS)

    # The whole window, so what is read is what the reader sees: the surface the popover painted
    # showing through the scrolled widget, and not the application's grey filled over it.
    shot = popover.grab().toImage()
    middle = area.mapTo(popover, area.rect().center())
    assert QtGui.QColor(shot.pixel(middle)).name() == QtGui.QColor(DARK.popover).name()
    popover.close()
    qtbot.wait(SETTLE_MS)


def test_the_generated_stylesheet_grounds_a_popup_on_the_popover_token():
    """One surface named in one place: the page's stylesheet and a popup's differ by that token."""
    page = generate_qss(DARK)
    popup = generate_qss(DARK, "popover")
    assert page != popup
    ground = QtGui.QColor(DARK.popover)
    assert f"rgba({ground.red()}, {ground.green()}, {ground.blue()}, {ground.alpha()})" in popup


def test_a_popover_s_own_title_reads_the_theme_it_ends_up_under(dark_host, qtbot):
    """Content is built before it is handed to a popover, so its labels read the host's theme."""
    content = PopoverContent(title="Filters", description="What the list is narrowed by")
    labels = content.findChildren(QtWidgets.QLabel)
    assert len(labels) == 2
    popover = Popover(dark_host.anchor, content, width=240)
    qtbot.addWidget(popover)
    popover.open()
    qtbot.wait(SETTLE_MS)
    ink = QtGui.QColor(DARK.popover_foreground)
    assert f"{ink.red()}, {ink.green()}, {ink.blue()}" in labels[0].styleSheet()
    muted = QtGui.QColor(DARK.muted_foreground)
    assert f"{muted.red()}, {muted.green()}, {muted.blue()}" in labels[1].styleSheet()
    popover.close()
    qtbot.wait(SETTLE_MS)


def test_the_dark_ink_reads_against_the_dark_surfaces():
    """The tokens themselves: what these tests assert a field wears has to be readable."""
    for palette in ("default", "nova", "vercel"):
        theme = theme_for(palette, dark=True)
        assert contrast_ratio(theme.foreground, theme.background) > 4.5, palette
        assert contrast_ratio(theme.popover_foreground, theme.popover) > 4.5, palette


def test_a_disabled_field_in_dark_is_dimmed_and_not_blacked_out(dark_host, qtbot):
    """The inert step is the theme's ink at half, and a repolish has to leave it that."""
    field = Input(parent=dark_host)
    field.setEnabled(False)
    field.show()
    qtbot.waitExposed(field)
    dim = field.palette().color(DISABLED, TEXT)
    assert dim.name() == DARK.foreground
    assert dim.alpha() == 128
