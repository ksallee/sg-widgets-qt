"""What the collection wave's state drives share: the state name, waiting, and framing.

A state drive is exec'd by `tools/qa.py`, so it puts this directory on `sys.path` itself before
importing this module:

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _collection_states import frame, state_name, wait_for

The collection pages are tall: the prose, then one stage per demo, then the props tables. A shot
of one is worthless unless the stage under test stands at the top of the window, which is what
`frame` does, and unless its rows have landed, which is what `settled` waits for. The upstream
half frames the same way, with `section.scrollIntoView({block: 'start'})`.
"""
from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import Any, Callable

from qtpy import QtCore, QtWidgets

__all__ = [
    "click",
    "current_state",
    "frame",
    "images_settled",
    "press_key",
    "stage_widget",
    "state_name",
    "wait_for",
]


def state_name(states: Sequence[str], default: str = "") -> str:
    """The state `QA_STATE` asks for, or the first one the drive offers."""
    fallback = default or (states[0] if states else "")
    wanted = os.environ.get("QA_STATE", fallback).strip().lower()
    return wanted if wanted in states else fallback


def current_state(states: Sequence[str], default: str = "") -> str:
    """`state_name`, kept for a drive that reads it more than once."""
    return state_name(states, default)


def wait_for(read: Callable[[], Any], wait: Callable[[int], None], ms: int = 15000) -> bool:
    """Spin the loop until `read` answers something truthy, or the time runs out."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        if read():
            return True
        wait(50)
    return bool(read())


def images_settled(wait: Callable[[int], None], ms: int = 8000) -> bool:
    """True once no thumbnail is still in flight, so a shot holds the pictures."""
    from sg_widgets_qt.images import image_loader

    return wait_for(lambda: image_loader().pending == 0, wait, ms)


def stage_widget(page: Any, name: str = "") -> Any:
    """The widget one demo stage built, by its item name, or the page's first stage."""
    stage = page.stage(name) if name else (page.stages[0] if page.stages else None)
    return None if stage is None else stage.widget


def frame(page: Any, wait: Callable[[int], None], name: str = "", offset: int = 8) -> bool:
    """Put a stage at the top of the window, the way the upstream shot frames its demo."""
    stage = page.stage(name) if name else (page.stages[0] if page.stages else None)
    if stage is None:
        return False
    body = page.scroll.widget()
    bar = page.scroll.verticalScrollBar()
    top = stage.mapTo(body, QtCore.QPoint(0, 0)).y()
    bar.setValue(max(0, min(bar.maximum(), top - offset)))
    wait(200)
    return True


def click(widget: Any, point: QtCore.QPoint | None = None) -> None:
    """A press and a release on a widget, in its middle unless a point is given."""
    from qtpy.QtTest import QTest

    where = point if point is not None else widget.rect().center()
    QTest.mouseClick(
        widget, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, where
    )


def press_key(widget: Any, key: Any, modifier: Any = None) -> None:
    """One key press on a widget."""
    from qtpy.QtTest import QTest

    QTest.keyClick(
        widget, key, modifier if modifier is not None else QtCore.Qt.KeyboardModifier.NoModifier
    )


def popups() -> list:
    """Every top-level window on show, which is where a popover's panel lives."""
    return [
        window
        for window in QtWidgets.QApplication.topLevelWidgets()
        if window.isVisible() and window.width() > 0
    ]
