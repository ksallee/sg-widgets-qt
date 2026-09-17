"""filter-dialog: open the dialog, edit inside it, and apply or cancel what was staged.

    .venv/bin/python tools/qa.py --page filter-dialog --drive tools/drives/walk/filter-dialog.py

The launcher counts what is applied and the dialog stages what is not yet. The walk opens both
launchers, edits the tree inside the dialog and cancels, proving nothing outside it moved; opens
it again, edits and applies, proving the launcher's count, the serialised filter and the rows
under it all follow; clears the lot from the launcher; and leaves no dialog standing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, click, key, popups, set_view, wait_for  # noqa: E402
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_core.filter import to_api3_hash  # noqa: E402


def slot(editor, kind: str, path: tuple = ()) -> Any:
    """The control of one kind on one path of the tree inside the dialog."""
    for one in editor.findChildren(QtWidgets.QWidget):
        held = getattr(one, "slot_path", None)
        if held is not None and held[1] == kind and tuple(held[0]) == tuple(path):
            return one
    return None


def foot(name: str) -> Any:
    """One of the dialog's own buttons, which stands on a window over the page."""
    for one in QtWidgets.QApplication.allWidgets():
        if one.objectName() == name and one.isVisible():
            return one
    return None


def paths_of(value) -> list:
    return [getattr(one, "path", None) for one in value.conditions]


def counted(results, wait, ms: int = 15000):
    wait_for(lambda: results.count.kind != "counting", wait, ms)
    return results.count


def drive(page, wait, find, prefs) -> dict:  # noqa: PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("filter-dialog-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no filter-dialog demo"}
    wait_for(lambda: demo.demo_ready, wait, 25000)
    empty, applied = demo.empty, demo.applied

    # --- what each launcher reads before it is opened -------------------------------------
    walk.same("empty: the launcher counts nothing", 0, empty.active)
    walk.same("empty: the launcher asks to add filters", "Add filters", empty.launcher().text)
    walk.same("applied: the launcher counts the two applied", 2, applied.active)
    walk.same("applied: the launcher asks to edit them", "Edit filters", applied.launcher().text)
    opening = counted(demo.results, wait)
    walk.check("applied: the rows under it were counted", opening.kind == "ready", "ready", opening)

    # --- edited, then cancelled ----------------------------------------------------------------
    held = list(paths_of(applied.value))
    click(applied.launcher())
    wait(900)
    walk.check("applied: the launcher opens the dialog", applied.open, True, applied.open)
    walk.check("applied: the dialog stands on a window of its own", "filter-dialog-panel" in popups(), True, popups())
    editor = applied.editor()
    walk.check("applied: the dialog holds a tree", editor is not None, True, editor)
    walk.same("applied: the tree opens on what was applied", held, paths_of(editor.value))

    click(slot(editor, "add-condition"))
    wait(900)
    walk.same("applied: a condition is added inside the dialog", len(held) + 1, len(editor.value.conditions))
    walk.same("applied: nothing outside the dialog moved yet", held, paths_of(applied.value))
    walk.same("applied: the launcher's count is unmoved", 2, applied.active)

    cancel = foot("filter-cancel")
    walk.check("applied: the dialog offers Cancel", cancel is not None, True, cancel)
    click(cancel)
    wait(900)
    walk.check("applied: Cancel closes the dialog", not applied.open, False, applied.open)
    walk.same("applied: Cancel throws the staged edit away", held, paths_of(applied.value))
    walk.same("applied: no dialog was left standing", [], popups())

    # --- edited, then applied ---------------------------------------------------------------------
    click(applied.launcher())
    wait(900)
    editor = applied.editor()
    click(slot(editor, "remove", (0,)))
    wait(900)
    staged = paths_of(editor.value)
    walk.same("applied: a row is taken away inside the dialog", held[1:], staged)
    walk.same("applied: the outside is still unmoved", held, paths_of(applied.value))

    apply_button = foot("filter-apply")
    walk.check("applied: the dialog offers Apply", apply_button is not None, True, apply_button)
    click(apply_button)
    wait(1200)
    walk.check("applied: Apply closes the dialog", not applied.open, False, applied.open)
    walk.same("applied: Apply takes the staged tree", staged, paths_of(applied.value))
    walk.same("applied: the launcher's count follows", 1, applied.active)
    walk.check(
        "applied: the block under the launcher follows",
        json.loads(demo.wire.toPlainText()) == to_api3_hash(applied.value),
        "the launcher's own wire",
        demo.wire.toPlainText()[:120],
    )
    loosened = counted(demo.results, wait)
    walk.check(
        "applied: one condition fewer matches at least as many rows",
        loosened.kind == "ready" and loosened.total >= opening.total,
        f">= {opening.total}",
        loosened,
    )

    # --- Escape leaves the dialog the way Cancel does -----------------------------------------------
    before = paths_of(applied.value)
    click(applied.launcher())
    wait(900)
    editor = applied.editor()
    click(slot(editor, "add-condition"))
    wait(900)
    key(applied.dialog(), QtCore.Qt.Key.Key_Escape)
    wait(900)
    walk.check("applied: Escape closes the dialog", not applied.open, False, applied.open)
    walk.same("applied: Escape throws the staged edit away", before, paths_of(applied.value))
    walk.same("applied: no dialog was left standing", [], popups())

    # --- the launcher's own clear ---------------------------------------------------------------------
    walk.check("applied: a launcher holding filters offers to clear them", applied._clear.isVisible(), True, False)  # noqa: SLF001
    click(applied._clear)  # noqa: SLF001
    wait(1200)
    walk.same("applied: Clear empties the tree", 0, len(applied.value.conditions))
    walk.same("applied: the launcher counts nothing again", 0, applied.active)
    walk.same("applied: the launcher asks to add filters again", "Add filters", applied.launcher().text)
    counted(demo.results, wait)

    # --- the empty launcher opens on an empty tree ------------------------------------------------------
    click(empty.launcher())
    wait(900)
    walk.check("empty: the launcher opens the dialog", empty.open, True, empty.open)
    walk.same("empty: the tree opens on nothing", 0, len(empty.editor().value.conditions))
    click(slot(empty.editor(), "add-condition"))
    wait(900)
    walk.same("empty: a condition is added inside it", 1, len(empty.editor().value.conditions))
    click(foot("filter-cancel"))
    wait(900)
    walk.same("empty: Cancel leaves it empty", 0, len(empty.value.conditions))

    # --- the Note launcher ----------------------------------------------------------------------------------
    note = find("filter-dialog-note")
    walk.check("the Note example stands on the page", note is not None, True, note)
    if note is not None:
        walk.same("the Note launcher counts its one condition", 1, note.active)

    # --- the view controls ------------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("filter-dialog-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready, wait, 25000)
        walk.same("header: the launchers wear the size step", "lg", again.applied.size)
        walk.same("header: the sizes section keeps the steps it named", "sm", find("filter-dialog-sm").size)
        click(again.applied.launcher())
        wait(900)
        walk.check("header: the rebuilt launcher still opens", again.applied.open, True, again.applied.open)
        click(foot("filter-cancel"))
        wait(900)
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS the launcher counts what is applied, the dialog stages an edit until Apply takes it,"
        " Cancel and Escape throw it away, Clear empties the tree, and the serialised filter and"
        " the rows under the launcher follow every applied change"
    )
