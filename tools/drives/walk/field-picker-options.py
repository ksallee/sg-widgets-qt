"""field-picker-options: a fixed list of paths is drawn flat, the same way as upstream.

Three rows, no breadcrumb and no descend control; each row is its resolved path with the
leaf's code beside it and its data type under it; the search box narrows the list on the
label and on the path; a pick emits the path the caller wrote.

The port of `tools/drive/field-picker-options.js`.

    .venv/bin/python tools/qa.py --page field-picker --drive tools/drives/walk/field-picker-options.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _walk_pickers import (  # noqa: E402
    Walk,
    click,
    click_row,
    orphans,
    outside_click,
    scroll_to,
    type_into,
    wait_for,
)

from sg_widgets_qt.primitives.roles import Roles  # noqa: E402

#: The path through a link the fixed list carries, and the label it reads as.
LINKED = "entity.Shot.sg_turnover_date"
LINKED_LABEL = "Link › Shot › Turnover Date"


def open_list(picker, wait) -> None:
    if not picker.control.is_open:
        click(picker.control)
        wait(250)
    wait_for(lambda: not picker.levels.loading, wait)


def read(picker, row: int) -> dict:
    """The row as it is drawn: the glyph, the label and its code, the sub-label."""
    model = picker.rows_model
    index = model.index(row, 0)
    return {
        "glyph": model.data(index, Roles.GLYPH),
        "label": model.data(index, Roles.LABEL),
        "code": model.data(index, Roles.CODE),
        "sub": model.data(index, Roles.SUB_LABEL),
        "descend": bool(model.data(index, Roles.DRILLABLE)),
    }


def rows_of(picker) -> list[dict]:
    return [read(picker, row) for row in range(picker.rows_model.rowCount())]


def narrow(picker, query: str, wait) -> list[str]:
    """What the search box leaves, read on its labels."""
    type_into(picker.control.caret(), query, wait)
    wait(300)
    return [row["label"] for row in rows_of(picker)]


def drive(page, wait, find, prefs) -> dict:
    walk = Walk(page, wait, find, prefs)
    fixed = find("field-picker-fixed")
    value_line = find("field-picker-fixed-value")
    walk.check("fixed: the demo carries a fixed list", fixed is not None, "a picker", fixed)
    if fixed is None:
        return walk.result()

    scroll_to(page, fixed, wait)
    open_list(fixed, wait)
    drawn = rows_of(fixed)
    walk.notes["rows"] = drawn

    # --- flat --------------------------------------------------------------------------
    walk.same("flat: the list holds exactly the paths it was given", 3, len(drawn))
    walk.check(
        "flat: no row descends",
        all(not row["descend"] for row in drawn),
        "no chevron",
        [row["label"] for row in drawn if row["descend"]],
    )
    walk.check(
        "flat: the breadcrumb never shows",
        not fixed.breadcrumb.isVisible() and not fixed.levels.deep,
        "no breadcrumb",
        (fixed.breadcrumb.isVisible(), fixed.levels.deep),
    )

    # --- labelled ----------------------------------------------------------------------
    if len(drawn) == 3:
        linked = drawn[2]
        walk.same("labelled: the linked row names the type it travels", LINKED_LABEL, linked["label"])
        walk.same("labelled: show_code puts the leaf's code beside it", "sg_turnover_date", linked["code"])
        walk.same("labelled: the leaf's data type reads under it", "date", linked["sub"])
        walk.same("labelled: the data type's own glyph leads the row", "calendar", linked["glyph"])

    # --- narrowed ----------------------------------------------------------------------
    by_label = narrow(fixed, "turnover", wait)
    walk.same("search: the label narrows the list", [LINKED_LABEL], by_label)
    by_path = narrow(fixed, "entity.Shot", wait)
    walk.same("search: the path behind the row narrows it too", [LINKED_LABEL], by_path)

    # --- picked ------------------------------------------------------------------------
    walk.check("pick: the row takes the press", click_row(fixed.control.list_surface(), 0), True, False)
    wait(350)
    walk.same("pick: the value is the path the caller wrote", LINKED, fixed.value)
    walk.same("pick: the readout carries it", LINKED, value_line.text() if value_line else None)
    walk.same("pick: the closed control reads the resolved path", LINKED_LABEL, fixed.label)
    chips = fixed.control.chips()
    walk.same("pick: the chip reads the same path", LINKED_LABEL, chips[0].text() if chips else None)

    outside_click(page, wait)
    walk.check("nothing is left standing at the end", not orphans(), [], orphans())
    return walk.result()
