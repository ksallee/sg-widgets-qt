"""What the editor, chip, badge, filter and sort walks share: a live window and real events.

A walk drive does on a page what its captions invite a person to do — type and commit, step a
number, pick a day, open a popover, tick a facet, drag a row — and answers `PASS` or `FAIL` for
the whole page. It is the net under a control that draws itself and does nothing.

    .venv/bin/python tools/qa.py --page text-editor --drive tools/drives/walk/text-editor.py

Every drive starts with `Walk(page, wait, find, prefs)`, which makes the showcase window the
active one. Focus events only reach an active window, and a commit on leaving a field is a focus
event, so without that a drive reads as if half of every page were dead.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import click, escape, key, press_enter, top_levels, type_text  # noqa: E402, F401
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

__all__ = [
    "Walk",
    "activate",
    "blur",
    "case_widget",
    "chrome_control",
    "click",
    "click_chip_cross",
    "click_row",
    "escape",
    "focus",
    "hover",
    "key",
    "outside_click",
    "pick_select",
    "popups",
    "press_enter",
    "retype",
    "scroll_to",
    "set_view",
    "top_levels",
    "type_into",
    "type_text",
    "unhover",
    "wait_for",
    "wear",
]

#: How long `wait_for` gives a read before it gives up.
SETTLE_MS = 8000

#: What the stage leaves for a rebuild after a pref that rebuilds the demo.
REBUILD_MS = 700

#: How a demo marks the example one caption stands over, in the three spellings in use.
CASE_KEYS = ("data_demo_case", "data_case", "data_name")


def activate(page: QtWidgets.QWidget, wait) -> QtWidgets.QWidget:
    """Make the showcase window the active one, so focus and keys land where they are sent."""
    top = page.window()
    top.raise_()
    top.activateWindow()
    QtWidgets.QApplication.setActiveWindow(top)
    wait(150)
    return top


def wait_for(held, wait, ms: int = SETTLE_MS) -> bool:
    """Spin until a condition holds, or until the time runs out. Answers whether it held."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        if held():
            return True
        wait(50)
    return bool(held())


def case_widget(page: QtWidgets.QWidget, case: str) -> QtWidgets.QWidget | None:
    """The example a demo marked with that case name.

    A demo names its examples one of three ways — the `data_demo_case` property the picker demos
    set, the `data_case` the editor tables set, or a `case-<name>` object name — and a drive
    should not have to know which.
    """
    for one in page.findChildren(QtWidgets.QWidget):
        if one.objectName() in (f"case-{case}", case):
            return one
        for held in CASE_KEYS:
            if one.property(held) == case:
                return one
    return None


def scroll_to(page: QtWidgets.QWidget, widget: QtWidgets.QWidget | None, wait) -> None:
    """Bring an example into view, as a reader scrolls to it before using it."""
    if widget is None:
        return
    area = None
    walker: QtWidgets.QWidget | None = widget
    while walker is not None:
        if isinstance(walker, QtWidgets.QScrollArea):
            area = walker
            break
        walker = walker.parentWidget()
    if area is None:
        return
    area.ensureWidgetVisible(widget, 0, 40)
    wait(120)


def type_into(field: QtWidgets.QWidget | None, text: str, wait, clear: bool = True) -> None:
    """Put the caret in a field and type, key by key, the way a query is typed."""
    if field is None:
        return
    focus(field)
    if clear:
        selector = getattr(field, "selectAll", None)
        if callable(selector):
            selector()
            QTest.keyClick(field, QtCore.Qt.Key.Key_Delete)
    if text:
        QTest.keyClicks(field, text)
    wait(120)


def focus(field: QtWidgets.QWidget) -> None:
    """Put the caret in a field, making its window the active one first.

    A focus event only reaches an active window, and on a real desktop the showcase is not always
    the window the platform has in front — another application, or the run before this one, may
    hold it. Without this a walk reads as if every commit on leaving a field were dead.
    """
    window = field.window()
    # A popover that says it takes no focus must not be asked to become the active window: Qt
    # answers that with a warning and nothing else, and the caret lands from the anchor anyway.
    takes_focus = not (
        window.windowFlags() & QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
    )
    if takes_focus and not window.isActiveWindow():
        window.raise_()
        window.activateWindow()
        QtWidgets.QApplication.setActiveWindow(window)
    field.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)


def retype(field: QtWidgets.QWidget, text: str) -> None:
    """Select what a field holds and type over it, with no wait after."""
    focus(field)
    selector = getattr(field, "selectAll", None)
    if callable(selector):
        selector()
        QTest.keyClick(field, QtCore.Qt.Key.Key_Delete)
    if text:
        QTest.keyClicks(field, text)


def blur(field: QtWidgets.QWidget) -> None:
    """Leave a field, which is the other commit.

    `clearFocus` on a window the platform never made active sends no focus event at all, so the
    event a blur is made of is delivered outright when that happens. What is under test is the
    control's answer to losing the caret, not which window the desktop has in front.
    """
    had = field.hasFocus()
    field.clearFocus()
    if not had:
        QtWidgets.QApplication.sendEvent(
            field, QtGui.QFocusEvent(QtCore.QEvent.Type.FocusOut, QtCore.Qt.FocusReason.OtherFocusReason)
        )


def click_row(surface: QtWidgets.QAbstractItemView | None, index: int) -> bool:
    """Press one row of a list with the mouse. False where there is no such row."""
    if surface is None:
        return False
    model = surface.model()
    if model is None or index < 0 or index >= model.rowCount():
        return False
    spot = model.index(index, 0)
    box = surface.visualRect(spot)
    if not box.isValid() or box.isEmpty():
        surface.scrollTo(spot)
        box = surface.visualRect(spot)
    QTest.mouseClick(
        surface.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        box.center(),
    )
    return True


def click_chip_cross(chip: QtWidgets.QWidget | None) -> bool:
    """Press the cross a removable chip or badge carries. False where it carries none."""
    if chip is None:
        return False
    box = None
    for name in ("_cross_hit", "cross_rect", "remove_rect", "_cross_rect"):
        reader = getattr(chip, name, None)
        if callable(reader):
            box = reader()
            break
    if box is None or not box.isValid() or box.isEmpty():
        return False
    QTest.mouseClick(
        chip,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        box.center(),
    )
    return True


def hover(widget: QtWidgets.QWidget | None, wait, ms: int = 600) -> None:
    """Rest the pointer on a widget, which is what opens a hover card.

    A hover card listens for `Enter` on its anchor, so the pointer is moved onto the widget and
    the event sent outright, because an offscreen platform moves no pointer of its own.
    """
    if widget is None:
        return
    middle = widget.rect().center()
    QTest.mouseMove(widget, middle)
    where = QtCore.QPointF(middle)
    somewhere = QtCore.QPointF(widget.mapToGlobal(middle))
    QtWidgets.QApplication.sendEvent(widget, QtGui.QEnterEvent(where, somewhere, somewhere))
    wait(ms)


def unhover(widget: QtWidgets.QWidget | None, wait, ms: int = 600) -> None:
    """Take the pointer off a widget again."""
    if widget is None:
        return
    QtWidgets.QApplication.sendEvent(widget, QtCore.QEvent(QtCore.QEvent.Type.Leave))
    wait(ms)


def outside_click(page: QtWidgets.QWidget, wait) -> None:
    """Press the page away from any control, which is what closes a popover."""
    heading = None
    for one in page.findChildren(QtWidgets.QWidget):
        if one.objectName() == "page-heading":
            heading = one
            break
    target = heading if heading is not None else page
    QTest.mouseClick(
        target,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.QPoint(4, 4),
    )
    wait(250)


def popups() -> list[str]:
    """Every window standing over the showcase: where an orphaned popover shows up."""
    return [
        one.objectName() or type(one).__name__
        for one in top_levels()
        if one.objectName() != "showcase"
    ]


def wear(prefs, wait, settle: int = 250, **changes: str) -> None:
    """Move the view without touching its controls, for what an open popup must survive."""
    prefs.update(**changes)
    wait(settle)


# --- the header ---------------------------------------------------------------------------


def chrome_control(page: QtWidgets.QWidget, name: str) -> QtWidgets.QWidget | None:
    """One of the view controls, wherever it stands.

    `size`, `density`, `radius` and `motion` are on the stage's own caption, inside the page;
    `palette`, `theme` and `source` are on the window's header, outside it. A walk should reach
    either by name.
    """
    window = page.window()
    found = [
        one
        for one in window.findChildren(QtWidgets.QWidget)
        if one.objectName() == name and one.isVisible()
    ]
    return found[0] if found else None


def pick_select(select: QtWidgets.QWidget | None, value: str, wait) -> bool:
    """Open a select and press the row holding that value, the way a reader picks one.

    The rows are a menu, not a list view, so the row is found by the value its entry carries and
    pressed where it is drawn; headings and separators sit between the rows and are skipped.
    """
    if select is None:
        return False
    select.open()
    wait(250)
    rows = select.list
    for index, entry in enumerate(rows.entries):
        if entry.selectable and entry.value == value:
            QTest.mouseClick(
                rows,
                QtCore.Qt.MouseButton.LeftButton,
                QtCore.Qt.KeyboardModifier.NoModifier,
                rows.row_rect(index).center(),
            )
            wait(250)
            return True
    select.close()
    return False


def set_view(page: QtWidgets.QWidget, wait, settle: int = REBUILD_MS, **changes: str) -> list[str]:
    """Move the view controls themselves, not the prefs behind them. Answers what would not move.

    `theme` and `motion` are a switch and a toggle, which are pressed; the rest are selects,
    which are opened and picked from.
    """
    missed: list[str] = []
    for key_name, value in changes.items():
        if key_name == "theme":
            control = chrome_control(page, "theme-switch")
            if control is None:
                missed.append("theme")
                continue
            if bool(control.track.checked) != (value == "dark"):
                click(control.track)
        elif key_name == "motion":
            control = chrome_control(page, "motion-toggle")
            if control is None:
                missed.append("motion")
                continue
            if bool(control.checked) != (value == "reduced"):
                click(control)
        else:
            control = chrome_control(page, key_name + "-select")
            if not pick_select(control, value, wait):
                missed.append(key_name)
        wait(200)
    wait(settle)
    return missed


class Walk:
    """What a walk found: a note per action, and a line per action that did not answer."""

    def __init__(self, page, wait, find, prefs) -> None:
        self.page = page
        self.wait = wait
        self.find = find
        self.prefs = prefs
        self.notes: list[str] = []
        self.failures: list[str] = []
        activate(page, wait)

    def check(self, said: str, held: object, wanted: object = True, got: object = None) -> bool:
        """One action and whether it answered. The failure names what was wanted and what came."""
        if held:
            self.notes.append(f"{said}: {got!r}" if got is not None else said)
            return True
        self.failures.append(f"{said} — wanted {wanted!r}, got {got!r}")
        return False

    def same(self, said: str, wanted: object, got: object) -> bool:
        """The action answered with `wanted`, or the failure says what it answered instead."""
        return self.check(said, got == wanted, wanted, got)

    def says(self, note: str) -> None:
        """One thing the walk read, which no assertion hangs on."""
        self.notes.append(note)

    def result(self, passed: str = "") -> dict:
        """The drive's answer, for `tools/qa.py` to print and take an exit code from."""
        if self.failures:
            verdict = "FAIL " + "; ".join(self.failures)
        else:
            verdict = passed or f"PASS {len(self.notes)} actions answered"
        return {"verdict": verdict, "failures": self.failures, "notes": self.notes}
