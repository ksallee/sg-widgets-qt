"""search-control: type a query, page it, pick a row, and read the two states beside it.

    .venv/bin/python tools/qa.py --page search-control \
        --drive tools/drives/walk/search-control.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click_row,
    key,
    scroll_to,
    type_into,
    wait_for,
    wear,
    wheel,
)
from qtpy import QtCore  # noqa: E402


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    query = find("search-control-query")
    bare = find("search-control-bare")
    failing = find("search-control-error")
    picked = find("demo-picked")

    # --- a query, debounced, paged and picked -------------------------------------------
    scroll_to(page, query, wait)
    type_into(query.input(), "a", wait)
    wait(120)
    walk.check("query: typing starts a read", query.loading or query.items, True, query.view)
    wait_for(lambda: not query.loading, wait)
    walk.check("query: the read answers rows", len(query.items) > 0, "> 0", len(query.items))
    walk.same("query: a page is four rows", 4, len(query.items))
    walk.check("query: a further page is offered", query.has_more, True, query.has_more)

    surface = query.list_surface()
    walk.check(
        "query: the load-more row stands under the rows",
        surface.load_more_visible(),
        True,
        surface.load_more_visible(),
    )

    # Enter on the load-more row asks for the next page.
    held = len(query.items)
    surface.set_highlight(surface.row_count() - 1)
    walk.check(
        "query: the cursor reaches the load-more row",
        surface.is_load_more(surface.highlighted()),
        True,
        surface.highlighted(),
    )
    key(query.input(), QtCore.Qt.Key.Key_Return)
    wait_for(lambda: not query.loading and len(query.items) > held, wait)
    walk.check(
        "query: Enter on the load-more row lands a page",
        len(query.items) > held,
        f"> {held}",
        len(query.items),
    )
    walk.same("query: the cursor took the first row of the new page", held, surface.highlighted())

    # The wheel belongs to the list while it has somewhere to go, and to the page after that.
    held = len(query.items)
    bar = surface.verticalScrollBar()
    behind = page.scroll.verticalScrollBar().value()
    bar.setValue(0)
    wait(100)
    wheel(surface.viewport(), -3)
    wait(200)
    walk.check("query: the wheel scrolls the list", bar.value() > 0, "> 0", bar.value())
    walk.same("query: and leaves the page behind it where it was", behind, page.scroll.verticalScrollBar().value())
    for _ in range(6):
        wheel(surface.viewport(), -3)
        wait(80)
    walk.check(
        "query: a gesture that reaches the end keeps the wheel off the page",
        page.scroll.verticalScrollBar().value() == behind,
        behind,
        page.scroll.verticalScrollBar().value(),
    )
    if query.has_more:
        bar.setValue(bar.maximum())
        wait(150)
        surface.set_highlight(surface.row_count() - 1)
        key(query.input(), QtCore.Qt.Key.Key_Return)
        wait_for(lambda: not query.loading and len(query.items) > held, wait)
        walk.check(
            "query: the list pages again from the bottom",
            len(query.items) > held,
            f"> {held}",
            len(query.items),
        )

    # A row picked with the mouse writes the readout under the example.
    before = picked.text()
    walk.check("query: a row is picked with the mouse", click_row(surface, 1), True, False)
    wait(250)
    walk.check(
        "query: the pick reaches the demo's readout",
        picked.text() not in ("", "Nothing yet") and picked.text() != before,
        "a name",
        picked.text(),
    )

    # A row picked from the keyboard writes it too.
    before = picked.text()
    surface.set_highlight(0)
    key(query.input(), QtCore.Qt.Key.Key_Down)
    key(query.input(), QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.check(
        "query: Enter on a row picks it",
        picked.text() and picked.text() != "Nothing yet",
        "a name",
        picked.text(),
    )

    # A query nothing answers draws the empty line.
    type_into(query.input(), "zzzqqq", wait)
    wait_for(lambda: not query.loading and query.view == "empty", wait)
    walk.same("query: a query nothing matches draws the empty line", "empty", query.view)
    query.input().clear()
    wait_for(lambda: not query.loading, wait)

    # --- no query: one read, the same list ----------------------------------------------
    scroll_to(page, bare, wait)
    wait_for(lambda: not bare.loading, wait)
    walk.check("bare: the list read itself", len(bare.items) > 0, "> 0", len(bare.items))
    walk.check("bare: the bare shell has no search box", bare.input() is None, None, bare.input())
    before = picked.text()
    walk.check("bare: a row takes a click", click_row(bare.list_surface(), 0), True, False)
    wait(200)

    # --- a read that failed --------------------------------------------------------------
    scroll_to(page, failing, wait)
    wait_for(lambda: not failing.loading, wait)
    walk.same("error: the failed read draws the error line", "error", failing.view)
    walk.check("error: the failure is carried", bool(failing.failure), "a message", failing.failure)

    # --- the header -----------------------------------------------------------------------
    wear(prefs, wait, theme="dark")
    walk.same("header: the page wears dark", "dark", prefs.theme)
    wear(prefs, wait, size="lg", density="compact", palette="nova", settle=900)
    rebuilt = find("search-control-query")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        wait_for(lambda: not rebuilt.loading, wait)
        walk.same("header: the control wears the size step", "lg", rebuilt.size)
        type_into(rebuilt.input(), "ir", wait)
        wait_for(lambda: not rebuilt.loading, wait)
        walk.check(
            "header: the rebuilt control still reads",
            len(rebuilt.items) > 0,
            "> 0",
            len(rebuilt.items),
        )
    wear(prefs, wait, theme="light", size="md", density="default", palette="slate", settle=900)
    return walk.result()
