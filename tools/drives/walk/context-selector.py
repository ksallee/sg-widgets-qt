"""context-selector: open the panel, choose a context from the recents, the tasks and the tree.

    .venv/bin/python tools/qa.py --page context-selector \
        --drive tools/drives/walk/context-selector.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    arm,
    check_ink,
    click,
    click_row,
    key,
    orphans,
    scroll_to,
    type_into,
    wait_for,
    wear,
)
from qtpy import QtCore, QtWidgets  # noqa: E402


def open_panel(selector, wait) -> None:
    if not selector.open:
        click(selector.trigger())
        wait(400)
    wait_for(lambda: not selector.tasks_control().loading, wait)


def recent_rows(selector) -> list:
    from sg_widgets_qt.widgets.context_selector import _ChipRow

    holder = selector.popover().findChild(QtWidgets.QWidget, "context-recents")
    if holder is None:
        return []
    return [one for one in holder.findChildren(_ChipRow) if one.isVisible()]


def task_row(selector) -> int:
    """The first row of My tasks that is a task rather than its project heading."""
    from sg_widgets_qt.primitives.roles import Roles

    model = selector.tasks_control().list_surface().model()
    for row in range(model.rowCount()):
        if model.index(row, 0).data(Roles.KIND) != "heading":
            return row
    return -1


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    arm(page, wait)
    selector = find("context-selector")
    line = find("demo-context")
    scroll_to(page, selector, wait)

    walk.check(
        "trigger: it draws a chip for each part of the context it holds",
        [ref.name for ref in selector.trigger().refs]
        == ["Blue Moon Rising", "sh010_0010", "Comp"],
        ["Blue Moon Rising", "sh010_0010", "Comp"],
        [ref.name for ref in selector.trigger().refs],
    )
    walk.same("trigger: it is named for the innermost of them", "Comp", selector.label)
    walk.check(
        "trigger: the line under it says the same",
        "Blue Moon Rising" in line.text() and "Comp" in line.text(),
        "project / entity / task",
        line.text(),
    )

    # --- the panel ------------------------------------------------------------------------
    open_panel(selector, wait)
    walk.check("panel: the trigger opens it", selector.open, True, selector.open)
    panel = selector.popover()
    for name in ("context-recents", "context-my-tasks", "context-hierarchy"):
        walk.check(
            f"panel: it carries the {name.split('-', 1)[1].replace('-', ' ')} section",
            panel.findChild(QtWidgets.QWidget, name) is not None,
            True,
            None,
        )

    # --- a context from the recents -----------------------------------------------------------
    rows = recent_rows(selector)
    walk.check("recents: the two contexts used before are listed", len(rows) >= 2, ">= 2", len(rows))
    if rows:
        before = line.text()
        click(rows[0])
        wait(500)
        walk.check("recents: choosing one moves the context", line.text() != before, f"not {before}", line.text())
        walk.check("recents: choosing one closes the panel", not selector.open, False, selector.open)
        walk.check("recents: nothing is left standing", not orphans(), [], orphans())
        held = selector.work_context
        walk.check(
            "recents: the line under the demo says what was chosen",
            (held.project.name if held.project else "") in line.text(),
            held.project.name if held.project else "",
            line.text(),
        )
        open_panel(selector, wait)
        walk.check(
            "recents: the context just taken leads them",
            bool(selector.recents) and selector.recents[0] == held,
            held,
            selector.recents[0] if selector.recents else None,
        )

    # --- a task of one person's own -------------------------------------------------------------
    open_panel(selector, wait)
    tasks = selector.tasks_control()
    wait_for(lambda: not tasks.loading, wait)
    walk.check("my tasks: the person's tasks are listed", len(tasks.items) > 0, "> 0", len(tasks.items))
    row = task_row(selector)
    walk.check("my tasks: they are grouped under their project", row > 0, "> 0", row)
    if row >= 0:
        before = line.text()
        walk.check("my tasks: a task is taken with the mouse", click_row(tasks.list_surface(), row), True, False)
        wait(500)
        walk.check("my tasks: the pick moves the context", line.text() != before, f"not {before}", line.text())
        walk.check("my tasks: the pick closes the panel", not selector.open, False, selector.open)
        walk.check(
            "my tasks: the context carries a task",
            selector.work_context.task is not None,
            "a task",
            selector.work_context.task,
        )

    # --- browse the tree ---------------------------------------------------------------------------
    open_panel(selector, wait)
    tree = selector.tree()
    control = tree.search_control()
    wait_for(lambda: not control.loading, wait)
    walk.check("browse: the tree lists the project's level", control.list_surface().row_count() > 0, "> 0", control.list_surface().row_count())
    deep = tree.level_path
    opened = -1
    for candidate in range(control.list_surface().row_count()):
        found = tree._model.row_at(candidate)
        if getattr(found, "has_children", False) and not getattr(found, "up", False):
            opened = candidate
            break
    walk.check("browse: a row that opens a level is offered", opened >= 0, "a row", opened)
    if opened >= 0:
        click_row(control.list_surface(), opened)
        wait_for(lambda: not control.loading, wait)
        wait(400)
        walk.check("browse: the level moved", tree.level_path != deep, f"not {deep}", tree.level_path)
        # And a leaf under it takes the whole path as the context.
        leaf = -1
        for candidate in range(control.list_surface().row_count()):
            found = tree._model.row_at(candidate)
            if getattr(found, "selectable", False) and getattr(found, "ref", None) is not None:
                leaf = candidate
                break
        if leaf < 0:
            for candidate in range(control.list_surface().row_count()):
                found = tree._model.row_at(candidate)
                if getattr(found, "has_children", False) and not getattr(found, "up", False):
                    click_row(control.list_surface(), candidate)
                    wait_for(lambda: not control.loading, wait)
                    wait(400)
                    break
            for candidate in range(control.list_surface().row_count()):
                found = tree._model.row_at(candidate)
                if getattr(found, "selectable", False) and getattr(found, "ref", None) is not None:
                    leaf = candidate
                    break
        walk.check("browse: a leaf is reachable", leaf >= 0, "a leaf", leaf)
        if leaf >= 0:
            before = line.text()
            click_row(control.list_surface(), leaf)
            wait(600)
            walk.check("browse: the leaf moves the context", line.text() != before, f"not {before}", line.text())
            walk.check("browse: the pick closes the panel", not selector.open, False, selector.open)
            walk.check("browse: nothing is left standing", not orphans(), [], orphans())

    # --- Escape closes the panel ------------------------------------------------------------------------
    open_panel(selector, wait)
    key(selector.tree().search_control().input(), QtCore.Qt.Key.Key_Escape)
    wait(500)
    walk.check("panel: Escape closes it", not selector.open, False, selector.open)
    walk.check("panel: nothing is left standing", not orphans(), [], orphans())

    # --- searching the tree from the panel -------------------------------------------------------------------
    open_panel(selector, wait)
    control = selector.tree().search_control()
    type_into(control.input(), "sh010", wait)
    wait_for(lambda: not control.loading, wait)
    wait(300)
    walk.check("browse: a query answers rows", len(control.items) > 0, "> 0", len(control.items))
    key(control.input(), QtCore.Qt.Key.Key_Escape)
    wait(250)
    walk.same("browse: the first Escape clears the query", "", control.query)
    key(control.input(), QtCore.Qt.Key.Key_Escape)
    wait(500)
    walk.check("browse: the second Escape closes the panel", not selector.open, False, selector.open)

    # --- the sizes ---------------------------------------------------------------------------------------------
    for step in ("sm", "md", "lg"):
        sized = find(f"context-selector-{step}")
        walk.check(f"sizes: the {step} selector stands in the page", sized is not None, True, sized)
        if sized is not None:
            walk.same(f"sizes: it wears {step}", step, sized.size)

    # --- the header ---------------------------------------------------------------------------------------------
    scroll_to(page, selector, wait)
    open_panel(selector, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open panel up", selector.open, True, selector.open)
    # The panel's three sections in dark. The recents block is a scroll area, and a scroll area
    # fills its scrolled widget from the application's palette unless the stylesheet says not to.
    check_ink(walk)
    key(selector.tree().search_control().input(), QtCore.Qt.Key.Key_Escape)
    wait(400)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1600)
    rebuilt = find("context-selector")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the selector wears the size step", "lg", rebuilt.size)
        walk.same("header: the size row keeps its own step", "sm", find("context-selector-sm").size)
        scroll_to(page, rebuilt, wait)
        open_panel(rebuilt, wait)
        walk.check("header: the rebuilt selector still opens", rebuilt.open, True, rebuilt.open)
        walk.check(
            "header: its tasks are read again",
            len(rebuilt.tasks_control().items) > 0,
            "> 0",
            len(rebuilt.tasks_control().items),
        )
        key(rebuilt.tree().search_control().input(), QtCore.Qt.Key.Key_Escape)
        wait(400)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1600)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
