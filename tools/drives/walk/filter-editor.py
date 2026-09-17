"""filter-editor: build the tree the demo invites, and watch the wire and the rows follow.

    .venv/bin/python tools/qa.py --page filter-editor --drive tools/drives/walk/filter-editor.py

The page opens on a tree a person would have built. The walk adds a condition and removes it,
adds a group and nests a condition inside it, moves a row with the grip, turns All into Any on
both levels, changes a field, an operator and a value on every data type the tree carries, and
after each act reads the serialised filter under the tree and the count of the rows it matches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import (  # noqa: E402
    Walk,
    click,
    key,
    popups,
    press_enter,
    retype,
    scroll_to,
    set_view,
    wait_for,
)
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_core.filter import FilterGroup, to_api3_hash  # noqa: E402


def slot(editor, kind: str, path: tuple = ()) -> Any:
    """The control of one kind on one path of the tree.

    Every control the editor builds carries the path it edits and what it edits there, so a walk
    reaches the operator of the third row the way a person reaches it: by where it stands.
    """
    for one in editor.findChildren(QtWidgets.QWidget):
        held = getattr(one, "slot_path", None)
        if held is not None and held[1] == kind and tuple(held[0]) == tuple(path):
            return one
    return None


def slots(editor, kind: str) -> list:
    """Every control of one kind, with the path it edits."""
    found = []
    for one in editor.findChildren(QtWidgets.QWidget):
        held = getattr(one, "slot_path", None)
        if held is not None and held[1] == kind:
            found.append((tuple(held[0]), one))
    return found


def wire(editor) -> dict:
    """What the tree sends, which is what the block under it prints."""
    return to_api3_hash(editor.value)


def paths_of(value: FilterGroup) -> list:
    """The field each child of the root names, a group reading as its own operator."""
    return [
        getattr(one, "path", None) or f"group:{getattr(one, 'logical_operator', '')}"
        for one in value.conditions
    ]


def one_value(node) -> Any:
    """The value a condition holds, whether it is a bare one or a list of them."""
    held = getattr(node, "value", None)
    return held[0] if isinstance(held, list) and held else held


def listed(node) -> list:
    """The values a condition holds, as a list however it holds them."""
    held = getattr(node, "value", None)
    if isinstance(held, list):
        return list(held)
    return [] if held is None else [held]


def counted(results, wait, ms: int = 15000) -> Any:
    """Wait for the result set under the tree to stop counting, and answer what it counted."""
    wait_for(lambda: results.count.kind != "counting", wait, ms)
    return results.count


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("filter-editor-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no filter-editor demo"}
    wait_for(lambda: demo.demo_ready, wait, 25000)
    editor = demo.editor
    results = demo.results

    # --- the tree the page opens on ------------------------------------------------------------
    walk.same("the demo opens on five children", 5, len(editor.value.conditions))
    walk.check(
        "the block under the tree prints its filter",
        json.loads(demo.wire.toPlainText()) == wire(editor),
        "the tree's own wire",
        demo.wire.toPlainText()[:120],
    )
    opening = counted(results, wait)
    walk.check("the rows under the tree were counted", opening.kind == "ready", "ready", opening)
    walk.check("the tree matches rows", opening.total > 0, "> 0", opening.total)

    # --- a condition added, then taken away -------------------------------------------------------
    held = len(editor.value.conditions)
    click(slot(editor, "add-condition"))
    wait(800)
    walk.same("Condition adds a row to the root", held + 1, len(editor.value.conditions))
    walk.check(
        "the new row names no field yet",
        not getattr(editor.value.conditions[-1], "path", ""),
        "an empty path",
        getattr(editor.value.conditions[-1], "path", None),
    )
    walk.check(
        "the row says what is missing",
        bool(editor.issues()),
        "an issue",
        editor.issues(),
    )
    click(slot(editor, "remove", (held,)))
    wait(800)
    walk.same("the cross takes the row away again", held, len(editor.value.conditions))
    walk.check("the tree is whole again", not editor.issues(), "no issue", editor.issues())

    # --- a group nested, with a condition inside it -------------------------------------------------
    click(slot(editor, "add-group"))
    wait(800)
    walk.same("Group nests a group in the root", held + 1, len(editor.value.conditions))
    nested = editor.value.conditions[-1]
    walk.check(
        "the nested node is a group",
        isinstance(nested, FilterGroup),
        "a group",
        type(nested).__name__,
    )
    walk.same("a nested group opens on Any", "or", nested.logical_operator)
    at = (held,)
    inner_add = slot(editor, "add-condition", at)
    walk.check("the nested group offers to add a condition", inner_add is not None, True, inner_add)
    if inner_add is not None:
        click(inner_add)
        wait(800)
        walk.same("the condition lands inside the group", 1, len(editor.value.conditions[held].conditions))

    # The nested group's own All and Any is its own.
    logic = slot(editor, "logic", at)
    walk.check("the nested group carries its own All and Any", logic is not None, True, logic)
    if logic is not None:
        click(logic.toggles()[0])
        wait(600)
        walk.same("pressing All turns the nested group", "and", editor.value.conditions[held].logical_operator)

    click(slot(editor, "remove", at))
    wait(800)
    walk.same("the group's cross takes the whole group", held, len(editor.value.conditions))

    # --- All and Any on the root --------------------------------------------------------------------
    # The group is drawn afresh after every edit, so its All and Any is looked up again each time:
    # a walk that held the first one would be pressing a widget that has gone.
    walk.same("the root opens on All", "and", editor.value.logical_operator)
    click(slot(editor, "logic").toggles()[1])
    wait(700)
    walk.same("pressing Any turns the root", "or", editor.value.logical_operator)
    walk.same("the wire follows the turn", "or", wire(editor).get("logical_operator"))
    walk.check(
        "the block follows the turn",
        json.loads(demo.wire.toPlainText()).get("logical_operator") == "or",
        "or",
        json.loads(demo.wire.toPlainText()).get("logical_operator"),
    )
    loosened = counted(results, wait)
    walk.check(
        "Any matches at least as many rows as All",
        loosened.kind == "ready" and loosened.total >= opening.total,
        f">= {opening.total}",
        loosened,
    )
    click(slot(editor, "logic").toggles()[0])
    wait(700)
    walk.same("pressing All turns it back", "and", editor.value.logical_operator)
    counted(results, wait)

    # --- a row moved by its grip ----------------------------------------------------------------------
    order = paths_of(editor.value)
    grip = slot(editor, "grip", (0,))
    grip.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(grip, QtCore.Qt.Key.Key_Down, QtCore.Qt.KeyboardModifier.AltModifier)
    wait(800)
    moved = paths_of(editor.value)
    walk.check(
        "Alt and an arrow move the row down one place",
        moved[:2] == [order[1], order[0]],
        [order[1], order[0]],
        moved[:2],
    )
    grip = slot(editor, "grip", (1,))
    grip.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    key(grip, QtCore.Qt.Key.Key_Up, QtCore.Qt.KeyboardModifier.AltModifier)
    wait(800)
    walk.same("Alt and the other arrow move it back", order, paths_of(editor.value))

    # --- the operator of a row ------------------------------------------------------------------------
    where = next(path for path, one in slots(editor, "operator") if editor.node_at(path) is not None
                 and getattr(editor.node_at(path), "path", "") == "code")
    operator = slot(editor, "operator", where)
    walk.same("the text row opens on contains", "contains", editor.node_at(where).operator)
    entries = [one for one in operator.list.entries if one.selectable]
    other = next(one for one in entries if one.value != "contains")
    operator.open()
    wait(300)
    row_at = [one for one in operator.list.entries].index(other)
    QtCore.QCoreApplication.processEvents()
    from qtpy.QtTest import QTest

    QTest.mouseClick(
        operator.list,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        operator.list.row_rect(row_at).center(),
    )
    wait(800)
    walk.same("picking another operator writes it into the tree", other.value, editor.node_at(where).operator)
    walk.check(
        "the wire carries the new operator",
        json.dumps(wire(editor)).find(f'"{other.value}"') >= 0,
        other.value,
        json.dumps(wire(editor))[:160],
    )
    counted(results, wait)

    # --- a value, on each kind of control the tree carries ----------------------------------------------
    kinds: dict[str, tuple] = {}
    for path, one in slots(editor, "value"):
        kinds.setdefault(type(one).__name__, (path, one))
    walk.check(
        "the tree carries a control for every value kind",
        len(kinds) >= 6,
        ">= 6 kinds",
        sorted(kinds),
    )

    text_at, text_value = kinds.get("TextEditor", (None, None))
    if text_value is not None:
        scroll_to(page, text_value, wait)
        retype(text_value.control, "plate")
        press_enter(text_value.control)
        wait(800)
        walk.same("a typed text lands in the tree", "plate", one_value(editor.node_at(text_at)))
        counted(results, wait)

    number_at, number_value = kinds.get("NumberEditor", (None, None))
    if number_value is not None:
        scroll_to(page, number_value, wait)
        number_value.input.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)
        was = one_value(editor.node_at(number_at))
        key(number_value.input, QtCore.Qt.Key.Key_Up)
        wait(800)
        walk.check(
            "a stepped number lands in the tree",
            one_value(editor.node_at(number_at)) != was,
            f"not {was}",
            one_value(editor.node_at(number_at)),
        )
        counted(results, wait)

    colour_at, colour_value = kinds.get("ColorEditor", (None, None))
    if colour_value is not None:
        scroll_to(page, colour_value, wait)
        retype(colour_value.input, "#00ff00")
        press_enter(colour_value.input)
        wait(800)
        walk.same("a typed colour lands as the stored triple", "0,255,0", one_value(editor.node_at(colour_at)))
        counted(results, wait)

    list_at, list_values = kinds.get("_ListValues", (None, None))
    if list_values is not None:
        scroll_to(page, list_values, wait)
        held_values = listed(editor.node_at(list_at))
        add = None
        for one in list_values.findChildren(QtWidgets.QWidget):
            if one.objectName() == "filter-list-add":
                add = one
                break
        walk.check("the list of values offers to add one", add is not None, True, add)
        if add is not None:
            click(add)
            wait(800)
            walk.check(
                "adding a value grows the list",
                len(listed(editor.node_at(list_at))) > len(held_values),
                f"> {len(held_values)}",
                listed(editor.node_at(list_at)),
            )
            grown = next(
                one for path, one in slots(editor, "value") if tuple(path) == tuple(list_at)
            )
            walk.same(
                "the added value is drawn a line of its own",
                len(listed(editor.node_at(list_at))),
                len(
                    [
                        one
                        for one in grown.findChildren(QtWidgets.QWidget)
                        if one.objectName() == "filter-list-value"
                    ]
                ),
            )
            crosses = [
                one
                for one in grown.findChildren(QtWidgets.QWidget)
                if one.objectName() == "filter-list-remove"
            ]
            walk.check("each value carries a cross", len(crosses) > 0, "> 0", len(crosses))
            if crosses:
                click(crosses[-1])
                wait(800)
                walk.same(
                    "the cross takes that value off the list",
                    len(held_values),
                    len(listed(editor.node_at(list_at))),
                )
            counted(results, wait)

    relative_at, relative = kinds.get("_RelativeValue", (None, None))
    if relative is not None:
        scroll_to(page, relative, wait)
        field = relative.findChild(QtWidgets.QLineEdit)
        if field is not None:
            retype(field, "5")
            press_enter(field)
            wait(800)
            walk.same("a relative window takes a new count", 5, one_value(editor.node_at(relative_at)))
            counted(results, wait)

    # --- the Note editor, whose read-state field takes `is` alone -----------------------------------------
    note = find("filter-editor-note")
    walk.check("the Note example stands on the page", note is not None, True, note)
    if note is not None:
        note_operator = slot(note, "operator", (0,))
        walk.check("the read-state row carries an operator", note_operator is not None, True, note_operator)
        if note_operator is not None:
            offered = sorted(one.value for one in note_operator.list.entries if one.selectable)
            walk.same("the read-state field offers is and is_not alone", ["is", "is_not"], offered)

    # --- the view controls --------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("filter-editor-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        wait_for(lambda: again.demo_ready, wait, 25000)
        walk.same("header: the tree wears the size step", "lg", again.editor.size)
        walk.same("header: the sizes section keeps the steps it named", "sm", find("filter-editor-sm").size)
        before = len(again.editor.value.conditions)
        click(slot(again.editor, "add-condition"))
        wait(800)
        walk.same("header: the rebuilt tree still adds a row", before + 1, len(again.editor.value.conditions))
        click(slot(again.editor, "remove", (before,)))
        wait(800)
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS a condition and a group are added, nested and taken away, a row moves by its grip,"
        " All and Any turn on both levels, a field's operator and every kind of value are edited,"
        " and the wire and the count under the tree follow each act"
    )
