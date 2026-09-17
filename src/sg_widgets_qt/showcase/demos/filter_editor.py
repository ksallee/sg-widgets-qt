"""The filter-editor demo: a nested tree on Version, a Note read-state row, and the sizes.

The port of `apps/site/src/demos/filter-editor/Demo.tsx`. The tree is one a person would build:
a status list on the multi picker, two conditions reached through links, a duration and a nested
any-of holding a list of values, a colour and two relative windows. The duration is typed
`1h 30m` or `1:30` and goes out as the 90 minutes it stores.

The link rows name the fixtures' own sequence and project, so a real site gets the status row
alone and the reviewer builds the rest against rows that exist.
"""
from __future__ import annotations

import json

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef, FilterGroup, condition, group, to_api3_hash

from ...widgets.filter_editor import FilterEditor
from ..context import DemoContext
from . import _layout
from ._results import VersionResults, WireView

__all__ = ["build"]

#: The three steps the last section stands every control on.
SIZES: tuple[str, ...] = ("sm", "md", "lg")


def initial(live: bool) -> FilterGroup:
    """The tree the page opens on."""
    status = condition("sg_status_list", "in", ["rev", "vwd", "fin", "cmpt", "apr"])
    if live:
        return group("and", [status])
    return group(
        "and",
        [
            status,
            condition(
                "entity.Shot.sg_sequence", "is", EntityRef(type="Sequence", id=100, name="sh010")
            ),
            condition("project.Project.sg_status", "is", "Active"),
            condition("entity.Shot.sg_working_duration", "greater_than", 90),
            group(
                "or",
                [
                    condition("code", "contains", "comp"),
                    condition("sg_version_type", "in", ["Type A", "Type B"]),
                    condition("sg_bar_color", "is", "253,94,99"),
                    condition("sg_first_frame", "in", [1001, 1101]),
                    condition("created_at", "in_last", [3, "MONTH"]),
                    condition("entity.Shot.sg_turnover_date", "in_next", [2, "WEEK"]),
                ],
            ),
        ],
    )


def sized_tree() -> FilterGroup:
    """One row per control kind: a status list on the multi picker and a text on the input."""
    return group(
        "and",
        [condition("sg_status_list", "in", ["rev"]), condition("code", "contains", "sh")],
    )


class FilterEditorDemo(QtWidgets.QWidget):
    """Every example of the page, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filter-editor-demo")
        self._sized: list[FilterEditor] = []

        body = _layout.column(self)

        self.editor = FilterEditor(
            entity_type="Version",
            context=context.context,
            value=initial(context.live),
            hide_paths=["sg_task"],
            parent=self,
        )
        self.editor.setObjectName("filter-editor-main")
        body.addWidget(self.editor)

        self.wire = WireView(self)
        self.wire.setObjectName("filter-json")
        self.wire.set_text(_wire_text(self.editor.value))
        body.addWidget(_layout.section("api3_hash", self.wire, parent=self))

        self.results = VersionResults(context, self.editor.value, parent=self)
        body.addWidget(self.results)

        self.editor.changed.connect(self._on_changed)

        note = FilterEditor(
            entity_type="Note",
            context=context.context,
            value=group("and", [condition("read_by_current_user", "is", "unread")]),
            parent=self,
        )
        note.setObjectName("filter-editor-note")
        body.addWidget(
            _layout.section(
                "Note, whose read-state field takes is and is not alone", note, parent=self
            )
        )

        stack = QtWidgets.QWidget(self)
        rows = QtWidgets.QVBoxLayout(stack)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(_layout.SECTION_GAP)
        for size in SIZES:
            made = FilterEditor(
                entity_type="Version",
                context=context.context,
                value=sized_tree(),
                size=size,
                parent=stack,
            )
            made.setObjectName(f"filter-editor-{size}")
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
        self.editor.set_size(size)

    @property
    def demo_ready(self) -> bool:
        """True once the result set under the editor has answered. The stage polls it."""
        return bool(self.results.demo_ready)


def _wire_text(value: FilterGroup) -> str:
    return json.dumps(to_api3_hash(value), indent=2)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FilterEditorDemo(context, parent)
