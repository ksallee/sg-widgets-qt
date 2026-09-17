"""Several values of a list field, picked from the set its schema declares.

The port of `apps/site/src/demos/list-multi-picker/Demo.tsx`: the valid values, the display
values, a project's hidden values removed, a search box, a mandatory field which offers no clear,
and the disabled state. Each row writes the chosen strings under the control.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.list_multi_picker import ListMultiPicker
from .. import chrome
from ..context import DemoContext
from ._pickers import CAPTION_SIZE, column, field, section
from .list_picker import SCOPED_PROJECT, SHOT_TYPE, STEP, VERSION_TYPE

__all__ = ["build"]


class ListMultiPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other, each with the chosen strings under it."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("list-multi-picker-demo")
        self._pickers: list = []
        self.demo_ready = True

        body = column(self)
        body.addWidget(self._case("valid values", "values", field=VERSION_TYPE, value=["Type A"]))
        body.addWidget(
            self._case(
                "display values", "labels", field=SHOT_TYPE, value=["VFX", "2D"], show_code=True
            )
        )
        body.addWidget(
            self._case(
                f"project {SCOPED_PROJECT}",
                "project",
                field=SHOT_TYPE,
                project_id=SCOPED_PROJECT,
                value=["Full CG"],
            )
        )
        body.addWidget(self._case("searchable", "searchable", field=SHOT_TYPE, searchable=True))
        body.addWidget(self._case("mandatory", "mandatory", field=STEP, value=["Model"]))
        body.addWidget(
            self._case(
                "disabled", "disabled", field=VERSION_TYPE, value=["Type B"], disabled=True
            )
        )
        body.addStretch(1)

    def _case(self, title: str, name: str, **props: Any) -> QtWidgets.QWidget:
        picker = ListMultiPicker(parent=self, **props)
        self._pickers.append(picker)
        line = chrome.TextLine(_shown(picker.value), size=CAPTION_SIZE, parent=self)
        picker.value_changed.connect(lambda value: line.set_text(_shown(value)))
        return section(title, field("", picker, line, name=name, parent=self), parent=self)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def _shown(value: Any) -> str:
    """The chosen strings as a caller would read them back, the way `JSON.stringify` writes them."""
    return "[" + ",".join(f'"{one}"' for one in value or []) + "]"


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ListMultiPickerDemo(context, parent)
