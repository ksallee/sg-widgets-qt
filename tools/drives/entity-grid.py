"""The port of `~/dev/sg-widgets/tools/drives/entity-grid.js`.

Tiles carry their status over the thumbnail and no id; the arrows walk the grid, Space selects,
Enter and one press open a tile, the picture-less grid stands on the placeholder, and the
scroller asks for the next page.

    .venv/bin/python tools/qa.py --page entity-grid --drive tools/drives/entity-grid.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "states"))

from _collection_states import images_settled, stage_widget, wait_for  # noqa: E402
from qtpy import QtCore, QtGui  # noqa: E402


def settled(grid) -> bool:
    return grid.control.snapshot().status in ("ready", "error")


def key(grid, code) -> None:
    grid.on_key(
        QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, int(code), QtCore.Qt.KeyboardModifier.NoModifier)
    )


def drive(page, wait, find, prefs) -> dict:  # noqa: C901
    notes: list[str] = []
    holder = stage_widget(page, "entity-grid")
    if holder is None:
        return {"verdict": "FAIL the page built no entity-grid demo"}
    grids = [holder.grid, holder.selectable, holder.bare, holder.held]
    if not wait_for(lambda: all(settled(one) and one.control.rows for one in grids), wait):
        return {"verdict": "FAIL a grid rendered no tiles", "notes": notes}
    images_settled(wait)
    grid = holder.grid
    notes.append(f"{len(grid.control.rows)} tiles")

    # The thumbnail fills the top of every tile, in one of its three states.
    tiles = [grid.tile_of(row) for row in grid.control.rows]
    states = {"ready" if tile.thumbnail else "none" for tile in tiles}
    notes.append(f"thumbnail states {', '.join(sorted(states))}")

    # The status sits on the thumbnail, and nothing on a tile spells the row's id.
    without = [tile.name for tile in tiles if not tile.status_code]
    if without:
        return {"verdict": f"FAIL {len(without)} tiles carry no status over the thumbnail", "notes": notes}
    notes.append(f"{len(tiles)} tiles carry a status over the thumbnail")
    spelled = [
        tile.name
        for tile, row in zip(tiles, grid.control.rows)
        if f"#{row.id}" in f"{tile.name} {tile.code} {tile.sub_label} {tile.secondary}"
    ]
    if spelled:
        return {"verdict": f"FAIL a tile spells an id: {spelled[0]}", "notes": notes}
    notes.append("no tile text carries a # id")

    # The arrows walk the grid from one tab stop, down by a whole row of tiles.
    grid.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    wait(150)
    grid.control.set_cursor(0)
    key(grid, QtCore.Qt.Key.Key_Right)
    wait(200)
    if grid.control.active != 1:
        return {"verdict": f"FAIL ArrowRight moved to {grid.control.active}", "notes": notes}
    across = grid.view.columns_across()
    key(grid, QtCore.Qt.Key.Key_Down)
    wait(200)
    if grid.control.active != 1 + across:
        return {
            "verdict": f"FAIL ArrowDown moved to {grid.control.active} over {across} columns",
            "notes": notes,
        }
    key(grid, QtCore.Qt.Key.Key_Home)
    wait(200)
    if grid.control.active != 0:
        return {"verdict": f"FAIL Home left the cursor on {grid.control.active}", "notes": notes}
    notes.append(f"{across} columns, ArrowRight to 1, ArrowDown to {1 + across}, Home back to 0")

    # Space selects on the selectable grid, and Enter opens a tile.
    picked = holder.selectable
    picked.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    picked.control.set_cursor(0)
    key(picked, QtCore.Qt.Key.Key_Space)
    wait(300)
    count = holder._count.text()
    notes.append(f"selection reads {count}")
    if not count.startswith("1 "):
        return {"verdict": f'FAIL selection reads "{count}", expected 1', "notes": notes}

    opened: list = []
    grid.selected.connect(opened.append)
    grid.view.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    grid.control.set_cursor(0)
    key(grid, QtCore.Qt.Key.Key_Return)
    wait(250)
    if len(opened) != 1:
        return {"verdict": f"FAIL Enter opened {len(opened)} tiles", "notes": notes}
    index = grid.model.index(1, 0)
    grid.on_tile_pressed(index, grid.view.visualRect(index).center())
    wait(250)
    if len(opened) != 2:
        return {"verdict": f"FAIL one press opened {len(opened) - 1} tiles, expected one", "notes": notes}
    notes.append("Enter and one press both open a tile")

    # Every tile of the third grid is on the placeholder.
    bare = [holder.bare.tile_of(row) for row in holder.bare.control.rows]
    on_placeholder = [tile for tile in bare if not tile.thumbnail]
    notes.append(f"{len(on_placeholder)} tiles on the placeholder")
    if not on_placeholder:
        return {"verdict": "FAIL the picture-less grid drew no placeholder tile", "notes": notes}

    # A held-back tile refuses the cursor and the selection.
    held = holder.held
    if not held.control.disabled_at(0):
        return {"verdict": "FAIL the demo held no tile back", "notes": notes}
    held.control.toggle(held.control.rows[0])
    if held.selection:
        return {"verdict": "FAIL a held-back tile was taken", "notes": notes}

    # Infinite scroll: reaching the end of the body asks the source for the next page.
    before = len(grid.control.rows)
    grid.control.on_last_visible(before - 1)
    if not wait_for(lambda: len(grid.control.rows) > before, wait):
        return {"verdict": f"FAIL the scroller loaded no more than {before} tiles", "notes": notes}
    notes.append(f"scrolling loaded {len(grid.control.rows) - before} more tiles")

    return {
        "verdict": "PASS status over the thumbnail, no id, arrows, Space, Enter, one press and the placeholder",
        "notes": notes,
    }
