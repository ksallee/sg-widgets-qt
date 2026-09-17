"""The result set a filter demo shows under its editor.

The port of `apps/site/src/demos/_shared/results.ts` and the source half of its
`version-results.tsx`. Every filter demo answers the same question, what does this tree match,
so the columns, the debounce, the project scoping and the count line live here rather than in
each demo.

The table itself is `entity-table`, which is not ported yet, so the rows are drawn as the
matching Version codes in a list surface. When the table lands, the list is what it replaces.

    results = VersionResults(context, tree, parent=self)
    editor.changed.connect(results.set_value)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, Qt

from sg_widgets_core.client import Page, SearchOptions, SummarizeOptions, SummaryField
from sg_widgets_core.filter import FilterNode, condition, group, to_api3_hash

from ...primitives.list_view import ListSurface
from ...primitives.roles import Roles
from ...primitives.row_delegate import RowDelegate
from ...primitives.scrollbar import install_overlay_scrollbars
from ...theme import theme_of, watch_theme
from ...workers import Debounce, Ticket, default_pool
from .. import chrome
from ..context import DemoContext
from . import _layout

__all__ = [
    "RESULT_DEBOUNCE_MS",
    "RESULT_PAGE_SIZE",
    "VERSION_COLUMNS",
    "ResultColumn",
    "ResultCount",
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


@dataclass(frozen=True)
class ResultColumn:
    """One column of a result set: the path it reads and the width it is drawn at."""

    path: str
    width: int


#: The columns a Version result set is shown with.
VERSION_COLUMNS: tuple[ResultColumn, ...] = (
    ResultColumn("code", 220),
    ResultColumn("entity", 140),
    ResultColumn("sg_status_list", 130),
    ResultColumn("user", 150),
    ResultColumn("created_at", 170),
    ResultColumn("description", 260),
)


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


class _CodeModel(QtCore.QAbstractListModel):
    """The matching rows, as the code each one carries and its status beside it."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str]] = []

    def set_rows(self, rows: Sequence[tuple[str, str]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= index.row() < len(self._rows):
            return None
        label, secondary = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return label
        if role == Roles.SECONDARY:
            return secondary
        if role == Roles.KIND:
            return "row"
        return None

    def flags(self, index: QModelIndex) -> Any:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


@dataclass
class _Read:
    """One answer of the pair of reads a result set takes."""

    rows: list[tuple[str, str]] = dc_field(default_factory=list)
    total: ResultCount = dc_field(default_factory=ResultCount)


class EntityResults(QtWidgets.QWidget):
    """The rows a filter tree matches: the count and the codes behind it.

    The editor emits a tree on every keystroke, so the read is debounced. The count and the
    rows come from one read, so both answer the same filter, and a path the site refuses fails
    that read rather than the page: the line says so in place.
    """

    #: How tall the list of matching codes grows before it scrolls.
    MAX_HEIGHT = 320

    def __init__(
        self,
        context: DemoContext,
        value: FilterNode,
        heading: str = "Versions matching the filter",
        entity_type: str = "Version",
        noun: str = "Version",
        sort: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("entity-results")
        self._context = context
        self._entity_type = entity_type
        self._noun = noun
        self._sort = sort
        self._value = value
        self._count = ResultCount()
        self._ticket = Ticket()
        self._debounce = Debounce(RESULT_DEBOUNCE_MS, self)
        #: False while a read is in flight. The stage polls it.
        self.demo_ready = False

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(_layout.INNER_GAP)
        column.addWidget(_layout.heading(heading, self))

        self._line = _CountLine("Counting…", size=14, parent=self)
        self._line.setObjectName("result-count")
        column.addWidget(self._line)

        self._model = _CodeModel(self)
        delegate = RowDelegate(None, size="md", thumbnail=False, indicator="none")
        self._list = ListSurface(self, max_height=self.MAX_HEIGHT, size="md", delegate=delegate)
        delegate.setParent(self._list)
        self._list.setObjectName("result-rows")
        self._list.setModel(self._model)
        column.addWidget(self._list)

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
        return self._sort

    def set_sort(self, value: str) -> None:
        """Order the rows. A key the site cannot sort on is a silent no-op (026_result_order)."""
        self._sort = value or ""
        self.demo_ready = False
        self._debounce.call(self._read)

    @property
    def count(self) -> ResultCount:
        """The count the last read answered."""
        return self._count

    def count_line(self) -> QtWidgets.QWidget:
        """The line reading how many rows match."""
        return self._line

    def rows(self) -> list[tuple[str, str]]:
        """The codes the list is drawing."""
        return list(self._model._rows)  # noqa: SLF001

    def flush(self) -> None:
        """Read now rather than at the end of the pause. For a test that cannot wait."""
        self._debounce.flush()

    # --- the read -------------------------------------------------------------------------

    def _read(self) -> None:
        client = self._context.client
        wire = to_api3_hash(scope_to_project(self._context, self._value))
        entity_type = self._entity_type
        # A Version set reads the columns the table would draw; another type reads the two
        # the list stands on until `entity-table` lands.
        fields = (
            [column.path for column in VERSION_COLUMNS]
            if entity_type == "Version"
            else ["code", "sg_status_list"]
        )
        sort = self._sort or None

        def run() -> _Read:
            found = read_count(lambda: _total(client, entity_type, wire))
            if found.kind == "error":
                return _Read(rows=[], total=found)
            page = client.search(
                entity_type,
                SearchOptions(
                    filters=wire,
                    fields=fields,
                    sort=sort,
                    page=Page(size=RESULT_PAGE_SIZE),
                ),
            )
            return _Read(rows=[_row_of(row) for row in page.data], total=found)

        self._count = ResultCount()
        self._line.set_text(match_label(self._count, self._noun))
        token = self._ticket.next()
        default_pool().submit(
            run,
            on_result=self._answered,
            on_error=self._failed,
            ticket=(self._ticket, token),
        )

    def _answered(self, found: _Read) -> None:
        self._count = found.total
        self._line.set_text(match_label(self._count, self._noun))
        self._line.set_token("destructive" if self._count.kind == "error" else "muted_foreground")
        self._model.set_rows(found.rows)
        self._list.setVisible(bool(found.rows))
        self.demo_ready = True

    def _failed(self, error: BaseException) -> None:
        self._count = ResultCount(kind="error", message=str(error))
        self._line.set_text(self._count.message)
        self._line.set_token("destructive")
        self._model.set_rows([])
        self._list.setVisible(False)
        self.demo_ready = True


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


def _row_of(row: Any) -> tuple[str, str]:
    code = row.values.get("code") or f"{row.type} {row.id}"
    status = row.values.get("sg_status_list") or ""
    return str(code), str(status)


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
