"""user-picker: search people by name, address and login, and check what each example scopes to.

    .venv/bin/python tools/qa.py --page user-picker --drive tools/drives/walk/user-picker.py
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

from sg_widgets_qt.widgets.user_picker import UserPicker  # noqa: E402

#: A name, an address and a login the fixtures answer.
NAME = "ada"
ADDRESS = "@example.studio"
LOGIN = "cleo.dias"


def picker_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(UserPicker) if one.isVisible()]
    return found[index] if index < len(found) else None


def names_of(picker) -> list:
    return [row.name for row in picker.state.rows]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- one person or script ---------------------------------------------------------------
    one = picker_in(page, "single")
    walk_single(walk, page, one, wait, NAME, "one person")

    # --- matched on the name, the address or the login ----------------------------------------
    matched = picker_in(page, "by-address")
    scroll_to(page, matched, wait)
    found = open_and_type(matched, wait, NAME)
    walk.check("matching: the name answers rows", found > 0, "> 0", names_of(matched))
    found = open_and_type(matched, wait, ADDRESS)
    walk.check("matching: the address answers rows", found > 0, "> 0", names_of(matched))
    found = open_and_type(matched, wait, LOGIN)
    walk.check(
        "matching: the login answers the one person",
        found > 0 and "Cleo Dias" in names_of(matched),
        "Cleo Dias",
        names_of(matched),
    )
    outside_click(page, wait)

    # --- people only ----------------------------------------------------------------------------
    people = picker_in(page, "people-only")
    scroll_to(page, people, wait)
    open_and_type(people, wait, "")
    walk.check(
        "people only: no script user is offered",
        all(row.type == "HumanUser" for row in people.state.rows),
        "HumanUser only",
        sorted({row.type for row in people.state.rows}),
    )
    outside_click(page, wait)

    # --- inactive people included ----------------------------------------------------------------
    inactive = picker_in(page, "inactive")
    scroll_to(page, inactive, wait)
    open_and_type(inactive, wait, "bo")
    walk.check(
        "inactive: a person whose status is dis is offered",
        "Bo Chen" in names_of(inactive),
        "Bo Chen",
        names_of(inactive),
    )
    outside_click(page, wait)
    # And the picker that does not ask for them leaves them out.
    scroll_to(page, one, wait)
    open_and_type(one, wait, "bo")
    walk.check(
        "inactive: the picker that asks for none leaves them out",
        "Bo Chen" not in names_of(one),
        "no Bo Chen",
        names_of(one),
    )
    outside_click(page, wait)

    # --- a bare reference, resolved on the way in --------------------------------------------------
    bare = picker_in(page, "hydrate")
    scroll_to(page, bare, wait)
    labels = list(bare.control.labels)
    walk.check(
        "hydrate: the bare reference resolved to a name",
        labels and labels[0] == "Cleo Dias",
        "Cleo Dias",
        labels,
    )

    # --- sizes, then disabled, read-only, invalid -----------------------------------------------------
    states = case_widget(page, "states")
    inert = [one for one in states.findChildren(UserPicker) if one.isVisible()]
    walk.same("states: six controls stand in the example", 6, len(inert))
    if len(inert) == 6:
        scroll_to(page, inert[0], wait)
        walk.same("states: the three heights are sm, md and lg", ["sm", "md", "lg"], [one.control.size for one in inert[:3]])
        click(inert[3].control)
        wait(150)
        walk.check("states: the disabled picker does not open", not inert[3].control.is_open, False, True)
        click(inert[4].control)
        wait(150)
        walk.check("states: the read-only picker does not open", not inert[4].control.is_open, False, True)
        walk.check("states: the invalid picker is marked invalid", inert[5].control.invalid, True, False)

    # --- the header --------------------------------------------------------------------------------------
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
        held = case_widget(page, "states")
        sizes = [one.control.size for one in held.findChildren(UserPicker) if one.isVisible()][:3]
        walk.same("header: the three heights stay their own example", ["sm", "md", "lg"], sizes)
        scroll_to(page, rebuilt, wait)
        found = open_and_type(rebuilt, wait, NAME)
        walk.check("header: the rebuilt picker still searches", found > 0, "> 0", found)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
