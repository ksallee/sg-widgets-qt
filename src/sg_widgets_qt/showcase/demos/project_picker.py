"""One project, chosen by server-side search.

The port of `apps/site/src/demos/project-picker/Demo.tsx`: one project, archived projects
included, a bare reference resolved on the way in, the three heights and the three states.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import placeholder_name

from ...widgets.project_picker import ProjectPicker
from ..context import DemoContext
from ._pickers import column, field, poll_ready, section

__all__ = ["build"]

#: The mock's second project, which the hydration example is handed bare.
OTHER_PROJECT = 71

SIZES = (("sm", "Small"), ("md", "Medium, the default"), ("lg", "Large"))

#: The three inert states, with the captions the upstream demo writes over them.
STATES = (("disabled", "Disabled"), ("readonly", "Read-only"), ("invalid", "Invalid"))


class ProjectPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("project-picker-demo")
        self._context = context
        self._pickers: list = []
        self.demo_ready = True
        # The name is the mock's. A live site holds its own projects, so there the preset
        # arrives bare and the picker resolves it.
        preset = (
            EntityRef(type="Project", id=context.project_id)
            if context.live
            else EntityRef(type="Project", id=context.project_id, name="Blue Moon Rising")
        )

        body = column(self)
        body.addWidget(
            section(
                "One project",
                field("One project, clearable", self._picker(), parent=self),
                case="single",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Archived projects included",
                field(
                    "Archived projects included", self._picker(include_archived=True), parent=self
                ),
                case="archived",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Bare reference, resolved on the way in",
                field(
                    "Type and id in, name resolved on the way in",
                    self._picker(
                        value=EntityRef(
                            type="Project", id=context.project_for(OTHER_PROJECT)
                        )
                    ),
                    parent=self,
                ),
                case="hydrate",
                parent=self,
            )
        )

        states = [
            field(caption, self._picker(value=preset, size=size, follow=False), parent=self)
            for size, caption in SIZES
        ]
        states.extend(
            field(caption, self._picker(value=preset, **{flag: True}), parent=self)
            for flag, caption in STATES
        )
        body.addWidget(
            section(
                "Sizes, then disabled, read-only, invalid", *states, case="states", parent=self
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _picker(self, follow: bool = True, **props: Any) -> ProjectPicker:
        picker = ProjectPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def _pending(self) -> bool:
        for picker in self.findChildren(ProjectPicker):
            value = picker.value
            if value is None:
                continue
            labels = picker.control.labels
            if not labels or labels[0] == placeholder_name(value):
                return True
        return False

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ProjectPickerDemo(context, parent)
