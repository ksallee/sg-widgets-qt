"""The avatar: the ladder, the initials, the name hue, the dimmed person and the script account.

Every test runs on both bindings, offscreen, and never reaches the network: every picture here is
a `data:` url, which the loader decodes where it stands.
"""
from __future__ import annotations

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_core.render import initials_of, name_hue
from sg_widgets_qt.images import ImageLoader
from sg_widgets_qt.primitives.base import THUMB_SIZE
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.user_avatar import AVATAR_SIZE_VALUES, UserAvatar

#: An 8 by 8 block, as a self-contained data URI.
RED_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAACXBIWXMAAA7EAAAOxAGV"
    "Kw4bAAAAFklEQVQYlWM8oaHxnwEPYMInOXwUAAArkgInxYgTRAAAAABJRU5ErkJggg=="
)

#: A truncated PNG: it fails to decode, which falls back to the initials.
BROKEN_PNG = "data:image/png;base64,iVBORw0KGgo="


@pytest.fixture
def loader():
    return ImageLoader()


@pytest.fixture
def root(qtbot):
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(600, 300)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget):
    widget.setParent(parent)
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def image(widget: QtWidgets.QWidget) -> QtGui.QImage:
    pixmap = widget.grab()
    assert not pixmap.isNull()
    return pixmap.toImage()


def counts(shot: QtGui.QImage) -> dict:
    tally: dict = {}
    for y in range(shot.height()):
        for x in range(shot.width()):
            name = shot.pixelColor(x, y).name()
            tally[name] = tally.get(name, 0) + 1
    return tally


def test_constructs_and_paints(root, loader):
    avatar = place(root, UserAvatar(name="Ada Lovelace", loader=loader))
    assert avatar.objectName() == "user-avatar"
    assert avatar.initials == "AL"
    assert avatar.toolTip() == "Ada Lovelace"
    assert counts(image(avatar))


@pytest.mark.parametrize("step", AVATAR_SIZE_VALUES)
def test_every_step_is_a_circle_on_the_ladder(root, loader, step):
    avatar = UserAvatar(name="Ada Lovelace", size=step, loader=loader)
    assert avatar.sizeHint().width() == THUMB_SIZE[step]
    assert avatar.sizeHint().height() == THUMB_SIZE[step]


@pytest.mark.parametrize(
    "name,letters",
    [
        ("Ada Lovelace", "AL"),
        ("Anna van der Meer", "AM"),
        ("Madonna", "M"),
        ("j.doe", "JD"),
        ("", ""),
    ],
)
def test_the_initials_are_core_s(root, loader, name, letters):
    avatar = place(root, UserAvatar(name=name, loader=loader))
    assert avatar.initials == letters == initials_of(name)
    assert counts(image(avatar))


def test_a_picture_replaces_the_initials(root, loader):
    avatar = place(root, UserAvatar(name="Ada Lovelace", image=RED_PNG, loader=loader))
    assert avatar.pixmap is not None
    assert QtGui.QColor(200, 40, 40).name() in counts(image(avatar))


def test_a_picture_that_fails_falls_back_to_the_initials(root, loader):
    avatar = place(root, UserAvatar(name="Alan Turing", image=BROKEN_PNG, loader=loader))
    plain = place(root, UserAvatar(name="Alan Turing", loader=loader))
    assert avatar.pixmap is None
    assert image(avatar) == image(plain)


def test_the_tint_is_the_name_hue_from_core(root, loader):
    avatar = place(root, UserAvatar(name="Anna van der Meer", color="auto", loader=loader))
    assert avatar.hue == name_hue("Anna van der Meer")
    assert avatar.tinted is True
    plain = place(root, UserAvatar(name="Anna van der Meer", loader=loader))
    assert plain.tinted is False
    assert image(avatar) != image(plain)


def test_two_names_take_two_grounds(root, loader):
    one = place(root, UserAvatar(name="Ada Lovelace", color="auto", loader=loader))
    other = place(root, UserAvatar(name="Grace Hopper", color="auto", loader=loader))
    assert one.hue != other.hue


def test_an_api_user_draws_a_glyph_and_says_so(root, loader):
    bot = place(root, UserAvatar(name="sg_widgets_demo", api_user=True, loader=loader))
    assert bot.toolTip() == "sg_widgets_demo (API user)"
    assert bot.tinted is False
    assert counts(image(bot))


def test_an_api_user_never_shows_a_picture(root, loader):
    bot = place(root, UserAvatar(name="sg_widgets_demo", api_user=True, image=RED_PNG, loader=loader))
    assert bot.pixmap is None
    assert QtGui.QColor(200, 40, 40).name() not in counts(image(bot))


def test_inactive_dims_without_hiding(root, loader):
    lit = place(root, UserAvatar(name="Grace Hopper", loader=loader))
    dim = place(root, UserAvatar(name="Grace Hopper", inactive=True, loader=loader))
    assert dim.inactive is True
    assert image(dim) != image(lit)
    assert counts(image(dim))


def test_inactive_takes_the_hue_out_of_the_tint(root, loader):
    """A dimmed person is desaturated as well as dimmed, the tint behind the initials included."""
    lit = place(root, UserAvatar(name="Bo Chen", color="auto", loader=loader))
    dim = place(root, UserAvatar(name="Bo Chen", color="auto", inactive=True, loader=loader))
    assert dim.tinted is True
    for shot, greys in ((image(lit), False), (image(dim), True)):
        colours = [QtGui.QColor(name) for name in counts(shot)]
        painted = [c for c in colours if c.saturation() > 40]
        assert bool(painted) is not greys


def test_the_loaded_signal_fires_when_a_picture_lands(root, qtbot, loader):
    avatar = place(root, UserAvatar(name="Ada Lovelace", loader=loader))
    with qtbot.waitSignal(avatar.loaded, timeout=1000) as caught:
        avatar.set_image(RED_PNG)
    assert caught.args == [True]


def test_every_setter_repaints(root, loader):
    avatar = place(root, UserAvatar(name="Ada Lovelace", loader=loader))
    avatar.set_name("Anna van der Meer")
    avatar.set_size("lg")
    avatar.set_color("auto")
    avatar.set_inactive(True)
    avatar.set_api_user(True)
    QtWidgets.QApplication.processEvents()
    assert avatar.name == "Anna van der Meer"
    assert avatar.size == "lg"
    assert avatar.color == "auto"
    assert avatar.api_user is True
    assert counts(image(avatar))
