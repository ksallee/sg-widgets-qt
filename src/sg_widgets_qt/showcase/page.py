"""One documentation page: its prose, its demo stages and its props tables.

`docs/widgets/<name>.md` is the page; `docs/widgets/<name>.props.json` beside it holds the tables.
A `QTextBrowser` cannot hold a widget, so a page is a column of blocks instead: the prose in text
blocks, each as tall as its content and with no scrollbar of its own, and between them the stages
and the tables, all inside one scroll area wearing the overlay scrollbar.
"""
from __future__ import annotations

import json
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

from ..theme import Theme, theme_of, watch_theme
from . import chrome, markdown
from .context import DemoContext, repo_root
from .prefs import Prefs
from .stage import DemoStage, demo_module_name

__all__ = ["PropsTable", "WidgetPage", "docs_dir", "page_path"]

#: The columns each kind of table draws, and what the header calls them.
TABLE_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "props": (("name", "Name"), ("py_type", "Type"), ("default", "Default"), ("meaning", "Meaning")),
    "events": (("name", "Signal"), ("payload", "Payload"), ("when", "When")),
    "slots": (("name", "Slot"), ("receives", "Receives"), ("draws", "Draws")),
    "keyboard": (("key", "Key"), ("does", "Does")),
}

#: Where a page of each section lives.
SECTIONS = ("widgets", "core", "start")


def docs_dir() -> Path:
    """The `docs/` of this checkout."""
    return repo_root() / "docs"


def page_path(name: str, root: Path | None = None) -> Path | None:
    """The markdown file of a page, by its name or its `section/name`."""
    base = root if root is not None else docs_dir()
    if "/" in name:
        section, _, leaf = name.partition("/")
        found = base / section / (leaf + ".md")
        return found if found.is_file() else None
    for section in SECTIONS:
        found = base / section / (name + ".md")
        if found.is_file():
            return found
    return None


def _strip(value: object) -> str:
    """A props cell as plain text: the backticks and the `kbd` runs of the upstream cell dropped."""
    text = "" if value is None else str(value)
    return (
        text.replace("<kbd>", "").replace("</kbd>", "").replace("`", "").replace("<br>", " ").strip()
    )


class _Prose(QtWidgets.QTextBrowser):
    """One run of prose, as tall as its content and with no scrollbar of its own."""

    def __init__(self, source: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("prose")
        self._source = source
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setOpenExternalLinks(True)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        watch_theme(self, self.restyle)
        self.restyle(theme_of(self))

    def restyle(self, theme: Theme) -> None:
        """Dress the document from the theme and lay it out again."""
        self.document().setDefaultStyleSheet(markdown.stylesheet(theme))
        self.document().setDefaultFont(theme.font(14))
        self.setHtml(markdown.to_html(self._source, theme))
        self._fit()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        document = self.document()
        document.setTextWidth(max(1, self.viewport().width()))
        self.setFixedHeight(int(document.size().height()) + 4)


class _RowDelegate(QtWidgets.QStyledItemDelegate):
    """A props table's cell: the documented inset, the row line, and the selection left out."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        theme = theme_of(self.parent())
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        box = QtCore.QRectF(option.rect)
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.drawLine(
            QtCore.QPointF(box.left(), box.bottom() - 0.5),
            QtCore.QPointF(box.right(), box.bottom() - 0.5),
        )
        mono = bool(index.data(QtCore.Qt.ItemDataRole.UserRole))
        painter.setFont(theme.font(12, mono=True) if mono else theme.font(13))
        painter.setPen(theme.color("foreground" if not mono else "muted_foreground"))
        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")
        painter.drawText(
            box.adjusted(12, 8, -12, -8).toRect(),
            int(
                QtCore.Qt.AlignmentFlag.AlignTop
                | QtCore.Qt.AlignmentFlag.AlignLeft
                | QtCore.Qt.TextFlag.TextWordWrap
            ),
            text,
        )
        painter.restore()

    def sizeHint(  # noqa: N802
        self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex
    ) -> QtCore.QSize:
        theme = theme_of(self.parent())
        mono = bool(index.data(QtCore.Qt.ItemDataRole.UserRole))
        metrics = QtGui.QFontMetrics(theme.font(12, mono=True) if mono else theme.font(13))
        width = max(80, option.rect.width() - 24)
        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "")
        box = metrics.boundingRect(
            QtCore.QRect(0, 0, width, 10000), int(QtCore.Qt.TextFlag.TextWordWrap), text
        )
        return QtCore.QSize(option.rect.width(), box.height() + 16)


class PropsTable(QtWidgets.QWidget):
    """One table of a page: props, events, slots or keyboard.

    The `py_type` is what a row shows; the upstream TypeScript type is its tooltip.
    """

    def __init__(
        self,
        name: str,
        kind: str = "props",
        root: Path | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("props-table")
        self.data_name = name
        self.data_kind = kind
        self._rows = self._read(name, kind, root)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        columns = TABLE_COLUMNS.get(kind, TABLE_COLUMNS["props"])
        surface = chrome.primitive("TableSurface")
        self.table = self._build_table(columns, surface)
        layout.addWidget(self.table)
        watch_theme(self, self._restyle)
        self._restyle(theme_of(self))

    @property
    def row_count(self) -> int:
        """Rows the table draws."""
        return len(self._rows)

    def _read(self, name: str, kind: str, root: Path | None) -> list[dict]:
        base = root if root is not None else docs_dir()
        path = base / "widgets" / (name + ".props.json")
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        rows = data.get(kind) or []
        return [row for row in rows if isinstance(row, dict)]

    def _build_table(self, columns: tuple, surface: object) -> QtWidgets.QTableWidget:
        table = QtWidgets.QTableWidget(len(self._rows), len(columns), self)
        table.setObjectName("props-table-view")
        table.setHorizontalHeaderLabels([label for _key, label in columns])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setWordWrap(True)
        table.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setItemDelegate(_RowDelegate(self))
        header = table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        for column, (key, _label) in enumerate(columns):
            mode = (
                QtWidgets.QHeaderView.ResizeMode.Stretch
                if key in ("meaning", "when", "draws", "does")
                else QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
            header.setSectionResizeMode(column, mode)
        for row, values in enumerate(self._rows):
            for column, (key, _label) in enumerate(columns):
                item = QtWidgets.QTableWidgetItem(_strip(values.get(key)))
                if key in ("name", "py_type", "type", "default", "key", "payload", "receives"):
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, True)
                if key == "py_type" and values.get("type"):
                    item.setToolTip("TypeScript: " + _strip(values.get("type")))
                if key == "meaning" and values.get("owner"):
                    item.setToolTip("From " + _strip(values.get("owner")))
                table.setItem(row, column, item)
        return table

    def _restyle(self, theme: Theme) -> None:
        self.table.setStyleSheet(
            _TABLE_QSS.format(
                muted=theme.muted_foreground,
                border=theme.border,
                background=theme.background,
            )
        )
        self.table.horizontalHeader().setFont(theme.font(12, weight=QtGui.QFont.Weight.Medium))
        self.table.resizeRowsToContents()
        self._fit()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.table.resizeRowsToContents()
        self._fit()

    def _fit(self) -> None:
        height = self.table.horizontalHeader().height()
        for row in range(self.table.rowCount()):
            height += self.table.rowHeight(row)
        self.table.setFixedHeight(height + 2)
        self.setFixedHeight(height + 2)


_TABLE_QSS = """
QTableWidget {{
    background: transparent;
    border: none;
    color: {muted};
}}
QHeaderView::section {{
    background: transparent;
    color: {muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 8px 12px;
    text-transform: uppercase;
}}
"""


class _Heading(QtWidgets.QWidget):
    """The page head: the title at 24px medium and the description at 14px muted under it."""

    def __init__(
        self, title: str, description: str, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-heading")
        self._title = title
        self._description = description
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum
        )
        watch_theme(self, lambda _theme: self.updateGeometry())

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(0, 56 if self._description else 34)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setFont(theme.font(24, weight=QtGui.QFont.Weight.Medium))
        painter.setPen(theme.color("foreground"))
        metrics = QtGui.QFontMetrics(painter.font())
        painter.drawText(
            QtCore.QRect(0, 0, self.width(), 32),
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(self._title, QtCore.Qt.TextElideMode.ElideRight, self.width()),
        )
        if self._description:
            painter.setFont(theme.font(14))
            painter.setPen(theme.color("muted_foreground"))
            metrics = QtGui.QFontMetrics(painter.font())
            painter.drawText(
                QtCore.QRect(0, 34, self.width(), 22),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                metrics.elidedText(
                    self._description, QtCore.Qt.TextElideMode.ElideRight, self.width()
                ),
            )
        painter.end()


class WidgetPage(QtWidgets.QWidget):
    """One page of the showcase: the prose, the stages and the tables, in one scroll area."""

    def __init__(
        self,
        name: str,
        context: DemoContext | None = None,
        prefs: Prefs | None = None,
        root: Path | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.data_name = name
        self._root = root if root is not None else docs_dir()
        self._context = context
        self._prefs = prefs if prefs is not None else Prefs(self, persist=False)
        #: Every stage on the page, in the order the prose puts them.
        self.stages: list[DemoStage] = []
        #: Every table on the page.
        self.tables: list[PropsTable] = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = chrome.overlay_scroll_area(self)
        outer.addWidget(self.scroll)

        body = QtWidgets.QWidget(self.scroll)
        body.setObjectName("page-body")
        self._column = QtWidgets.QVBoxLayout(body)
        self._column.setContentsMargins(24, 24, 24, 24)
        self._column.setSpacing(16)
        self.scroll.setWidget(body)

        meta, blocks = self._read()
        self.title = meta.get("title", name)
        self.description = meta.get("description", "")
        self._column.addWidget(_Heading(self.title, self.description, body))
        for block in blocks:
            self._add(block, body)
        self._column.addStretch(1)

    @property
    def ready(self) -> bool:
        """True once every stage on the page has built and its first read has settled."""
        return all(stage.ready for stage in self.stages)

    def stage(self, name: str) -> DemoStage | None:
        """The stage of that demo name."""
        for found in self.stages:
            if found.data_name == name:
                return found
        return None

    def _read(self) -> tuple[dict, list[markdown.Block]]:
        path = page_path(self.data_name, self._root)
        if path is not None:
            meta, body = markdown.front_matter(path.read_text(encoding="utf-8"))
            return meta, markdown.split_blocks(body)
        # A name with no page of its own, but a demo module: the demo alone, so
        # `qa.py --page hello` opens something.
        try:
            __import__(demo_module_name(self.data_name))
        except ImportError:
            return (
                {"title": self.data_name, "description": "No page and no demo of this name."},
                [],
            )
        return (
            {"title": self.data_name, "description": "The demo, with no page beside it."},
            [markdown.Block("demo", name=self.data_name, title=self.data_name)],
        )

    def _add(self, block: markdown.Block, parent: QtWidgets.QWidget) -> None:
        if block.kind == "text":
            self._column.addWidget(_Prose(block.source, parent))
            return
        if block.kind == "demo":
            stage = DemoStage(block.name, block.title, self._context, self._prefs, parent)
            self.stages.append(stage)
            self._column.addWidget(stage)
            return
        table = PropsTable(block.name, block.table, self._root, parent)
        if table.row_count:
            self.tables.append(table)
            self._column.addWidget(table)
        else:
            table.setParent(None)
            table.deleteLater()
