"""The entity grid's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/entity-grid-<state>.js`, run against
`/widgets/entity-grid/`.

    QA_STATE=selected .venv/bin/python tools/qa.py --page entity-grid \\
        --drive tools/drives/states/entity-grid.py --shot shots/states/entity-grid-selected.png

    rest      the wall of tiles at rest: the picture, the status corner, no box
    selected  one tile of the selectable grid taken, its box up and the count reading 1
    hovered   the pointer on a tile, which is what reveals its box
    cursor    the cursor moved off the first tile with the arrows, wearing its ring
    paged     the scroller asked for a page, so the grid holds two
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _collection_states import (  # noqa: E402
    frame,
    images_settled,
    stage_widget,
    state_name,
    wait_for,
)
from qtpy import QtCore, QtGui, QtWidgets  # noqa: E402

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = ("rest", "selected", "hovered", "cursor", "paged")


def described(grid) -> dict:
    control = grid.control
    return {
        "name": grid.objectName(),
        "tiles": len(control.rows),
        "loaded": control.pager.loaded_label,
        "bottom": control.bottom(),
        "selection": len(grid.selection),
        "cursor": control.active,
        "size": grid.size,
    }


def settled(grid) -> bool:
    return grid.control.snapshot().status in ("ready", "error")


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    state = state_name(STATES, "rest")
    wait(200)
    holder = stage_widget(page, "entity-grid")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-grid demo"}
    grids = [holder.grid, holder.selectable, holder.bare, holder.held]
    if not wait_for(lambda: all(settled(one) and one.control.rows for one in grids), wait):
        return {"verdict": "FAIL a grid on the page never landed a page"}
    images_settled(wait)
    frame(page, wait, "entity-grid")

    if state == "selected":
        grid = holder.selectable
        row = grid.control.rows[0]
        grid.control.toggle(row)
        wait(300)
        if len(grid.selection) != 1:
            return {"verdict": f"FAIL the tile was not taken: {described(grid)}"}
        if not holder._count.text().startswith("1 "):
            return {"verdict": f"FAIL the count reads {holder._count.text()!r}"}

    elif state == "hovered":
        grid = holder.selectable
        index = grid.model.index(0, 0)
        rect = grid.view.visualRect(index)
        QtWidgets.QApplication.sendEvent(grid.view.viewport(), _move(rect.center()))
        wait(300)
        if grid.view.indexAt(rect.center()) != index:
            return {"verdict": "FAIL the pointer landed on no tile"}

    elif state == "cursor":
        grid = holder.grid
        grid.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
        wait(150)
        for key in (QtCore.Qt.Key.Key_Right, QtCore.Qt.Key.Key_Down):
            grid.on_key(
                QtGui.QKeyEvent(
                    QtCore.QEvent.Type.KeyPress, int(key), QtCore.Qt.KeyboardModifier.NoModifier
                )
            )
            wait(200)
        across = grid.view.columns_across()
        if grid.control.active != 1 + across:
            return {
                "verdict": (
                    f"FAIL the cursor sits on {grid.control.active} over {across} columns, "
                    f"expected {1 + across}"
                )
            }

    elif state == "paged":
        grid = holder.grid
        before = len(grid.control.rows)
        grid.control.on_last_visible(before - 1)
        if not wait_for(lambda: len(grid.control.rows) > before, wait):
            return {"verdict": f"FAIL the scroller loaded no page past {before} tiles"}

    wait(300)
    return {
        "verdict": f"PASS {state}",
        "state": state,
        "grids": [described(one) for one in grids],
    }


def _move(point):
    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove,
        QtCore.QPointF(point),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
