"""The filter-bar demo: facets over Shot, a seeded bar, every value named, Notes, and the sizes.

The port of `apps/site/src/demos/filter-bar/Demo.tsx`. The first bar drives the result set under
it. The Note bar counts two entity facets through the site's own groups and a read state the
site refuses to group, so that facet falls back to a tally of one page and its list says so.
"""
from __future__ import annotations

import json

from qtpy import QtWidgets

from sg_widgets_core.filter import FilterGroup, condition, empty_filter, group, to_api3_hash
from sg_widgets_core.filter_ux import facet_counts

from ...widgets.filter_bar import FilterBar
from ..context import DemoContext
from . import _layout
from ._results import EntityResults, WireView

__all__ = ["build"]

#: The facet the seeded examples tick, and the two beside it.
GROUP_FIELD = "sg_status_list"
SHOT_FACETS = ("sg_status_list", "sg_sequence", "sg_shot_type")
NOTE_FACETS = ("user", "addressings_to", "read_by_current_user")

#: The three steps the last section stands every bar on.
SIZES: tuple[str, ...] = ("sm", "md", "lg")


def seeded_tree() -> FilterGroup:
    """Four statuses and three kinds ticked: the pill names two and reads the rest as `+n`."""
    return group(
        "and",
        [
            condition(GROUP_FIELD, "in", ["ip", "rev", "apr", "fin"]),
            condition("sg_shot_type", "in", ["VFX", "2D", "Full CG"]),
        ],
    )


def every_tree() -> FilterGroup:
    """Every status ticked, on a bar that names every value: the pill holds its cap."""
    return group(
        "and",
        [condition(GROUP_FIELD, "in", ["wtg", "ip", "rev", "apr", "fin", "hld", "omt"])],
    )


class FilterBarDemo(QtWidgets.QWidget):
    """Every example of the page, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filter-bar-demo")
        self._bars: list[FilterBar] = []
        scope = (
            group(
                "and",
                [condition("project", "is", {"type": "Project", "id": context.project_id})],
            )
            if context.live
            else None
        )

        body = _layout.column(self)

        self.bar = self._bar(
            "main",
            context=context.context,
            entity_type="Shot",
            facets=list(SHOT_FACETS),
            labels={"sg_shot_type": "Kind"},
            base_filter=scope,
            value=empty_filter(),
        )
        body.addWidget(self.bar)

        self.results = EntityResults(
            context,
            empty_filter(),
            heading="Shots matching the filter",
            entity_type="Shot",
            noun="Shot",
            sort=GROUP_FIELD,
            parent=self,
        )
        body.addWidget(self.results)
        self.bar.changed.connect(self._on_changed)

        body.addWidget(
            _layout.section(
                "Seeded with four statuses and three kinds",
                self._bar(
                    "seeded",
                    context=context.context,
                    entity_type="Shot",
                    facets=["sg_status_list", "sg_shot_type"],
                    labels={"sg_shot_type": "Kind"},
                    base_filter=scope,
                    value=seeded_tree(),
                ),
                parent=self,
            )
        )

        body.addWidget(
            _layout.section(
                "Every status ticked, every value named",
                self._bar(
                    "every",
                    context=context.context,
                    entity_type="Shot",
                    facets=["sg_status_list"],
                    max_values=0,
                    base_filter=scope,
                    value=every_tree(),
                ),
                parent=self,
            )
        )

        notes = self._bar(
            "notes",
            context=context.context,
            entity_type="Note",
            facets=list(NOTE_FACETS),
            labels={"user": "From"},
            counts=facet_counts(context.client, "Note"),
            base_filter=scope,
            value=empty_filter(),
        )
        self.note_wire = WireView(self)
        self.note_wire.setObjectName("note-filter-json")
        self.note_wire.set_text(_wire_text(empty_filter()))
        notes.changed.connect(
            lambda value: self.note_wire.set_text(_wire_text(value))
            if _layout.alive(self)
            else None
        )
        body.addWidget(
            _layout.section(
                "Notes by sender, recipient and read state, counted by the site",
                notes,
                self.note_wire,
                parent=self,
            )
        )

        stack = QtWidgets.QWidget(self)
        rows = QtWidgets.QVBoxLayout(stack)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(_layout.SECTION_GAP)
        for size in SIZES:
            rows.addWidget(
                self._bar(
                    size,
                    context=context.context,
                    entity_type="Shot",
                    facets=["sg_status_list", "sg_shot_type"],
                    labels={"sg_shot_type": "Kind"},
                    size=size,
                    base_filter=scope,
                    value=seeded_tree(),
                    parent=stack,
                )
            )
        body.addWidget(_layout.section("Sizes", stack, parent=self))
        body.addStretch(1)

    def _bar(self, name: str, parent: QtWidgets.QWidget | None = None, **props: object) -> FilterBar:
        made = FilterBar(parent=parent if parent is not None else self, **props)
        made.setObjectName(f"filter-bar-{name}")
        self._bars.append(made)
        return made

    def _on_changed(self, value: FilterGroup) -> None:
        if _layout.alive(self):
            self.results.set_value(value)

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The sizes section names its own."""
        self.bar.set_size(size)

    @property
    def demo_ready(self) -> bool:
        """True once the result set under the bar has answered. The stage polls it."""
        return bool(self.results.demo_ready) and not self.bar.counting


def _wire_text(value: FilterGroup) -> str:
    return json.dumps(to_api3_hash(value), indent=2)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FilterBarDemo(context, parent)
