"""The result set a filter demo shows under its editor.

The port of `apps/site/src/demos/_shared/results.ts` and the source half of its
`version-results.tsx`. Every filter demo answers the same question, what does this tree match,
so the columns, the debounce, the project scoping and the count line live here rather than in
each demo.

The rows are drawn where upstream draws them: `EntityTable` under the editor, the dialog and
the sort picker, and `GroupedList` under the filter bar, both over one `EntitySource` so the
count and the rows answer the same filter.

    results = VersionResults(context, tree, parent=self)
    editor.changed.connect(results.set_value)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.client import SummarizeOptions, SummaryField
from sg_widgets_core.collection import (
    ColumnSpec,
    EntitySourceOptions,
    SortSpec,
    create_entity_source,
    resolve_columns,
)
from sg_widgets_core.filter import FilterNode, condition, group, to_api3_hash

from ...images import image_loader
from ...primitives.scrollbar import install_overlay_scrollbars
from ...theme import theme_of, watch_theme
from ...widgets.entity_table import EntityTable
from ...widgets.grouped_list import GroupedList
from ...workers import Debounce, Ticket, default_pool
from .. import chrome
from ..context import DemoContext
from . import _layout

__all__ = [
    "RESULT_DEBOUNCE_MS",
    "RESULT_PAGE_SIZE",
    "SHOT_COLUMNS",
    "VERSION_COLUMNS",
    "ResultCount",
    "columns_for",
    "to_sort_specs",
    "EntityResults",
    "VersionResults",
    "WireView",
    "match_label",
    "read_count",
    "scope_to_project",
]

#: Keystrokes settle before the result set is read again.
RESULT_DEBOUNCE_MS = 250

#: Rows per page in a result set.
RESULT_PAGE_SIZE = 25

#: `p-3` of the block a demo draws its serialised filter in, and the one line it never
#: falls under.
WIRE_PAD = 12
WIRE_MIN_HEIGHT = 44


#: `maxHeight="20rem"` of every result set upstream.
RESULT_MAX_HEIGHT = "20rem"

#: The columns a Version result set is shown with.
VERSION_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(path="code", width=220),
    ColumnSpec(path="entity", width=140),
    ColumnSpec(path="sg_status_list", width=130),
    ColumnSpec(path="user", width=150),
    ColumnSpec(path="created_at", width=170),
    ColumnSpec(path="description", width=260),
)

#: The columns a Shot result set is shown with, which the sort picker orders.
SHOT_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(path="code", width=200),
    ColumnSpec(path="sg_status_list", width=130),
    ColumnSpec(path="sg_sequence", width=150),
    ColumnSpec(path="sg_shot_type", width=130),
    ColumnSpec(path="updated_at", width=170),
)

#: The grouped set under the filter bar: the heading, the muted line and the right-hand column.
GROUPED_COLUMNS: tuple[ColumnSpec, ...] = (
    ColumnSpec(path="code"),
    ColumnSpec(path="sg_status_list"),
    ColumnSpec(path="description"),
    ColumnSpec(path="sg_sequence"),
)


def columns_for(entity_type: str, grouped: bool = False) -> tuple[ColumnSpec, ...]:
    """The columns a result set over one type is drawn with."""
    if grouped:
        return GROUPED_COLUMNS
    return SHOT_COLUMNS if entity_type == "Shot" else VERSION_COLUMNS


def to_sort_specs(sort: str) -> list[SortSpec]:
    """A `sort` string as the source's own sort: a leading `-` is descending."""
    out: list[SortSpec] = []
    for part in (sort or "").split(","):
        name = part.strip()
        if not name:
            continue
        out.append(SortSpec(path=name.lstrip("-"), descending=name.startswith("-")))
    return out


def scope_to_project(context: DemoContext, tree: FilterNode) -> FilterNode:
    """The tree as the source reads it, scoped to the project the toolbar picked."""
    # The mock's rows are one project's already; a real site's are not.
    if not context.live:
        return tree
    return group(
        "and",
        [condition("project", "is", {"type": "Project", "id": context.project_id}), tree],
    )


@dataclass
class ResultCount:
    """What a count line reads while the total is on its way, or when there is none."""

    kind: str = "counting"
    total: int = 0
    message: str = ""


def match_label(count: ResultCount, noun: str) -> str:
    """`3 Versions match`."""
    if count.kind == "counting":
        return "Counting…"
    if count.kind == "none":
        return "The site answered no count."
    if count.kind == "error":
        return count.message
    plural = "" if count.total == 1 else "s"
    verb = "es" if count.total == 1 else ""
    return f"{count.total} {noun}{plural} match{verb}"


def read_count(count: Callable[[], int | None]) -> ResultCount:
    """The count of the filter the source now holds, as a state a view can render."""
    try:
        total = count()
    except Exception as error:  # noqa: BLE001
        # A path the site cannot summarize fails the call; the demo says so in place.
        return ResultCount(kind="error", message=str(error))
    return ResultCount(kind="none") if total is None else ResultCount(kind="ready", total=total)


class _CountLine(chrome.TextLine):
    """The line reading how many rows match, which turns `destructive` on a refusal."""

    def set_token(self, token: str) -> None:
        """Draw the line in another token."""
        self._token = token
        self.update()


class EntityResults(QtWidgets.QWidget):
    """The rows a filter tree matches: the count and the table behind it.

    The editor emits a tree on every keystroke, so the read is debounced. The count and the rows
    come from one source, so both answer the same filter, and a path the site refuses fails that
    read rather than the page: the line says so in place.
    """

    def __init__(
        self,
        context: DemoContext,
        value: FilterNode,
        heading: str = "Versions matching the filter",
        entity_type: str = "Version",
        noun: str = "Version",
        sort: str = "",
        grouped: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-results")
        self._context = context
        self._entity_type = entity_type
        self._noun = noun
        self._value = value
        self._count = ResultCount()
        self._ticket = Ticket()
        self._debounce = Debounce(RESULT_DEBOUNCE_MS, self)
        self._columns = list(columns_for(entity_type, grouped))
        self._resolved = False
        #: False while a read is in flight. The stage polls it.
        self.demo_ready = False

        # The first tree goes in at construction, so the source's own first read is already
        # the filtered one.
        self._source = create_entity_source(
            EntitySourceOptions(
                client=context.client,
                entity_type=entity_type,
                fields=[column.path for column in self._columns],
                filters=to_api3_hash(scope_to_project(context, value)),
                sort=to_sort_specs(sort),
                mode="more",
                page_size=RESULT_PAGE_SIZE,
            )
        )

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(_layout.INNER_GAP)
        column.addWidget(_layout.heading(heading, self))

        self._line = _CountLine("Counting…", size=14, parent=self)
        self._line.setObjectName("result-count")
        column.addWidget(self._line)

        empty = f"No {noun} matches this filter"
        if grouped:
            # The bar's set is the grouped list upstream draws under it, keyed on the facet
            # the demo groups by.
            self._view: QtWidgets.QWidget = GroupedList(
                source=self._source,
                group_by=self._columns[1],
                sub_label_field=self._columns[2].path,
                secondary_field=self._columns[3].path,
                context=context,
                paging="more",
                max_height=RESULT_MAX_HEIGHT,
                empty_label=empty,
                parent=self,
            )
        else:
            self._view = EntityTable(
                source=self._source,
                columns=self._columns,
                context=context,
                paging="more",
                max_height=RESULT_MAX_HEIGHT,
                empty_label=empty,
                parent=self,
            )
        self._view.setObjectName("result-rows")
        column.addWidget(self._view)

        self._read_columns()
        self._read()

    # --- what it shows --------------------------------------------------------------------

    @property
    def value(self) -> FilterNode:
        """The tree the set answers."""
        return self._value

    def set_value(self, value: FilterNode) -> None:
        """Take a tree and read the set again once the keystrokes have settled."""
        self._value = value
        self.demo_ready = False
        self._debounce.call(self._read)

    @property
    def sort(self) -> str:
        """The `sort` string the rows come back in."""
        return ",".join(
            ("-" if one.descending else "") + one.path for one in self._source.sort or []
        )

    def set_sort(self, value: str) -> None:
        """Order the rows. A key the site cannot sort on is a silent no-op (026_result_order)."""
        self._sort = to_sort_specs(value)
        self.demo_ready = False
        self._debounce.call(self._read)

    @property
    def count(self) -> ResultCount:
        """The count the last read answered."""
        return self._count

    def count_line(self) -> QtWidgets.QWidget:
        """The line reading how many rows match."""
        return self._line

    def table(self) -> QtWidgets.QWidget:
        """The view the rows are drawn in."""
        return self._view

    def rows(self) -> list[Any]:
        """The rows the view is drawing."""
        return list(self._view.control.rows)

    def flush(self) -> None:
        """Read now rather than at the end of the pause. For a test that cannot wait."""
        self._debounce.flush()

    # --- the columns ----------------------------------------------------------------------

    def _read_columns(self) -> None:
        context = self._context
        entity_type = self._entity_type
        specs = list(self._columns)

        def resolve() -> tuple[Any, Any]:
            return resolve_columns(context.schema, entity_type, specs), dict(
                context.statuses.by_code()
            )

        default_pool().submit(resolve, on_result=self._columns_read, on_error=self._failed)

    def _columns_read(self, answer: Any) -> None:
        if not _layout.alive(self):
            return
        columns, statuses = answer
        self._view.set_statuses(statuses)
        if isinstance(self._view, EntityTable):
            self._view.set_columns(columns)
        elif len(columns) > 3:
            # A grouped list draws its heading, its muted line and its right-hand column from
            # the resolved schema, so a status heading reads its name and an entity its own.
            self._view.set_group_by(columns[1])
            self._view.set_sub_label_field(columns[2])
            self._view.set_secondary_field(columns[3])
        self._resolved = True

    # --- the read -------------------------------------------------------------------------

    def _read(self) -> None:
        client = self._context.client
        wire = to_api3_hash(scope_to_project(self._context, self._value))
        entity_type = self._entity_type
        # An unchanged tree only re-counts: setting the same filter would re-read the page.
        if self._view.control.filters != wire:
            self._view.set_filters(wire)
        wanted = getattr(self, "_sort", None)
        if wanted is not None:
            self._view.set_sort(wanted)
            self._sort = None

        def run() -> ResultCount:
            return read_count(lambda: _total(client, entity_type, wire))

        self._count = ResultCount()
        self._line.set_text(match_label(self._count, self._noun))
        token = self._ticket.next()
        default_pool().submit(
            run, on_result=self._answered, on_error=self._failed, ticket=(self._ticket, token)
        )

    def _answered(self, found: ResultCount) -> None:
        if not _layout.alive(self):
            return
        self._count = found
        self._line.set_text(match_label(self._count, self._noun))
        self._line.set_token("destructive" if self._count.kind == "error" else "muted_foreground")
        self.demo_ready = True

    def _failed(self, error: BaseException) -> None:
        if not _layout.alive(self):
            return
        self._count = ResultCount(kind="error", message=str(error))
        self._line.set_text(self._count.message)
        self._line.set_token("destructive")
        self.demo_ready = True

    @property
    def ready(self) -> bool:
        """True once the columns, the first page and the count have all landed."""
        return (
            self.demo_ready
            and self._resolved
            and self._view.control.snapshot().status in ("ready", "error")
            # A cell's picture lands after the rows do, and a screenshot wants both.
            and image_loader().pending == 0
        )


class VersionResults(EntityResults):
    """The Versions a filter tree matches, which is what the filter demos show."""


def _total(client: Any, entity_type: str, wire: Any) -> int | None:
    """The total the filter matches, through `_summarize` (020_summarize)."""
    summary = client.summarize(
        entity_type,
        SummarizeOptions(filters=wire, summary_fields=[SummaryField(field="id", type="count")]),
    )
    total = summary.summaries.get("id")
    return int(total) if isinstance(total, (int, float)) and not isinstance(total, bool) else None


class WireView(QtWidgets.QPlainTextEdit):
    """The serialised filter, in the monospace family at the metadata step.

    A demo shows what its tree sends, so the block is read-only and scrolls at the height
    upstream gives it.
    """

    #: `max-h-64` of the block upstream draws the JSON in.
    MAX_HEIGHT = 256

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wire-view")
        self.setReadOnly(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumHeight(self.MAX_HEIGHT)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.document().setDocumentMargin(WIRE_PAD)
        install_overlay_scrollbars(self)
        watch_theme(self, lambda _theme: self._apply_theme())
        self._apply_theme()

    def set_text(self, text: str) -> None:
        """Write the serialised filter into the block."""
        self.setPlainText(text)
        # A `max-h-64` block is as tall as its filter and never shorter: a column that runs
        # past the page would otherwise take its slack out of the one widget that has any.
        self.setFixedHeight(self.sizeHint().height())
        self.updateGeometry()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        """As tall as the filter it holds, up to the height the block scrolls at.

        A plain text document measures its height in lines, not pixels, so the block counts
        them and multiplies by the line it is set in.
        """
        spacing = QtGui.QFontMetrics(self.font()).lineSpacing()
        tall = self.document().blockCount() * spacing + 2 * WIRE_PAD
        return QtCore.QSize(
            super().sizeHint().width(), min(self.MAX_HEIGHT, max(WIRE_MIN_HEIGHT, tall))
        )

    def _apply_theme(self) -> None:
        theme = theme_of(self)
        self.setFont(theme.font(12, mono=True))
        self.viewport().setAutoFillBackground(False)
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self.viewport())
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        radius = float(theme.radius_px("lg"))
        box = QtCore.QRectF(self.viewport().rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(theme.color("muted"))
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.drawRoundedRect(box, radius, radius)
        painter.end()
        super().paintEvent(event)
