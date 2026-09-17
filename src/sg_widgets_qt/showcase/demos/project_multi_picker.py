"""Several projects, chosen by server-side search.

The port of `apps/site/src/demos/project-multi-picker/Demo.tsx`: several projects, a token field,
archived projects included, bare references resolved on the way in, the three summary modes wide
and narrow, a capped chip row, the three heights and the three states.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import placeholder_name

from ...widgets.project_multi_picker import ProjectMultiPicker
from ..context import DemoContext
from ._pickers import boxed, column, field, poll_ready, section

__all__ = ["build"]

OTHER_PROJECT = 71
SUMMARIES = ("chips", "ellipsis", "count")
SIZES = ("sm", "md", "lg")


class ProjectMultiPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("project-multi-picker-demo")
        self._context = context
        self._pickers: list = []
        self.demo_ready = True
        # A live site holds its own projects, so the preset arrives bare and the picker
        # resolves its name.
        preset = (
            [EntityRef(type="Project", id=context.project_id)]
            if context.live
            else [
                EntityRef(type="Project", id=70),
                EntityRef(type="Project", id=71),
                EntityRef(type="Project", id=72),
            ]
        )

        body = column(self)
        body.addWidget(
            section(
                "Several projects",
                field("Several projects at once", self._picker(), parent=self),
                case="multi",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "A token field: Backspace walks the chips",
                field(
                    "The projects already chosen, as chips",
                    self._picker(summary="chips", value=preset),
                    parent=self,
                ),
                case="tokens",
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
                "Bare references, resolved on the way in",
                field(
                    "Types and ids in, names resolved on the way in",
                    self._picker(
                        value=[
                            EntityRef(type="Project", id=context.project_for(OTHER_PROJECT))
                        ]
                    ),
                    parent=self,
                ),
                case="hydrate",
                parent=self,
            )
        )

        summaries: list = []
        for summary in SUMMARIES:
            summaries.append(
                field(
                    f"{summary}, full width",
                    self._picker(value=preset, summary=summary, clearable=False),
                    name=summary,
                    parent=self,
                )
            )
            summaries.append(
                field(
                    f"{summary}, at most 20rem",
                    boxed(self._picker(value=preset, summary=summary, clearable=False)),
                    name=f"{summary}-narrow",
                    parent=self,
                )
            )
        summaries.append(
            field(
                "chips, two at most",
                self._picker(value=preset, summary="chips", max=2, clearable=False),
                name="max",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "What the control shows for the selection, wide and narrow",
                *summaries,
                case="summary",
                parent=self,
            )
        )

        states = [
            field(size, self._picker(value=preset, size=size, follow=False), parent=self)
            for size in SIZES
        ]
        states.extend(
            field(flag.capitalize(), self._picker(value=preset, **{flag: True}), parent=self)
            for flag in ("disabled", "readonly", "invalid")
        )
        body.addWidget(
            section(
                "Sizes, then disabled, read-only, invalid", *states, case="states", parent=self
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _picker(self, follow: bool = True, **props: Any) -> ProjectMultiPicker:
        picker = ProjectMultiPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def _pending(self) -> bool:
        for picker in self.findChildren(ProjectMultiPicker):
            for ref, label in zip(picker.value, picker.control.labels):
                if not label or label == placeholder_name(ref):
                    return True
        return False

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ProjectMultiPickerDemo(context, parent)
