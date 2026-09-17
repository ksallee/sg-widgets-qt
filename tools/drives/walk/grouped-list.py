"""The grouped-list page, walked the way a reader walks it.

Compact, Collapse all and Expand all, one heading shut on its own, a row taken by a press and
by Space against the count line, the arrows, the pager, the derived list appending a page over
a group boundary, the empty list's own line, and the wheel at the bottom edge.

    .venv/bin/python tools/qa.py --headed --page grouped-list --drive tools/drives/walk/grouped-list.py

A popup dismissing, the focus and the wheel's owner are what a real window decides, so
this drive is run headed; offscreen is for the unit tests.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _walk import Walk, press, settled, stage, wait_until, wheel  # noqa: E402
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

Qt = QtCore.Qt

TOTAL = 40
PAGE_SIZE = 25


def key(listing, code) -> None:
    listing.view.keyPressEvent(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), Qt.KeyboardModifier.NoModifier)
    )


def line_press(listing, line: int) -> None:
    rect = listing.view.visualRect(listing.model.index(line, 0))
    QTest.mouseClick(
        listing.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        rect.center(),
    )


def first(listing, kind: str) -> int:
    return next(i for i, line in enumerate(listing.model.lines) if line.kind == kind)


def buttons(holder, label: str) -> list:
    return [
        one
        for one in holder.findChildren(QtWidgets.QWidget)
        if type(one).__name__ == "Button" and getattr(one, "text", "") == label
    ]


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    walk = Walk("grouped-list")
    demo = stage(page, "grouped-list")
    if demo is None:
        return {"verdict": "FAIL the page built no grouped-list demo"}
    listing = demo.listing
    control = listing.control
    if not wait_until(lambda: demo.demo_ready and control.rows, wait, 30000):
        return {"verdict": "FAIL the list drew no row"}
    settled(control, wait)
    wait(200)

    walk.check(
        "the Tasks group by pipeline step",
        bool(listing.model.groups) and control.pager.range_label == f"1 to {PAGE_SIZE} of {TOTAL}",
        f"{len(listing.model.groups)} headings, {control.pager.range_label}",
    )
    lines = listing.model.rowCount()

    # --- the toolbar -----------------------------------------------------------------------
    press(find("compact"))
    wait(250)
    walk.check("Compact halves the row padding", listing.density == "compact", listing.density)
    press(find("compact"))
    wait(250)
    walk.check("and stands back up", listing.density == "default", listing.density)

    collapse = buttons(demo, "Collapse all")[0]
    expand = buttons(demo, "Expand all")[0]
    press(collapse)
    wait(300)
    walk.check(
        "Collapse all leaves the headings alone",
        listing.model.rowCount() == len(listing.model.groups),
        f"{lines} -> {listing.model.rowCount()} lines",
    )
    press(expand)
    wait(300)
    walk.check("Expand all puts the rows back", listing.model.rowCount() == lines, listing.model.rowCount())

    line_press(listing, first(listing, "heading"))
    wait(300)
    walk.check(
        "a press on one heading shuts that group alone",
        0 < listing.model.rowCount() < lines,
        f"{lines} -> {listing.model.rowCount()} lines",
    )
    line_press(listing, first(listing, "heading"))
    wait(300)
    walk.check("and opens it again", listing.model.rowCount() == lines, listing.model.rowCount())

    # --- the rows and the count line ------------------------------------------------------
    line_press(listing, first(listing, "row"))
    wait(250)
    walk.check(
        "a press on a row takes it and the count says so",
        len(listing.selection) == 1 and demo._count.text() == "1 selected",
        demo._count.text(),
    )
    listing.view.setFocus(Qt.FocusReason.TabFocusReason)
    listing.view.setCurrentIndex(listing.model.index(first(listing, "row"), 0))
    key(listing, Qt.Key.Key_Down)
    wait(150)
    walked = listing.view.currentIndex().row()
    key(listing, Qt.Key.Key_Up)
    wait(150)
    walk.check(
        "the arrows walk the cursor over the rows",
        walked == first(listing, "row") + 1
        and listing.view.currentIndex().row() == first(listing, "row"),
        f"{walked} then {listing.view.currentIndex().row()}",
    )
    key(listing, Qt.Key.Key_Space)
    wait(250)
    walk.check("Space drops the row under the cursor", not listing.selection, demo._count.text())
    key(listing, Qt.Key.Key_Space)
    wait(250)
    walk.check("and Space again takes it", len(listing.selection) == 1, demo._count.text())

    # --- the pager -------------------------------------------------------------------------
    press(listing.footer._next)
    settled(control, wait)
    wait(300)
    walk.check(
        "the next arrow pages forward and regroups",
        control.pager.range_label == f"26 to {TOTAL} of {TOTAL}" and bool(listing.model.groups),
        f"{control.pager.range_label}, {len(listing.model.groups)} headings",
    )
    press(listing.footer._previous)
    settled(control, wait)
    wait(300)
    walk.check(
        "the previous arrow pages back",
        control.pager.range_label == f"1 to {PAGE_SIZE} of {TOTAL}",
        control.pager.range_label,
    )

    # --- the derived list ------------------------------------------------------------------
    derived = demo.derived
    settled(derived.control, wait)
    walk.check(
        "the derived list walks the set with a load-more row",
        derived.paging == "more" and derived.control.bottom() == "more",
        derived.control.bottom(),
    )
    held = len(derived.control.rows)
    keys = {group.key for group in derived.model.groups}
    derived.control.load_more()
    settled(derived.control, wait)
    wait(400)
    grown = {group.key for group in derived.model.groups}
    walk.check(
        "the load-more row appends a page and keeps every group whole",
        len(derived.control.rows) > held
        and keys <= grown
        and sum(len(group.rows) for group in derived.model.groups) == len(derived.control.rows),
        f"{held} -> {len(derived.control.rows)} rows over {len(grown)} groups",
    )
    bar = derived.view.verticalScrollBar()
    bar.setValue(bar.maximum())
    wait(100)
    kept = [wheel(derived.view) for _ in range(3)]
    walk.check("a gesture at the bottom stays on the list", all(kept[1:]), kept)

    # --- the empty list --------------------------------------------------------------------
    empty = demo.empty
    settled(empty.control, wait)
    walk.check(
        "the empty list draws the caller's own line",
        empty.control.view(len(empty.model.lines)) == "empty" and not empty.model.rowCount(),
        empty.empty_label,
    )

    # --- the view controls --------------------------------------------------------------------
    for name, value in (("theme", "dark"), ("size", "lg"), ("density", "compact"), ("motion", "reduced")):
        prefs.set(name, value)
        wait(120)
    wait(300)
    walk.check(
        "the header's view controls leave the page standing",
        control.snapshot().status in ("ready", "error") and bool(control.rows),
        f"{len(control.rows)} rows, {control.pager.range_label}",
    )
    return walk.verdict("the toolbar, the headings, the rows, the pager and the derived list")
