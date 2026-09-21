"""No ground on a dark page keeps the value it was given for a light one.

`test_dark_ink.py` beside this file holds down the ink: what Qt draws with a palette it rebuilt
from the application's. This holds down the other half, the ground a widget paints for itself.

Upstream a field, a select trigger and a checkbox carry no background of their own -- they are
`bg-transparent`, so the card, the popover or the page under them is what a reader sees -- and
each lifts off a dark page with `dark:bg-input/30`. A port that fills `background` instead keeps
the light value in both places at once: on a dark page the box reads flat against the page where
upstream lifts it, and inside a dark popover or card it paints the page's own ground over the
surface and reads as a hole cut in it.

The classes are `input.tsx`, `textarea.tsx`, `select.tsx` and `checkbox.tsx` of the upstream
registry; each test names the one it holds.
"""
from __future__ import annotations

from collections import Counter

import pytest
from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.primitives.checkbox import Checkbox
from sg_widgets_qt.primitives.input import Input, Textarea
from sg_widgets_qt.primitives.popover import Popover, PopoverContent
from sg_widgets_qt.primitives.select import Select
from sg_widgets_qt.theme import apply_theme, theme_for, to_color

#: Long enough for a 100ms open to land.
SETTLE_MS = 300

DARK = theme_for("default", dark=True)
LIGHT = theme_for("default")


class Ground(QtWidgets.QWidget):
    """A flat surface in one token, so what a child paints is read against a known colour."""

    def __init__(self, token: str, theme, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._token = token
        self._theme = theme

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), to_color(getattr(self._theme, self._token)))
        painter.end()


def luminance(color: QtGui.QColor) -> float:
    """The WCAG relative luminance of a colour, 0 for black and 1 for white."""
    out = 0.0
    for channel, weight in ((color.red(), 0.2126), (color.green(), 0.7152), (color.blue(), 0.0722)):
        value = channel / 255.0
        out += weight * (value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return out


def ground_under(host: QtWidgets.QWidget, widget: QtWidgets.QWidget) -> QtGui.QColor:
    """The colour a reader sees inside `widget`, read out of the picture `host` painted.

    The host is grabbed rather than the widget, because a widget that paints no ground of its
    own has nothing to grab: what shows through it is the surface its parent painted.
    """
    shot = host.grab().toImage()
    middle = widget.mapTo(host, widget.rect().center())
    return QtGui.QColor(shot.pixel(middle))


@pytest.fixture
def dark_page(qtbot):
    """A `background` surface in the dark theme, with an anchor to hang a popover off."""
    widget = Ground("background", DARK)
    apply_theme(widget, DARK)
    qtbot.addWidget(widget)
    widget.resize(520, 400)
    widget.anchor = QtWidgets.QLineEdit(widget)
    widget.anchor.setGeometry(16, 16, 240, 32)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def light_page(qtbot):
    """The same surface in the light theme."""
    widget = Ground("background", LIGHT)
    apply_theme(widget, LIGHT)
    qtbot.addWidget(widget)
    widget.resize(520, 400)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def _placed(widget: QtWidgets.QWidget, page: QtWidgets.QWidget, qtbot) -> QtWidgets.QWidget:
    widget.setParent(page)
    widget.setGeometry(16, 120, 240, 32)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


# --- a field -----------------------------------------------------------------------------


def test_a_field_on_a_dark_page_lifts_off_it(dark_page, qtbot):
    """`input.tsx`: `dark:bg-input/30`. The box stands off the page rather than flat on it."""
    field = _placed(Input(), dark_page, qtbot)
    ground = ground_under(dark_page, field)
    page = to_color(DARK.background)
    assert luminance(ground) > luminance(page), ground.name()


def test_a_textarea_on_a_dark_page_lifts_off_it(dark_page, qtbot):
    """`textarea.tsx` carries the same pair, and the box is the one `_Field` paints."""
    area = Textarea()
    area.setParent(dark_page)
    area.setGeometry(16, 180, 240, 80)
    area.show()
    qtbot.waitExposed(area)
    ground = ground_under(dark_page, area)
    assert luminance(ground) > luminance(to_color(DARK.background)), ground.name()


def test_a_field_on_a_light_page_paints_no_ground_of_its_own(light_page, qtbot):
    """`bg-transparent`: the surface under the field is what a light page shows through it."""
    field = _placed(Input(), light_page, qtbot)
    ground = ground_under(light_page, field)
    assert ground.name() == to_color(LIGHT.background).name()


def test_a_field_in_a_dark_popover_stands_on_the_popover_surface(dark_page, qtbot):
    """The defect this holds down: the page's own ground painted over a popover's.

    A picker's search box, an editor in a popover and the command palette's input are all this
    shape, and `background` filled inside one reads as a hole cut in the surface.
    """
    content = PopoverContent()
    field = Input()
    content.add_widget(field)
    popover = Popover(dark_page.anchor, content, takes_focus=True)
    qtbot.addWidget(popover)
    popover.open()
    qtbot.wait(SETTLE_MS)

    ground = ground_under(popover, field)
    assert ground.name() != to_color(DARK.background).name()
    assert luminance(ground) >= luminance(to_color(DARK.popover))
    popover.close()
    qtbot.wait(SETTLE_MS)


# --- a select trigger --------------------------------------------------------------------


def test_a_select_trigger_on_a_dark_page_lifts_off_it(dark_page, qtbot):
    """`select.tsx`: `bg-transparent dark:bg-input/30` on the trigger, as the field has."""
    trigger = _placed(Select(items=[("a", "Alpha"), ("b", "Beta")], value="a"), dark_page, qtbot)
    ground = ground_under(dark_page, trigger)
    assert luminance(ground) > luminance(to_color(DARK.background)), ground.name()


def test_a_select_trigger_on_a_light_page_paints_no_ground_of_its_own(light_page, qtbot):
    """In light the trigger is transparent, so the surface under it is what a reader sees."""
    trigger = _placed(Select(items=[("a", "Alpha")], value="a"), light_page, qtbot)
    ground = ground_under(light_page, trigger)
    assert ground.name() == to_color(LIGHT.background).name()


# --- a checkbox --------------------------------------------------------------------------


def _checkbox_ground(host: QtWidgets.QWidget, box: Checkbox) -> QtGui.QColor:
    """The ground of the checkbox's own square, which is its leading 16 pixels.

    The colour covering most of the square, because a tick is a stroke drawn across its middle
    and a point sample there would read the glyph rather than the ground under it.
    """
    shot = host.grab().toImage()
    top_left = box.mapTo(host, QtCore.QPoint(2, box.height() // 2 - 6))
    counts: Counter = Counter()
    for down in range(12):
        for across in range(12):
            counts[shot.pixel(top_left.x() + across, top_left.y() + down)] += 1
    return QtGui.QColor(counts.most_common(1)[0][0])


def test_an_unticked_checkbox_on_a_dark_page_lifts_off_it(dark_page, qtbot):
    """`checkbox.tsx`: `dark:bg-input/30` under the tick, and no ground at all in light."""
    box = Checkbox(parent=dark_page)
    box.setGeometry(16, 260, 120, 16)
    box.show()
    qtbot.waitExposed(box)
    ground = _checkbox_ground(dark_page, box)
    assert luminance(ground) > luminance(to_color(DARK.background)), ground.name()


def test_a_ticked_checkbox_is_the_primary_token(dark_page, qtbot):
    """`data-checked:bg-primary`: the tick's ground is the token itself, opaque."""
    box = Checkbox(parent=dark_page)
    box.setGeometry(16, 300, 120, 16)
    box.set_checked(True)
    box.show()
    qtbot.waitExposed(box)
    qtbot.wait(SETTLE_MS)
    ground = _checkbox_ground(dark_page, box)
    assert ground.name() == to_color(DARK.primary).name()
