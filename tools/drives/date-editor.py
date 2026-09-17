"""The date editor, driven on the date-editor page.

The value is exactly `YYYY-MM-DD` and the API validates the day rather than only parsing it, so
`2026-02-30` is refused here too (field_types/date). The anatomy is one trigger over a popover
holding the typed day and the calendar; the keyboard table of `docs/widgets/date-editor.md` is
what the popover answers.

    .venv/bin/python tools/qa.py --page date-editor --drive tools/drives/date-editor.py
"""
from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import click, escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT

    failures: list[str] = []
    seen: dict = {}

    editors = find("date-editor", all=True)
    if len(editors) < 7:
        return {"verdict": f"FAIL the page holds {len(editors)} date editors, wanted 7"}
    sm, md, lg, unset, invalid, readonly, disabled = editors[:7]

    committed: list = []
    md.committed.connect(committed.append)

    # The row holds a trigger and nothing else: the typed day lives in the popover, which is a
    # window of its own rather than a widget in the row.
    seen["inRow"] = md.day_input.window() is md.window()
    if seen["inRow"] is not False:
        failures.append("the typed day stands in the row beside the trigger")

    # A press on the trigger opens the popover and the caret lands in the typed day.
    click(md.trigger)
    wait(250)
    seen["openOnPress"] = md.is_open
    if md.is_open is not True:
        failures.append("a press on the trigger did not open the popover")
    if not md.day_input.hasFocus():
        failures.append("the popover did not focus the typed day")

    # The popover holds the typed day and the month grid, in that order.
    seen["parts"] = (md.day_input.isVisible(), md.calendar.isVisible())
    if seen["parts"] != (True, True):
        failures.append(f"the popover holds {seen['parts']}")

    # Enter commits the typed day, closes the popover, and lands it in the calendar. The month
    # grid of a date editor follows the stored day, not the draft, as `date-editor.tsx` does.
    type_text(md.day_input, "2026-05-06")
    wait(80)
    press_enter(md.day_input)
    wait(250)
    seen["inCalendar"] = str(md.calendar.value)
    if seen["inCalendar"] != str(datetime.date(2026, 5, 6)):
        failures.append(f"the committed day put {seen['inCalendar']} in the calendar")
    seen["committed"] = committed[-1:]
    seen["closedOnEnter"] = md.is_open
    if committed[-1:] != ["2026-05-06"]:
        failures.append(f"Enter committed {committed[-1:]}, wanted ['2026-05-06']")
    if md.is_open is not False:
        failures.append("Enter left the popover open")
    if md.trigger.text != "2026-05-06":
        failures.append(f"the trigger reads {md.trigger.text!r}")

    # A day the calendar has no square for is refused: the API validates it, not only parses it.
    md.set_open(True)
    wait(200)
    type_text(md.day_input, "2026-02-30")
    before = len(committed)
    press_enter(md.day_input)
    wait(120)
    seen["refused"] = md.message
    if not md.message:
        failures.append("2026-02-30 showed no error line")
    if len(committed) != before:
        failures.append("2026-02-30 reached the value")
    if md.reads_invalid is not True:
        failures.append("a refused day left the control reading valid")

    # Escape restores the stored day, drops the message and closes the popover.
    escape(md.day_input)
    wait(250)
    seen["escaped"] = (md.day_input.text(), md.message, md.is_open)
    if md.day_input.text() != "2026-05-06" or md.message is not None or md.is_open:
        failures.append(f"Escape left {seen['escaped']}")

    # Space on the trigger opens it too, per the docs page's keyboard table, and an outside
    # press closes it.
    key(md.trigger, QtCore.Qt.Key.Key_Space)
    wait(250)
    if md.is_open is not True:
        failures.append("Space on the trigger did not open the popover")
    QTest.mouseClick(
        page, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(4, 4),
    )
    wait(300)
    seen["closeOnOutside"] = md.is_open
    if md.is_open is not False:
        failures.append("an outside press did not close the popover")

    # A picked day commits and closes.
    md.set_open(True)
    wait(200)
    before = len(committed)
    md.calendar.grid().picked.emit(datetime.date(2026, 7, 14))
    wait(250)
    seen["picked"] = (committed[-1:], md.is_open)
    if committed[-1:] != ["2026-07-14"] or md.is_open:
        failures.append(f"a picked day left {seen['picked']}")

    # The unset case shows the placeholder and stores null.
    seen["unset"] = (unset.value, unset.trigger.text)
    if unset.value is not None or unset.trigger.text != "":
        failures.append(f"the unset case reads {seen['unset']}")

    # The marked states: invalid wears the message, readonly never opens and keeps full
    # contrast, disabled is inert.
    seen["invalid"] = (invalid.message, invalid.reads_invalid)
    if not invalid.message or invalid.reads_invalid is not True:
        failures.append(f"the invalid case reads {seen['invalid']}")
    readonly.set_open(True)
    wait(150)
    seen["readonly"] = (readonly.is_open, readonly.isEnabled(), readonly.trigger.readonly)
    if readonly.is_open or readonly.isEnabled() is not True or not readonly.trigger.readonly:
        failures.append(f"readonly reads {seen['readonly']}")
    if readonly.trigger.focusPolicy() != QtCore.Qt.FocusPolicy.NoFocus:
        failures.append("readonly left the trigger in the tab order")
    disabled.set_open(True)
    wait(150)
    seen["disabled"] = (disabled.is_open, disabled.isEnabled())
    if disabled.is_open or disabled.isEnabled() is not False:
        failures.append(f"disabled reads {seen['disabled']}")

    # The size ladder, measured on the real triggers the three ladder cases wear.
    ladder = {"sm": sm.trigger.sizeHint().height(), "md": md.trigger.sizeHint().height(),
              "lg": lg.trigger.sizeHint().height()}
    for step, height in CONTROL_HEIGHT.items():
        if ladder[step] != height:
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    seen["ladder"] = ladder

    return {
        "verdict": (
            "PASS the popover opens on a press and on Space, focuses the typed day, lands it in "
            "the calendar, commits on Enter, refuses 2026-02-30, closes on Escape and outside, "
            "ladder 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
