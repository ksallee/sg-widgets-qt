"""What the walk drives share: a settled collection, a real press, and the check list.

A walk drive is a functional pass over one showcase page, done the way a reader does it:
every toolbar control, every footer control, the keyboard, and the view controls in the
header, each one checked against what the demo says it did. It is exec'd by `tools/qa.py`,
so it puts this directory on `sys.path` itself before importing this module:

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _walk import Walk, settled, stage

    .venv/bin/python tools/qa.py --page entity-table --drive tools/drives/walk/entity-table.py
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

__all__ = ["Walk", "press", "settled", "stage", "wait_until", "wheel"]


def stage(page: Any, name: str) -> Any:
    """The widget one demo stage built, by its item name."""
    found = page.stage(name)
    return None if found is None else found.widget


def wait_until(read: Callable[[], Any], wait: Callable[[int], None], ms: int = 15000) -> bool:
    """Spin the loop until `read` answers something truthy, or the time runs out."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        if read():
            return True
        wait(50)
    return bool(read())


def settled(control: Any, wait: Callable[[int], None], ms: int = 15000) -> bool:
    """Wait for the read and for the call behind it: a queued sort has not landed at `ready`."""
    return wait_until(
        lambda: control.snapshot().status in ("ready", "error") and not control.binding.busy,
        wait,
        ms,
    )


def press(widget: Any) -> None:
    """A press and a release in the middle of a control, which is what a reader does."""
    from qtpy.QtTest import QTest

    QTest.mouseClick(
        widget,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        widget.rect().center(),
    )


def wheel(view: QtWidgets.QAbstractScrollArea, steps: int = -120) -> bool:
    """One wheel notch over a view's body. True when the view kept it off the page."""
    point = view.viewport().rect().center()
    event = QtGui.QWheelEvent(
        QtCore.QPointF(point),
        QtCore.QPointF(view.viewport().mapToGlobal(point)),
        QtCore.QPoint(0, steps),
        QtCore.QPoint(0, steps),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QtWidgets.QApplication.sendEvent(view.viewport(), event)
    return event.isAccepted()


class Walk:
    """The checks one page's walk made, and the verdict they add up to."""

    def __init__(self, page: str) -> None:
        self._page = page
        self.notes: list[str] = []
        self.faults: list[str] = []

    def check(self, name: str, ok: bool, saw: Any = "") -> bool:
        """Record one action and what it did. False when it did the wrong thing."""
        line = f"{name}: {saw}" if saw != "" else name
        if ok:
            self.notes.append(line)
        else:
            self.faults.append(line)
        return bool(ok)

    def verdict(self, what: str) -> dict:
        if self.faults:
            return {
                "verdict": f"FAIL {self._page}: {len(self.faults)} of "
                f"{len(self.faults) + len(self.notes)} actions did the wrong thing",
                "faults": self.faults,
                "notes": self.notes,
            }
        return {
            "verdict": f"PASS {self._page}: {len(self.notes)} actions, {what}",
            "notes": self.notes,
        }
