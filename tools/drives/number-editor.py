"""The number editor's stepping, driven on the number-editor page.

The port of `~/dev/sg-widgets/tools/drives/number-editor-stepping.js`, plus the keyboard table of
`docs/widgets/number-editor.md`: Up and Down step once, Shift with them ten times, Page Up and
Page Down a hundred, a held stepper repeats, and the percent field stops at its bound.

    .venv/bin/python tools/qa.py --page number-editor --drive tools/drives/number-editor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

SHIFT = QtCore.Qt.KeyboardModifier.ShiftModifier


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT

    failures: list[str] = []
    seen: dict = {}

    editors = find("number-editor", all=True)
    by_type = {}
    for editor in editors:
        by_type.setdefault(editor.data_type, []).append(editor)
    duration = by_type.get("duration", [None])[0]
    percent = by_type.get("percent", [None])[0]
    if duration is None or percent is None:
        return {"verdict": "FAIL the page holds no duration or no percent field"}

    committed: list = []
    duration.committed.connect(committed.append)

    # A duration steps by a quarter of an hour (field_types/duration): 480 goes to 495.
    seen["before"] = duration.value
    if duration.value != 480:
        failures.append(f"started at {duration.value}, wanted 480")
    key(duration.input, QtCore.Qt.Key.Key_Up)
    wait(60)
    seen["afterKey"] = duration.value
    seen["shown"] = duration.input.text()
    if duration.value != 495:
        failures.append(f"Up gave {duration.value}, wanted 495")
    if duration.input.text() != "8:15":
        failures.append(f"the input reads {duration.input.text()!r}, wanted '8:15'")
    if committed[-1:] != [495]:
        failures.append(f"the signal carried {committed[-1:]}, wanted [495]")

    # Shift takes ten steps at once and Page Up a hundred, per the docs page's table.
    key(duration.input, QtCore.Qt.Key.Key_Up, SHIFT)
    wait(40)
    seen["afterShift"] = duration.value
    if duration.value != 495 + 15 * 10:
        failures.append(f"Shift with Up gave {duration.value}, wanted {495 + 150}")
    key(duration.input, QtCore.Qt.Key.Key_Down, SHIFT)
    key(duration.input, QtCore.Qt.Key.Key_PageUp)
    wait(40)
    seen["afterPage"] = duration.value
    if duration.value != 495 + 15 * 100:
        failures.append(f"Page Up gave {duration.value}, wanted {495 + 1500}")
    key(duration.input, QtCore.Qt.Key.Key_PageDown)
    wait(40)
    if duration.value != 495:
        failures.append(f"Page Down gave {duration.value}, wanted 495")

    # A hold repeats after 400ms, then every 60ms. Half a second of holding is worth several
    # steps; the assertion is only that it kept going.
    increment = duration._increment
    QTest.mousePress(increment, QtCore.Qt.MouseButton.LeftButton)
    wait(900)
    QTest.mouseRelease(increment, QtCore.Qt.MouseButton.LeftButton)
    wait(150)
    seen["afterHold"] = duration.value
    if not duration.value >= 495 + 15 * 4:
        failures.append(f"a held stepper reached {duration.value}, wanted at least 555")

    # The hint names the minutes that will be written (field_types/duration).
    seen["hint"] = duration._hint_line.text
    if not seen["hint"].endswith("minutes"):
        failures.append(f"the hint reads {seen['hint']!r}")

    # A typed unit parses: `1h 30m` is ninety minutes.
    type_text(duration.input, "1h 30m")
    press_enter(duration.input)
    wait(60)
    seen["typed"] = duration.value
    if duration.value != 90:
        failures.append(f"'1h 30m' emitted {duration.value}, wanted 90")

    # Escape restores the stored value.
    type_text(duration.input, "not a number")
    press_enter(duration.input)
    wait(60)
    seen["refused"] = duration.message
    if not duration.message:
        failures.append("a bad value showed no error line")
    if duration.value != 90:
        failures.append(f"a bad value reached the store ({duration.value})")
    escape(duration.input)
    wait(60)
    seen["restored"] = duration.input.text()
    if duration.message is not None:
        failures.append("Escape left the error line standing")

    # The percent field stops at its bound: its increment goes inert once the value is 100.
    key(percent.input, QtCore.Qt.Key.Key_PageUp)
    wait(60)
    seen["percent"] = percent.value
    seen["stuck"] = not percent._increment.isEnabled()
    if percent.value != 100:
        failures.append(f"Page Up on percent gave {percent.value}, wanted 100")
    if percent._increment.isEnabled():
        failures.append("the percent increment is still live at 100")

    # Readonly drops the steppers and keeps the value at full contrast; disabled is inert.
    percent.set_readonly(True)
    wait(40)
    seen["readonlySteppers"] = percent._increment.isVisible()
    if percent._increment.isVisible():
        failures.append("readonly kept the steppers")
    if percent.input.isReadOnly() is not True:
        failures.append("readonly left the input writable")
    percent.set_readonly(False)
    percent.set_disabled(True)
    wait(40)
    before = percent.value
    key(percent.input, QtCore.Qt.Key.Key_Down)
    if percent.value != before:
        failures.append("a disabled editor still stepped")
    percent.set_disabled(False)

    # The size ladder, measured on the real control.
    ladder = {}
    for step, height in CONTROL_HEIGHT.items():
        duration.set_size(step)
        wait(20)
        ladder[step] = duration._group.sizeHint().height()
        if ladder[step] != height:
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    duration.set_size("md")
    seen["ladder"] = ladder

    return {
        "verdict": (
            "PASS Up steps a duration 480 to 495, Shift ten and Page a hundred, a held stepper "
            "repeats, percent stops at 100, and the ladder is 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
