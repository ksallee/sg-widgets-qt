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

from sg_widgets_core.filter import condition, empty_filter
from sg_widgets_core.filter_ux import field_operators, operator_menu
from sg_widgets_qt.widgets.filter_editor import FilterEditor

#: The widths the stage is pinned to.
WIDTHS: tuple[int, ...] = (800, 1000, 1200)

#: Combinations allowed to take a second line at the narrowest width. None are.
ALLOWED_TO_WRAP: tuple[str, ...] = ()

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

    # One row per type, built on an empty tree.
    editor.set_value(empty_filter())
    wait(200)
    built: list[tuple[str, str, int]] = []
    for data_type, path in FIELDS:
        at = len(editor.value.conditions)
        editor.append([], condition("", "is", ""))
        wait(80)
        node = editor.node_at([at])
        editor.pick_field([at], node, path)
        landed = wait_for(
            lambda a=at, p=path, n=node: (editor.node_at([a]) or n).path == p, wait, 8000
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
        built.append((data_type, path, at))

    # The one-line baseline: `Version Name is`, a plain text editor, at each width.
    text_at = next((at for kind, _p, at in built if kind == "text"), None)
    if text_at is None:
        return {"verdict": "FAIL no text row to measure the baseline on", "failures": failures}
    editor.pick_preset([text_at], editor.node_at([text_at]), "is")
    wait(200)
    baseline: dict[int, int] = {}
    for width in WIDTHS:
        set_width(editor, width, wait)
        baseline[width] = rows_of(editor)[text_at].height()

    measured: list[dict] = []
    for data_type, path, at in built:
        field = editor.field_of(path)
        presets = [
            preset.id
            for run in operator_menu(data_type, field_operators(field))
            for preset in run.presets
        ]
        if not presets:
            failures.append({"type": data_type, "preset": "-", "why": "the menu offers nothing"})
            continue
        for preset_id in presets:
            editor.pick_preset([at], editor.node_at([at]), preset_id)
            wait(80)
            heights: dict[int, int] = {}
            for width in WIDTHS:
                set_width(editor, width, wait)
                rows = rows_of(editor)
                heights[width] = rows[at].height() if at < len(rows) else -1
            measured.append({"type": data_type, "preset": preset_id, "heights": heights})
            marks = [
                f"{w}:{'wrapped' if heights[w] > baseline[w] + 1 else 'one'}" for w in WIDTHS
            ]
            table.append(f"{data_type} {preset_id} {' '.join(marks)}")
            for width in WIDTHS:
                if heights[width] <= baseline[width] + 1:
                    continue
                if width == WIDTHS[0] and f"{data_type}|{preset_id}" in ALLOWED_TO_WRAP:
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
        widest = next((one for one in WIDEST if one in presets), presets[-1])
        editor.pick_preset([at], editor.node_at([at]), widest)
        wait(60)

    # The screenshot takes the widest row of every type at 1000px.
    set_width(editor, 1000, wait)
    wait(400)

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
