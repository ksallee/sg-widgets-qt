"""entity-picker: search the site, pick a shot, page the list, and arm a read to fail.

    .venv/bin/python tools/qa.py --page entity-picker \
        --drive tools/drives/walk/entity-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    case_widget,
    click,
    click_row,
    key,
    outside_click,
    scroll_to,
    type_into,
    wait_for,
    wear,
    wheel,
)
from qtpy import QtCore  # noqa: E402

from sg_widgets_qt.widgets.entity_picker import EntityPicker  # noqa: E402

#: A run the shot names of the fixtures answer.
QUERY = "sh"


def picker_in(page, case: str, index: int = 0):
    holder = case_widget(page, case)
    if holder is None:
        return None
    found = [one for one in holder.findChildren(EntityPicker) if one.isVisible()]
    return found[index] if index < len(found) else None


def settled(picker, wait, ms: int = 8000) -> bool:
    return wait_for(lambda: not picker.state.loading, wait, ms)


def rows_for(walk, picker, wait, query: str = QUERY) -> int:
    """Open the picker, type a query, and wait for the rows."""
    control = picker.control
    if not control.is_open:
        click(control)
        wait(150)
    type_into(control.caret(), query, wait)
    settled(picker, wait)
    return len(picker.state.rows)


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)

    # --- one shot, clearable -------------------------------------------------------------
    one = picker_in(page, "single")
    scroll_to(page, one, wait)
    click(one.control)
    wait(200)
    walk.check("single: a click opens the list", one.control.is_open, True, one.control.is_open)
    found = rows_for(walk, one, wait)
    walk.check("single: the query answers rows", found > 0, "> 0", found)

    key(one.control.caret(), QtCore.Qt.Key.Key_Down)
    key(one.control.caret(), QtCore.Qt.Key.Key_Return)
    wait(250)
    walk.check("single: Enter picks the armed row", one.value is not None, "a reference", one.value)
    walk.check(
        "single: the chip carries the row's name",
        bool(one.control.labels and one.control.labels[0]),
        "a name",
        list(one.control.labels),
    )
    walk.check("single: a pick closes the list", not one.control.is_open, False, True)

    click(one.control.clear_control())
    wait(200)
    walk.same("single: the clear control empties the value", None, one.value)

    click(one.control)
    wait(150)
    key(one.control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(200)
    walk.check("single: Escape closes the list", not one.control.is_open, False, True)
    click(one.control)
    wait(150)
    outside_click(page, wait)
    walk.check("single: a press outside closes the list", not one.control.is_open, False, True)

    # --- a status on the right of every row ----------------------------------------------
    from sg_widgets_qt.primitives.roles import Roles

    second = picker_in(page, "status-secondary")
    scroll_to(page, second, wait)
    found = rows_for(walk, second, wait)
    walk.check("status secondary: the query answers rows", found > 0, "> 0", found)
    surface = second.control.list_surface()
    # The field's own schema and the status table land on their own threads, and the column is
    # drawn by the data type, so the badge is what the row carries once they have.
    wait_for(lambda: callable(surface.model().index(0, 0).data(Roles.PAINTER)), wait)
    index = surface.model().index(0, 0)
    walk.check(
        "status secondary: the row draws a status badge on the right",
        callable(index.data(Roles.PAINTER)),
        "a status painter",
        (index.data(Roles.SECONDARY), index.data(Roles.PAINTER)),
    )
    outside_click(page, wait)

    # --- three types in one list ---------------------------------------------------------
    many = picker_in(page, "multi-type")
    scroll_to(page, many, wait)
    found = rows_for(walk, many, wait, "sh")
    walk.check("three types: the query answers rows", found > 0, "> 0", found)
    kinds = {row.type for row in many.state.rows}
    walk.check("three types: more than one type is offered", len(kinds) > 1, "> 1 type", sorted(kinds))
    walk.check("three types: a row is picked with the mouse", click_row(many.control.list_surface(), 0), True, False)
    wait(250)
    walk.check("three types: the pick lands", many.value is not None, "a reference", many.value)

    # --- the id, rendered by the caller ---------------------------------------------------
    own = picker_in(page, "custom-secondary")
    scroll_to(page, own, wait)
    rows_for(walk, own, wait)
    index = own.control.list_surface().model().index(0, 0)
    secondary = index.data(Roles.SECONDARY)
    walk.check(
        "custom secondary: the caller's own text is drawn",
        isinstance(secondary, str) and secondary.startswith("#"),
        "#<id>",
        secondary,
    )
    outside_click(page, wait)

    # --- scoped to one project ------------------------------------------------------------
    scoped = picker_in(page, "project")
    scroll_to(page, scoped, wait)
    found = rows_for(walk, scoped, wait, "hb")
    walk.check("scoped: the project's own rows answer", found > 0, "> 0", found)
    walk.check(
        "scoped: nothing from another project is offered",
        all(row.id >= 884 for row in scoped.state.rows),
        "only the project's shots",
        [row.id for row in scoped.state.rows][:12],
    )
    # A query only the other project answers has nothing to show here.
    type_into(scoped.control.caret(), "sh010", wait)
    settled(scoped, wait)
    walk.same("scoped: a shot of another project is out of scope", 0, len(scoped.state.rows))
    outside_click(page, wait)

    # --- type and id in, name resolved on the way in ---------------------------------------
    bare = picker_in(page, "hydrate")
    scroll_to(page, bare, wait)
    label = list(bare.control.labels)
    walk.check(
        "hydrate: the bare reference resolved to a name",
        label and label[0] and not label[0].startswith("Shot 8"),
        "a name",
        label,
    )
    again = find("hand-in-another")
    walk.check("hydrate: the demo offers another reference", again is not None, True, again)
    if again is not None:
        click(again)
        wait_for(
            lambda: bool(bare.control.labels)
            and bare.control.labels[0]
            and not bare.control.labels[0].startswith("Asset 1229"),
            wait,
        )
        walk.check(
            "hydrate: the second bare reference resolves too",
            bool(bare.control.labels) and not str(bare.control.labels[0]).startswith("Asset 1229"),
            "a name",
            list(bare.control.labels),
        )

    # --- five a page, with a load more row --------------------------------------------------
    paged = picker_in(page, "more")
    scroll_to(page, paged, wait)
    found = rows_for(walk, paged, wait)
    walk.same("paging: a page is five rows", 5, found)
    walk.check("paging: another page is offered", paged.state.has_more, True, paged.state.has_more)
    surface = paged.control.list_surface()
    walk.check(
        "paging: the load-more row stands under the rows",
        surface.load_more_visible(),
        True,
        surface.load_more_visible(),
    )
    held = len(paged.state.rows)
    surface.set_highlight(surface.row_count() - 1)
    key(paged.control.caret(), QtCore.Qt.Key.Key_Return)
    wait_for(lambda: not paged.state.loading and len(paged.state.rows) > held, wait)
    walk.check(
        "paging: Enter on the load-more row lands a page",
        len(paged.state.rows) > held,
        f"> {held}",
        len(paged.state.rows),
    )
    # The wheel over an open popup belongs to the list, never to the page under it.
    behind = page.scroll.verticalScrollBar().value()
    bar = surface.verticalScrollBar()
    bar.setValue(0)
    wait(100)
    for _ in range(6):
        wheel(surface.viewport(), -3)
        wait(80)
    walk.check("paging: the wheel scrolls the list", bar.value() > 0, "> 0", bar.value())
    walk.same(
        "paging: and leaves the page under the popup where it was",
        behind,
        page.scroll.verticalScrollBar().value(),
    )

    # And again from the bottom of the list, the way a wheel gesture ends.
    held = len(paged.state.rows)
    if paged.state.has_more:
        bar.setValue(bar.maximum())
        wait(150)
        surface.set_highlight(surface.row_count() - 1)
        key(paged.control.caret(), QtCore.Qt.Key.Key_Return)
        wait_for(lambda: not paged.state.loading and len(paged.state.rows) > held, wait)
        walk.check(
            "paging: the list pages again from the bottom",
            len(paged.state.rows) > held,
            f"> {held}",
            len(paged.state.rows),
        )
    outside_click(page, wait)

    # --- a read armed to fail ----------------------------------------------------------------
    broken = picker_in(page, "error")
    scroll_to(page, broken, wait)
    arm = find("arm-failure")
    walk.check("error: the demo offers the arming control", arm is not None, True, arm)
    if arm is not None:
        click(arm)
        wait(100)
        click(broken.control)
        wait(150)
        type_into(broken.control.caret(), "sha", wait)
        wait_for(lambda: broken.state.error is not None or not broken.state.loading, wait)
        wait(400)
        walk.check(
            "error: the armed failure reaches the control",
            broken.state.error is not None or broken.control.error,
            "an error",
            (broken.state.error, broken.control.error),
        )
        outside_click(page, wait)

    # --- row anatomy -------------------------------------------------------------------------
    anatomy = case_widget(page, "anatomy")
    pickers = [one for one in anatomy.findChildren(EntityPicker) if one.isVisible()]
    walk.same("anatomy: two pickers stand in the example", 2, len(pickers))
    if len(pickers) == 2:
        scroll_to(page, pickers[1], wait)
        rows_for(walk, pickers[1], wait, "a")
        index = pickers[1].control.list_surface().model().index(0, 0)
        walk.check(
            "anatomy: the version row carries a sub-label",
            bool(index.data(Roles.SUB_LABEL)),
            "a status",
            index.data(Roles.SUB_LABEL),
        )
        walk.check(
            "anatomy: the id is drawn on the right",
            str(index.data(Roles.SECONDARY) or "").strip().isdigit(),
            "the row id",
            index.data(Roles.SECONDARY),
        )
        walk.check(
            "anatomy: no picture stands in the row that asked for none",
            pickers[0].control.list_surface().model().index(0, 0).data(Roles.PIXMAP) is None,
            None,
            "a picture",
        )
        outside_click(page, wait)

    # --- disabled, read-only, invalid -----------------------------------------------------
    states = case_widget(page, "states")
    inert = [one for one in states.findChildren(EntityPicker) if one.isVisible()]
    walk.same("states: three pickers stand in the example", 3, len(inert))
    if len(inert) == 3:
        scroll_to(page, inert[0], wait)
        click(inert[0].control)
        wait(150)
        walk.check("states: the disabled picker does not open", not inert[0].control.is_open, False, True)
        click(inert[1].control)
        wait(150)
        walk.check("states: the read-only picker does not open", not inert[1].control.is_open, False, True)
        walk.check("states: the invalid picker is marked invalid", inert[2].control.invalid, True, False)

    # --- the header -------------------------------------------------------------------------
    scroll_to(page, one, wait)
    click(one.control)
    wait(200)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", one.control.is_open, True, one.control.is_open)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = picker_in(page, "single")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        scroll_to(page, rebuilt, wait)
        found = rows_for(walk, rebuilt, wait)
        walk.check("header: the rebuilt picker still searches", found > 0, "> 0", found)
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    return walk.result(reads=dict(page.context.reads) if page.context else {})
