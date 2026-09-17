"""The date-time-editor demo: three sizes, a second zone, unset, and the three marked states.

The port of `apps/site/src/demos/date-time-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.date_time_editor import DateTimeEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]

ZONE = "America/Los_Angeles"
APPROVED_AT = "2026-03-04T13:06:07Z"


def field(name: str, display_name: str) -> FieldSchema:
    """One date_time field of the shape the editor reads for its label."""
    return FieldSchema(
        name=name,
        display_name=display_name,
        entity_type="Version",
        data_type="date_time",
        editable=True,
        mandatory=False,
        unique=False,
    )


class DateTimeEditorDemo(QtWidgets.QWidget):
    """Eight instant editors: the ladder, a second zone, unset, and the three marked states."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("date-time-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        approved = field("sg_client_approved_at", "Client Approved At")
        self.cases = [
            _editors.Case(
                "sm",
                DateTimeEditor(
                    value=APPROVED_AT, time_zone=ZONE, size="sm", hint=False, field=approved
                ),
                readout=False,
            ),
            _editors.Case(
                "md", DateTimeEditor(value=APPROVED_AT, time_zone=ZONE, field=approved)
            ),
            _editors.Case(
                "lg",
                DateTimeEditor(
                    value=APPROVED_AT, time_zone=ZONE, size="lg", hint=False, field=approved
                ),
                readout=False,
            ),
            _editors.Case(
                "Paris, seconds",
                DateTimeEditor(
                    value=APPROVED_AT,
                    time_zone="Europe/Paris",
                    show_seconds=True,
                    field=field("sg_import_time", "Media Center Import Time"),
                ),
            ),
            _editors.Case("unset", DateTimeEditor(value=None, time_zone="UTC")),
            _editors.Case(
                "invalid",
                DateTimeEditor(
                    value=APPROVED_AT,
                    time_zone=ZONE,
                    hint=False,
                    invalid=True,
                    error="Before the version was delivered.",
                    field=approved,
                ),
                readout=False,
            ),
            _editors.Case(
                "readonly",
                DateTimeEditor(
                    value=APPROVED_AT, time_zone=ZONE, hint=False, readonly=True, field=approved
                ),
                readout=False,
            ),
            _editors.Case(
                "disabled",
                DateTimeEditor(
                    value=APPROVED_AT, time_zone=ZONE, hint=False, disabled=True, field=approved
                ),
                readout=False,
            ),
        ]
        for case in self.cases:
            _editors.bind(case, case.editor.value)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(_editors.rows(self, self.cases))

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The three ladder cases name their own."""
        for case in self.cases:
            if case.name not in ("sm", "lg"):
                case.editor.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return DateTimeEditorDemo(context, parent)
