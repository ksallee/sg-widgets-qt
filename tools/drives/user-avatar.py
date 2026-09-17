"""The avatar: the ladder, the initials, the hue one name always takes, and the dimmed person.

    .venv/bin/python tools/qa.py --page user-avatar --drive tools/drives/user-avatar.py
    .venv/bin/python tools/qa.py --page user-avatar --drive tools/drives/user-avatar.py --qt5

There is no upstream drive for the avatar: the claims are the page's own. An avatar with no
picture draws the initials core derives, one name takes one hue wherever it is drawn, an API user
draws the bot glyph instead, and a dimmed person is desaturated as well as dimmed (rule 5).
"""
from __future__ import annotations

from qtpy import QtGui

from sg_widgets_core.render import initials_of, name_hue
from sg_widgets_qt.primitives.base import THUMB_SIZE
from sg_widgets_qt.widgets.user_avatar import UserAvatar

#: Avatars follow the first three steps of the thumbnail ladder (rule 3).
LADDER = {"sm": 24, "md": 32, "lg": 40}


def _colours(image: QtGui.QImage) -> dict:
    """What one avatar put down, by colour, so a ground and an ink can be told apart."""
    tally: dict = {}
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() == 0:
                continue
            tally[colour.name()] = tally.get(colour.name(), 0) + 1
    return tally


def _saturation(image: QtGui.QImage) -> float:
    total = count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() == 0:
                continue
            total += colour.saturation()
            count += 1
    return total / count if count else 0.0


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    failures: list[str] = []
    seen: dict = {}

    avatars = find(UserAvatar, all=True)
    if not avatars:
        return {"verdict": "FAIL the page drew no avatar"}
    seen["avatars"] = len(avatars)

    # --- the ladder ---

    steps: dict = {}
    for avatar in avatars:
        step = avatar.size
        if step in steps:
            continue
        steps[step] = [avatar.width(), avatar.height()]
        if (avatar.width(), avatar.height()) != (LADDER[step], LADDER[step]):
            failures.append(
                f"a {step} avatar is {avatar.width()}x{avatar.height()}, wanted a {LADDER[step]} circle"
            )
        if THUMB_SIZE[step] != LADDER[step]:
            failures.append(f"the {step} step is {THUMB_SIZE[step]}, wanted {LADDER[step]}")
    seen["ladder"] = steps
    for step in ("sm", "md", "lg"):
        if step not in steps:
            failures.append(f"the page drew no {step} avatar to measure")

    # --- initials, where there is no picture ---

    bare = [a for a in avatars if a.pixmap is None and not a.api_user and a.name]
    if not bare:
        failures.append("the page drew no avatar without a picture")
    else:
        avatar = bare[0]
        seen["initials"] = {"name": avatar.name, "letters": avatar.initials}
        if avatar.initials != initials_of(avatar.name):
            failures.append("the initials are not the ones core derives")
        if not avatar.initials:
            failures.append(f"{avatar.name} gave no initials")
        # The ink of the letters is a second colour on the circle, so a drawn letter shows up as
        # one: a circle with nothing on it carries its ground and its ring alone.
        if len(_colours(avatar.grab().toImage())) < 3:
            failures.append("the circle drew no letters on its ground")

    # --- one name, one hue ---

    tinted = [a for a in avatars if a.tinted]
    seen["tinted"] = len(tinted)
    if not tinted:
        failures.append("the page drew no tinted avatar")
    else:
        one = tinted[0]
        twin = UserAvatar(name=one.name, color="auto", size=one.size, parent=one.parentWidget())
        twin.move(one.pos())
        twin.show()
        wait(60)
        seen["hue"] = {"name": one.name, "core": name_hue(one.name), "drawn": [one.hue, twin.hue]}
        if one.hue != twin.hue or one.hue != name_hue(one.name):
            failures.append(f"{one.name} took two hues: {one.hue} and {twin.hue}")
        if _colours(one.grab().toImage()) != _colours(twin.grab().toImage()):
            failures.append(f"{one.name} drew two different circles")
        twin.setParent(None)
        twin.deleteLater()

    # --- a script account ---

    bots = [a for a in avatars if a.api_user]
    seen["api_users"] = len(bots)
    if not bots:
        failures.append("the page drew no API user")
    elif bots[0].tinted:
        failures.append("an API user took the initials tint")
    elif "(API user)" not in bots[0].toolTip():
        failures.append(f"an API user says {bots[0].toolTip()!r}, which does not name the account")

    # --- the dimmed person ---

    dimmed = [a for a in avatars if a.inactive and a.tinted]
    if not dimmed:
        failures.append("the page drew no dimmed person on a tint")
    else:
        dim = dimmed[0]
        lit = UserAvatar(name=dim.name, color="auto", size=dim.size, parent=dim.parentWidget())
        lit.move(dim.pos())
        lit.show()
        wait(60)
        one, other = _saturation(lit.grab().toImage()), _saturation(dim.grab().toImage())
        seen["inactive"] = {"name": dim.name, "saturation": [round(one, 1), round(other, 1)]}
        if other >= one:
            failures.append(
                f"a dimmed person keeps the hue of its name: {round(one, 1)} became {round(other, 1)}"
            )
        lit.setParent(None)
        lit.deleteLater()

    return {
        "verdict": (
            "PASS the ladder is 24/32/40, an avatar with no picture draws core's initials, one "
            "name takes one hue wherever it is drawn, a script account draws the bot glyph, and "
            "a dimmed person is desaturated"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
