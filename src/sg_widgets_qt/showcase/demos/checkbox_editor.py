"""The checkbox-editor demo: two states, and the two blocked ones.

The port of `apps/site/src/demos/checkbox-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.checkbox_editor import CheckboxEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]


def field(name: str, display_name: str) -> FieldSchema:
    """One checkbox field of the shape the editor reads for its label."""
    return FieldSchema(
        name=name,
        display_name=display_name,
        entity_type="Shot",
        data_type="checkbox",
        editable=True,
        mandatory=False,
        unique=False,
    )


class CheckboxEditorDemo(QtWidgets.QWidget):
    """Four switches: the two values, and the two blocked states."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("checkbox-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.cases = [
            _editors.Case("flagged", CheckboxEditor(value=True, field=field("flagged", "Flagged"))),
            _editors.Case(
                "client approved",
                CheckboxEditor(
                    value=False,
                    field=field("sg_client_approved", "Client Approved"),
                    labels=("Approved", "Not approved"),
                ),
            ),
            _editors.Case("readonly", CheckboxEditor(value=True, readonly=True)),
            _editors.Case("disabled", CheckboxEditor(value=False, disabled=True)),
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
    return CheckboxEditorDemo(context, parent)
