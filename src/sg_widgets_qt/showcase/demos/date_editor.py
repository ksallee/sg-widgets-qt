"""The date-editor demo: three sizes, set, unset, and the three marked states.

The port of `apps/site/src/demos/date-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.date_editor import DateEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]

TURNOVER = "2026-09-02"


def field(name: str, display_name: str) -> FieldSchema:
    """One date field of the shape the editor reads for its label."""
    return FieldSchema(
        name=name,
        display_name=display_name,
        entity_type="Shot",
        data_type="date",
        editable=True,
        mandatory=False,
        unique=False,
    )


class DateEditorDemo(QtWidgets.QWidget):
    """Seven date editors: the ladder, the two values, and the three marked states."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("date-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        turnover = field("sg_turnover_date", "Turnover Date")
        self.cases = [
            _editors.Case("sm", DateEditor(value=TURNOVER, size="sm", field=turnover), readout=False),
            _editors.Case("md", DateEditor(value=TURNOVER, field=turnover)),
            _editors.Case("lg", DateEditor(value=TURNOVER, size="lg", field=turnover), readout=False),
            _editors.Case(
                "unset",
                DateEditor(
                    value=None, field=field("sg_next_version_expected", "Next Version Expected")
                ),
            ),
            _editors.Case(
                "invalid",
                DateEditor(
                    value=TURNOVER,
                    invalid=True,
                    error="Outside the shoot window.",
                    field=turnover,
                ),
                readout=False,
            ),
            _editors.Case(
                "readonly", DateEditor(value=TURNOVER, readonly=True, field=turnover), readout=False
            ),
            _editors.Case(
                "disabled", DateEditor(value=TURNOVER, disabled=True, field=turnover), readout=False
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
    return DateEditorDemo(context, parent)
