"""The filter-dialog demo: an empty launcher, an applied one, a Note, and the sizes.

The port of `apps/site/src/demos/filter-dialog/Demo.tsx`. The second launcher drives the result
set under it, so applying an edit is what moves the rows.
"""
from __future__ import annotations

import json

from qtpy import QtWidgets

from sg_widgets_core.filter import FilterGroup, condition, empty_filter, group, to_api3_hash

from ...widgets.filter_dialog import FilterDialog
from ..context import DemoContext
from . import _layout
from ._results import VersionResults, WireView

__all__ = ["build"]

#: The three steps the last section stands every launcher on.
SIZES: tuple[str, ...] = ("sm", "md", "lg")


def applied_tree() -> FilterGroup:
    """Two conditions, which is what the launcher reads as its count."""
    return group(
        "and",
        [
            condition("sg_status_list", "in", ["rev", "vwd", "fin"]),
            condition("created_at", "in_last", [1, "YEAR"]),
        ],
    )


class FilterDialogDemo(QtWidgets.QWidget):
    """Every example of the page, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filter-dialog-demo")
        self._sized: list[FilterDialog] = []

        body = _layout.column(self)

        self.empty = FilterDialog(
            entity_type="Version", context=context.context, value=empty_filter(), parent=self
        )
        self.empty.setObjectName("filter-dialog-empty")
        body.addWidget(
            _layout.section("No filters yet, not wired to the list", self.empty, parent=self)
        )

        self.applied = FilterDialog(
            entity_type="Version", context=context.context, value=applied_tree(), parent=self
        )
        self.applied.setObjectName("filter-dialog-applied")
        self.wire = WireView(self)
        self.wire.setObjectName("dialog-json")
        self.wire.set_text(_wire_text(self.applied.value))
        body.addWidget(
            _layout.section(
                "Two applied, drives the list below", self.applied, self.wire, parent=self
            )
        )

        self.results = VersionResults(
            context,
            self.applied.value,
            heading="Versions matching the second launcher",
            parent=self,
        )
        body.addWidget(self.results)
        self.applied.changed.connect(self._on_changed)

        note = FilterDialog(
            entity_type="Note",
            context=context.context,
            value=group("and", [condition("read_by_current_user", "is", "unread")]),
            parent=self,
        )
        note.setObjectName("filter-dialog-note")
        body.addWidget(
            _layout.section(
                "Note, whose read-state field takes is and is not alone", note, parent=self
            )
        )

        stack = QtWidgets.QWidget(self)
        rows = QtWidgets.QVBoxLayout(stack)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(_layout.ROW_GAP)
        for size in SIZES:
            made = FilterDialog(
                entity_type="Version",
                context=context.context,
                value=empty_filter(),
                size=size,
                parent=stack,
            )
            made.setObjectName(f"filter-dialog-{size}")
            self._sized.append(made)
            rows.addWidget(made)
        body.addWidget(_layout.section("Sizes", stack, parent=self))
        body.addStretch(1)

    def _on_changed(self, value: FilterGroup) -> None:
        if not _layout.alive(self):
            return
        self.wire.set_text(_wire_text(value))
        self.results.set_value(value)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The sizes section names its own."""
        self.empty.set_size(size)
        self.applied.set_size(size)

    @property
    def demo_ready(self) -> bool:
        """True once the result set under the launcher has answered. The stage polls it."""
        return bool(self.results.demo_ready)


def _wire_text(value: FilterGroup) -> str:
    return json.dumps(to_api3_hash(value), indent=2)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FilterDialogDemo(context, parent)
