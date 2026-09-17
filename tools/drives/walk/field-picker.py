"""field-picker: drill into a link, walk back, and pick a field of the type it landed on.

    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/walk/field-picker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click,
    click_at,
    click_row,
    key,
    orphans,
    outside_click,
    scroll_to,
    type_into,
    wait_for,
    wear,
)
from qtpy import QtCore  # noqa: E402


def open_list(picker, wait) -> None:
    if not picker.control.is_open:
        click(picker.control)
        wait(250)
    wait_for(lambda: not picker.levels.loading, wait)


def rows_of(picker) -> list:
    return list(picker.levels.rows(picker.control.query))


def drillable_row(picker):
    """The first row that descends into a type of its own, and where its chevron is."""
    for index, option in enumerate(rows_of(picker)):
        if option.traversable:
            return index, option
    return -1, None


def click_drill(picker, row: int) -> bool:
    """Press the chevron of a row, which is the drill rather than the pick."""
    surface = picker.control.list_surface()
    index = surface.model().index(row, 0)
    if not index.isValid():
        return False
    surface.scrollTo(index, surface.ScrollHint.EnsureVisible)
    box = surface.visualRect(index)
    if box.isEmpty():
        return False
    mark = surface.row_delegate().drill_rect(box, index)
    point = mark.center() if not mark.isNull() else QtCore.QPoint(box.right() - 8, box.center().y())
    click_at(surface.viewport(), point)
    return True


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    free = find("field-picker-free")
    value_line = find("field-picker-free-value")

    # --- Version, deep links on ----------------------------------------------------------
    scroll_to(page, free, wait)
    open_list(free, wait)
    walk.check("deep links: a click opens the list", free.control.is_open, True, False)
    walk.check("deep links: the type's own fields are listed", len(rows_of(free)) > 0, "> 0", len(rows_of(free)))

    row, option = drillable_row(free)
    walk.check("deep links: a link row is offered", option is not None, "a link", option)
    if option is not None:
        walk.check("deep links: its chevron takes the press", click_drill(free, row), True, False)
        wait_for(lambda: not free.levels.loading, wait)
        wait(300)
        walk.check(
            "deep links: the press descends a level",
            free.levels.deep or free.levels.choosing is not None,
            "a level or a type to choose",
            (free.levels.crumbs(), free.levels.choosing),
        )
        # A link naming several types asks which one first; the first row answers it.
        if free.levels.choosing is not None:
            walk.check("deep links: it asks which type", bool(free.levels.targets()), "targets", free.levels.targets())
            walk.check("deep links: the type is chosen", click_row(free.control.list_surface(), 0), True, False)
            wait_for(lambda: not free.levels.loading, wait)
            wait(300)
        walk.check("deep links: the list now stands on the linked type", free.levels.deep, True, free.levels.deep)
        walk.check("deep links: the crumb says where it stands", bool(free.levels.crumbs()), "a crumb", free.levels.crumbs())
        walk.check(
            "deep links: the linked type's own fields are listed",
            len(rows_of(free)) > 0,
            "> 0",
            len(rows_of(free)),
        )

        # A field of that level is picked, and the value is the dotted path.
        picked = next((i for i, one in enumerate(rows_of(free)) if one.selectable), -1)
        if picked >= 0:
            walk.check("deep links: a field of that level is picked", click_row(free.control.list_surface(), picked), True, False)
            wait(350)
            walk.check(
                "deep links: the value is the dotted path",
                "." in free.value,
                "a dotted path",
                free.value,
            )
            walk.check(
                "deep links: the readout under the example follows",
                value_line.text() == free.value,
                free.value,
                value_line.text(),
            )
            walk.check(
                "deep links: the control reads the friendly path",
                bool(free.label) and free.label != free.value,
                "a friendly path",
                (free.label, free.value),
            )

    # Left walks back out of a level.
    open_list(free, wait)
    row, option = drillable_row(free)
    if option is not None:
        click_drill(free, row)
        wait_for(lambda: not free.levels.loading, wait)
        wait(250)
        if free.levels.choosing is not None:
            click_row(free.control.list_surface(), 0)
            wait_for(lambda: not free.levels.loading, wait)
            wait(250)
        deep = list(free.levels.crumbs())
        key(free.control.caret(), QtCore.Qt.Key.Key_Left)
        wait(350)
        walk.check(
            "deep links: Left walks back out of the level",
            len(free.levels.crumbs()) < len(deep),
            f"fewer than {deep}",
            free.levels.crumbs(),
        )
    key(free.control.caret(), QtCore.Qt.Key.Key_Escape)
    wait(250)
    walk.check("deep links: Escape closes the list", not free.control.is_open, False, True)

    # --- restricted to dates ----------------------------------------------------------------
    dates = find("field-picker-dates")
    scroll_to(page, dates, wait)
    open_list(dates, wait)
    offered = rows_of(dates)
    walk.check("dates: the list answers rows", len(offered) > 0, "> 0", len(offered))
    walk.check(
        "dates: only dates can be chosen, links stay for the walk",
        all(one.traversable or one.data_type in ("date", "date_time") for one in offered),
        "dates and links",
        sorted({one.data_type for one in offered}),
    )
    outside_click(page, wait)

    # --- a dotted value ------------------------------------------------------------------------
    preset = find("field-picker-preset")
    scroll_to(page, preset, wait)
    walk.same("dotted value: the raw path is held", "entity.Shot.sg_turnover_date", preset.value)
    walk.check(
        "dotted value: it reads as its friendly path",
        preset.label and preset.label != preset.value and "." not in preset.label,
        "a friendly path",
        preset.label,
    )

    # --- filterable types only ---------------------------------------------------------------------
    computed = find("field-picker-computed")
    scroll_to(page, computed, wait)
    open_list(computed, wait)
    names = [one.path for one in rows_of(computed)]
    walk.check(
        "computed: the two computed columns are offered",
        "row_number" in names and "note_count" in names,
        "row_number and note_count",
        [name for name in names if name in ("row_number", "note_count")],
    )
    walk.check("computed: the hidden path is not", "image" not in names, "no image", "image" in names)
    type_into(computed.control.caret(), "note", wait)
    wait(300)
    walk.check(
        "computed: the query cuts the list down",
        rows_of(computed)
        and all("note" in (one.display_name + one.name).lower() for one in rows_of(computed)),
        "only what matches",
        [one.display_name for one in rows_of(computed)],
    )
    walk.check("computed: a computed column is picked", click_row(computed.control.list_surface(), 0), True, False)
    wait(300)
    walk.check("computed: the pick lands", bool(computed.value), "a path", computed.value)

    # --- fixed options: three paths, flat --------------------------------------------------------------
    fixed = find("field-picker-fixed")
    if fixed is not None:
        scroll_to(page, fixed, wait)
        open_list(fixed, wait)
        walk.check("fixed: the three paths are offered", len(rows_of(fixed)) == 3, 3, len(rows_of(fixed)))
        walk.check(
            "fixed: none of them descends",
            not any(one.traversable for one in rows_of(fixed)),
            "no link to walk",
            [one.path for one in rows_of(fixed) if one.traversable],
        )
        type_into(fixed.control.caret(), "turnover", wait)
        wait(300)
        walk.check(
            "fixed: the search reads the label and the path",
            len(rows_of(fixed)) == 1,
            1,
            [one.path for one in rows_of(fixed)],
        )
        walk.check("fixed: the matched row is picked", click_row(fixed.control.list_surface(), 0), True, False)
        wait(300)
        walk.same("fixed: the pick is the path itself", "entity.Shot.sg_turnover_date", fixed.value)

    # --- sizes, read-only and invalid ------------------------------------------------------------------
    small = find("field-picker-small")
    large = find("field-picker-large")
    readonly = find("field-picker-readonly")
    invalid = find("field-picker-invalid")
    disabled = find("field-picker-disabled")
    walk.same("sizes: the small control wears sm", "sm", small.control.size)
    walk.same("sizes: the large control wears lg", "lg", large.control.size)
    scroll_to(page, readonly, wait)
    click(readonly.control)
    wait(200)
    walk.check("states: the read-only picker does not open", not readonly.control.is_open, False, True)
    click(disabled.control)
    wait(200)
    walk.check("states: the disabled picker does not open", not disabled.control.is_open, False, True)
    walk.check("states: the invalid picker is marked invalid", invalid.control.invalid, True, False)

    # --- the header -------------------------------------------------------------------------------------
    scroll_to(page, free, wait)
    open_list(free, wait)
    wear(prefs, wait, theme="dark")
    walk.check("header: dark leaves the open popup up", free.control.is_open, True, False)
    outside_click(page, wait)
    wear(prefs, wait, palette="nova", size="lg", density="compact", settle=1200)
    rebuilt = find("field-picker-free")
    walk.check("header: the demo survives a rebuild", rebuilt is not None, True, rebuilt)
    if rebuilt is not None:
        walk.same("header: the picker wears the size step", "lg", rebuilt.control.size)
        walk.same("header: the two that name their own height keep it", "sm", find("field-picker-small").control.size)
        scroll_to(page, rebuilt, wait)
        open_list(rebuilt, wait)
        walk.check("header: the rebuilt picker still lists", len(rows_of(rebuilt)) > 0, "> 0", len(rows_of(rebuilt)))
        outside_click(page, wait)
    wear(prefs, wait, theme="light", palette="slate", size="md", density="default", settle=1200)
    walk.check("header: nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
