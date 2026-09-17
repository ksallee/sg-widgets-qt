"""The color-editor demo: a triple, a hex code, the pipeline-step token.

The port of `apps/site/src/demos/color-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.color_editor import ColorEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]


def field(name: str, display_name: str, entity_type: str = "PipelineStep") -> FieldSchema:
    """One colour field of the shape the editor reads for its label."""
    return FieldSchema(
        name=name,
        display_name=display_name,
        entity_type=entity_type,
        data_type="color",
        editable=True,
        mandatory=False,
        unique=False,
    )


class ColorEditorDemo(QtWidgets.QWidget):
    """Four colour editors: a triple, a hex code, the token, and the blocked state."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("color-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.cases = [
            _editors.Case("triple", ColorEditor(value="253,94,99", field=field("color", "Color"))),
            _editors.Case(
                "hex accepted",
                ColorEditor(
                    value="0,126,174", placeholder="#ff8000", field=field("color", "Color", "Project")
                ),
            ),
            _editors.Case(
                "pipeline step",
                ColorEditor(
                    value="pipeline_step",
                    field=field("color", "Gantt Bar Color", "Task"),
                ),
            ),
            _editors.Case("disabled", ColorEditor(value="45,45,45", disabled=True)),
        ]
        for case in self.cases:
            _editors.bind(case, case.editor.value)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(_editors.rows(self, self.cases))

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for case in self.cases:
            case.editor.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ColorEditorDemo(context, parent)
