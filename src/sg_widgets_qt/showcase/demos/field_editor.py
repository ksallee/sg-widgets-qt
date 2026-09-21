"""The field-editor demo: every data type, with a display and edit toggle.

The port of `apps/site/src/demos/field-editor/Demo.tsx`, with the two cases the upstream drives
cover: a duration that reads `1h 30m` as 90 minutes, and a text and a status field editing in a
popover the way a table cell does.
"""
from __future__ import annotations

import json
from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.field_editor import FieldEditor
from .. import chrome
from ..context import DemoContext
from . import _layout, _rows

__all__ = ["build"]

#: The width the editor column takes, so a popover has an anchor of a real size.
EDITOR_WIDTH = 320
TYPE_WIDTH = 110
VALUE_WIDTH = 260


def schema(name: str, label: str, data_type: str, **extra: Any) -> FieldSchema:
    return FieldSchema(
        name=name,
        display_name=label,
        entity_type="Version",
        data_type=data_type,
        editable=True,
        mandatory=False,
        unique=False,
        **extra,
    )


#: One row per data type, with a value in the shape the API sends.
ROWS: list[dict[str, Any]] = [
    {"key": "text", "field": schema("sg_department", "Department", "text"), "value": "lighting"},
    {
        "key": "list",
        "field": schema(
            "sg_version_type", "Version Type", "list", valid_values=["Type A", "Type B", "Type C"]
        ),
        "value": "Type A",
    },
    {"key": "number", "field": schema("frame_count", "Frame Count", "number"), "value": 1001},
    {
        "key": "float",
        "field": schema("sg_movie_aspect_ratio", "Movie Aspect Ratio", "float"),
        "value": "1.777778",
        "precision": 2,
    },
    {"key": "percent", "field": schema("sg___complete", "Complete", "percent"), "value": 50},
    {"key": "currency", "field": schema("sg_bid", "Bid", "currency"), "value": 12500},
    {"key": "duration", "field": schema("sg_bid___total", "Bid Total", "duration"), "value": 480},
    {
        "key": "timecode",
        "field": schema("sg_timecode", "Timecode", "timecode"),
        "value": 3600000,
        "frame_rate": 23.976,
    },
    {
        "key": "date",
        "field": schema("sg_turnover_date", "Turnover Date", "date"),
        "value": "2026-09-02",
    },
    {
        "key": "date_time",
        "field": schema("client_approved_at", "Client Approved At", "date_time"),
        "value": "2026-03-04T13:06:07Z",
        "time_zone": "America/Los_Angeles",
    },
    {"key": "checkbox", "field": schema("flagged", "Flagged", "checkbox"), "value": True},
    {
        "key": "url",
        "field": schema("sg_uploaded_movie", "Uploaded Movie", "url"),
        "value": {
            "url": "https://example.com/plate.mov",
            "name": "plate.mov",
            "link_type": "web",
        },
    },
    {"key": "color", "field": schema("color", "Gantt Bar Color", "color"), "value": "pipeline_step"},
    {
        "key": "status_list",
        "field": schema("sg_status_list", "Status", "status_list"),
        "value": "ip",
    },
    {
        "key": "entity",
        "field": schema("entity", "Link", "entity", valid_types=["Shot"]),
        "value": _rows.value("Shot", 862),
    },
    {
        "key": "multi_entity",
        "field": schema("sg_shots", "Shots", "multi_entity", valid_types=["Shot"]),
        "value": [_rows.value("Shot", 862)],
    },
]

#: The two fields the popover examples edit, which is what a table cell does.
POPOVER_ROWS: list[dict[str, Any]] = [
    {
        "key": "popover-text",
        "field": schema("description", "Description", "text"),
        "value": "Plate delivered.",
    },
    {
        "key": "popover-status",
        "field": schema("sg_status_list", "Status", "status_list"),
        "value": "ip",
    },
]


class FieldEditorDemo(QtWidgets.QWidget):
    """Every data type on one page, with the toggle that opens them all at once."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("field-editor-demo")
        self._context = context
        self._editors: list[FieldEditor] = []
        #: The rows the toggle opens. A popover is opened one at a time, from its own value.
        self._inline: list[FieldEditor] = []
        #: What the toggle last asked for. An editor commits and closes when the focus leaves
        #: it, and the press on the toggle is one such focus change, so the rows are no longer
        #: all in their editors by the time the press is handled; the button holds the state
        #: rather than reading it back off them. Upstream holds the same flag in `useState`.
        self._editing = False
        #: Nothing here waits on a read, so the page is ready as soon as it stands.
        self.demo_ready = True

        body = _layout.column(self)
        self.toggle = chrome.button(
            "Edit every field", variant="outline", size="md", parent=self, on_click=self._toggle
        )
        self.toggle.setObjectName("demo-toggle")
        hint = chrome.TextLine(
            "Press a value or Enter on it to edit. Enter commits, Escape cancels.",
            size=12,
            parent=self,
        )
        body.addWidget(_layout.row(self.toggle, hint, parent=self))
        body.addWidget(self._table("types", ROWS, placement="inline"))
        body.addWidget(
            _layout.section(
                "In a popover",
                self._table("popover", POPOVER_ROWS, placement="popover"),
                caption="The value stays where it is and the editor opens under it, with Cancel and Save",
                parent=self,
            )
        )
        body.addStretch(1)

    # --- the table ---------------------------------------------------------------------------

    def _table(self, name: str, rows: list[dict], placement: str) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        holder.setObjectName(f"field-editor-{name}")
        grid = QtWidgets.QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        for index, row in enumerate(rows):
            grid.addWidget(self._type_line(row, holder), index, 0)
            grid.addWidget(self._editor(row, placement, holder), index, 1)
            grid.addWidget(self._value_line(row, holder), index, 2)
        grid.setColumnStretch(1, 1)
        return holder

    def _type_line(self, row: dict, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        line = chrome.TextLine(row["field"].data_type, size=12, parent=parent)
        line.setFixedWidth(TYPE_WIDTH)
        return line

    def _value_line(self, row: dict, parent: QtWidgets.QWidget) -> QtWidgets.QWidget:
        line = chrome.TextLine(json.dumps(row["value"]), size=12, parent=parent)
        line.setObjectName(f"field-editor-{row['key']}-value")
        line.setFixedWidth(VALUE_WIDTH)
        row["line"] = line
        return line

    def _editor(self, row: dict, placement: str, parent: QtWidgets.QWidget) -> FieldEditor:
        editor = FieldEditor(
            value=row["value"],
            field=row["field"],
            editable=True,
            editor_placement=placement,
            context=self._context,
            precision=row.get("precision"),
            frame_rate=row.get("frame_rate"),
            time_zone=row.get("time_zone"),
            parent=parent,
        )
        editor.setObjectName(f"field-editor-{row['key']}")
        editor.setMinimumWidth(EDITOR_WIDTH)
        editor.value_changed.connect(lambda value, r=row: self._emitted(r, value))
        self._editors.append(editor)
        if placement != "popover":
            self._inline.append(editor)
        row["editor"] = editor
        return editor

    def _emitted(self, row: dict, value: Any) -> None:
        line = row.get("line")
        if line is None or not _layout.alive(line):
            return
        try:
            line.set_text(json.dumps(value))
        except TypeError:
            line.set_text(str(value))

    def _toggle(self) -> None:
        self._editing = not self._editing
        for editor in self._inline:
            editor.set_mode("edit" if self._editing else "display")
        self.toggle.set_text("Show values" if self._editing else "Edit every field")

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for editor in self._editors:
            editor.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FieldEditorDemo(context, parent)
