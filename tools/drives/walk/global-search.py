"""global-search: open the palette by its trigger and its hotkey, search the site, take a row.

    .venv/bin/python tools/qa.py --page global-search \
        --drive tools/drives/walk/global-search.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    arm,
    click,
    click_row,
    key,
    orphans,
    scroll_to,
    type_into,
    wait_for,
    wear,
)
from qtpy import QtCore  # noqa: E402

#: A run the shot names of the fixtures answer.
QUERY = "sh010"


def control_of(one):
    return one.search_control()


def settled(one, wait) -> bool:
    return wait_for(lambda: not control_of(one).loading, wait)


def first_row(one) -> int:
    """The first row that is a row: the list groups its hits under a heading each."""
    from sg_widgets_qt.primitives.roles import Roles

    model = one.search_control().list_surface().model()
    for row in range(model.rowCount()):
        if model.index(row, 0).data(Roles.KIND) != "heading":
            return row
    return -1


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    arm(page, wait)
    palette = find("global-search-palette")
    inline = find("global-search-inline")
    anatomy = find("global-search-anatomy")
    picked = find("demo-picked")

    # --- the palette, opened by its trigger --------------------------------------------------
    scroll_to(page, palette, wait)
    trigger = palette.trigger()
    walk.check("palette: a trigger stands in the page", trigger is not None, "a trigger", trigger)
    walk.check("palette: it names its hotkey", "." in (trigger.hint or ""), "the hotkey", trigger.hint)
    click(trigger)
    wait(400)
    walk.check("palette: the trigger opens it", palette.open, True, palette.open)
    walk.check(
        "palette: the recents are there before a word is typed",
        control_of(palette).list_surface().row_count() > 0,
        "> 0",
        control_of(palette).list_surface().row_count(),
    )

    # Escape closes it.
    key(control_of(palette).input(), QtCore.Qt.Key.Key_Escape)
    wait(400)
    walk.check("palette: Escape closes it", not palette.open, False, palette.open)
    walk.check("palette: nothing is left standing", not orphans(), [], orphans())

    # --- the hotkey ----------------------------------------------------------------------------
    # The dialog took the activation while it was up, so the window is asked for it again: a
    # shortcut is only delivered to the active window.
    window = arm(page, wait)
    key(window, QtCore.Qt.Key.Key_Period, QtCore.Qt.KeyboardModifier.ControlModifier)
    wait(500)
    walk.check("palette: the hotkey opens it", palette.open, True, palette.open)

    # --- search the site and take a row ------------------------------------------------------------
    box = control_of(palette).input()
    walk.check("palette: the palette carries a search box", box is not None, "a box", box)
    if box is not None:
        type_into(box, QUERY, wait)
        settled(palette, wait)
        walk.check(
            "palette: the query answers rows",
            len(control_of(palette).items) > 0,
            "> 0",
            len(control_of(palette).items),
        )
        before = picked.text()
        row = first_row(palette)
        walk.check("palette: a row is taken with the mouse", row >= 0 and click_row(control_of(palette).list_surface(), row), True, row)
        wait(400)
        walk.check(
            "palette: the pick reaches the readout",
            picked.text() != before and picked.text().startswith("Selected"),
            "Selected …",
            picked.text(),
        )
        walk.check("palette: the pick closes it", not palette.open, False, palette.open)
        walk.same("palette: the query is cleared after a pick", "", control_of(palette).query)

        # And the row just taken leads the recents next time.
        window = arm(page, wait)
        key(window, QtCore.Qt.Key.Key_Period, QtCore.Qt.KeyboardModifier.ControlModifier)
        wait(500)
        walk.check("palette: it opens again on the hotkey", palette.open, True, palette.open)
        walk.check(
            "palette: the row just taken leads the recents",
            bool(palette.recents) and picked.text().endswith(palette.recents[0].name or ""),
            "the row just taken",
            (picked.text(), [ref.name for ref in palette.recents]),
        )
        key(control_of(palette).input(), QtCore.Qt.Key.Key_Escape)
        wait(400)

    # --- inline, scoped to one project ----------------------------------------------------------------
    scroll_to(page, inline, wait)
    walk.check("inline: it stands in the page rather than behind a trigger", inline.trigger() is None, None, inline.trigger())
    box = control_of(inline).input()
    type_into(box, QUERY, wait)
    settled(inline, wait)
    walk.check("inline: the query answers rows", len(control_of(inline).items) > 0, "> 0", len(control_of(inline).items))
    before = picked.text()
    surface = control_of(inline).list_surface()
    surface.set_highlight(first_row(inline))
    key(box, QtCore.Qt.Key.Key_Down)
    key(box, QtCore.Qt.Key.Key_Return)
    wait(400)
    walk.check(
        "inline: Enter takes the highlighted row",
        picked.text() != before and picked.text().startswith("Selected"),
        "Selected …",
        picked.text(),
    )
    walk.same("inline: the query is cleared after a pick", "", control_of(inline).query)

    # --- the row props ----------------------------------------------------------------------------------
    from sg_widgets_qt.primitives.roles import Roles

    scroll_to(page, anatomy, wait)
    box = control_of(anatomy).input()
    type_into(box, QUERY, wait)
    settled(anatomy, wait)
    walk.check("row props: the query answers rows", len(control_of(anatomy).items) > 0, "> 0", len(control_of(anatomy).items))
    model = control_of(anatomy).list_surface().model()
    row = first_row(anatomy)
    index = model.index(row, 0)
    walk.check(
        "row props: a description stands under the label",
        bool(index.data(Roles.SUB_LABEL)),
        "a description",
        index.data(Roles.SUB_LABEL),
    )
    wait_for(
        lambda: callable(model.index(row, 0).data(Roles.PAINTER))
        or bool(model.index(row, 0).data(Roles.SECONDARY)),
        wait,
    )
    index = model.index(row, 0)
    walk.check(
        "row props: a typed secondary stands on the right",
        callable(index.data(Roles.PAINTER)) or bool(index.data(Roles.SECONDARY)),
        "a status",
        (index.data(Roles.SECONDARY), index.data(Roles.PAINTER)),
    )

    # A query nothing answers draws the empty line.
    type_into(box, "zzzqqq", wait)
    wait_for(lambda: not control_of(anatomy).loading and control_of(anatomy).view == "empty", wait)
    walk.same("row props: a query nothing matches draws the empty line", "empty", control_of(anatomy).view)
    box.clear()
    settled(anatomy, wait)

    # --- the sizes ----------------------------------------------------------------------------------------
    for step in ("sm", "md", "lg"):
        sized = find(f"global-search-{step}")
        walk.check(f"sizes: the {step} palette stands in the page", sized is not None, True, sized)
        if sized is not None:
            walk.same(f"sizes: it wears {step}", step, sized.size)

    # --- the header -----------------------------------------------------------------------------------------
    scroll_to(page, palette, wait)
    click(palette.trigger())
    wait(400)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open palette up", palette.open, True, palette.open)
    key(control_of(palette).input(), QtCore.Qt.Key.Key_Escape)
    wait(400)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = find("global-search-palette")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the palette wears the size step", "lg", rebuilt.size)
        walk.same("header: the size row keeps its own step", "sm", find("global-search-sm").size)
        scroll_to(page, rebuilt, wait)
        click(rebuilt.trigger())
        wait(400)
        walk.check("header: the rebuilt palette still opens", rebuilt.open, True, rebuilt.open)
        type_into(control_of(rebuilt).input(), QUERY, wait)
        settled(rebuilt, wait)
        walk.check("header: it still reads", len(control_of(rebuilt).items) > 0, "> 0", len(control_of(rebuilt).items))
        # The first Escape belongs to the query it holds, the second to the palette.
        key(control_of(rebuilt).input(), QtCore.Qt.Key.Key_Escape)
        wait(250)
        walk.same("header: the first Escape clears the query", "", control_of(rebuilt).query)
        walk.check("header: and leaves the palette up", rebuilt.open, True, rebuilt.open)
        key(control_of(rebuilt).input(), QtCore.Qt.Key.Key_Escape)
        wait(400)
        walk.check("header: the second Escape closes the rebuilt palette", not rebuilt.open, False, rebuilt.open)
        walk.check("header: its dialog goes with it", not orphans(), [], orphans())
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result(reads=dict(page.context.reads) if page.context else {})
