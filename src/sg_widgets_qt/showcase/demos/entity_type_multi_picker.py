"""Several entity types, as a searchable combobox.

The port of `apps/site/src/demos/entity-type-multi-picker/Demo.tsx`: a deny list of the two user
types, the three summary modes wide and narrow, the code beside the display name and without it,
the sizes, read-only, invalid and disabled.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.entity_type_multi_picker import EntityTypeMultiPicker
from ..context import DemoContext
from ._pickers import boxed, column, field, poll_ready, readout, section
from .entity_type_picker import PRODUCTION

__all__ = ["build"]

SUMMARIES = ("chips", "ellipsis", "count")


class EntityTypeMultiPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-type-multi-picker-demo")
        self._context = context
        self._pickers: list = []
        #: False until the site's enabled types have landed.
        self.demo_ready = False

        body = column(self)
        many = self._picker(value=["Version"], deny=["HumanUser", "ApiUser"])
        many_line = readout(self)
        many_line.set_text("[Version]")
        many.value_changed.connect(
            lambda codes: many_line.set_text("[" + ", ".join(codes) + "]")
        )
        body.addWidget(
            field(
                "Deny list: everything but the two user types",
                many,
                many_line,
                name="multi",
                parent=self,
            )
        )

        summaries: list = []
        for summary in SUMMARIES:
            summaries.append(
                field(
                    f"{summary}, full width",
                    self._picker(
                        value=list(PRODUCTION),
                        summary=summary,
                        allow=PRODUCTION,
                        clearable=False,
                    ),
                    name=summary,
                    parent=self,
                )
            )
            summaries.append(
                field(
                    f"{summary}, at most 20rem",
                    boxed(
                        self._picker(
                            value=list(PRODUCTION),
                            summary=summary,
                            allow=PRODUCTION,
                            clearable=False,
                        )
                    ),
                    name=f"{summary}-narrow",
                    parent=self,
                )
            )
        body.addWidget(
            section(
                "What the control shows for six selected, wide and narrow",
                *summaries,
                case="summary",
                parent=self,
            )
        )

        body.addWidget(
            section(
                "The code beside the display name, and without it",
                field(
                    "With the code",
                    self._picker(value=["Version"], allow=PRODUCTION),
                    parent=self,
                ),
                field(
                    "Without it",
                    self._picker(value=["Version"], allow=PRODUCTION, show_code=False),
                    parent=self,
                ),
                case="codes",
                parent=self,
            )
        )

        body.addWidget(
            section(
                "Sizes, read-only and invalid",
                field(
                    "sm",
                    self._picker(
                        value=["Shot", "Asset"], size="sm", allow=PRODUCTION, follow=False
                    ),
                    parent=self,
                ),
                field(
                    "lg",
                    self._picker(
                        value=["Shot", "Asset"], size="lg", allow=PRODUCTION, follow=False
                    ),
                    parent=self,
                ),
                field("Read-only", self._picker(value=["Task"], readonly=True), parent=self),
                field("Invalid", self._picker(value=[], invalid=True), parent=self),
                field("Disabled", self._picker(value=["Version"], disabled=True), parent=self),
                parent=self,
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _pending(self) -> bool:
        """True while the one schema read is still in flight."""
        return any(not one.control.items for one in self.findChildren(EntityTypeMultiPicker))

    def _picker(self, follow: bool = True, **props: Any) -> EntityTypeMultiPicker:
        picker = EntityTypeMultiPicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityTypeMultiPickerDemo(context, parent)
