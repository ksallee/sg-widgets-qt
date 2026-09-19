"""The picker control's box: where its ink sits, and what its hover wash composites to.

Rule 3 of `docs/design-rules.md`: a filled control's leading inset matches the room above and
below the chip, and an empty one gives that inset back and reads as a plain input. Either way
the ink — a chip's label, a plain-text value, the caret's placeholder — sits on the control's
own centre line. The inset is what the chip and the border leave under the ladder, halved, so
the border counts: 20 and 2 under 28 at sm, 24 and 2 under 32 at md, and md's 24 and 2 under 36
at lg.

Rule 1: `bg-background hover:bg-muted/30`. `muted` is a translucent overlay in several
palettes, so the wash is that alpha taken to 30% of itself and laid over the surface, never a
blend towards the token's raw colour, which reads as a grey the web never draws.

    .venv/bin/python tools/qa.py --page picker-control --drive tools/drives/picker-box.py
    .venv/bin/python tools/qa.py --page picker-control --drive tools/drives/picker-box.py --dark
    .venv/bin/python tools/qa.py --page entity-picker --drive tools/drives/picker-box.py --qt5

The ink is read off a real grab rather than from font metrics, so the measurement holds where
the platform's own metrics differ.
"""
from __future__ import annotations

from qtpy.QtGui import QColor
from qtpy.QtWidgets import QWidget

from sg_widgets_qt.primitives.badge import Chip
from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
from sg_widgets_qt.theme import apply_theme, theme_of, with_alpha
from sg_widgets_qt.widgets.picker_control import (
    PICKER_CHIP,
    PICKER_SIZE_VALUES,
    PickerControl,
    over,
)

#: How far off the control's own centre line the ink may sit.
CENTRE_TOLERANCE = 1.0

#: A pixel counts as ink when it differs from the surface by this much on any channel.
INK_THRESHOLD = 24


def ink_rows(image, box, surface: QColor) -> tuple[int, int] | None:
    """The first and last row of `box` holding a pixel that is not the surface."""
    first = last = None
    for y in range(box[1], box[1] + box[3]):
        for x in range(box[0], box[0] + box[2]):
            pixel = QColor(image.pixel(x, y))
            near = (
                abs(pixel.red() - surface.red())
                + abs(pixel.green() - surface.green())
                + abs(pixel.blue() - surface.blue())
            )
            if near > INK_THRESHOLD:
                if first is None:
                    first = y
                last = y
                break
    if first is None or last is None:
        return None
    return first, last


def measure(control: PickerControl, note, where: str) -> dict:
    """Where the control's ink sits against its own centre line."""
    theme = theme_of(control)
    image = control.grab().toImage()
    ratio = image.width() / max(1, control.width())
    surface = theme.color("background")
    left, right, _pad = control._insets()
    # The reading column: past the leading inset, short of the trailing reserve.
    box = (
        int(left * ratio) + 1,
        int(2 * ratio),
        max(1, int((control.width() - left - right) * ratio) - 2),
        max(1, int((control.height() - 4) * ratio)),
    )
    found = ink_rows(image, box, surface)
    out: dict = {
        "where": where,
        "size": control.size,
        "filled": len(control.labels),
        "h": control.height(),
        "ladder": CONTROL_HEIGHT[control.size],
    }
    if found is None:
        out["ink"] = None
        note("centre", f"{where}: the control draws no ink to measure")
        return out
    top, bottom = (value / ratio for value in found)
    middle = (top + bottom) / 2.0
    out["ink"] = [round(top, 1), round(bottom, 1)]
    out["centre"] = round(middle, 2)
    out["off"] = round(middle - control.height() / 2.0, 2)
    if abs(out["off"]) > CENTRE_TOLERANCE:
        note(
            "centre",
            f"{where}: the ink centres at {out['centre']} in a {control.height()}px control,"
            f" {out['off']}px off",
        )
    return out


def hover_wash(control: PickerControl, wait, note) -> dict:
    """The fill under hover, against the composite `hover:bg-muted/30` asks for."""
    theme = theme_of(control)
    wanted = over(theme.color("background"), with_alpha(theme.muted, 0.3))
    control.set_hovered(True)
    wait(400)
    image = control.grab().toImage()
    ratio = image.width() / max(1, control.width())
    # Clear of the text on the left and the trailing pair on the right.
    x = int(control.width() * 0.5 * ratio)
    y = int(control.height() * 0.5 * ratio)
    got = QColor(image.pixel(x, y))
    control.set_hovered(False)
    wait(300)
    off = [
        got.red() - wanted.red(),
        got.green() - wanted.green(),
        got.blue() - wanted.blue(),
    ]
    if max(abs(value) for value in off) > 1:
        note(
            "hover",
            f"the hover wash reads {got.name()} where `muted/30` over the surface"
            f" is {wanted.name()}",
        )
    return {"wanted": wanted.name(), "got": got.name(), "off": off}


def build_matrix(page, wait) -> list:
    """One control per size, empty and filled, so the ladder is measured whatever the page holds."""
    host = QWidget(page)
    apply_theme(host, theme_of(page))
    host.setGeometry(0, 0, 420, 240)
    host.show()
    made = []
    y = 4
    for size in PICKER_SIZE_VALUES:
        for filled in (False, True):
            control = PickerControl(
                slot="matrix-picker",
                picker="matrix",
                size=size,
                placeholder="Search for an entity",
                parent=host,
            )
            control.setGeometry(4, y, 400, CONTROL_HEIGHT[size])
            if filled:
                control.set_chip_factory(
                    lambda index, c=control: Chip(
                        "charAda", size=PICKER_CHIP[c.size], parent=c
                    )
                )
                control.set_keys(["Asset:1226"])
                control.set_labels(["charAda"])
            control.show()
            y += CONTROL_HEIGHT[size] + 8
            made.append((f"{size}/{'filled' if filled else 'empty'}", control))
    wait(250)
    return made


def drive(page, wait, find, prefs) -> dict:
    wait(400)
    failures: list = []

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    seen: list = []
    for where, control in build_matrix(page, wait):
        seen.append(measure(control, note, where))

    # The page's own controls, at whatever size the toolbar holds.
    live = [
        control
        for control in find(PickerControl, all=True)
        if not control.disabled and control.isVisible() and control.width() > 120
    ]
    for control in live[:6]:
        seen.append(measure(control, note, f"page/{control.objectName()}"))

    wash = hover_wash(live[0], wait, note) if live else {}

    # The popup's search row: 32 high under a 1px border, its caret filling it.
    row_seen = {}
    summary = next((c for c in live if not c.inline and c.searchable), None)
    if summary is not None:
        summary.set_open(True)
        wait(400)
        row = summary.search_row()
        caret = summary.caret()
        row_seen = {
            "row_h": row.height(),
            "caret": list(caret.geometry().getRect()),
            "off": caret.y() + caret.height() / 2.0 - (row.height() - 1) / 2.0,
        }
        if abs(row_seen["off"]) > CENTRE_TOLERANCE:
            note("search-row", f"the search caret centres {row_seen['off']}px off the row")
        summary.set_open(False)
        wait(200)

    return {
        "verdict": (
            "PASS the control's ink sits on its centre line at every size and the hover wash"
            " is `muted/30` over the surface"
            if not failures
            else "FAIL " + "; ".join(failures[:10])
        ),
        "failures": failures,
        "measured": seen,
        "hover": wash,
        "search_row": row_seen,
    }
