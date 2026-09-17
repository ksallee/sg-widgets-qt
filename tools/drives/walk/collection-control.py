"""The collection-control page, walked the way a reader walks it.

The paging toggles, the page size and the pager arrows, the select-all box and the row boxes
against the count line, the keyboard cursor, the scroller at the end of the set, and the wheel
at the bottom edge.

    .venv/bin/python tools/qa.py --headed --page collection-control --drive tools/drives/walk/collection-control.py

A popup dismissing, the focus and the wheel's owner are what a real window decides, so
this drive is run headed; offscreen is for the unit tests.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _walk import Walk, press, settled, stage, wait_until, wheel  # noqa: E402
from qtpy import QtCore, QtGui  # noqa: E402

Qt = QtCore.Qt

#: What the mock answers for this page, and the sizes the footer offers.
TOTAL = 33
PAGE_SIZE = 8


def _popups() -> list:
    """Every window standing over the showcase, which is where an orphan shows up."""
    from qtpy import QtWidgets

    return [
        one.objectName() or type(one).__name__
        for one in QtWidgets.QApplication.topLevelWidgets()
        if one.isVisible() and one.objectName() != "showcase"
    ]


def _focused(fallback):
    """Where a keystroke lands: the widget holding the caret, or the control that opened."""
    from qtpy import QtWidgets

    return QtWidgets.QApplication.focusWidget() or fallback


def key(demo, code) -> None:
    demo.view.keyPressEvent(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), Qt.KeyboardModifier.NoModifier)
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    walk = Walk("collection-control")
    demo = stage(page, "collection-control")
    if demo is None:
        return {"verdict": "FAIL the page built no collection-control demo"}
    control = demo.control
    if not wait_until(lambda: demo.demo_ready and control.rows, wait, 30000):
        return {"verdict": "FAIL the queue drew no row"}
    settled(control, wait)

    # --- the footer in `pages` ------------------------------------------------------------
    walk.check(
        "opens on the first page",
        control.pager.range_label == f"1 to {PAGE_SIZE} of {TOTAL}",
        control.pager.range_label,
    )
    select = demo.footer._size_select
    select.open()
    wait(250)
    from qtpy.QtTest import QTest

    QTest.keyClick(select, Qt.Key.Key_Down)
    QTest.keyClick(select, Qt.Key.Key_Return)
    settled(control, wait)
    wait(200)
    walk.check(
        "the page size select reopens the set",
        control.pager.page_size == 16 and control.pager.range_label == f"1 to 16 of {TOTAL}",
        control.pager.range_label,
    )
    # A press is what a reader makes, and it is what puts the caret on the trigger: a list
    # opened by a call alone leaves the caret where it was and Escape never reaches it.
    press(select)
    wait(350)
    walk.check("the page size select opens a list of its own", bool(_popups()), _popups())
    QTest.keyClick(_focused(select), Qt.Key.Key_Escape)
    wait(400)
    walk.check("and Escape shuts it, leaving nothing standing", not _popups(), _popups())

    press(demo.footer._next)
    settled(control, wait)
    wait(200)
    walk.check(
        "the next arrow pages forward",
        control.pager.range_label == f"17 to 32 of {TOTAL}",
        control.pager.range_label,
    )
    press(demo.footer._previous)
    settled(control, wait)
    wait(200)
    walk.check(
        "the previous arrow pages back",
        control.pager.range_label == f"1 to 16 of {TOTAL}",
        control.pager.range_label,
    )

    # --- the boxes and the count line -----------------------------------------------------
    demo.toggle_at(0)
    wait(150)
    walk.check(
        "a row box takes the row and the count says so",
        len(control.selection) == 1 and demo._count.text() == "1 selected",
        demo._count.text(),
    )
    walk.check(
        "the head's box goes partial over one taken row",
        demo._head.box.check_state == 1,
        demo._head.box.check_state,
    )
    # A read that publishes must not be read as a press on the head's box.
    control.count()
    settled(control, wait)
    wait(300)
    walk.check(
        "a read landing keeps the selection",
        len(control.selection) == 1 and demo._count.text() == "1 selected",
        demo._count.text(),
    )
    demo._head.box.toggle()
    wait(200)
    walk.check(
        "the head's box takes every loaded row",
        len(control.selection) == len(control.rows) and demo._head.box.check_state == 2,
        demo._count.text(),
    )
    demo._head.box.toggle()
    wait(200)
    walk.check(
        "pressing it again drops them all, with no partial in between",
        not control.selection and demo._head.box.check_state == 0,
        f"{demo._count.text()}, box {demo._head.box.check_state}",
    )

    # --- the keyboard ----------------------------------------------------------------------
    demo.view.setFocus(Qt.FocusReason.TabFocusReason)
    demo.view.setCurrentIndex(control.model.index(0, 0))
    key(demo, Qt.Key.Key_Down)
    key(demo, Qt.Key.Key_Down)
    key(demo, Qt.Key.Key_Up)
    wait(150)
    walk.check(
        "the arrows walk the cursor",
        demo.view.currentIndex().row() == 1,
        demo.view.currentIndex().row(),
    )
    key(demo, Qt.Key.Key_Space)
    wait(200)
    walk.check(
        "Space takes the row under the cursor",
        len(control.selection) == 1 and demo._count.text() == "1 selected",
        demo._count.text(),
    )
    key(demo, Qt.Key.Key_Space)
    wait(200)
    walk.check("Space again drops it", not control.selection, demo._count.text())

    # --- the three paging modes -------------------------------------------------------------
    press(find("paging-more"))
    settled(control, wait)
    wait(300)
    walk.check(
        "load more draws its own row and no pager",
        control.bottom() == "more" and not demo.footer._pager_box.isVisible(),
        f"{control.bottom()}, {control.pager.loaded_label}",
    )
    held = len(control.rows)
    demo._bottom.more_requested.emit()
    settled(control, wait)
    wait(300)
    walk.check(
        "the load-more row appends a page",
        len(control.rows) > held,
        f"{held} -> {len(control.rows)}",
    )

    press(find("paging-scroll"))
    settled(control, wait)
    wait(300)
    walk.check("scroll draws the sentinel", control.bottom() == "sentinel", control.bottom())
    bar = demo.view.verticalScrollBar()
    held = len(control.rows)
    for _ in range(8):
        bar.setValue(bar.maximum())
        wait(100)
        demo._on_scrolled(bar.value())
        settled(control, wait)
        wait(150)
        if not control.snapshot().has_more:
            break
    walk.check(
        "scrolling to the end walks the whole set",
        len(control.rows) == TOTAL and not control.snapshot().has_more,
        control.pager.loaded_label,
    )

    # --- the wheel stays on the queue --------------------------------------------------------
    press(find("paging-more"))
    settled(control, wait)
    wait(300)
    bar.setValue(bar.maximum())
    wait(100)
    kept = [wheel(demo.view) for _ in range(3)]
    walk.check(
        "a gesture that reached the bottom stays on the queue",
        all(kept[1:]),
        kept,
    )

    # --- the view controls, with the set walked ----------------------------------------------
    press(find("paging-pages"))
    settled(control, wait)
    for name, value in (
        ("theme", "dark"),
        ("size", "lg"),
        ("density", "compact"),
        ("palette", prefs.values().get("palette", "")),
        ("motion", "reduced"),
    ):
        if not value:
            continue
        prefs.set(name, value)
        wait(120)
    wait(200)
    walk.check(
        "the header's view controls leave the page standing",
        control.snapshot().status in ("ready", "error") and bool(control.rows),
        f"{len(control.rows)} rows, {control.pager.range_label}",
    )
    return walk.verdict("paging, the pager, the boxes, the keyboard, the scroller and the wheel")
