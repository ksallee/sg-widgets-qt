"""The colour editor, driven on the color-editor page.

The stored form is decimal `r,g,b`: hex is converted before it is emitted, a channel over 255 is
refused, and the token `pipeline_step` is the only way to un-set the field (field_types/color).
The swatch opens the picker this package paints, on a press and on Enter or Space, and the picker
closes on Escape and on a press outside it.

    .venv/bin/python tools/qa.py --page color-editor --drive tools/drives/color-editor.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import click, escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore, QtWidgets  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT
    from sg_widgets_qt.widgets.color_editor import SENTINEL_NOTE, SWATCH_SIZE

    failures: list[str] = []
    seen: dict = {}

    editors = find("color-editor", all=True)
    if len(editors) < 4:
        return {"verdict": f"FAIL the page holds {len(editors)} colour editors, wanted 4"}
    triple, hexed, sentinel, disabled = editors[:4]

    committed: list = []
    triple.committed.connect(committed.append)

    # Typing and Enter commit the stored form, and a hex code is converted on the way.
    for typed, wanted in (("255, 128, 0", "255,128,0"), ("#ff8000", "255,128,0"), ("#f80", "255,136,0")):
        type_text(triple.input, typed)
        press_enter(triple.input)
        wait(40)
        if committed[-1:] != [wanted]:
            failures.append(f"{typed!r} committed {committed[-1:]}, wanted [{wanted!r}]")
    seen["committed"] = committed[-1:]

    # The swatch follows the draft, so a typed hex shows its colour before it is committed.
    type_text(triple.input, "#00ff00")
    wait(40)
    seen["preview"] = triple.swatch.color.name() if triple.swatch.color else None
    if seen["preview"] != "#00ff00":
        failures.append(f"the swatch reads {seen['preview']}, wanted #00ff00")

    # A channel over 255 is refused: the error line stands and nothing is committed.
    type_text(triple.input, "300,0,0")
    before = len(committed)
    press_enter(triple.input)
    wait(60)
    seen["refused"] = triple.message
    if not triple.message:
        failures.append("a channel over 255 showed no error line")
    if triple.reads_invalid is not True:
        failures.append("a refused triple left the control reading valid")
    if len(committed) != before:
        failures.append("a refused triple reached the value")

    # Escape restores the stored value and drops the message.
    escape(triple.input)
    wait(60)
    seen["restored"] = (triple.input.text(), triple.message)
    if triple.input.text() != triple.value or triple.message is not None:
        failures.append(f"Escape left {seen['restored']}")

    # A blur commits.
    type_text(triple.input, "10,20,30")
    triple.input.clearFocus()
    wait(60)
    seen["blurred"] = committed[-1:]
    if committed[-1:] != ["10,20,30"]:
        failures.append(f"leaving the control committed {committed[-1:]}")

    # The token is explained under the control and has no colour of its own.
    seen["sentinel"] = (sentinel.sentinel, sentinel._note.text, sentinel.preview)
    if sentinel.sentinel is not True or sentinel._note.text != SENTINEL_NOTE:
        failures.append(f"the token case reads {seen['sentinel'][:2]}")
    if sentinel.preview is not None:
        failures.append("the token drew a colour it has none of")

    # The picker opens on a press on the swatch and on Enter, and closes on Escape.
    click(triple.swatch)
    wait(200)
    seen["openOnPress"] = triple.is_open
    if triple.is_open is not True:
        failures.append("a press on the swatch did not open the picker")
    escape(triple.picker)
    wait(200)
    seen["closeOnEscape"] = triple.is_open
    if triple.is_open is not False:
        failures.append("Escape did not close the picker")

    key(triple.swatch, QtCore.Qt.Key.Key_Return)
    wait(200)
    if triple.is_open is not True:
        failures.append("Enter on the swatch did not open the picker")

    # An outside press closes it.
    QTest.mouseClick(
        page, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(4, 4),
    )
    wait(250)
    seen["closeOnOutside"] = triple.is_open
    if triple.is_open is not False:
        failures.append("an outside press did not close the picker")

    # A walk of the picker commits a triple.
    triple.set_open(True)
    wait(150)
    before = len(committed)
    # Shift takes ten steps at once, which is a move the triple is sure to show.
    key(triple.picker, QtCore.Qt.Key.Key_Up, QtCore.Qt.KeyboardModifier.ShiftModifier)
    wait(60)
    seen["picked"] = committed[-1:]
    if len(committed) == before or len(str(committed[-1]).split(",")) != 3:
        failures.append(f"walking the picker committed {committed[-1:]}")
    triple.set_open(False)
    wait(150)

    # Readonly never opens the picker and keeps full contrast; disabled is inert.
    hexed.set_readonly(True)
    wait(40)
    hexed.set_open(True)
    wait(120)
    seen["readonly"] = (hexed.is_open, hexed.isEnabled(), hexed.input.isReadOnly())
    if hexed.is_open is not False:
        failures.append("readonly opened the picker")
    if hexed.isEnabled() is not True or hexed.input.isReadOnly() is not True:
        failures.append(f"readonly reads {seen['readonly']}")
    if hexed.swatch.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus:
        failures.append("readonly left the swatch in the tab order")
    hexed.set_readonly(False)

    disabled.set_open(True)
    wait(120)
    seen["disabled"] = (disabled.is_open, disabled.isEnabled())
    if disabled.is_open is not False or disabled.isEnabled() is not False:
        failures.append(f"disabled reads {seen['disabled']}")

    # The ladder: the input on the control ladder, the swatch one step over it.
    ladder = {}
    for step, height in CONTROL_HEIGHT.items():
        triple.set_size(step)
        wait(20)
        ladder[step] = (triple.input.sizeHint().height(), triple.swatch.sizeHint().height())
        if ladder[step] != (height, SWATCH_SIZE[step]):
            failures.append(f"{step} stands {ladder[step]}, wanted {(height, SWATCH_SIZE[step])}")
    triple.set_size("md")
    seen["ladder"] = ladder

    assert QtWidgets.QApplication.instance() is not None
    return {
        "verdict": (
            "PASS hex converts to the triple, a bad channel is refused, Escape restores, a blur "
            "commits, the picker opens on a press and on Enter and closes on Escape and outside"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
