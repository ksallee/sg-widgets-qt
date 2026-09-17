"""The text-editor demo: single line, multi-line, and the three blocked states.

The port of `apps/site/src/demos/text-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.text_editor import TextEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]

FIELD = FieldSchema(
    name="description",
    display_name="Description",
    entity_type="Shot",
    data_type="text",
    editable=True,
    mandatory=False,
    unique=False,
)

BLOCKED = "sh010_comp_v001"


class TextEditorDemo(QtWidgets.QWidget):
    """Five text editors, one per state the docs page names."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("text-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.cases = [
            _editors.Case(
                "input", TextEditor(value="Plate delivered.", field=FIELD, placeholder="Type here")
            ),
            _editors.Case(
                "multiline",
                TextEditor(
                    value="Plate delivered.\nSecond pass pending.", field=FIELD, multiline=True
                ),
            ),
            _editors.Case("readonly", TextEditor(value=BLOCKED, field=FIELD, readonly=True)),
            _editors.Case("disabled", TextEditor(value=BLOCKED, field=FIELD, disabled=True)),
            _editors.Case(
                "invalid",
                TextEditor(
                    value=None,
                    field=FIELD,
                    invalid=True,
                    error="The site refused this value.",
                ),
            ),
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
    return TextEditorDemo(context, parent)
