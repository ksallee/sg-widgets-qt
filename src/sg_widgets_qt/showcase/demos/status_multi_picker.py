"""Several statuses, picked from the codes a project offers.

The port of `apps/site/src/demos/status-multi-picker/Demo.tsx`: Version in two projects, the codes
both projects offer, Project's own plain list, a mandatory field with no clear, a code the field
does not carry, rows without the code, a secondary of the caller's own, the three summary modes
wide and narrow, the three badge variants, a capped badge row, the three states and the three
heights.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.status_multi_picker import StatusMultiPicker
from ..context import DemoContext
from ._pickers import boxed, column, field, poll_ready, readout, section
from .status_picker import OTHER_PROJECT, stage_of

__all__ = ["build"]

MODES = ("chips", "ellipsis", "count")
BADGES = ("both", "icon", "text")
TWO = ["ip", "apr"]
FIVE = ["ip", "apr", "rev", "fin", "vwd"]
SIZES = ("sm", "md", "lg")


class StatusMultiPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("status-multi-picker-demo")
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
                field(
                    f"Project {here}",
                    self._picker(project_id=here, value=TWO),
                    name="p70",
                    parent=self,
                ),
                field(
                    f"Project {there}",
                    self._picker(project_id=there, value=["pndad"]),
                    name="p71",
                    parent=self,
                ),
                parent=self,
            )
        )

        shared = self._picker(project_ids=[here, there])
        shared_line = readout(self)
        shared.value_changed.connect(
            lambda codes: shared_line.set_text(", ".join(codes) or "—")
        )
        body.addWidget(
            section(
                "The statuses both projects offer",
                field(
                    "The intersection of both projects' codes",
                    shared,
                    shared_line,
                    name="both",
                    parent=self,
                ),
                parent=self,
            )
        )

        body.addWidget(
            section(
                "Project, whose status field is a plain list with no icons",
                field(
                    "Project's own status field",
                    self._picker(entity_type="Project", value=["Active", "Bidding"]),
                    name="project",
                    parent=self,
                ),
                parent=self,
            )
        )

        note = self._picker(entity_type="Note", value=["opn"])
        note_line = readout(self)
        note.value_changed.connect(lambda codes: note_line.set_text(", ".join(codes) or "—"))
        body.addWidget(
            section(
                "A mandatory field, which offers no clear",
                field(
                    "Note's status, which the site flags mandatory",
                    note,
                    note_line,
                    name="mandatory",
                    parent=self,
                ),
                parent=self,
            )
        )

        body.addWidget(
            section(
                "A code the field does not carry, rows without the code, and a secondary of "
                "the caller's own",
                field(
                    "A code the field does not carry",
                    self._picker(project_id=here, value=["zz_retired", "rev"]),
                    name="unknown",
                    parent=self,
                ),
                field(
                    "Rows with the label alone",
                    self._picker(
                        project_id=here, value=["ip", "fin"], show_code=False, clearable=False
                    ),
                    name="no-code",
                    parent=self,
                ),
                field(
                    "A secondary of the caller's own, in place of the code",
                    self._picker(
                        project_id=here, value=["ip", "fin"], secondary=stage_of, clearable=False
                    ),
                    name="own-secondary",
                    parent=self,
                ),
                parent=self,
            )
        )

        summaries: list = []
        for mode in MODES:
            summaries.append(
                field(
                    f"{mode}, full width",
                    self._picker(
                        project_id=here, value=list(FIVE), summary=mode, clearable=False
                    ),
                    name=f"summary-{mode}-5",
                    parent=self,
                )
            )
            summaries.append(
                field(
                    f"{mode}, at most 20rem",
                    boxed(
                        self._picker(
                            project_id=here, value=list(FIVE), summary=mode, clearable=False
                        )
                    ),
                    name=f"summary-{mode}-narrow",
                    parent=self,
                )
            )
        summaries.append(
            field(
                "chips, two selected",
                self._picker(project_id=here, value=TWO, summary="chips", clearable=False),
                name="summary-chips-2",
                parent=self,
            )
        )
        summaries.append(
            field(
                "text badges, two selected",
                self._picker(
                    project_id=here, value=TWO, summary="chips", badge="text", clearable=False
                ),
                name="badge-text-2",
                parent=self,
            )
        )
        body.addWidget(
            section(
                "What the closed trigger shows for five selected, wide and narrow",
                *summaries,
                parent=self,
            )
        )

        body.addWidget(
            section(
                "What one badge is drawn as, for five selected",
                *[
                    field(
                        badge,
                        self._picker(
                            project_id=here,
                            value=list(FIVE),
                            summary="chips",
                            badge=badge,
                            clearable=False,
                        ),
                        name=f"badge-{badge}-5",
                        parent=self,
                    )
                    for badge in BADGES
                ],
                parent=self,
            )
        )

        body.addWidget(
            section(
                'Two selected, one badge and a "+1"',
                field(
                    "One badge at most, whatever the room",
                    self._picker(project_id=here, value=TWO, max=1, clearable=False),
                    name="max-one",
                    parent=self,
                ),
                parent=self,
            )
        )

        body.addWidget(
            section(
                "Disabled, read-only, invalid",
                field(
                    "Disabled",
                    self._picker(project_id=here, value=["apr", "fin"], disabled=True),
                    parent=self,
                ),
                field(
                    "Read-only",
                    self._picker(project_id=here, value=["apr"], readonly=True),
                    parent=self,
                ),
                field(
                    "Invalid",
                    self._picker(project_id=here, value=["apr", "fin"], invalid=True),
                    parent=self,
                ),
                parent=self,
            )
        )
        body.addWidget(
            section(
                "Sizes",
                *[
                    field(
                        size,
                        self._picker(
                            project_id=here, value=["rev"], size=size, follow=False
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
        return any(one.load.loading for one in self.findChildren(StatusMultiPicker))

    def _picker(self, follow: bool = True, **props: Any) -> StatusMultiPicker:
        props.setdefault("entity_type", "Version")
        picker = StatusMultiPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return StatusMultiPickerDemo(context, parent)
