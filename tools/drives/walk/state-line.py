"""state-line: the line an empty read and a refused one leave, in each place it stands.

    .venv/bin/python tools/qa.py --page state-line --drive tools/drives/walk/state-line.py

The line is display, so what the page invites is reading it: the two states in a popup list, the
same pair in a table body, and the one under rows already drawn. Each says what happened in words
and carries a mark beside them, and each takes the padding the place it stands in asks for.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import Walk, case_widget, popups, set_view  # noqa: E402

from sg_widgets_qt.widgets.state_line import StateLine  # noqa: E402


def lines_in(page, case: str) -> list:
    holder = case_widget(page, case)
    return list(holder.findChildren(StateLine)) if holder is not None else []


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    demo = find("state-line-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no state-line demo"}
    wait(300)

    every = list(demo.lines)
    walk.check("the page draws lines", len(every) >= 5, ">= 5", len(every))
    walk.check(
        "every line says what happened",
        all(one.label for one in every),
        "a label on each",
        [one.state for one in every if not one.label],
    )
    walk.check(
        "every line carries a mark beside the words",
        all(one.icon for one in every),
        "a glyph on each",
        [one.label for one in every if not one.icon],
    )
    walk.check(
        "every line is drawn",
        all(one.height() > 0 and one.width() > 0 for one in every),
        "room for each",
        [(one.label, one.width(), one.height()) for one in every if one.height() <= 0],
    )

    # --- in a popup list -----------------------------------------------------------------------
    popover = lines_in(page, "popover")
    walk.same("the popup example holds both states", 2, len(popover))
    walk.same("the two states are the empty one and the refused one", ["empty", "error"], [one.state for one in popover])
    walk.check(
        "each takes the padding a popup asks for",
        all(one.pad == "popover" for one in popover),
        "popover",
        [one.pad for one in popover],
    )
    walk.same("the empty one says nothing matched", "No department matches", popover[0].label)
    walk.same("the refused one says the read was refused", "The read was refused", popover[1].label)

    # --- in a table body --------------------------------------------------------------------------
    table = lines_in(page, "table")
    walk.same("the table example holds both states", 2, len(table))
    walk.check(
        "each takes the padding a table body asks for",
        all(one.pad == "table" for one in table),
        "table",
        [one.pad for one in table],
    )
    walk.check(
        "a line in a table body stands taller than one in a popup",
        min(one.height() for one in table) > max(one.height() for one in popover),
        "taller",
        ([one.height() for one in table], [one.height() for one in popover]),
    )

    # --- under rows already drawn ---------------------------------------------------------------------
    under = find("state-line-page-error")
    walk.check("the page-error line stands under the rows", under is not None, True, under)
    if under is not None:
        walk.same("it names itself so a drive can find it", "state-line-page-error", under.objectName())
        walk.same("it is the refused state", "error", under.state)
        walk.same("it says the next page did not arrive", "The next page did not arrive", under.label)
        walk.same("it takes no padding of its own", "none", under.pad)

    # --- the states can be swapped in place -------------------------------------------------------------
    one = popover[0]
    one.apply_state("error", message="The site said no.")
    wait(200)
    walk.same("a line takes another state in place", "error", one.state)
    walk.same("and says the message it was handed", "The site said no.", one.label)
    one.apply_state("empty")
    wait(200)
    walk.same("and goes back", "empty", one.state)

    # --- the view controls ----------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("state-line-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        rebuilt = list(again.lines)
        walk.check("header: the lines came back", len(rebuilt) >= 5, ">= 5", len(rebuilt))
        walk.check(
            "header: the lines wear the size step",
            all(one.size == "lg" for one in rebuilt),
            "lg",
            sorted({one.size for one in rebuilt}),
        )
        walk.check(
            "header: each still says what happened",
            all(one.label for one in rebuilt),
            "a label on each",
            [one.state for one in rebuilt if not one.label],
        )
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS both states say what happened and carry a mark, each takes the padding the place it"
        " stands in asks for, the line under rows names itself, a line takes another state in"
        " place, and the page follows the view controls"
    )
