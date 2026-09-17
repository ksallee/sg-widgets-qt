"""The state line: the two states, the caller's label and glyph, and the inset of each surface.

    .venv/bin/python tools/qa.py --page state-line --drive tools/drives/state-line.py
    .venv/bin/python tools/qa.py --page state-line --drive tools/drives/state-line.py --qt5

The port of `~/dev/sg-widgets/tools/drives/state-line-demo.js`, which reads the `py-6`, `py-10`
and bare classes off the DOM. Here the inset is the height the line stands at: the line itself
plus twice the padding of `docs/design-rules.md` rule 5, 24 in a popup list, 40 in a table body,
and none under rows already drawn, where the block around it owns the inset.

Loading is not one of the two: it is skeletons shaped like the rows, so it stays with the widget
that knows that shape.
"""
from __future__ import annotations

from qtpy import QtGui

from sg_widgets_qt.widgets.state_line import STATE_LINE_PAD, StateLine

#: What each case on the page carries: its object name, the states in it and the inset it takes.
CASES = {
    "case-popover": {"states": ["empty", "error"], "pad": "popover", "room": 24},
    "case-table": {"states": ["empty", "error"], "pad": "table", "room": 40},
    "case-under-rows": {"states": ["error"], "pad": "none", "room": 0},
}


def _inks(image: QtGui.QImage) -> list:
    """The colours the line put down, commonest first, so its tone can be read."""
    tally: dict = {}
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 0:
                tally[colour.name()] = tally.get(colour.name(), 0) + 1
    return sorted(tally, key=tally.get, reverse=True)


def _nearest(colour: QtGui.QColor, ink: QtGui.QColor, other: QtGui.QColor) -> bool:
    """True when `colour` is nearer `ink` than `other`."""
    def gap(one: QtGui.QColor) -> float:
        return (
            (one.red() - colour.red()) ** 2
            + (one.green() - colour.green()) ** 2
            + (one.blue() - colour.blue()) ** 2
        ) ** 0.5

    return gap(ink) < gap(other)


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    failures: list[str] = []
    seen: dict = {}

    lines = find(StateLine, all=True)
    on_show = [line for line in lines if line.parent() is not None and line.isVisible()]
    if not on_show:
        return {"verdict": "FAIL the page drew no state line"}
    seen["lines"] = len(on_show)

    for name, wants in CASES.items():
        case = find(name)
        if case is None:
            failures.append(f"the page has no {name}")
            continue
        drawn = [line for line in case.findChildren(StateLine)]
        seen[name] = []
        if len(drawn) != len(wants["states"]):
            failures.append(f"{name} drew {len(drawn)} lines, wanted {len(wants['states'])}")
        for line, state in zip(drawn, wants["states"]):
            room = (line.sizeHint().height() - max(line._glyph(), QtGui.QFontMetrics(line._font()).height())) // 2
            seen[name].append(
                {
                    "state": line.state,
                    "pad": line.pad,
                    "label": line.label,
                    "icon": line.icon,
                    "height": line.sizeHint().height(),
                    "room": room,
                }
            )
            if line.state != state:
                failures.append(f"{name} drew a {line.state} line where a {state} one belongs")
            if line.pad != wants["pad"]:
                failures.append(f"{name} took the {line.pad} inset, wanted {wants['pad']}")
            if STATE_LINE_PAD[line.pad] != wants["room"]:
                failures.append(f"the {line.pad} inset is {STATE_LINE_PAD[line.pad]}, wanted {wants['room']}")
            if room != wants["room"]:
                failures.append(f"a {line.pad} line leaves {room} above its text, wanted {wants['room']}")
            if not line.label:
                failures.append(f"{name} drew a line with no label")
            if not line.icon:
                failures.append(f"{name} drew a line with no glyph in front of it")

    # --- the tone of each state ---

    theme = on_show[0].theme
    muted, destructive = theme.color("muted_foreground"), theme.color("destructive")
    for state, wanted, unwanted in (
        ("empty", muted, destructive),
        ("error", destructive, muted),
    ):
        drawn = [line for line in on_show if line.state == state]
        if not drawn:
            failures.append(f"no {state} line on the page")
            continue
        line = drawn[0]
        inks = _inks(line.grab().toImage())
        # The commonest colour is the ground; the next one along is the line's own ink.
        ink = QtGui.QColor(inks[1]) if len(inks) > 1 else QtGui.QColor(inks[0])
        seen.setdefault("tone", {})[state] = {"ink": ink.name(), "wanted": wanted.name()}
        if not _nearest(ink, wanted, unwanted):
            failures.append(f"the {state} line draws in {ink.name()}, wanted {wanted.name()}")

    return {
        "verdict": (
            "PASS the empty and error line with the caller's label and glyph, at the 24 of a "
            "popup list, the 40 of a table body and the none under rows already drawn, each in "
            "its own tone"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
