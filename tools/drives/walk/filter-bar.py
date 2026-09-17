"""filter-bar: open a facet, tick a value, read the pill, and clear the lot.

    .venv/bin/python tools/qa.py --page filter-bar --drive tools/drives/walk/filter-bar.py

Each facet is a pill that opens a checklist of the values under it with their counts. The walk
opens a pill, ticks a value and reads what the pill then names, ticks a second, unticks one, types
in the checklist's own search box, clears one facet from inside it and the rest from Clear all, and
after each tick reads the rows under the bar. The dialog beside the pills is opened and cancelled.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_editors import (  # noqa: E402
    Walk,
    click,
    click_row,
    key,
    popups,
    retype,
    scroll_to,
    set_view,
    wait_for,
)
from qtpy import QtCore, QtWidgets  # noqa: E402

from sg_widgets_core.filter_ux import find_facet  # noqa: E402

STATUS = "sg_status_list"
KIND = "sg_shot_type"


def settled(bar, wait, ms: int = 25000) -> bool:
    """Wait for the bar to finish counting its facets."""
    return wait_for(lambda: not bar.counting, wait, ms)


def counted(results, wait, ms: int = 20000):
    wait_for(lambda: results.count.kind != "counting", wait, ms)
    return results.count


def pill_text(pill) -> str:
    """What the pill's value slot names, the overflow left out."""
    holders = [
        one
        for one in pill.findChildren(QtWidgets.QWidget)
        if one.objectName() == "filter-pill-values"
    ]
    if not holders:
        return ""
    runs = []
    for child in holders[0].findChildren(QtWidgets.QWidget):
        if child.objectName() == "filter-pill-overflow":
            continue
        # A run is a `text()`; a chip and a badge in the same slot name themselves otherwise.
        held = getattr(child, "text", None)
        runs.append(held() if callable(held) else str(held or ""))
    return " ".join(one for one in runs if one)


def surface(pill) -> Any:
    """The checklist inside an open pill."""
    return pill._command.list_surface()  # noqa: SLF001


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0915
    walk = Walk(page, wait, find, prefs)
    demo = find("filter-bar-demo")
    if demo is None:
        return {"verdict": "FAIL the page drew no filter-bar demo"}
    bar = demo.bar
    settled(bar, wait)
    wait(400)
    opening = counted(demo.results, wait)
    walk.check("the rows under the bar were counted", opening.kind == "ready", "ready", opening)

    # --- a facet opened, and a value ticked ---------------------------------------------------
    pill = bar.pill(STATUS)
    walk.check("the status facet draws a pill", pill is not None, True, pill)
    scroll_to(page, pill, wait)
    walk.same("the pill is quiet before anything is ticked", [], bar.selected_of(STATUS))

    click(pill)
    wait(500)
    walk.check("a press opens the checklist", pill.open, True, pill.open)
    walk.check("the checklist stands on a window of its own", popups() != [], "a popover", popups())
    listed = bar.facet_list(STATUS)
    walk.check("the facet counted its values", listed is not None and listed.values, "> 0 values", listed)
    walk.check(
        "every value carries a count",
        all(one.count >= 0 for one in listed.values),
        "a count on each",
        [(one.key, one.count) for one in listed.values][:4],
    )

    first = listed.values[0]
    walk.check("the checklist offers a row to tick", click_row(surface(pill), 0), True, False)
    settled(bar, wait)
    wait(400)
    walk.same("the tick lands on the bar", [first.value], bar.selected_of(STATUS))
    # The bar draws its pills again on every tick, so the pill a walk holds is not the one now
    # standing there: the checklist that stayed up belongs to the new one.
    walk.check("the checklist stays up for a second tick", bar.pill(STATUS).open, True, bar.pill(STATUS).open)
    walk.same("only the one checklist stands over the page", 1, len(popups()))
    narrowed = counted(demo.results, wait)
    walk.check(
        "the rows under the bar narrow",
        narrowed.kind == "ready" and narrowed.total <= opening.total,
        f"<= {opening.total}",
        narrowed,
    )

    # --- a second value ticked, and one unticked -----------------------------------------------
    pill = bar.pill(STATUS)
    if not pill.open:
        click(pill)
        wait(500)
    click_row(surface(pill), 1)
    settled(bar, wait)
    wait(400)
    walk.same("a second tick joins the first", 2, len(bar.selected_of(STATUS)))
    counted(demo.results, wait)

    pill = bar.pill(STATUS)
    if not pill.open:
        click(pill)
        wait(500)
    click_row(surface(pill), 1)
    settled(bar, wait)
    wait(400)
    walk.same("pressing a ticked row unticks it", 1, len(bar.selected_of(STATUS)))

    # --- the pill names what it holds -------------------------------------------------------------
    pill = bar.pill(STATUS)
    walk.check(
        "the pill names the value it holds",
        bool(pill_text(pill)) or bool(pill.accessibleName()),
        "a name",
        (pill_text(pill), pill.accessibleName()),
    )

    # --- the checklist's own search box -------------------------------------------------------------
    if not pill.open:
        click(pill)
        wait(500)
    rows = surface(pill).model().rowCount()
    retype(pill._command.input(), "zzzz")  # noqa: SLF001
    wait(400)
    walk.check(
        "a query with no match empties the checklist",
        surface(pill).model().rowCount() < rows,
        f"< {rows}",
        surface(pill).model().rowCount(),
    )
    retype(pill._command.input(), "")  # noqa: SLF001
    wait(400)
    walk.same("clearing the query brings every value back", rows, surface(pill).model().rowCount())

    # --- the facet cleared from inside its own checklist -----------------------------------------------
    walk.check("a facet holding a value offers to clear it", pill._clear.isVisible(), True, False)  # noqa: SLF001
    click(pill._clear)  # noqa: SLF001
    settled(bar, wait)
    wait(400)
    walk.same("clearing the facet unticks everything under it", [], bar.selected_of(STATUS))
    key(bar.pill(STATUS), QtCore.Qt.Key.Key_Escape)
    wait(400)
    walk.check("Escape closes the checklist", not bar.pill(STATUS).open, False, True)
    walk.same("nothing was left standing over the page", [], popups())

    # --- two facets ticked, then Clear all --------------------------------------------------------------
    for name in (STATUS, KIND):
        one = bar.pill(name)
        scroll_to(page, one, wait)
        click(one)
        wait(500)
        click_row(surface(one), 0)
        settled(bar, wait)
        wait(300)
        key(bar.pill(name), QtCore.Qt.Key.Key_Escape)
        wait(300)
    walk.check("the status facet holds a value", bar.selected_of(STATUS), "a value", bar.selected_of(STATUS))
    walk.check("the Kind facet holds a value", bar.selected_of(KIND), "a value", bar.selected_of(KIND))
    counted(demo.results, wait)

    clear_all = bar.clear_all_button()
    walk.check("a bar holding facets offers Clear all", clear_all.isVisible(), True, False)
    click(clear_all)
    settled(bar, wait)
    wait(400)
    walk.check(
        "Clear all unticks every facet",
        not any(find_facet(bar.value, name, bar.field_of(name)) for name in bar.facets),
        "nothing ticked",
        {name: bar.selected_of(name) for name in bar.facets},
    )
    back = counted(demo.results, wait)
    walk.same("the rows under the bar go back to the whole set", opening.total, back.total)

    # --- a facet takes the caller's own name ---------------------------------------------------------------
    walk.same("the named facet reads the caller's name", "Kind", bar.label_of(KIND))

    # --- the dialog beside the pills -------------------------------------------------------------------------
    more = bar.more_filters()
    walk.check("the bar carries a launcher for the rest", more is not None, True, more)
    if more is not None:
        scroll_to(page, more, wait)
        click(more.launcher())
        wait(900)
        walk.check("the launcher opens its dialog", more.open, True, more.open)
        cancel = next(
            (
                one
                for one in QtWidgets.QApplication.allWidgets()
                if one.objectName() == "filter-cancel" and one.isVisible()
            ),
            None,
        )
        walk.check("the dialog offers Cancel", cancel is not None, True, cancel)
        if cancel is not None:
            click(cancel)
            wait(900)
        walk.check("Cancel closes it", not more.open, False, more.open)
        walk.same("no dialog was left standing", [], popups())

    # --- the seeded bar, whose pill is capped ------------------------------------------------------------------
    seeded = find("filter-bar-seeded")
    walk.check("the seeded bar stands on the page", seeded is not None, True, seeded)
    if seeded is not None:
        settled(seeded, wait)
        wait(300)
        held = seeded.selected_of(STATUS)
        walk.check("the seeded bar opens on four statuses", len(held) == 4, 4, len(held))
        capped = seeded.pill(STATUS)
        overflow = [
            one
            for one in capped.findChildren(QtWidgets.QWidget)
            if one.objectName() == "filter-pill-overflow"
        ]
        walk.check("the capped pill reads the rest as a count", overflow, "a +n", overflow)
        if overflow:
            walk.same(
                "the count is what the pill did not name",
                f"+{len(held) - seeded.max_values}",
                overflow[0].text(),
            )
        cross = [
            one
            for one in capped.findChildren(QtWidgets.QWidget)
            if one.objectName() == "filter-pill-remove"
        ]
        walk.check("a pill holding values carries a cross", cross, "a cross", cross)
        if cross:
            click(cross[0])
            settled(seeded, wait)
            wait(400)
            walk.same("the pill's cross unticks the whole facet", [], seeded.selected_of(STATUS))

    # --- the view controls ---------------------------------------------------------------------------------------
    missed = set_view(page, wait, theme="dark", size="lg", density="compact")
    walk.same("header: every control moved", [], missed)
    again = find("filter-bar-demo")
    walk.check("header: the demo survived the rebuild", again is not None, True, again)
    if again is not None:
        settled(again.bar, wait)
        wait(400)
        walk.same("header: the bars wear the size step", "lg", again.bar.size)
        walk.same("header: the sizes section keeps the steps it named", "sm", find("filter-bar-sm").size)
        rebuilt = again.bar.pill(STATUS)
        scroll_to(page, rebuilt, wait)
        click(rebuilt)
        wait(500)
        walk.check("header: the rebuilt pill still opens", rebuilt.open, True, rebuilt.open)
        click_row(surface(rebuilt), 0)
        settled(again.bar, wait)
        wait(400)
        walk.check(
            "header: the rebuilt checklist still ticks",
            bool(again.bar.selected_of(STATUS)),
            "a value",
            again.bar.selected_of(STATUS),
        )
        key(again.bar.pill(STATUS), QtCore.Qt.Key.Key_Escape)
        wait(400)
        click(again.bar.clear_all_button())
        settled(again.bar, wait)
        wait(300)
    set_view(page, wait, motion="reduced", palette="nova")
    walk.same("header: reduced motion holds", "reduced", prefs.motion)
    set_view(page, wait, theme="light", size="md", density="default", motion="normal", palette="slate")
    walk.same("header: nothing was left standing over the page", [], popups())
    return walk.result(
        "PASS a pill opens its counted checklist, a value ticks and unticks, the pill names and"
        " caps what it holds, its own search box filters, a facet clears from inside it and Clear"
        " all empties the bar, and the rows under the bar follow every tick"
    )
