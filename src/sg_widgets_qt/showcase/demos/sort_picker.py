"""The sort-picker demo: two keys, the string they serialise to, the rows, and the sizes.

The port of `apps/site/src/demos/sort-picker/Demo.tsx`. A key the site cannot sort on is a
silent no-op or a refusal, never a crash: the list shows whichever it was (026_result_order).
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.filter import empty_filter
from sg_widgets_core.filter_ux import SortKey, to_sort_string

from ...widgets.sort_picker import SortPicker
from ..context import DemoContext
from . import _layout
from ._results import EntityResults, WireView

__all__ = ["build"]

#: The three steps the last section stands every trigger on.
SIZES: tuple[str, ...] = ("sm", "md", "lg")


def initial() -> list[SortKey]:
    """The keys the page opens on: a status first, a code descending behind it."""
    return [SortKey(field="sg_status_list", direction="asc"), SortKey(field="code", direction="desc")]


class SortPickerDemo(QtWidgets.QWidget):
    """Every example of the page, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sort-picker-demo")
        self._sized: list[SortPicker] = []

        body = _layout.column(self)

        self.picker = SortPicker(
            entity_type="Shot", context=context.context, value=initial(), parent=self
        )
        self.picker.setObjectName("sort-picker-main")
        body.addWidget(self.picker)

        self.wire = WireView(self)
        self.wire.setObjectName("sort-string")
        self.wire.set_text(to_sort_string(initial()) or "(none)")
        body.addWidget(_layout.section("sort", self.wire, parent=self))

        self.results = EntityResults(
            context,
            empty_filter(),
            heading="Shots in that order",
            entity_type="Shot",
            noun="Shot",
            sort=to_sort_string(initial()),
            parent=self,
        )
        body.addWidget(self.results)
        self.picker.changed.connect(self._on_changed)

        stack = QtWidgets.QWidget(self)
        rows = QtWidgets.QVBoxLayout(stack)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(_layout.ROW_GAP)
        for size in SIZES:
            made = SortPicker(
                entity_type="Shot",
                context=context.context,
                value=initial(),
                size=size,
                parent=stack,
            )
            made.setObjectName(f"sort-picker-{size}")
            self._sized.append(made)
            rows.addWidget(made)
        body.addWidget(_layout.section("Sizes", stack, parent=self))
        body.addStretch(1)

    def _on_changed(self, _keys: object, sort: str) -> None:
        if not _layout.alive(self):
            return
        self.wire.set_text(sort or "(none)")
        self.results.set_sort(sort)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The sizes section names its own."""
        self.picker.set_size(size)

    @property
    def demo_ready(self) -> bool:
        """True once the rows in that order have answered. The stage polls it."""
        return bool(self.results.ready)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return SortPickerDemo(context, parent)
