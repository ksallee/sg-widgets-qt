"""One status, picked from the codes a project offers.

The port of `apps/site/src/demos/status-picker/Demo.tsx`: Version in two projects, the codes both
projects offer, Project's own plain list, a mandatory field with no clear, a code the field does
not carry, rows without the code, a secondary of the caller's own, a project switch that drops a
hidden status, the three states and the three heights.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.status_picker import StatusPicker
from .. import chrome
from ..context import DemoContext
from ._pickers import boxed, column, field, poll_ready, readout, section

__all__ = ["build"]

#: An invented pipeline stage per code, for the row secondary a caller supplies.
STAGE = {"ip": "Animation", "rev": "Review", "fin": "Delivery"}

#: The mock's second project. Live mode has one project, the toolbar's.
OTHER_PROJECT = 71

SIZES = ("sm", "md", "lg")


def stage_of(option: Any) -> str:
    return STAGE.get(option.code, "")


class StatusPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("status-picker-demo")
        self._context = context
        self._pickers: list = []
        #: False until every status read on the page has answered.
        self.demo_ready = False
        here = context.project_id
        there = context.project_for(OTHER_PROJECT)

        body = column(self)
        title = (
            f"Version, in project {here}"
            if here == there
            else f"Version, in project {here} and in project {there}"
        )
        body.addWidget(
            section(
                title,
                field("", boxed(self._picker(project_id=here, value="ip")), name="p70", parent=self),
                field(
                    "",
                    boxed(self._picker(project_id=there, value="pndad")),
                    name="p71",
                    parent=self,
                ),
                parent=self,
            )
        )

        shared = self._picker(project_ids=[here, there])
        shared_line = readout(self)
        shared.value_changed.connect(lambda code: shared_line.set_text(code or "—"))
        body.addWidget(
            section(
                "The statuses both projects offer",
                field("", boxed(shared), shared_line, name="both", parent=self),
                parent=self,
            )
        )

        body.addWidget(
            section(
                "Project, whose status field is a plain list with no icons",
                field(
                    "",
                    boxed(self._picker(entity_type="Project", value="Active")),
                    name="project",
                    parent=self,
                ),
                parent=self,
            )
        )

        note = self._picker(entity_type="Note", value="opn")
        note_line = readout(self)
        note.value_changed.connect(lambda code: note_line.set_text(code or "—"))
        body.addWidget(
            section(
                "A mandatory field, which offers no clear",
                field("", boxed(note), note_line, name="mandatory", parent=self),
                parent=self,
            )
        )

        body.addWidget(
            section(
                "A code the field does not carry, rows without the code, and a secondary of "
                "the caller's own",
                field(
                    "",
                    boxed(self._picker(project_id=here, value="zz_retired")),
                    name="unknown",
                    parent=self,
                ),
                field(
                    "",
                    boxed(
                        self._picker(
                            project_id=here, value="ip", show_code=False, clearable=False
                        )
                    ),
                    name="no-code",
                    parent=self,
                ),
                field(
                    "",
                    boxed(
                        self._picker(
                            project_id=here, value="ip", secondary=stage_of, clearable=False
                        )
                    ),
                    name="own-secondary",
                    parent=self,
                ),
                parent=self,
            )
        )

        switching = self._picker(project_id=there, value="part")
        switch_line = readout(self)
        switching.value_changed.connect(lambda code: switch_line.set_text(code or "—"))
        self._switch_to = there
        self._here, self._there = here, there
        self._switching = switching
        self._switch = chrome.button(
            f"Project {there}",
            variant="outline",
            size="md",
            parent=self,
            on_click=self._toggle_project,
        )
        self._switch.setObjectName("switch-project")
        body.addWidget(
            section(
                "Switching project drops a status the new one hides",
                field("", boxed(switching), self._switch, switch_line, name="switching", parent=self),
                case="switch",
                parent=self,
            )
        )

        body.addWidget(
            section(
                "Disabled, read-only, invalid",
                *[
                    field(
                        flag.capitalize(),
                        boxed(self._picker(project_id=here, value="apr", **{flag: True})),
                        parent=self,
                    )
                    for flag in ("disabled", "readonly", "invalid")
                ],
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Sizes",
                *[
                    field(
                        size,
                        boxed(
                            self._picker(
                                project_id=here, value="rev", size=size, follow=False
                            )
                        ),
                        parent=self,
                    )
                    for size in SIZES
                ],
                parent=self,
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _pending(self) -> bool:
        """True while any status read on the page is still in flight."""
        return any(one.load.loading for one in self.findChildren(StatusPicker))

    def _picker(self, follow: bool = True, **props: Any) -> StatusPicker:
        props.setdefault("entity_type", "Version")
        picker = StatusPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def _toggle_project(self) -> None:
        self._switch_to = self._here if self._switch_to == self._there else self._there
        self._switching.set_project_id(self._switch_to)
        self._switch.set_text(f"Project {self._switch_to}")

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return StatusPickerDemo(context, parent)
