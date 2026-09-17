"""The filter-editor demo: a catalogue of Version filters, a Note read-state row, and the sizes.

The port of `apps/site/src/demos/filter-editor/Demo.tsx`. The first tree is a catalogue: one
group per data-type family, each holding a spread of that family's operators, so every value
control and every operator shape is on the page at once.

The Note example stands under it, on a field that takes `is` and `is_not` alone, and the sizes
section stands the same two rows on each step of the ladder.
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
    """The tree the page opens on.

    A catalogue of the editor: one group per data-type family, each holding a spread of that
    family's operators, so every value control and every operator shape is on the page without a
    reader building one. Each row names a field the Version schema carries, on its own or through
    Link and Project, so the chooser draws a resolved path.

    The operators are the ones the field's data type accepts, from the operator-by-type map in
    `sg_widgets_core/field_types.py` (`OPERATORS_BY_TYPE`, from `017_filter_operators` and
    `findings/field_types/*`). A `url` field takes no operator at all and has no row; the mock
    carries no `currency` field.

    The top level is Any: a catalogue holds rows that contradict each other, and Any keeps the
    count under it a count of rows. The link rows name the fixtures' own sequence, shots, assets
    and people, so a real site gets the status row alone and the reviewer builds the rest against
    rows that exist.
    """
    status = condition("sg_status_list", "in", ["rev", "vwd", "fin", "cmpt", "apr"])
    if live:
        return group("and", [status])
    return group(
        "or",
        [
            # text
            group(
                "or",
                [
                    condition("code", "contains", "comp"),
                    condition("code", "starts_with", "sh"),
                    condition("sg_path_to_movie", "ends_with", ".mov"),
                    condition("description", "not_contains", "prores"),
                    condition("sg_department", "is_not", "Comp"),
                ],
            ),
            # number, float, percent and duration. A duration is typed `1h 30m` or `1:30` and
            # goes out as the 90 minutes it stores.
            group(
                "or",
                [
                    condition("sg_first_frame", "between", [1001, 1200]),
                    condition("sg_last_frame", "greater_than", 1100),
                    condition("frame_count", "less_than", 120),
                    condition("sg_first_frame", "in", [1001, 1101]),
                    condition("sg_uploaded_movie_frame_rate", "is_not", 25),
                    condition("entity.Shot.sg_complexity", "greater_than", 60),
                    condition("entity.Shot.sg_working_duration", "greater_than", 90),
                ],
            ),
            # entity and multi_entity. `type_is`, `type_is_not` and `name_contains` compare
            # against a plain string, so they draw a text input rather than a picker.
            group(
                "or",
                [
                    condition(
                        "entity.Shot.sg_sequence",
                        "is",
                        EntityRef(type="Sequence", id=100, name="sh010"),
                    ),
                    condition(
                        "user", "is_not", EntityRef(type="HumanUser", id=20, name="Ada Lovelace")
                    ),
                    condition(
                        "entity",
                        "in",
                        [
                            EntityRef(type="Shot", id=862, name="sh010_0010"),
                            EntityRef(type="Asset", id=1226, name="charAda"),
                        ],
                    ),
                    condition(
                        "entity.Shot.assets",
                        "not_in",
                        [EntityRef(type="Asset", id=1228, name="propLantern")],
                    ),
                    condition("entity", "type_is", "Shot"),
                    condition("entity", "type_is_not", "Asset"),
                    condition("playlists", "name_contains", "dailies"),
                ],
            ),
            # status_list and list, on one value and on many
            group(
                "or",
                [
                    status,
                    condition("sg_status_list", "not_in", ["na", "clsd"]),
                    condition("sg_status_list", "is", "rev"),
                    condition("sg_version_type", "is", "Type A"),
                    condition("project.Project.sg_status", "in", ["Active", "Bidding"]),
                ],
            ),
            # date and date_time, one row per value shape: one date, two dates, a count and a
            # unit, and the calendar entries, which carry their own value and draw no editor.
            group(
                "or",
                [
                    condition("entity.Shot.sg_turnover_date", "is", "2026-10-01"),
                    condition("project.Project.sg_start_date", "is_not", "2026-05-20"),
                    condition(
                        "entity.Shot.sg_turnover_date",
                        "between",
                        ["2026-09-20", "2026-10-20"],
                    ),
                    condition("created_at", "greater_than", "2026-06-20T00:00:00Z"),
                    condition("created_at", "less_than", "2026-08-20T00:00:00Z"),
                    condition("created_at", "in_last", [3, "MONTH"]),
                    condition("entity.Shot.sg_turnover_date", "in_next", [2, "WEEK"]),
                    condition("updated_at", "in_calendar_day", -1),
                    condition("created_at", "in_calendar_week", 0),
                    condition("entity.Shot.sg_turnover_date", "in_calendar_month", 1),
                ],
            ),
            # checkbox, colour and the empty pair, under All, so a group inside a group inside a
            # group reads at three depths.
            group(
                "and",
                [
                    condition("client_approved", "is", True),
                    condition("entity.Shot.sg_omit", "is", False),
                    group(
                        "or",
                        [
                            condition("sg_bar_color", "is", "253,94,99"),
                            condition("sg_bar_color", "is_not", "110,180,200"),
                            group(
                                "or",
                                [
                                    condition("sg_department", "is", None),
                                    condition("sg_department", "is_not", None),
                                ],
                            ),
                        ],
                    ),
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
        """True once every row is drawn and the result set under them has answered.

        A row past the first builds on its own turn of the loop, so a screenshot waits for the
        skeletons to give way before it is taken.
        """
        drawn = all(one.pending_rows() == 0 for one in self.findChildren(FilterEditor))
        return drawn and bool(self.results.ready)


def _wire_text(value: FilterGroup) -> str:
    return json.dumps(to_api3_hash(value), indent=2)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FilterEditorDemo(context, parent)
