"""The Qt half of the filter editor's state matrix, one state per `QA_STATE`.

The upstream half is `tools/drives/upstream/filter-editor-<state>.js`; the two leave their page
in the same state and the shots are read as a pair.

    QA_STATE=added .venv/bin/python tools/qa.py --page filter-editor \\
        --drive tools/drives/states/filter-editor.py --shot shots/states/filter-editor-added.png

    rest        the seeded tree as it settles: every value control the demo draws
    added       a blank condition added at the root, with its issue line under it
    removed     the first root condition removed
    nested      a group added at the root, on its own inset surface
    unnested    that group removed again, so the root is back to its rows
    operator    the first row moved onto `is none of`, so the value control swaps
    field-date  the first row pointed at Date Created on `is`, so a date editor stands
    field-list  the first row pointed at First Frame on `is any of`, so the value list stands
    stress      twelve blank conditions on the root, which is the tallest the tree gets
    disabled    the whole editor inert at half opacity

A field is chosen through the editor's own `pick_field`, which is the handler `FieldPicker`
calls, so the row is rebuilt exactly as a person's pick rebuilds it; the popup search that
upstream has to walk is not a state this matrix shoots.
"""
from __future__ import annotations

import os
import time

from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QTest

from sg_widgets_core.filter import condition as make_condition
from sg_widgets_qt.widgets.filter_editor import FilterEditor

#: The states this drive can leave the page in.
STATES: tuple[str, ...] = (
    "rest",
    "added",
    "removed",
    "nested",
    "unnested",
    "operator",
    "field-date",
    "field-list",
    "stress",
    "disabled",
)

#: How many blank rows the stress state puts on the root.
STRESS_ROWS = 12


def state_name() -> str:
    wanted = os.environ.get("QA_STATE", "rest").strip().lower()
    return wanted if wanted in STATES else "rest"


def wait_for(read, wait, ms: int = 10000) -> bool:
    """Spin the loop until `read` answers, or give up."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def main_editor(find) -> FilterEditor | None:
    """The demo's own editor, which is the tree this matrix drives."""
    found = find("filter-editor-main")
    if isinstance(found, FilterEditor):
        return found
    every = find(FilterEditor, all=True)
    return every[0] if every else None


def named(editor: FilterEditor, name: str) -> list[QtWidgets.QWidget]:
    return [
        widget
        for widget in editor.findChildren(QtWidgets.QWidget)
        if widget.objectName() == name
    ]


def root_button(editor: FilterEditor, name: str) -> QtWidgets.QWidget | None:
    """The foot control of the root group, which is the first one drawn."""
    for widget in named(editor, name):
        if getattr(widget, "slot_path", None) == ((), name.removeprefix("filter-")):
            return widget
    found = named(editor, name)
    return found[0] if found else None


def click(widget) -> None:
    QTest.mouseClick(
        widget,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        widget.rect().center(),
    )


def scroll_to(widget) -> None:
    """Put a widget at the top of the page, which is what upstream's `scrollIntoView` does."""
    walk = widget.parentWidget()
    while walk is not None:
        if isinstance(walk, QtWidgets.QScrollArea):
            bar = walk.verticalScrollBar()
            top = widget.mapTo(walk.widget(), QtCore.QPoint(0, 0)).y()
            bar.setValue(min(bar.maximum(), max(0, top - 8)))
            return
        walk = walk.parentWidget()


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0911
    wait(600)
    state = state_name()
    editor = main_editor(find)
    if editor is None:
        return {"verdict": f"FAIL {page.data_name}: no filter editor on the page"}
    wait_for(lambda: editor.fields(), wait, 8000)
    wait(400)
    scroll_to(editor)
    wait(100)
    before = len(editor.value.conditions)

    if state == "rest":
        return {
            "verdict": "PASS rest",
            "state": state,
            "rows": len(editor.rows()),
            "issues": editor.issues(),
        }

    if state == "disabled":
        editor.set_disabled(True)
        wait(300)
        return {"verdict": "PASS disabled", "state": state, "rows": len(editor.rows())}

    if state in ("added", "removed", "nested", "unnested", "stress"):
        if state == "added":
            found = root_button(editor, "filter-add-condition")
            if found is None:
                return {"verdict": "FAIL no add-condition control on the root"}
            click(found)
        elif state == "removed":
            editor.remove([0])
        elif state in ("nested", "unnested"):
            found = root_button(editor, "filter-add-group")
            if found is None:
                return {"verdict": "FAIL no add-group control on the root"}
            click(found)
            if state == "unnested":
                wait(200)
                editor.remove([len(editor.value.conditions) - 1])
        else:
            for _ in range(STRESS_ROWS):
                editor.append([], make_condition("", "is", ""))
        wait(400)
        return {
            "verdict": f"PASS {state}",
            "state": state,
            "before": before,
            "after": len(editor.value.conditions),
            "rows": len(editor.rows()),
            "issues": editor.issues()[:3],
        }

    node = editor.node_at([0])
    if node is None or node.kind != "condition":
        return {"verdict": "FAIL the first root child is not a condition"}

    if state == "operator":
        editor.pick_preset([0], node, "not_in")
        wait(400)
        after = editor.node_at([0])
        return {
            "verdict": "PASS operator",
            "state": state,
            "operator": after.operator if after is not None else "",
        }

    path = "created_at" if state == "field-date" else "sg_first_frame"
    editor.pick_field([0], node, path)
    wait_for(lambda: (editor.node_at([0]) or node).path == path, wait, 6000)
    wait(300)
    moved = editor.node_at([0])
    if moved is None or moved.kind != "condition":
        return {"verdict": f"FAIL the row did not move onto {path}"}
    if state == "field-list":
        editor.pick_preset([0], moved, "in")
        wait(400)
        moved = editor.node_at([0])
    wait(400)
    return {
        "verdict": f"PASS {state}",
        "state": state,
        "path": moved.path if moved is not None else "",
        "operator": moved.operator if moved is not None else "",
        "value_controls": len(named(editor, "filter-value")),
    }
