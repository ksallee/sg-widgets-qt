"""project-picker: pick a project, include the archived, and check what the states refuse.

    .venv/bin/python tools/qa.py --page project-picker \
        --drive tools/drives/walk/project-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    case_widget,
    click,
    open_and_type,
    orphans,
    outside_click,
    scroll_to,
    walk_single,
    wear,
)

from sg_widgets_qt.widgets.project_picker import ProjectPicker  # noqa: E402

QUERY = "har"


def picker_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(ProjectPicker) if one.isVisible()]
    return found[index] if index < len(found) else None


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    one = picker_in(page, "single")
    walk_single(walk, page, one, wait, QUERY, "one project")
    walk.check(
        "one project: the query matched the project by name",
        any("Harbour" in row.name for row in one.state.rows),
        "Harbour Lights",
        [row.name for row in one.state.rows],
    )

    # --- archived projects included ------------------------------------------------------
    archived = picker_in(page, "archived")
    scroll_to(page, archived, wait)
    found = open_and_type(archived, wait, "")
    walk.check("archived: the list answers rows", found > 0, "> 0", found)
    plain = open_and_type(one, wait, "")
    walk.check(
        "archived: the list includes what the plain picker offers",
        found >= plain,
        f">= {plain}",
        found,
    )
    outside_click(page, wait)

    # --- a bare reference, resolved on the way in ---------------------------------------------
    bare = picker_in(page, "hydrate")
    scroll_to(page, bare, wait)
    labels = list(bare.control.labels)
    walk.check(
        "hydrate: the bare reference resolved to a name",
        labels and labels[0] == "Harbour Lights",
        "Harbour Lights",
        labels,
    )

    # --- sizes, then disabled, read-only, invalid ----------------------------------------------
    states = case_widget(page, "states")
    inert = [one for one in states.findChildren(ProjectPicker) if one.isVisible()]
    walk.same("states: six controls stand in the example", 6, len(inert))
    if len(inert) == 6:
        scroll_to(page, inert[0], wait)
        walk.same(
            "states: the three heights are sm, md and lg",
            ["sm", "md", "lg"],
            [held.control.size for held in inert[:3]],
        )
        click(inert[3].control)
        wait(150)
        walk.check("states: the disabled picker does not open", not inert[3].control.is_open, False, True)
        click(inert[4].control)
        wait(150)
        walk.check("states: the read-only picker does not open", not inert[4].control.is_open, False, True)
        walk.check("states: the invalid picker is marked invalid", inert[5].control.invalid, True, False)

    # --- the header -----------------------------------------------------------------------------
    scroll_to(page, one, wait)
    click(one.control)
    wait(200)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", one.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = picker_in(page, "single")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        found = open_and_type(rebuilt, wait, QUERY)
        walk.check("header: the rebuilt picker still searches", found > 0, "> 0", found)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
