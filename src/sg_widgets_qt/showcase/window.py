"""The showcase window: the sidebar, the header and the page between them.

The port of the site's chrome: Starlight's sidebar becomes the left rail, its header becomes the
row of controls that set the view, and a docs page becomes a `WidgetPage`. Nothing here is a stock
Qt control: the rail, its rows, the wordmark and the header band are painted from the tokens.
"""
from __future__ import annotations

import json
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

from sg_widgets_core.filter import EntityRef

from ..theme import Theme, mix, theme_of, watch_theme, with_alpha
from ..widgets.project_picker import ProjectPicker
from . import chrome
from .context import DemoContext, demo_context, live_available
from .page import SECTIONS, WidgetPage, docs_dir
from .prefs import Prefs
from .toolbar import HEADER_KEYS, PrefsToolbar

__all__ = ["ShowcaseWindow", "SidebarEntry", "read_index", "sidebar_model"]

#: The rail's width.
SIDEBAR_WIDTH = 240

#: A row's height.
ROW_HEIGHT = 32

#: The window's title, and the wordmark's.
TITLE = "SG Widgets"


class SidebarEntry:
    """One row of the rail, or one heading above a run of them."""

    def __init__(self, kind: str, name: str = "", label: str = "") -> None:
        self.kind = kind
        self.name = name
        self.label = label


def read_index(root: Path | None = None) -> dict:
    """`docs/widgets/_index.json`, or an empty sidebar where it has not landed."""
    base = root if root is not None else docs_dir()
    path = base / "widgets" / "_index.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _title_of(path: Path) -> str:
    """A page's `title`, without reading more of it than the front matter."""
    try:
        with path.open(encoding="utf-8") as handle:
            for _ in range(12):
                line = handle.readline()
                if not line or line.strip() == "---" and handle.tell() > 8:
                    break
                if line.startswith("title:"):
                    return line.partition(":")[2].strip().strip("'\"")
    except OSError:
        pass
    return path.stem


def sidebar_model(root: Path | None = None) -> list[SidebarEntry]:
    """The rail, in the order `_index.json` gives."""
    base = root if root is not None else docs_dir()
    index = read_index(base)
    out: list[SidebarEntry] = []

    def add(section: str, names: list) -> None:
        for name in names:
            path = base / section / (str(name) + ".md")
            if path.is_file():
                out.append(SidebarEntry("page", section + "/" + str(name), _title_of(path)))

    if index.get("start"):
        out.append(SidebarEntry("heading", label="Start"))
        add("start", list(index["start"]))
    if index.get("core"):
        out.append(SidebarEntry("heading", label="Core"))
        add("core", list(index["core"]))
    overview = index.get("overview")
    if overview:
        path = base / "widgets" / (str(overview) + ".md")
        if path.is_file():
            out.append(SidebarEntry("heading", label="Widgets"))
            out.append(SidebarEntry("page", "widgets/" + str(overview), "Overview"))
    for group in index.get("widgets") or []:
        items = [name for name in group.get("items", []) if (base / "widgets" / (name + ".md")).is_file()]
        if not items:
            continue
        out.append(SidebarEntry("heading", label=str(group.get("category", ""))))
        add("widgets", items)
    return out


class Wordmark(QtWidgets.QWidget):
    """The mark and the title beside it: two tiles, `primary` behind and the ink at 30% in front."""

    def __init__(self, title: str = TITLE, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("wordmark")
        self._title = title
        self.setFixedHeight(28)
        watch_theme(self, lambda _theme: self.update())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        ground = theme.color("sidebar")
        ink = theme.color("sidebar_foreground")
        side = 22.0
        scale = side / 40.0
        radius = max(1.0, theme.radius_px("lg") * 0.5 * scale)
        top = (self.height() - side) / 2.0
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("sidebar_primary"))
        painter.drawRoundedRect(
            QtCore.QRectF(2 * scale, top + 2 * scale, 23 * scale, 23 * scale), radius, radius
        )
        # The gap that lifts the front tile off the back one is the ground, drawn as a stroke
        # outside the tile, so the tile keeps its size.
        front = QtCore.QRectF(15 * scale, top + 15 * scale, 23 * scale, 23 * scale)
        painter.setPen(QtGui.QPen(ground, 2.2 * scale))
        painter.setBrush(mix(ground, ink, 0.3))
        painter.drawRoundedRect(front, radius, radius)

        head, _, tail = self._title.partition(" ")
        x = side + 8.0
        painter.setFont(theme.font(15, weight=QtGui.QFont.Weight.Medium))
        painter.setPen(ink)
        metrics = QtGui.QFontMetrics(painter.font())
        box = QtCore.QRectF(x, 0.0, float(self.width()) - x, float(self.height()))
        painter.drawText(box, int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft), head)
        if tail:
            x += metrics.horizontalAdvance(head + " ")
            painter.setFont(theme.font(15))
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                QtCore.QRectF(x, 0.0, float(self.width()) - x, float(self.height())),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
                tail,
            )
        painter.end()


class SidebarRow(QtWidgets.QWidget):
    """One page in the rail: 32 high, `accent` where it is the page on show."""

    picked = QtCore.Signal(str)

    def __init__(self, name: str, label: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar-item")
        self.data_name = name
        self._label = label
        self._current = False
        self._hover = False
        self.setFixedHeight(ROW_HEIGHT)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)
        watch_theme(self, lambda _theme: self.update())

    def label(self) -> str:
        return self._label

    def set_current(self, current: bool) -> None:
        if self._current == current:
            return
        self._current = current
        self.update()

    def is_current(self) -> bool:
        return self._current

    def enterEvent(self, event: object) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)  # type: ignore[arg-type]

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.picked.emit(self.data_name)
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        box = QtCore.QRectF(self.rect()).adjusted(0.0, 1.0, 0.0, -1.0)
        radius = float(theme.radius_px("md"))
        ink = theme.color("sidebar_foreground")
        if self._current:
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(theme.color("sidebar_accent"))
            painter.drawRoundedRect(box, radius, radius)
            ink = theme.color("sidebar_accent_foreground")
        elif self._hover:
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(with_alpha(theme.color("sidebar_accent"), 0.6))
            painter.drawRoundedRect(box, radius, radius)
        painter.setFont(
            theme.font(13, weight=QtGui.QFont.Weight.Medium if self._current else QtGui.QFont.Weight.Normal)
        )
        painter.setPen(ink if self._current else with_alpha(ink, 0.85))
        metrics = QtGui.QFontMetrics(painter.font())
        text_box = box.adjusted(10, 0, -8, 0)
        painter.drawText(
            text_box,
            int(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft),
            metrics.elidedText(self._label, QtCore.Qt.TextElideMode.ElideRight, int(text_box.width())),
        )
        painter.end()


class SectionHeading(QtWidgets.QWidget):
    """A run's heading: 12px muted, upper case."""

    def __init__(self, label: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar-section")
        self._label = label.upper()
        self.setFixedHeight(28)
        watch_theme(self, lambda _theme: self.update())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        font = theme.font(12, weight=QtGui.QFont.Weight.Medium)
        font.setLetterSpacing(QtGui.QFont.SpacingType.PercentageSpacing, 104)
        painter.setFont(font)
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            self.rect().adjusted(10, 0, -8, 0),
            int(QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignLeft),
            self._label,
        )
        painter.end()


class Sidebar(QtWidgets.QWidget):
    """The rail: the wordmark, the search box and the pages under their headings."""

    picked = QtCore.Signal(str)

    def __init__(self, entries: list[SidebarEntry], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.rows: list[SidebarRow] = []
        self._headings: list[tuple[SectionHeading, list[SidebarRow]]] = []

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(12, 12, 12, 12)
        column.setSpacing(12)
        self.wordmark = Wordmark(TITLE, self)
        column.addWidget(self.wordmark)
        self.search = chrome.SearchField("Search pages", size="sm", parent=self)
        self.search.setObjectName("sidebar-search")
        self.search.text_changed.connect(self._filter)
        column.addWidget(self.search)

        self.scroll = chrome.overlay_scroll_area(self)
        self.scroll.setObjectName("sidebar-scroll")
        body = chrome.Ground("sidebar", self.scroll)
        body.setObjectName("sidebar-list")
        self._list = QtWidgets.QVBoxLayout(body)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(0)
        current_heading: SectionHeading | None = None
        for entry in entries:
            if entry.kind == "heading":
                current_heading = SectionHeading(entry.label, body)
                self._headings.append((current_heading, []))
                self._list.addWidget(current_heading)
                continue
            row = SidebarRow(entry.name, entry.label, body)
            row.picked.connect(self.picked)
            self.rows.append(row)
            if self._headings:
                self._headings[-1][1].append(row)
            self._list.addWidget(row)
        self._list.addStretch(1)
        self.scroll.setWidget(body)
        column.addWidget(self.scroll, 1)
        watch_theme(self, lambda _theme: self.update())

    def set_current(self, name: str) -> None:
        for row in self.rows:
            row.set_current(row.data_name == name)

    def _filter(self, query: str) -> None:
        text = query.strip().lower()
        for row in self.rows:
            hit = not text or text in row.data_name.lower() or text in row.label().lower()
            row.setVisible(hit)
        for heading, rows in self._headings:
            heading.setVisible(any(row.isVisible() for row in rows) if rows else False)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), theme.color("sidebar"))
        painter.setPen(QtGui.QPen(theme.color("sidebar_border"), 1.0))
        painter.drawLine(
            QtCore.QPointF(self.width() - 0.5, 0.0), QtCore.QPointF(self.width() - 0.5, self.height())
        )
        painter.end()


class HeaderBar(QtWidgets.QWidget):
    """The row of controls that set the view, on a `background` band with a border under it."""

    #: The project the header picked: its id and its name.
    project_picked = QtCore.Signal(int, str)

    def __init__(
        self,
        prefs: Prefs,
        live_enabled: bool,
        context: DemoContext,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("header")
        self.setFixedHeight(56)
        self._row = QtWidgets.QHBoxLayout(self)
        self._row.setContentsMargins(24, 12, 24, 12)
        self._row.setSpacing(8)
        self.toolbar = PrefsToolbar(
            prefs, HEADER_KEYS, size="md", live_enabled=live_enabled, parent=self
        )
        self.toolbar.setObjectName("header-toolbar")
        self._row.addWidget(self.toolbar, 1)
        self.project: ProjectPicker | None = None
        self.set_context(context)
        watch_theme(self, lambda _theme: self.update())

    def set_context(self, context: DemoContext) -> None:
        """Bind the project picker to the site the demos read: the mock's projects, or the live site's."""
        if self.project is not None:
            self._row.removeWidget(self.project)
            self.project.deleteLater()
        picker = ProjectPicker(
            context=context.context,
            value=EntityRef("Project", context.project_id) if context.project_id else None,
            size="md",
            clearable=False,
            placeholder="Project",
            parent=self,
        )
        picker.setObjectName("project-picker")
        picker.setFixedWidth(200)
        picker.setToolTip("The project the demos that take a project read.")
        picker.value_changed.connect(self._on_project)
        self._row.addWidget(picker, 0)
        self.project = picker

    def _on_project(self, ref: object, row: object) -> None:
        if ref is None:
            return
        name = getattr(row, "name", "") or getattr(ref, "name", "") or ""
        self.project_picked.emit(int(ref.id), str(name))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), theme.color("background"))
        painter.setPen(QtGui.QPen(theme.color("border"), 1.0))
        painter.drawLine(
            QtCore.QPointF(0.0, self.height() - 0.5),
            QtCore.QPointF(float(self.width()), self.height() - 0.5),
        )
        painter.end()


class ShowcaseWindow(QtWidgets.QMainWindow):
    """The showcase: one page at a time, with the rail beside it and the controls above it."""

    def __init__(
        self,
        prefs: Prefs | None = None,
        context: DemoContext | None = None,
        root: Path | None = None,
        project_id: int | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setObjectName("showcase")
        self._root = root if root is not None else docs_dir()
        self.prefs = prefs if prefs is not None else Prefs(self)
        self._project_id = project_id
        self.context = (
            context
            if context is not None
            else demo_context(live=self.prefs.live, project_id=project_id)
        )
        self._pages: dict[str, WidgetPage] = {}
        self._current = ""

        central = chrome.Ground("background", self)
        central.setObjectName("showcase-root")
        row = QtWidgets.QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.sidebar = Sidebar(sidebar_model(self._root), central)
        self.sidebar.picked.connect(self.open_page)
        row.addWidget(self.sidebar)

        right = QtWidgets.QWidget(central)
        right.setObjectName("showcase-main")
        column = QtWidgets.QVBoxLayout(right)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.header = HeaderBar(self.prefs, live_available(), self.context, right)
        self.header.project_picked.connect(self._on_project_picked)
        column.addWidget(self.header)
        self.area = chrome.Ground("background", right)
        self.area.setObjectName("page-area")
        self._area_layout = QtWidgets.QVBoxLayout(self.area)
        self._area_layout.setContentsMargins(0, 0, 0, 0)
        self._area_layout.setSpacing(0)
        column.addWidget(self.area, 1)
        row.addWidget(right, 1)
        self.setCentralWidget(central)

        self.prefs.changed.connect(self._on_prefs)
        self._source = self.prefs.source
        self.prefs.apply(self)
        self._paint_ground(self.prefs.theme_object())
        first = self.page_names()
        self.open_page(self.default_page() or (first[0] if first else ""))

    # --- pages -------------------------------------------------------------------------------

    def page_names(self) -> list[str]:
        """Every page the rail lists, in its order."""
        return [row.data_name for row in self.sidebar.rows]

    def default_page(self) -> str:
        """The widgets overview, where there is one."""
        index = read_index(self._root)
        overview = index.get("overview")
        name = "widgets/" + str(overview) if overview else ""
        return name if name in self.page_names() else ""

    def resolve(self, name: str) -> str:
        """A page name as the rail spells it: `widgets/index` for `index`, and so on."""
        if not name:
            return self.default_page()
        names = self.page_names()
        if name in names:
            return name
        # A bare name is a widget page first: `index` is the widgets overview, not `core/index`.
        for section in SECTIONS:
            candidate = section + "/" + name
            if candidate in names:
                return candidate
        return name

    @property
    def page(self) -> WidgetPage | None:
        """The page on show."""
        return self._pages.get(self._current)

    @property
    def current(self) -> str:
        """Its name."""
        return self._current

    def open_page(self, name: str) -> WidgetPage:
        """Show one page, building it the first time it is asked for."""
        resolved = self.resolve(name)
        page = self._pages.get(resolved)
        if page is None:
            page = WidgetPage(resolved, self.context, self.prefs, self._root, self.area)
            self._pages[resolved] = page
            self._area_layout.addWidget(page)
        current = self.page
        if current is not None and current is not page:
            current.hide()
        page.show()
        self._current = resolved
        self.sidebar.set_current(resolved)
        return page

    # --- the view ----------------------------------------------------------------------------

    def _on_project_picked(self, project_id: int, name: str) -> None:
        """A project picked in the header scopes every demo that takes one."""
        if project_id == self.context.project_id:
            return
        self._project_id = project_id
        self.context = demo_context(live=self.prefs.live, project_id=project_id)
        self.context.project_name = name
        for page in self._pages.values():
            for stage in page.stages:
                stage.set_context(self.context)

    def _on_prefs(self) -> None:
        if self.prefs.source != self._source:
            self._source = self.prefs.source
            # The mock's projects and the site's are different rows, so a switch of source
            # starts from that source's own default project.
            self._project_id = None
            self.context = demo_context(live=self.prefs.live, project_id=None)
            self.header.set_context(self.context)
            for page in self._pages.values():
                for stage in page.stages:
                    stage.set_context(self.context)
        theme = self.prefs.theme_object()
        self.prefs.apply(self)
        self._paint_ground(theme)
        self.update()

    def _paint_ground(self, theme: Theme) -> None:
        """The window's own ground, so the area around a page is the theme's background."""
        palette = self.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, theme.color("background"))
        self.setPalette(palette)
        central = self.centralWidget()
        if central is not None:
            central.setPalette(palette)
