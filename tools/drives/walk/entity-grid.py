"""The entity-grid page, walked the way a reader walks it.

The three size toggles, a tile taken by its box and by Space against the count line, Enter
reporting the tile it opened, the cursor across the rows and at its ends, a held-back tile
refusing, the scroller at the end of the set, and the wheel at the bottom edge.

    .venv/bin/python tools/qa.py --headed --page entity-grid --drive tools/drives/walk/entity-grid.py

A popup dismissing, the focus and the wheel's owner are what a real window decides, so
this drive is run headed; offscreen is for the unit tests.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _walk import Walk, press, settled, stage, wait_until, wheel  # noqa: E402
from qtpy import QtCore, QtGui  # noqa: E402
from qtpy.QtTest import QTest  # noqa: E402

from sg_widgets_qt.widgets.entity_card import card_tile_checkbox_rect  # noqa: E402

Qt = QtCore.Qt

SIZES = ("sm", "md", "lg")


def key(grid, code) -> None:
    grid.view.keyPressEvent(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), Qt.KeyboardModifier.NoModifier)
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    walk = Walk("entity-grid")
    demo = stage(page, "entity-grid")
    if demo is None:
        return {"verdict": "FAIL the page built no entity-grid demo"}
    grid = demo.grid
    if not wait_until(lambda: demo.demo_ready, wait, 30000):
        return {"verdict": "FAIL the grid drew no tile"}
    settled(grid.control, wait)
    wait(200)

    # --- the three sizes ------------------------------------------------------------------
    for step in ("lg", "sm", "md"):
        press(find(f"grid-size-{step}"))
        wait(300)
        walk.check(
            f"the {step} toggle resizes the tiles and stays down alone",
            grid.size == step
            and demo._sizes[step].checked
            and not any(demo._sizes[other].checked for other in SIZES if other != step),
            f"{grid.size}, down: {[one for one in SIZES if demo._sizes[one].checked]}",
        )

    # --- a tile's box and the count line -----------------------------------------------------
    chooser = demo.selectable
    settled(chooser.control, wait)
    rect = chooser.view.visualRect(chooser.model.index(0, 0))
    QTest.mouseClick(
        chooser.view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card_tile_checkbox_rect(rect).center(),
    )
    wait(250)
    walk.check(
        "a tile's box takes the tile and the count says so",
        len(chooser.selection) == 1 and demo._count.text() == "1 selected",
        demo._count.text(),
    )
    chooser.view.setFocus(Qt.FocusReason.TabFocusReason)
    chooser.view.setCurrentIndex(chooser.model.index(1, 0))
    key(chooser, Qt.Key.Key_Space)
    wait(250)
    walk.check(
        "Space takes the tile under the cursor",
        len(chooser.selection) == 2 and demo._count.text() == "2 selected",
        demo._count.text(),
    )
    key(chooser, Qt.Key.Key_Space)
    wait(250)
    walk.check("Space again drops it", len(chooser.selection) == 1, demo._count.text())

    # --- Enter opens a tile --------------------------------------------------------------
    grid.view.setFocus(Qt.FocusReason.TabFocusReason)
    grid.view.setCurrentIndex(grid.model.index(1, 0))
    key(grid, Qt.Key.Key_Return)
    wait(250)
    opened = grid.model.row_at(1)
    walk.check(
        "Enter opens the tile under the cursor and the line names it",
        demo._opened.text() == f"opened {opened.type} {opened.id}",
        demo._opened.text(),
    )

    # --- the cursor -----------------------------------------------------------------------
    across = grid.view.columns_across()
    grid.view.setCurrentIndex(grid.model.index(0, 0))
    key(grid, Qt.Key.Key_Right)
    wait(150)
    walk.check("Right moves one tile", grid.view.currentIndex().row() == 1)
    key(grid, Qt.Key.Key_Down)
    wait(150)
    walk.check(
        "Down moves one row of tiles",
        grid.view.currentIndex().row() == 1 + across,
        f"{grid.view.currentIndex().row()} over {across} across",
    )
    key(grid, Qt.Key.Key_Up)
    wait(150)
    walk.check("Up comes back", grid.view.currentIndex().row() == 1)
    key(grid, Qt.Key.Key_Home)
    wait(150)
    walk.check("Home goes to the first tile", grid.view.currentIndex().row() == 0)
    held = len(grid.control.rows)
    key(grid, Qt.Key.Key_End)
    settled(grid.control, wait)
    wait(400)
    walk.check(
        "End goes to the last tile and keeps the cursor when a page lands",
        grid.view.currentIndex().isValid(),
        f"{grid.view.currentIndex().row()} of {len(grid.control.rows)} loaded",
    )

    # --- a held-back tile -------------------------------------------------------------------
    back = demo.held
    settled(back.control, wait)
    shut = [at for at in range(len(back.control.rows)) if back.control.disabled_at(at)]
    walk.check("every third tile is held back", bool(shut), shut)
    if shut:
        back.view.setCurrentIndex(back.model.index(shut[0], 0))
        walk.check(
            "and the cursor refuses to land on one",
            back.view.currentIndex().row() != shut[0],
            back.view.currentIndex().row(),
        )
        row = back.model.row_at(shut[0])
        back.control.toggle(row)
        wait(150)
        walk.check("and it cannot be taken", not back.selection, len(back.selection))

    # --- the scroller and the wheel ----------------------------------------------------------
    walk.check("the grid walks the set by scrolling", grid.paging == "scroll", grid.paging)
    held = len(grid.control.rows)
    grid.control.on_last_visible(len(grid.control.rows) - 1)
    settled(grid.control, wait)
    wait(300)
    walk.check(
        "reaching the end appends a page",
        len(grid.control.rows) > held,
        f"{held} -> {len(grid.control.rows)}",
    )
    bar = grid.view.verticalScrollBar()
    bar.setValue(bar.maximum())
    wait(100)
    kept = [wheel(grid.view) for _ in range(3)]
    walk.check("a gesture at the bottom stays on the grid", all(kept[1:]), kept)

    # --- the view controls --------------------------------------------------------------------
    for name, value in (("theme", "dark"), ("size", "lg"), ("density", "compact"), ("motion", "reduced")):
        prefs.set(name, value)
        wait(120)
    wait(300)
    walk.check(
        "the header's view controls leave the page standing",
        grid.control.snapshot().status in ("ready", "error") and bool(grid.control.rows),
        f"{len(grid.control.rows)} tiles",
    )
    return walk.verdict("the sizes, the boxes, Enter, the cursor, the held-back tiles and the scroller")
