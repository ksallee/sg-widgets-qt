"""What the picker wave's walk drives share: doing what a caption invites, and saying so.

A walk drive is not a shot state. It uses the page the way a person does — click the control,
type, pick with the mouse and with Enter, remove a chip, clear, close with Escape and with a
press outside — and checks the visible result and the emitted value after every action. It
answers `PASS n checks` or `FAIL ...`, so the walk is re-runnable:

    .venv/bin/python tools/qa.py --page picker-control --drive tools/drives/walk/picker-control.py

`_walk.py` beside this file carries the same idea for the editor pages; the two are kept apart so
the two halves of the walkthrough cannot break each other's drives.

A drive file is exec'd by `tools/qa.py`, so it puts this directory on `sys.path` itself:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _walk_pickers import Walk
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Callable

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _ink import check_ink  # noqa: E402

__all__ = [
    "Walk",
    "arm",
    "case_widget",
    "check_ink",
    "click",
    "click_at",
    "click_chip_cross",
    "click_row",
    "demo_widget",
    "key",
    "orphans",
    "outside_click",
    "readouts",
    "scroll_to",
    "type_into",
    "open_and_type",
    "settled",
    "wait_for",
    "walk_multi",
    "wheel",
    "walk_single",
    "wear",
]


# --- the report -------------------------------------------------------------------------


class Walk:
    """The checks one page's walk made, and the verdict they add up to."""

    def __init__(self, page: Any, wait: Callable, find: Callable, prefs: Any) -> None:
        self.page = page
        self.wait = wait
        self.find = find
        self.prefs = prefs
        self.checks: list[dict] = []
        self.notes: dict[str, Any] = {}

    def check(self, what: str, ok: Any, expected: Any = None, actual: Any = None) -> bool:
        """One thing a caption promised, and whether the page did it."""
        row: dict = {"what": what, "ok": bool(ok)}
        if not ok:
            row["expected"] = expected
            row["actual"] = actual
        self.checks.append(row)
        return bool(ok)

    def same(self, what: str, expected: Any, actual: Any) -> bool:
        """The action answered with `expected`, or the failure says what it answered instead."""
        return self.check(what, expected == actual, expected, actual)

    @property
    def failures(self) -> list[dict]:
        return [row for row in self.checks if not row["ok"]]

    def result(self, **extra: Any) -> dict:
        """What `qa.py` prints, with the verdict `--drive` takes its exit code from."""
        bad = self.failures
        verdict = (
            f"FAIL {len(bad)} of {len(self.checks)}: " + "; ".join(row["what"] for row in bad[:6])
            if bad
            else f"PASS {len(self.checks)} checks"
        )
        out: dict = {"verdict": verdict, "checks": len(self.checks), "failed": bad}
        if self.notes:
            out["notes"] = self.notes
        out.update(extra)
        return out


# --- finding what to drive --------------------------------------------------------------


def case_widget(page: Any, wanted: str) -> QtWidgets.QWidget | None:
    """The holder a demo marked `data_demo_case`."""
    for widget in page.findChildren(QtWidgets.QWidget):
        if widget.property("data_demo_case") == wanted:
            return widget
    return None


def demo_widget(page: Any, wanted: str) -> QtWidgets.QWidget | None:
    """The holder a demo marked `data_demo`."""
    for widget in page.findChildren(QtWidgets.QWidget):
        if widget.property("data_demo") == wanted:
            return widget
    return None


def readouts(root: Any) -> list:
    """The lines a demo writes its current value into, in layout order."""
    return [
        widget
        for widget in root.findChildren(QtWidgets.QWidget)
        if widget.property("data_demo_readout")
    ]


def orphans() -> list[str]:
    """Every window standing over the showcase: what a popup left behind shows up in."""
    return [
        one.objectName() or type(one).__name__
        for one in QtWidgets.QApplication.topLevelWidgets()
        if one.isVisible() and one.objectName() != "showcase" and not one.isHidden()
    ]


def arm(page: Any, wait: Callable) -> Any:
    """Make the showcase window the active one, so shortcuts and focus land where they are sent.

    A `QShortcut` is delivered through the application's shortcut map, which only fires for the
    active window; offscreen, no window is active until it is asked for, and a hotkey would
    read as dead.
    """
    top = page.window()
    top.raise_()
    top.activateWindow()
    QtWidgets.QApplication.setActiveWindow(top)
    wait(150)
    return top


def scroll_to(page: Any, widget: QtWidgets.QWidget, wait: Callable, room: int = 120) -> None:
    """Put a widget `room` under the top of the pane, so a popover opens below it.

    The offscreen platform answers an 800x800 screen whatever the window is, so a control low in
    the page flips its popover above itself and a walk would read that as a placement defect.
    """
    inner = page.scroll.widget()
    top = widget.mapTo(inner, widget.rect().topLeft()).y()
    page.scroll.verticalScrollBar().setValue(max(0, top - room))
    wait(250)


def wait_for(read: Callable[[], bool], wait: Callable, ms: int = 8000) -> bool:
    """Spin the loop until `read()` answers True, or the time runs out."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return bool(read())


# --- the pointer and the keyboard -------------------------------------------------------


def click(widget: QtWidgets.QWidget, button: Any = QtCore.Qt.MouseButton.LeftButton) -> None:
    """A press and a release in the middle of a widget."""
    QTest.mouseClick(widget, button, QtCore.Qt.KeyboardModifier.NoModifier, widget.rect().center())


def click_at(widget: QtWidgets.QWidget, point: QtCore.QPoint) -> None:
    """A press and a release at a point inside a widget."""
    QTest.mouseClick(
        widget, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, point
    )


def key(
    widget: QtWidgets.QWidget,
    name: Any,
    modifier: Any = QtCore.Qt.KeyboardModifier.NoModifier,
) -> None:
    """One key press on a widget."""
    QTest.keyClick(widget, name, modifier)


def type_into(widget: QtWidgets.QWidget, text: str, wait: Callable | None = None) -> None:
    """Put the caret in a field and type `text`, key by key, over whatever it held.

    The keys go where a keyboard sends them: to the focus widget of the active window. A field
    in a popup that never takes the window's focus is not that widget, so the keys reach the
    anchor in the window and have to be handed on; typing into the field directly would have
    passed a picker whose anchor drops them.
    """
    widget.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
    select = getattr(widget, "selectAll", None)
    if callable(select):
        select()
        QTest.keyClick(widget, QtCore.Qt.Key.Key_Delete)
    target = widget
    window = QtWidgets.QApplication.activeWindow()
    if window is not None and widget.window() is not window and window.focusWidget() is not None:
        target = window.focusWidget()
    QTest.keyClicks(target, text)
    if wait is not None:
        wait(50)


def wheel(widget: QtWidgets.QWidget, steps: int = -3, point: QtCore.QPoint | None = None) -> None:
    """A wheel gesture over a widget, the way a trackpad sends one.

    Negative steps scroll down. The event is built and sent rather than synthesised by the
    platform, so it lands on the widget under the pointer on both bindings.
    """
    from qtpy import QtGui

    where = point if point is not None else widget.rect().center()
    delta = QtCore.QPoint(0, steps * 40)
    globally = widget.mapToGlobal(where)
    event = QtGui.QWheelEvent(
        QtCore.QPointF(where),
        QtCore.QPointF(globally),
        QtCore.QPoint(0, 0),
        delta,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QtWidgets.QApplication.sendEvent(widget, event)


def click_row(surface: Any, row: int) -> bool:
    """Click a row of a list surface where it is drawn. False when the row is not on show."""
    index = surface.model().index(row, 0)
    if not index.isValid():
        return False
    surface.scrollTo(index, QtWidgets.QAbstractItemView.ScrollHint.EnsureVisible)
    box = surface.visualRect(index)
    if box.isEmpty():
        return False
    click_at(surface.viewport(), box.center())
    return True


def click_chip_cross(chip: QtWidgets.QWidget) -> bool:
    """Click the cross that takes a chip away, wherever the chip keeps it.

    A `Badge` paints its own cross and answers for the hit box around it; a chip built out of
    parts holds a `RemoveControl` instead. Both are one gesture to a person.
    """
    from sg_widgets_qt.primitives.remove_control import RemoveControl

    hit = getattr(chip, "_cross_hit", None)
    if callable(hit) and getattr(chip, "removable", False):
        box = hit()
        if not box.isEmpty():
            click_at(chip, box.center())
            return True
    if isinstance(chip, RemoveControl):
        click(chip)
        return True
    found = chip.findChildren(RemoveControl)
    if found:
        click(found[0])
        return True
    return False


def outside_click(page: Any, wait: Callable) -> None:
    """A press on the page behind the popup, which is what dismisses it.

    A popover watches the application for a press outside its own surface, so the walk sends a
    real press at a point on the page rather than calling `close`.
    """
    inner = page.scroll.widget()
    point = QtCore.QPoint(max(8, inner.width() - 8), 8)
    QTest.mousePress(
        inner, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, point
    )
    QTest.mouseRelease(
        inner, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, point
    )
    wait(250)


# --- the header -------------------------------------------------------------------------


def wear(prefs: Any, wait: Callable, settle: int = 400, **view: Any) -> None:
    """Set the view the header sets, and let the demos rebuild behind it."""
    prefs.update(**view)
    wait(settle)


# --- the two shapes every search picker comes in ------------------------------------------


def settled(picker: Any, wait: Callable, ms: int = 8000) -> bool:
    """Spin until the read in flight has landed."""
    return wait_for(lambda: not picker.state.loading, wait, ms)


def open_and_type(picker: Any, wait: Callable, query: str = "") -> int:
    """Click the control open, type a query, and answer how many rows landed."""
    control = picker.control
    if not control.is_open:
        click(control)
        wait(150)
    if query:
        type_into(control.caret(), query, wait)
    settled(picker, wait)
    return len(picker.state.rows)


def walk_single(walk: Walk, page: Any, picker: Any, wait: Callable, query: str, name: str) -> None:
    """One search picker, used the way a reader uses one: open, type, pick, clear, dismiss."""
    control = picker.control
    scroll_to(page, picker, wait)
    click(control)
    wait(200)
    walk.check(f"{name}: a click opens the list", control.is_open, True, control.is_open)
    found = open_and_type(picker, wait, query)
    walk.check(f"{name}: the query answers rows", found > 0, "> 0", found)

    key(control.caret(), QtCore.Qt.Key.Key_Down)
    key(control.caret(), QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.check(f"{name}: Enter picks the armed row", picker.value is not None, "a value", picker.value)
    walk.check(
        f"{name}: the chip carries the row's name",
        bool(control.labels and control.labels[0]),
        "a name",
        list(control.labels),
    )
    walk.check(f"{name}: a pick closes the list", not control.is_open, False, True)

    if control.clearable:
        click(control.clear_control())
        wait(250)
        walk.same(f"{name}: the clear control empties the value", None, picker.value)

    # A pick with the mouse lands too.
    found = open_and_type(picker, wait, query)
    walk.check(f"{name}: the list opens again for the next pick", found > 0, "> 0", found)
    walk.check(f"{name}: a row is picked with the mouse", click_row(control.list_surface(), 0), True, False)
    wait(250)
    walk.check(f"{name}: the mouse pick lands", picker.value is not None, "a value", picker.value)

    click(control)
    wait(150)
    key(control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check(f"{name}: Escape closes the list", not control.is_open, False, True)
    click(control)
    wait(150)
    outside_click(page, wait)
    walk.check(f"{name}: a press outside closes the list", not control.is_open, False, True)
    walk.check(f"{name}: no popup is left standing", not orphans(), [], orphans())


def walk_multi(walk: Walk, page: Any, picker: Any, wait: Callable, query: str, name: str) -> None:
    """One multi picker: tick rows, take a chip off with the cross and with Backspace, clear."""
    control = picker.control
    scroll_to(page, picker, wait)
    held = len(picker.value)
    found = open_and_type(picker, wait, query)
    walk.check(f"{name}: the query answers rows", found > 0, "> 0", found)
    walk.check(f"{name}: a row is ticked with the mouse", click_row(control.list_surface(), 0), True, False)
    wait(250)
    walk.check(
        f"{name}: the tick adds a value",
        len(picker.value) == held + 1,
        held + 1,
        len(picker.value),
    )
    walk.check(f"{name}: a tick keeps the list open", control.is_open, True, control.is_open)

    # The same row again takes it off, which is what a checkbox promises.
    walk.check(f"{name}: the ticked row is clicked again", click_row(control.list_surface(), 0), True, False)
    wait(250)
    walk.same(f"{name}: the second click unticks it", held, len(picker.value))

    key(control.caret(), QtCore.Qt.Key.Key_Down)
    key(control.caret(), QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.same(f"{name}: Enter ticks the armed row", held + 1, len(picker.value))

    key(control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check(f"{name}: Escape closes the list", not control.is_open, False, True)

    if control.chips():
        before = list(picker.value)
        took = click_chip_cross(control.chips()[0])
        walk.check(f"{name}: the first chip carries a cross", took, True, took)
        wait(250)
        walk.same(f"{name}: the cross removes that chip", len(before) - 1, len(picker.value))

    if picker.value:
        before = list(picker.value)
        control.caret().setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
        key(control.caret(), QtCore.Qt.Key.Key_Backspace)
        wait(100)
        key(control.caret(), QtCore.Qt.Key.Key_Backspace)
        wait(250)
        walk.same(
            f"{name}: Backspace on an empty query takes the last chip",
            len(before) - 1,
            len(picker.value),
        )

    if control.clearable and picker.value:
        click(control.clear_control())
        wait(250)
        walk.same(f"{name}: the clear control empties the value", 0, len(picker.value))

    click(control)
    wait(150)
    outside_click(page, wait)
    walk.check(f"{name}: a press outside closes the list", not control.is_open, False, True)
    walk.check(f"{name}: no popup is left standing", not orphans(), [], orphans())
