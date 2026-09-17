"""Every value control the editor can draw, measured against a one-line row.

The port of `~/dev/sg-widgets/tools/drives/filter-editor-stress.js`.

    .venv/bin/python tools/qa.py --page filter-editor --viewport 2200x1600 \\
        --drive tools/drives/filter-editor-stress.py

The editor is pinned to exactly 800, 1000 and 1200px and every row is built through the editor's
own handlers: the field picker's `pick_field` chooses a field of the data type and the operator
select's `pick_preset` names every entry that type offers, so the matrix is whatever `presets_for`
allows. A combination passes when the row is as tall as the `Version Name is` row at the same
width. Nothing is allowed to wrap: the row's remove control sits on its own axis, so every width
the field, operator and value fit in is a one-line row.

`url` is not filterable, so the field list never offers it: no operator, no value. The drive
asserts it is absent rather than measuring it.

The run leaves each row on its widest preset at 1000px, which is what the screenshot takes.
"""
from __future__ import annotations

import time

from sg_widgets_core.filter import condition, group
from sg_widgets_core.filter_ux import field_operators, operator_menu
from sg_widgets_qt.widgets.filter_editor import FilterEditor

#: The widths the stage is pinned to.
WIDTHS: tuple[int, ...] = (800, 1000, 1200)

#: Combinations allowed to stand one step over the baseline, at any width.
#:
#: A colour's swatch is the square of the control beside it, `size-9` at md upstream as here,
#: so a colour row is a step taller than every other one on the web too. Upstream's own list
#: leaves `color` out rather than allowing it; this one measures it and says so.
ALLOWED_TO_WRAP: tuple[str, ...] = ("color|is", "color|is_not")

#: The preset each type is left on for the screenshot, the widest one it offers.
WIDEST: tuple[str, ...] = ("between", "in_last", "in", "name_contains", "is", "is_empty")

#: One field per filterable data type. `percent`, `duration`, `date` and `timecode` are not on
#: Version itself and are reached through Link, which is what a person does.
FIELDS: tuple[tuple[str, str], ...] = (
    ("text", "code"),
    ("number", "sg_first_frame"),
    ("float", "sg_uploaded_movie_frame_rate"),
    ("checkbox", "client_approved"),
    ("date_time", "created_at"),
    ("list", "sg_version_type"),
    ("status_list", "sg_status_list"),
    ("entity", "entity"),
    ("multi_entity", "playlists"),
    ("image", "image"),
    ("color", "sg_bar_color"),
    ("percent", "entity.Shot.sg_complexity"),
    ("duration", "entity.Shot.sg_working_duration"),
    ("date", "entity.Shot.sg_turnover_date"),
    ("timecode", "entity.Shot.sg_sequence.Sequence.sg_timecode"),
)

#: A field of a type the API refuses to filter on, which the list must not offer.
UNFILTERABLE = "sg_uploaded_movie"


def wait_for(read, wait, ms: int = 8000) -> bool:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        wait(50)
        if read():
            return True
    return False


def rows_of(editor: FilterEditor) -> list:
    return editor.rows()


def set_width(editor: FilterEditor, width: int, wait) -> None:
    """Pin the editor to a width, as upstream pins the stage's grid columns."""
    editor.setFixedWidth(width)
    editor.updateGeometry()
    wait(60)


def drive(page, wait, find, prefs) -> dict:  # noqa: C901, PLR0912, PLR0915
    wait(600)
    editor = find("filter-editor-main")
    if not isinstance(editor, FilterEditor):
        every = find(FilterEditor, all=True)
        editor = every[0] if every else None
    if editor is None:
        return {"verdict": "FAIL the page has no filter editor"}
    wait_for(lambda: editor.fields(), wait, 8000)
    wait(300)

    failures: list[dict] = []
    table: list[str] = []

    # `url` is not filterable, so the list never offers it.
    fields = editor.fields()
    url_field = fields.get(UNFILTERABLE)
    url_offered = url_field is not None and bool(field_operators(url_field))
    if url_offered:
        failures.append({"type": "url", "preset": "-", "why": "the field list offers a url field"})

    # The tree the matrix stands on is two rows: the `Version Name is` baseline and the row
    # under test. A rebuild costs one row rather than fourteen, so the run is a minute and not
    # an hour, and the result set under the editor is left out of it.
    editor.blockSignals(True)
    editor.set_value(group("and", [condition("code", "is", ""), condition("", "is", "")]))
    wait(300)
    baseline: dict[int, int] = {}
    for width in WIDTHS:
        set_width(editor, width, wait)
        baseline[width] = rows_of(editor)[0].height()

    measured: list[dict] = []
    widest_of: dict[str, str] = {}
    for data_type, path in FIELDS:
        editor.set_value(
            group("and", [condition("code", "is", ""), condition("", "is", "")])
        )
        wait(80)
        node = editor.node_at([1])
        editor.pick_field([1], node, path)
        landed = wait_for(
            lambda p=path, n=node: (editor.node_at([1]) or n).path == p, wait, 8000
        )
        if not landed:
            failures.append({"type": data_type, "preset": "-", "why": f"{path} never landed"})
            continue
        if editor.data_type_of(path) != data_type:
            failures.append(
                {
                    "type": data_type,
                    "preset": "-",
                    "why": f"{path} reads as {editor.data_type_of(path)!r}",
                }
            )
        field = editor.field_of(path)
        presets = [
            preset.id
            for run in operator_menu(data_type, field_operators(field))
            for preset in run.presets
        ]
        if not presets:
            failures.append({"type": data_type, "preset": "-", "why": "the menu offers nothing"})
            continue
        widest_of[path] = next((one for one in WIDEST if one in presets), presets[-1])
        for preset_id in presets:
            editor.pick_preset([1], editor.node_at([1]), preset_id)
            wait(60)
            heights: dict[int, int] = {}
            for width in WIDTHS:
                set_width(editor, width, wait)
                rows = rows_of(editor)
                heights[width] = rows[1].height() if len(rows) > 1 else -1
            measured.append({"type": data_type, "preset": preset_id, "heights": heights})
            marks = [
                f"{w}:{'wrapped' if heights[w] > baseline[w] + 1 else 'one'}" for w in WIDTHS
            ]
            table.append(f"{data_type} {preset_id} {' '.join(marks)}")
            for width in WIDTHS:
                if heights[width] <= baseline[width] + 1:
                    continue
                if f"{data_type}|{preset_id}" in ALLOWED_TO_WRAP:
                    continue
                failures.append(
                    {
                        "type": data_type,
                        "preset": preset_id,
                        "width": width,
                        "height": heights[width],
                        "baseline": baseline[width],
                    }
                )

    # The screenshot takes the widest row of every type, on one tree, at 1000px.
    editor.set_value(
        group(
            "and",
            [
                condition(path, "is", "")
                for _kind, path in FIELDS
                if path in widest_of
            ],
        )
    )
    wait(400)
    for i, (_kind, path) in enumerate(
        [one for one in FIELDS if one[1] in widest_of]
    ):
        editor.pick_preset([i], editor.node_at([i]), widest_of[path])
        wait(40)
    editor.blockSignals(False)
    set_width(editor, 1000, wait)
    wait(600)

    wrapped = len([one for one in failures if "width" in one])
    per = ", ".join(
        f"{w}px {len([f for f in failures if f.get('width') == w])} wrapped" for w in WIDTHS
    )
    return {
        "verdict": (
            f"PASS {len(measured)} combinations, {per}"
            if not failures
            else f"FAIL {len(measured)} combinations, {per}"
            + ("; " + "; ".join(str(f) for f in failures if "width" not in f) if any("width" not in f for f in failures) else "")
        ),
        "baseline": baseline,
        "url_offered": url_offered,
        "wrapped": wrapped,
        "failures": failures,
        "table": table,
    }
