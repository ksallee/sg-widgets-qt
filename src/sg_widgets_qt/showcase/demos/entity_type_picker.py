"""One entity type, as a searchable combobox.

The port of `apps/site/src/demos/entity-type-picker/Demo.tsx`: an allow list of the six
production types, a deny list of the two user types, the code beside the display name and without
it, the sizes, read-only, invalid and disabled.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from ...widgets.entity_type_picker import EntityTypePicker
from ..context import DemoContext
from ._pickers import column, field, poll_ready, readout, section

__all__ = ["build"]

PRODUCTION = ["Project", "Sequence", "Shot", "Asset", "Version", "Task"]


class EntityTypePickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-type-picker-demo")
        self._context = context
        self._pickers: list = []
        #: False until the site's enabled types have landed.
        self.demo_ready = False

        body = column(self)
        one = self._picker(value="Shot", allow=PRODUCTION)
        one_line = readout(self)
        one_line.set_text("Shot")
        one.value_changed.connect(lambda code: one_line.set_text(code or "null"))
        body.addWidget(
            field(
                "Allow list: the six production types", one, one_line, name="single", parent=self
            )
        )

        any_type = self._picker(deny=["HumanUser", "ApiUser"])
        any_line = readout(self)
        any_line.set_text("null")
        any_type.value_changed.connect(lambda code: any_line.set_text(code or "null"))
        body.addWidget(
            field(
                "Deny list: everything but the two user types",
                any_type,
                any_line,
                name="deny",
                parent=self,
            )
        )

        body.addWidget(
            section(
                "The code beside the display name, and without it",
                field(
                    "With the code",
                    self._picker(value="Version", allow=PRODUCTION),
                    parent=self,
                ),
                field(
                    "Without it",
                    self._picker(value="Version", allow=PRODUCTION, show_code=False),
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
                    self._picker(value="Shot", size="sm", allow=PRODUCTION, follow=False),
                    parent=self,
                ),
                field(
                    "lg",
                    self._picker(value="Asset", size="lg", allow=PRODUCTION, follow=False),
                    parent=self,
                ),
                field("Read-only", self._picker(value="Task", readonly=True), parent=self),
                field("Invalid", self._picker(value=None, invalid=True), parent=self),
                field("Disabled", self._picker(value="Version", disabled=True), parent=self),
                parent=self,
            )
        )
        body.addStretch(1)
        self._timer = poll_ready(self, self._pending)

    def _pending(self) -> bool:
        """True while the one schema read is still in flight."""
        return any(not one.control.items for one in self.findChildren(EntityTypePicker))

    def _picker(self, follow: bool = True, **props: Any) -> EntityTypePicker:
        picker = EntityTypePicker(context=self._context.context, parent=self, **props)
        if follow:
            self._pickers.append(picker)
        return picker

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityTypePickerDemo(context, parent)
