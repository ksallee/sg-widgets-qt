"""The date-time editor, driven on the date-time-editor page.

The port of `~/dev/sg-widgets/tools/drives/date-time-editor-popover.js`: the row holds a trigger
and nothing else, the popover it opens holds the typed day, the month grid and the time, the typed
day lands in the grid as it is typed, and Enter commits both halves to the trigger. The store is
UTC, so the wall-clock time typed here is converted before it is emitted (field_types/date_time).

    .venv/bin/python tools/qa.py --page date-time-editor --drive tools/drives/date-time-editor.py
"""
from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import click, escape, key, press_enter, type_text  # noqa: E402
from qtpy import QtCore  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

#: The demo reads its wall-clock time in America/Los_Angeles, so 07:08 on 6 May is 14:08 UTC
#: whatever zone the run itself is in.
TYPED_DATE = "2026-05-06"
TYPED_TIME = "07:08"
WANT_LABEL = "2026-05-06 07:08"
WANT_VALUE = "2026-05-06T14:08:00Z"


def drive(page, wait, find, prefs) -> dict:
    from sg_widgets_qt.primitives.base import CONTROL_HEIGHT

    failures: list[str] = []
    seen: dict = {}

    editors = find("date-time-editor", all=True)
    if len(editors) < 8:
        return {"verdict": f"FAIL the page holds {len(editors)} date-time editors, wanted 8"}
    sm, md, lg, paris, unset, invalid, readonly, disabled = editors[:8]

    committed: list = []
    md.committed.connect(committed.append)

    # The row holds a trigger and nothing else: both fields live in the popover's own window.
    seen["inRow"] = (md.date_input.window() is md.window(), md.time_input.window() is md.window())
    if seen["inRow"] != (False, False):
        failures.append(f"a field stands in the row beside the trigger {seen['inRow']}")

    # A press on the trigger opens the popover and the caret lands on the typed day.
    click(md.trigger)
    wait(300)
    seen["openOnPress"] = md.is_open
    seen["focused"] = md.date_input.hasFocus()
    if md.is_open is not True:
        failures.append("a press on the trigger did not open the popover")
    if not md.date_input.hasFocus():
        failures.append("the popover did not focus the typed day")

    # The three parts, top to bottom: the typed day, the month grid, the time.
    seen["parts"] = (
        md.date_input.isVisible(), md.calendar.isVisible(), md.time_input.isVisible()
    )
    if seen["parts"] != (True, True, True):
        failures.append(f"the popover holds {seen['parts']}")

    # The typed day lands in the calendar as it is typed: a date-time grid follows the draft.
    type_text(md.date_input, TYPED_DATE)
    wait(120)
    seen["inCalendar"] = str(md.calendar.value)
    if seen["inCalendar"] != str(datetime.date(2026, 5, 6)):
        failures.append(f"the typed day put {seen['inCalendar']} in the calendar")

    # Enter commits both halves, closes the popover, and the trigger reads the local instant.
    type_text(md.time_input, TYPED_TIME)
    press_enter(md.time_input)
    wait(300)
    seen["committed"] = committed[-1:]
    seen["label"] = md.trigger.text
    seen["stillOpen"] = md.is_open
    if committed[-1:] != [WANT_VALUE]:
        failures.append(f"Enter emitted {committed[-1:]}, wanted [{WANT_VALUE!r}]")
    if md.trigger.text != WANT_LABEL:
        failures.append(f"the trigger reads {md.trigger.text!r}, wanted {WANT_LABEL!r}")
    if md.is_open is not False:
        failures.append("Enter left the popover open")

    # A time the clock has no hour for is refused, with a line and no commit.
    md.set_open(True)
    wait(250)
    type_text(md.time_input, "25:61")
    before = len(committed)
    press_enter(md.time_input)
    wait(120)
    seen["refused"] = md.message
    if not md.message:
        failures.append("25:61 showed no error line")
    if len(committed) != before:
        failures.append("25:61 reached the value")
    if md.reads_invalid is not True:
        failures.append("a refused time left the control reading valid")

    # Escape restores the stored instant, drops the message and closes the popover.
    escape(md.time_input)
    wait(300)
    seen["escaped"] = (md.time_input.text(), md.message, md.is_open)
    if md.time_input.text() != TYPED_TIME or md.message is not None or md.is_open:
        failures.append(f"Escape left {seen['escaped']}")

    # Space on the trigger opens it too, and an outside press closes it.
    key(md.trigger, QtCore.Qt.Key.Key_Space)
    wait(300)
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

    # A picked day leaves the popover open, so the time can follow it.
    md.set_open(True)
    wait(250)
    md.calendar.grid().picked.emit(datetime.date(2026, 7, 14))
    wait(200)
    seen["picked"] = (md.value, md.is_open)
    if md.is_open is not True:
        failures.append("a picked day closed the popover")
    if not str(md.value).startswith("2026-07-14"):
        failures.append(f"a picked day stored {md.value!r}")
    md.set_open(False)
    wait(200)

    # The zone the typed time is read in is named under the trigger, and the store is UTC.
    seen["zone"] = (md.zone_name, md._zone_line.text)
    if "Los_Angeles" not in md.zone_name or "stored as UTC" not in md._zone_line.text:
        failures.append(f"the zone line reads {seen['zone']}")
    seen["paris"] = (paris.zone_name, paris.show_seconds, paris.trigger.text)
    if paris.show_seconds is not True or len(paris.trigger.text.split(":")) != 3:
        failures.append(f"the seconds case reads {seen['paris']}")

    # The unset case shows the placeholder and stores null.
    seen["unset"] = (unset.value, unset.trigger.text)
    if unset.value is not None or unset.trigger.text != "":
        failures.append(f"the unset case reads {seen['unset']}")

    # The marked states.
    seen["invalid"] = (invalid.message, invalid.reads_invalid)
    if not invalid.message or invalid.reads_invalid is not True:
        failures.append(f"the invalid case reads {seen['invalid']}")
    readonly.set_open(True)
    wait(150)
    seen["readonly"] = (readonly.is_open, readonly.isEnabled(), readonly.trigger.readonly)
    if readonly.is_open or readonly.isEnabled() is not True or not readonly.trigger.readonly:
        failures.append(f"readonly reads {seen['readonly']}")
    disabled.set_open(True)
    wait(150)
    seen["disabled"] = (disabled.is_open, disabled.isEnabled())
    if disabled.is_open or disabled.isEnabled() is not False:
        failures.append(f"disabled reads {seen['disabled']}")

    # The size ladder, measured on the real triggers.
    ladder = {"sm": sm.trigger.sizeHint().height(), "md": md.trigger.sizeHint().height(),
              "lg": lg.trigger.sizeHint().height()}
    for step, height in CONTROL_HEIGHT.items():
        if ladder[step] != height:
            failures.append(f"{step} stands {ladder[step]} high, wanted {height}")
    seen["ladder"] = ladder

    return {
        "verdict": (
            f"PASS the trigger reads {WANT_LABEL} and emits {WANT_VALUE}, the typed day lands in "
            "the grid, a picked day keeps the popover open, ladder 28/32/36"
            if not failures
            else "FAIL " + "; ".join(failures)
        ),
        "seen": seen,
    }
