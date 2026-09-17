"""Walk one page for text that cannot be read, in whatever theme the driver was given.

    .venv/bin/python tools/qa.py --dark --page text-editor --drive tools/drives/ink-sweep.py

The page is read the way `_ink.py` describes: the whole column is scrolled past a screenful at a
time and sampled, then every popup, popover, dialog and editor it holds is opened one at a time
and sampled with it on show, with a query typed into anything that takes one. The verdict is the
faults, deduplicated, with the state each was seen in.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ink import faults  # noqa: E402
from qtpy import QtCore, QtWidgets  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

#: How long an opened popup is given to place itself, read its rows and stop moving.
SETTLE_MS = 600

#: How far the page is stepped when it is read from top to bottom.
STEP = 700


def _arm(page, wait) -> None:
    top = page.window()
    top.raise_()
    top.activateWindow()
    QtWidgets.QApplication.setActiveWindow(top)
    wait(200)


def _openables(page) -> list:
    """Every widget on the page that opens a surface of its own."""
    out = []
    for widget in page.findChildren(QtWidgets.QWidget):
        if not widget.isVisible():
            continue
        setter = getattr(type(widget), "set_open", None)
        if setter is None or not callable(setter):
            continue
        # A picker's own control carries the same setter as the picker around it; the outer one
        # is what a reader presses, so a control inside another openable is left to its owner.
        out.append(widget)
    keep = []
    for widget in out:
        if any(other is not widget and other.isAncestorOf(widget) for other in out):
            continue
        keep.append(widget)
    return keep


def _fields(page) -> list:
    """Every field on the page a reader types into."""
    kinds = (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)
    return [
        one
        for one in page.findChildren(QtWidgets.QWidget)
        if isinstance(one, kinds)
        and one.isVisible()
        and one.isEnabled()
        and not one.isReadOnly()
        and not isinstance(one, QtWidgets.QTextBrowser)
    ]


def _alive(widget) -> bool:
    """False once Qt has deleted the widget under the wrapper, which a rebuilt demo does."""
    try:
        widget.objectName()
    except RuntimeError:
        return False
    return True


def _scroll_to(page, widget, wait) -> None:
    inner = page.scroll.widget()
    try:
        top = widget.mapTo(inner, widget.rect().topLeft()).y()
    except RuntimeError:
        return
    page.scroll.verticalScrollBar().setValue(max(0, top - 120))
    wait(250)


def _query_field(widget):
    """The box a picker or a search widget types its query into, where it has one."""
    for reader in ("input", "search_input"):
        found = getattr(widget, reader, None)
        if callable(found):
            try:
                box = found()
            except (TypeError, RuntimeError):
                continue
            if isinstance(box, QtWidgets.QLineEdit):
                return box
    holder = getattr(widget, "popover", None)
    surface = holder() if callable(holder) else None
    if surface is not None:
        for box in surface.findChildren(QtWidgets.QLineEdit):
            if box.isVisible():
                return box
    return None


def drive(page, wait, find, prefs) -> dict:  # noqa: ARG001
    _arm(page, wait)
    seen: dict[str, str] = {}

    def take(state: str) -> None:
        for line in faults():
            seen.setdefault(line, state)

    # --- the page itself, a screenful at a time ---------------------------------------------
    bar = page.scroll.verticalScrollBar()
    offset = 0
    while True:
        bar.setValue(offset)
        wait(200)
        take(f"page at {offset}")
        if offset >= bar.maximum():
            break
        offset = min(bar.maximum(), offset + STEP)
    bar.setValue(0)
    wait(150)

    # --- every surface it opens ---------------------------------------------------------------
    opened = 0
    for widget in _openables(page):
        if not _alive(widget):
            continue
        name = widget.objectName() or type(widget).__name__
        try:
            _scroll_to(page, widget, wait)
            widget.set_open(True)
            wait(SETTLE_MS)
            if not getattr(widget, "open", False):
                continue
            opened += 1
            take(f"{name} open")
            box = _query_field(widget)
            if box is not None and not box.isReadOnly():
                box.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
                QTest.keyClicks(box, "sh")
                wait(SETTLE_MS)
                take(f"{name} open with a query")
            widget.set_open(False)
        except (RuntimeError, TypeError):
            continue
        wait(250)

    # --- every editor a press turns into a field -----------------------------------------------
    edited = 0
    editors = [
        one
        for one in page.findChildren(QtWidgets.QWidget)
        if one.isVisible()
        and callable(getattr(type(one), "set_mode", None))
        and getattr(one, "mode", None) == "display"
    ]
    for widget in editors:
        if not _alive(widget):
            continue
        name = widget.objectName() or type(widget).__name__
        try:
            _scroll_to(page, widget, wait)
            widget.set_mode("edit")
            wait(SETTLE_MS)
            edited += 1
            take(f"{name} editing")
            for box in widget.window().findChildren(QtWidgets.QLineEdit):
                if box.isVisible() and not box.isReadOnly():
                    box.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
                    QTest.keyClicks(box, "Zx")
            wait(200)
            take(f"{name} editing, typed into")
            widget.set_mode("display")
        except (RuntimeError, TypeError, ValueError):
            continue
        wait(200)

    # --- every field a reader types into --------------------------------------------------------
    typed = 0
    for box in _fields(page):
        if not _alive(box):
            continue
        name = box.objectName() or type(box).__name__
        try:
            _scroll_to(page, box, wait)
            box.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
            QTest.keyClicks(box, "Zx")
        except RuntimeError:
            continue
        typed += 1
        wait(200)
        take(f"{name} typed into")

    lines = [f"{line}   [{state}]" for line, state in seen.items()]
    if lines:
        return {
            "verdict": f"FAIL {len(lines)} runs of text cannot be read",
            "faults": sorted(lines),
            "opened": opened,
            "edited": edited,
            "typed": typed,
        }
    return {
        "verdict": "PASS every run of text reads",
        "opened": opened,
        "edited": edited,
        "typed": typed,
    }
