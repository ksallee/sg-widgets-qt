"""What the wave's drives share: typing, keys, and finding a widget on a page.

A drive file is exec'd by `tools/qa.py`, so it puts this directory on `sys.path` itself before
importing this module:

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import ...
"""
from __future__ import annotations

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

__all__ = [
    "click",
    "escape",
    "key",
    "press_enter",
    "shot_ready",
    "top_levels",
    "type_text",
]


def type_text(widget, text: str) -> None:
    """Put the caret in a field and type `text` into it, key by key."""
    widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    clear = getattr(widget, "clear", None)
    if callable(clear):
        clear()
    QTest.keyClicks(widget, text)


def key(widget, name, modifier=QtCore.Qt.KeyboardModifier.NoModifier) -> None:
    """One key press on a widget."""
    QTest.keyClick(widget, name, modifier)


def press_enter(widget) -> None:
    key(widget, QtCore.Qt.Key.Key_Return)


def escape(widget) -> None:
    key(widget, QtCore.Qt.Key.Key_Escape)


def click(widget, button=QtCore.Qt.MouseButton.LeftButton) -> None:
    """A press and a release in the middle of a widget."""
    QTest.mouseClick(widget, button, QtCore.Qt.KeyboardModifier.NoModifier, widget.rect().center())


def top_levels():
    """Every top-level window on show, which is where a popover's panel lives."""
    return [w for w in QtWidgets.QApplication.topLevelWidgets() if w.isVisible()]


def shot_ready(wait) -> None:
    """Let motion land before a screenshot."""
    wait(300)
