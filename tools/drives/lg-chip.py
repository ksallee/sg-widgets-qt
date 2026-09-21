"""A large picker keeps md's chip, so the chip has room inside 36px.

Rule 3 of `docs/design-rules.md`: a chip sits one step under the control it is in, except at lg,
where a 32px chip left 1px above and below under 36. lg keeps md's 24px chip, inset 5, so the
control holds 36 exactly and the chip has room round it. The picker control, the context
selector's trigger and the text chips every picker draws all read the same ladder, so the drive
runs on either page and measures whatever that page holds.

    .venv/bin/python tools/qa.py --page picker-control --drive tools/drives/lg-chip.py
    .venv/bin/python tools/qa.py --page context-selector --drive tools/drives/lg-chip.py

The chip's box is read off its geometry inside the control, so the room above and below is what
the control actually leaves, not what the ladder says it should.
"""
from __future__ import annotations

from qtpy.QtWidgets import QWidget

from sg_widgets_qt.primitives.badge import Chip
from sg_widgets_qt.primitives.base import CHIP_HEIGHT, CONTROL_HEIGHT
from sg_widgets_qt.theme import apply_theme, theme_of
from sg_widgets_qt.widgets.context_selector import CHIP_STEP, ContextSelector
from sg_widgets_qt.widgets.picker_control import (
    BORDER,
    PICKER_BOX,
    PICKER_CHIP,
    PickerControl,
)

#: What lg now stands on: md's chip, inset 5, inside the 36px control.
LG_CHIP = "sm"
LG_INSET = 5


def room(control, chip) -> tuple[int, int]:
    """The room the control leaves above and below the chip, inside its own border."""
    above = chip.y() - BORDER
    below = control.height() - (chip.y() + chip.height()) - BORDER
    return above, below


def measure_control(control, where: str, note) -> dict:
    """One lg picker control: its height, its chip's step and the room round the chip."""
    out: dict = {
        "where": where,
        "kind": "picker-control",
        "min_h": control.minimumHeight(),
        "h": control.height(),
        "ladder": CONTROL_HEIGHT["lg"],
    }
    if control.minimumHeight() != CONTROL_HEIGHT["lg"]:
        note("height", f"{where}: the control stands {control.minimumHeight()}px under a 36px ladder")
    inset = control._insets()[2]
    out["inset"] = inset
    chips = [chip for chip in control.chips() if isinstance(chip, Chip)]
    if not chips:
        # An empty control gives its inset back, so there is no chip to measure here.
        out["chip"] = None
        return out
    if inset != LG_INSET:
        note("inset", f"{where}: a filled control insets {inset}px where lg takes {LG_INSET}px")
    chip = chips[0]
    out["chip"] = {"step": chip.size_step, "h": chip.height()}
    if chip.size_step != LG_CHIP:
        note("chip", f"{where}: the chip is the {chip.size_step} step where lg keeps md's {LG_CHIP}")
    if chip.height() != CHIP_HEIGHT[LG_CHIP]:
        note("chip", f"{where}: the chip stands {chip.height()}px where md's is {CHIP_HEIGHT[LG_CHIP]}px")
    if control.height() == CONTROL_HEIGHT["lg"]:
        above, below = room(control, chip)
        out["room"] = [above, below]
        if (above, below) != (LG_INSET, LG_INSET):
            note("room", f"{where}: the chip leaves {above}px above and {below}px below, not {LG_INSET}")
    return out


def measure_trigger(selector, where: str, note) -> dict:
    """The context selector's lg trigger: the same ladder, read off its own row."""
    trigger = selector.trigger()
    margins = trigger._row.contentsMargins()
    out: dict = {
        "where": where,
        "kind": "context-selector",
        "min_h": trigger.minimumSizeHint().height(),
        "ladder": CONTROL_HEIGHT["lg"],
        "inset": [margins.left(), margins.top(), margins.bottom()],
    }
    if trigger.minimumSizeHint().height() != CONTROL_HEIGHT["lg"]:
        note("height", f"{where}: the trigger stands {out['min_h']}px under a 36px ladder")
    chips = trigger.findChildren(Chip)
    if not chips:
        out["chip"] = None
        note("chip", f"{where}: the trigger carries no chip to measure")
        return out
    if out["inset"] != [LG_INSET, LG_INSET, LG_INSET]:
        note("inset", f"{where}: a filled trigger insets {out['inset']} where lg takes {LG_INSET}px")
    chip = chips[0]
    out["chip"] = {"step": chip.size_step, "h": chip.height()}
    if chip.size_step != LG_CHIP:
        note("chip", f"{where}: the chip is the {chip.size_step} step where lg keeps md's {LG_CHIP}")
    if chip.height() != CHIP_HEIGHT[LG_CHIP]:
        note("chip", f"{where}: the chip stands {chip.height()}px where md's is {CHIP_HEIGHT[LG_CHIP]}px")
    return out


def build_control(page, wait):
    """An lg control standing at exactly 36, so the room round its chip is measured somewhere."""
    host = QWidget(page)
    apply_theme(host, theme_of(page))
    host.setGeometry(0, 0, 420, 60)
    host.show()
    control = PickerControl(slot="lg-chip-picker", picker="lg-chip", size="lg", parent=host)
    control.setGeometry(4, 4, 400, CONTROL_HEIGHT["lg"])
    control.set_chip_factory(
        lambda index, c=control: Chip("charAda", size=PICKER_CHIP[c.size], parent=c)
    )
    control.set_keys(["Asset:1226"])
    control.set_labels(["charAda"])
    control.show()
    wait(250)
    return control


def drive(page, wait, find, prefs) -> dict:
    wait(400)
    failures: list = []

    def note(clause: str, detail: str) -> None:
        failures.append(f"{clause} — {detail}")

    if PICKER_CHIP["lg"] != LG_CHIP or PICKER_BOX["lg"][2] != LG_INSET:
        note("ladder", f"lg stands on {PICKER_CHIP['lg']} inset {PICKER_BOX['lg'][2]}")
    if CHIP_STEP["lg"] != LG_CHIP:
        note("ladder", f"the context selector stands lg on {CHIP_STEP['lg']}")

    seen = [measure_control(build_control(page, wait), "built/lg", note)]

    for control in find(PickerControl, all=True) or []:
        if control.size == "lg" and control.isVisible() and control.width() > 120:
            seen.append(measure_control(control, f"page/{control.objectName() or 'picker'}", note))

    for selector in find(ContextSelector, all=True) or []:
        if selector.size == "lg" and selector.isVisible():
            seen.append(measure_trigger(selector, f"page/{selector.objectName() or 'context'}", note))

    return {
        "verdict": (
            "PASS every lg control stands at 36 and keeps md's 24px chip with 5px round it"
            if not failures
            else "FAIL " + "; ".join(failures[:10])
        ),
        "failures": failures,
        "measured": seen,
    }
