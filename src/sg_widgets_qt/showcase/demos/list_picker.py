"""One value of a list field, picked from the set its schema declares.

The port of `apps/site/src/demos/list-picker/Demo.tsx`: the valid values, the display values, a
project's hidden values removed, a search box, a mandatory field which offers no clear, and the
disabled state. Each row writes the stored string under the control, byte for byte.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.list_picker import ListPicker
from .. import chrome
from ..context import DemoContext
from ._pickers import CAPTION_SIZE, column, field, section

__all__ = ["build"]


def _field(
    name: str,
    display_name: str,
    valid_values: list,
    mandatory: bool = False,
    display_values: dict | None = None,
    hidden_values: list | None = None,
) -> FieldSchema:
    return FieldSchema(
        name=name,
        display_name=display_name,
        entity_type="Shot",
        data_type="list",
        editable=True,
        mandatory=mandatory,
        unique=False,
        valid_values=valid_values,
        display_values=display_values,
        hidden_values=hidden_values,
    )


VERSION_TYPE = _field("sg_version_type", "Version Type", ["Type A", "Type B", "Type C"])
SHOT_TYPE = _field(
    "sg_shot_type",
    "Shot Type",
    ["VFX", "2D", "Full CG", "Trailer", "Marketing", "Look Dev"],
    display_values={"2D": "Two D", "Look Dev": "Lookdev"},
    hidden_values=["Marketing", "Trailer"],
)
#: A field the site flags mandatory: the picker offers no clear.
STEP = _field("sg_step", "Pipeline Step", ["Model", "Rig", "Animate", "Light", "Comp"], True)

#: The project the scoped example reads its hidden values with.
SCOPED_PROJECT = 63


class ListPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other, each with the stored string under it."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("list-picker-demo")
        self._pickers: list = []
        self.demo_ready = True

        body = column(self)
        body.addWidget(self._case("valid values", "values", field=VERSION_TYPE, value="Type A"))
        body.addWidget(
            self._case("display values", "labels", field=SHOT_TYPE, value="VFX", show_code=True)
        )
        body.addWidget(
            self._case(
                f"project {SCOPED_PROJECT}",
                "project",
                field=SHOT_TYPE,
                project_id=SCOPED_PROJECT,
                value="Full CG",
            )
        )
        body.addWidget(self._case("searchable", "searchable", field=SHOT_TYPE, searchable=True))
        body.addWidget(self._case("mandatory", "mandatory", field=STEP, value="Model"))
        body.addWidget(
            self._case(
                "disabled", "disabled", field=VERSION_TYPE, value="Type B", disabled=True
            )
        )
        body.addStretch(1)

    def _case(self, title: str, name: str, **props: Any) -> QtWidgets.QWidget:
        picker = ListPicker(parent=self, **props)
        self._pickers.append(picker)
        line = chrome.TextLine(_shown(picker.value), size=CAPTION_SIZE, parent=self)
        picker.value_changed.connect(lambda value: line.set_text(_shown(value)))
        return section(title, field("", picker, line, name=name, parent=self), parent=self)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def _shown(value: Any) -> str:
    """The stored string as a caller would read it back, quoted, or `null`."""
    return "null" if value is None else f'"{value}"'


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ListPickerDemo(context, parent)
