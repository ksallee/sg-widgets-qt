"""The status badge: the chip ladder, the inline padding, and the cross inside the pill.

    .venv/bin/python tools/qa.py --page status-badge --drive tools/drives/status-badge.py
    .venv/bin/python tools/qa.py --page status-badge --drive tools/drives/status-badge.py --qt5

The port of `~/dev/sg-widgets/tools/drives/status-badge-remove.js`, which reads the cross off the
DOM. Here the badge is one painted widget, so the same claims are read off its geometry and off
what it painted: the cross sits inside the pill after the label, it hovers with a wash of the
badge's own foreground rather than the destructive tint (`docs/design-rules.md` rule 5), a press
takes the badge away, and the icon and glyph variants carry none.

The ladder of rule 3 is measured on the badges the page itself drew: 20, 24, 32 and 40 high, with
a 12, 14, 16 or 20 glyph, a 12 to 18 cross, and the inline padding of `CHIP_PAD`.
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_qt.primitives.base import CHIP_CROSS, CHIP_GLYPH, CHIP_HEIGHT, CHIP_PAD
from sg_widgets_qt.widgets.status_badge import StatusBadge

#: The step a badge takes, and what rule 3 says it stands at.
LADDER = {"xs": 20, "sm": 24, "md": 32, "lg": 40}

#: How much of the badge's own ink the cross washes with on hover.
CROSS_WASH = 0.08


def _hover(widget: QtWidgets.QWidget, point: QtCore.QPoint) -> None:
    """Move the pointer onto a point of a widget, which is what arms a hover."""
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(point),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    QtWidgets.QApplication.sendEvent(widget, event)


def _average(shot: QtGui.QImage, box: QtCore.QRect) -> QtGui.QColor:
    """The mean colour of one region, which is how a translucent wash is read."""
    red = green = blue = count = 0
    for y in range(max(0, box.top()), min(shot.height(), box.bottom() + 1)):
        for x in range(max(0, box.left()), min(shot.width(), box.right() + 1)):
            colour = shot.pixelColor(x, y)
            red += colour.red()
            green += colour.green()
            blue += colour.blue()
            count += 1
    if not count:
        return QtGui.QColor(0, 0, 0)
    return QtGui.QColor(red // count, green // count, blue // count)


def _distance(one: QtGui.QColor, other: QtGui.QColor) -> float:
    return (
        (one.red() - other.red()) ** 2
        + (one.green() - other.green()) ** 2
        + (one.blue() - other.blue()) ** 2
    ) ** 0.5


def _blend(ground: QtGui.QColor, ink: QtGui.QColor, amount: float) -> QtGui.QColor:
    return QtGui.QColor(
        round(ground.red() * (1 - amount) + ink.red() * amount),
        round(ground.green() * (1 - amount) + ink.green() * amount),
        round(ground.blue() * (1 - amount) + ink.blue() * amount),
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    failures: list[str] = []
    seen: dict = {}

    badges = find(StatusBadge, all=True)
    if not badges:
        return {"verdict": "FAIL the page drew no status badge"}
    seen["badges"] = len(badges)

    # --- the ladder, on the badges the page drew ---

    steps: dict = {}
    for badge in badges:
        if not badge.code or badge.bare:
            continue
        step = badge.size_step
        if step in steps:
            continue
        pad = CHIP_PAD[step]
        steps[step] = {
            "height": badge.sizeHint().height(),
            "glyph": CHIP_GLYPH[step],
            "cross": CHIP_CROSS[step],
            "left": badge._left_pad(),
            "lead": pad.lead,
            "text": pad.text,
        }
        if badge.sizeHint().height() != LADDER[step]:
            failures.append(f"a {step} badge stands {badge.sizeHint().height()} high, wanted {LADDER[step]}")
        if CHIP_HEIGHT[step] != LADDER[step]:
            failures.append(f"the {step} step of the ladder is {CHIP_HEIGHT[step]}, wanted {LADDER[step]}")
        # Rule 3: the edge beside a glyph takes a step less inset than a bare text edge.
        wanted = pad.lead if badge.has_leading() else pad.text
        if badge._left_pad() != wanted:
            failures.append(
                f"a {step} badge insets its leading edge {badge._left_pad()}, wanted {wanted}"
            )
    seen["ladder"] = steps
    for step in ("sm", "md", "lg"):
        if step not in steps:
            failures.append(f"the page drew no {step} badge to measure")

    # --- the cross ---

    box = find("case-removable")
    crossed = [b for b in find(StatusBadge, all=True) if b.removable and b.variant == "both"]
    if box is None or not crossed:
        failures.append("the page drew no removable badge")
        return {"verdict": "FAIL " + "; ".join(failures), "seen": seen}

    badge = crossed[0]
    pill = badge.rect()
    cross = badge._cross_box()
    if not pill.contains(cross):
        failures.append(f"the cross {cross} is outside the pill {pill}")
    spacing_left = badge._left_pad() + (CHIP_GLYPH[badge.size_step] if badge.has_leading() else 0)
    content_right = spacing_left + badge._label_width()
    if cross.left() + 1 < content_right:
        failures.append(f"the cross starts at {cross.left()}, before the label ends at {content_right}")
    # Rule 3: the edge beside a cross is the room above the cross, which upstream reads inside the
    # pill's own border and writes down as `CHIP_PAD.trail`; here the border is drawn inside the
    # box, so the ladder's number is what the outer edge is measured against.
    room_above = cross.top() - badge._box().top()
    trail = badge.width() - cross.right() - 1
    wanted_trail = CHIP_PAD[badge.size_step].trail
    if trail != wanted_trail:
        failures.append(f"the cross sits {trail} from the right edge, wanted {wanted_trail}")
    if abs(room_above - trail) > 1:
        failures.append(f"the cross sits {trail} from the right edge and {room_above} from the top")
    seen["cross"] = {
        "pill": [pill.width(), pill.height()],
        "box": [cross.left(), cross.top(), cross.width(), cross.height()],
        "trail": trail,
        "room_above": room_above,
    }

    # The wash is read on the neutral surface, where the badge's own ink is the only thing that
    # can darken it: a destructive tint would turn the region red instead.
    was_coloured = badge.color
    badge.set_color(False)
    wait(50)
    rest = _average(badge.grab().toImage(), cross)
    _hover(badge, cross.center())
    wait(250)
    hovered = _average(badge.grab().toImage(), cross)
    theme = badge.theme
    wanted = _blend(theme.color("background"), theme.color("foreground"), CROSS_WASH)
    unwanted = _blend(theme.color("background"), theme.color("destructive"), CROSS_WASH)
    seen["wash"] = {"rest": rest.name(), "hovered": hovered.name(), "foreground": wanted.name(), "destructive": unwanted.name()}
    if _distance(hovered, rest) < 2:
        failures.append("the cross draws no wash on hover")
    if _distance(hovered, unwanted) < _distance(hovered, wanted):
        failures.append(f"the cross washes with the destructive tint: {hovered.name()}")
    _hover(badge, QtCore.QPoint(1, 1))
    wait(200)
    badge.set_color(was_coloured)

    # --- the press ---

    code = badge.code
    before = len([b for b in find(StatusBadge, all=True) if b.removable and b.variant == "both"])
    caught: list[str] = []
    badge.removed.connect(caught.append)
    QtWidgets.QApplication.sendEvent(
        badge,
        QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseButtonPress,
            QtCore.QPointF(cross.center()),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
        ),
    )
    QtWidgets.QApplication.sendEvent(
        badge,
        QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseButtonRelease,
            QtCore.QPointF(cross.center()),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
        ),
    )
    wait(300)
    after = len([b for b in find(StatusBadge, all=True) if b.removable and b.variant == "both"])
    seen["press"] = {"code": code, "caught": caught, "before": before, "after": after}
    if caught != [code]:
        failures.append(f"the cross emitted {caught}, wanted [{code!r}]")
    if after != before - 1:
        failures.append(f"{before} removable badges became {after}, wanted one fewer")

    # --- the two bare variants have no room for a cross ---

    bare = [b for b in find(StatusBadge, all=True) if b.removable and b.variant in ("icon", "glyph")]
    seen["bare_removable"] = len(bare)
    for one in bare:
        if one._removable:
            failures.append(f"the {one.variant} variant carries a cross")
    if not bare:
        failures.append("the page drew no icon-only removable badge to read")

    return {
        "verdict": (
            "PASS the ladder is 20/24/32/40 with its own padding, and the cross sits inside the "
            "pill after the label, washes with the badge's foreground, removes on a press, and "
            "the icon and glyph variants carry none"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
