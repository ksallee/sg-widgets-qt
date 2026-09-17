"""The project, the row and the task the user is working on.

The port of `context-selector.tsx`, which is the Toolkit context selector re-imagined on
`search_control`. The three ways in are the three sections of one popover: the contexts used
before, the tasks assigned to the current user, and a drill-down over the navigation tree.

    selector = ContextSelector(context=context, current_user=me)
    selector.work_context_changed.connect(publish.set_context)

Assigned tasks are one search on Task filtered by `task_assignees`, a multi-entity field of
Group and HumanUser (entity_types/Task), grouped under their project. A Task is named by
`content`: it has no `code` and no `name` (entity_types/Task).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from qtpy.QtCore import QEvent, QSize, Qt, Signal
from qtpy.QtGui import QFont, QFontMetrics, QKeyEvent, QPainter
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import flatten_row
from sg_widgets_core.row import path_of
from sg_widgets_core.search import prepend_recent
from sg_widgets_core.state import NO_ROWS_LABEL

from ..icons import paint_icon
from ..primitives.base import (
    CONTROL_GLYPH,
    CONTROL_HEIGHT,
    DURATION,
    THUMB_SIZE,
    ThemedWidget,
    fill_round_rect,
)
from ..primitives.popover import Popover
from ..primitives.scrollbar import install_overlay_scrollbars
from ..theme import theme_of, with_alpha
from .entity_chip import EntityChip
from .hierarchical_search import HierarchicalSearch
from .picker_row import PickerRowModel
from .search_control import SearchAnswer, SearchControl, SearchRequest
from .state_line import StateLine

__all__ = [
    "EMPTY_CONTEXT",
    "ContextSelector",
    "MyTask",
    "WorkContext",
    "context_from_path",
]

#: The fields a task row is read with. A Task is named by `content` (entity_types/Task).
TASK_FIELDS: tuple[str, ...] = ("content", "sg_status_list", "project", "entity", "step")

#: How many assigned tasks one read asks for.
TASK_PAGE = 50

#: The chip step inside a control, one rung under the leaf ladder.
CHIP_STEP: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: The popover's width, and how tall the first two sections stand before they scroll.
POPOVER_WIDTH = 384
RECENTS_HEIGHT = 112
TASKS_HEIGHT = 208

#: The room inside the popover, and between its sections.
POPOVER_PAD = 12
SECTION_GAP = 12

#: The heading over each section.
HEADING_TEXT = 12
HEADING_PAD_X = 8
HEADING_PAD_Y = 6

#: The glyph a task row draws where it has no picture.
TASK_GLYPH = "list-checks"


@dataclass
class WorkContext:
    """What a widget or a publish needs to know about where the user is working."""

    project: EntityRef | None = None
    #: The row the task hangs off: a Shot, an Asset, a Sequence.
    entity: EntityRef | None = None
    task: EntityRef | None = None

    @property
    def refs(self) -> list[EntityRef]:
        """The three parts that are set, project first."""
        return [r for r in (self.project, self.entity, self.task) if r is not None]


#: Nothing chosen.
EMPTY_CONTEXT = WorkContext()


@dataclass
class MyTask:
    """One assigned task, ready to draw as a row."""

    task: EntityRef
    project: EntityRef | None = None
    entity: EntityRef | None = None
    step: str = ""
    status: str = ""
    #: Every field the read answered, so the row anatomy can draw from it.
    values: dict = dc_field(default_factory=dict)

    @property
    def type(self) -> str:
        return "Task"

    @property
    def id(self) -> int:
        return self.task.id

    @property
    def name(self) -> str:
        return self.task.name or ""


@dataclass
class _Heading:
    """A project heading over the tasks under it."""

    name: str
    type: str = ""
    id: int = 0
    values: dict = dc_field(default_factory=dict)


def context_from_path(leaf: EntityRef, path: Sequence[EntityRef]) -> WorkContext:
    """The context a picked row implies.

    A Task carries its own link and project, so a path is only read for the rows a search
    returns.
    """
    project = next((r for r in path if r.type == "Project"), None)
    task = leaf if leaf.type == "Task" else None
    if task is not None:
        entity = next(
            (r for r in reversed(list(path)) if r.type not in ("Project", "Task")), None
        )
    elif leaf.type == "Project":
        entity = None
    else:
        entity = leaf
    return WorkContext(project=project, entity=entity, task=task)


def _key_of(context: WorkContext) -> str:
    return "|".join(
        f"{r.type}:{r.id}" if r is not None else "-"
        for r in (context.project, context.entity, context.task)
    )


def _label_of(context: WorkContext) -> str:
    for ref in (context.task, context.entity, context.project):
        if ref is not None and ref.name:
            return ref.name
    return "No context"


class _SectionHeading(ThemedWidget):
    """A section heading: 12px, medium, muted."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, QFontMetrics(self.theme.font(HEADING_TEXT)).height() + 2 * HEADING_PAD_Y)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(theme.font(HEADING_TEXT, QFont.Weight.Medium))
        painter.setPen(theme.color("muted_foreground"))
        painter.drawText(
            self.rect().adjusted(HEADING_PAD_X, 0, -HEADING_PAD_X, 0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._text,
        )
        painter.end()


class _ChipRow(ThemedWidget):
    """A row of chips, which is how a context reads: project, row, task."""

    chosen = Signal()

    def __init__(
        self,
        refs: Sequence[EntityRef],
        size: str = "md",
        context: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, size_step=size)
        self._hover = self.animated(DURATION["hover"])
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(HEADING_PAD_X, HEADING_PAD_Y, HEADING_PAD_X, HEADING_PAD_Y)
        row.setSpacing(8)
        for ref in refs:
            row.addWidget(
                EntityChip(entity=ref, size=CHIP_STEP[size], context=context, parent=self)
            )
        row.addStretch(1)

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.chosen.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.chosen.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._hover.value > 0:
            fill_round_rect(
                painter,
                self.rect(),
                float(theme.radius_px("sm")),
                brush=with_alpha(theme.accent, self._hover.value * 0.5),
            )
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), float(theme.radius_px("sm")))
        painter.end()


class ContextTrigger(ThemedWidget):
    """The control the popover hangs off: the chips of the context, and a chevron."""

    clicked = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        size: str = "md",
        empty_label: str = "No context",
        context: Any = None,
    ) -> None:
        super().__init__(parent, size_step=size)
        self._empty_label = empty_label
        self._context = context
        self._refs: list[EntityRef] = []
        self._hover = self.animated(DURATION["hover"])
        self.setObjectName("context-selector-trigger")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._row = QHBoxLayout(self)
        self._row.setSpacing(6)
        self._apply_insets()
        self._rebuild()

    def _apply_insets(self) -> None:
        """An empty control gives its leading inset back, so it reads as a plain input."""
        step = self.size_step
        lead = 8 if step == "sm" else 8
        trail = 8 if step == "sm" else 12
        # `PICKER_BOX` of `picker-classes.ts`: what the chip and the control's own border leave
        # under the ladder, halved — 3 at sm and md, 1 at lg — and nothing while it is empty.
        pad_y = 0 if not self._refs else (1 if step == "lg" else 3)
        self._row.setContentsMargins(
            lead if not self._refs else 3, pad_y, trail + CONTROL_GLYPH[step] + 6, pad_y
        )

    @property
    def refs(self) -> list[EntityRef]:
        """The chips on show."""
        return list(self._refs)

    def set_refs(self, refs: Sequence[EntityRef]) -> None:
        self._refs = list(refs)
        self._rebuild()

    def set_size(self, value: str) -> None:
        self.set_size_step(value)
        self._rebuild()

    def _rebuild(self) -> None:
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Hidden before it is let go: a widget reparented to None is a top-level
                # window, and one Qt never saw explicitly hidden stands as a stray window over
                # the panel until the deferred delete runs.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._apply_insets()
        step = CHIP_STEP[self.size_step]
        for ref in self._refs:
            self._row.addWidget(
                EntityChip(entity=ref, size=step, context=self._context, parent=self)
            )
        self._row.addStretch(1)
        self.setAccessibleName("Context: " + (" › ".join(r.name or r.type for r in self._refs) or self._empty_label))
        self.updateGeometry()
        self.update()

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, CONTROL_HEIGHT[self.size_step])

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setOpacity(self.disabled_opacity())
        radius = float(theme.radius_px("lg"))
        fill = (
            with_alpha(theme.accent, self._hover.value)
            if self._hover.value > 0
            else theme.color("background")
        )
        fill_round_rect(painter, self.rect(), radius, brush=fill, border=theme.color("border"))
        if not self._refs:
            painter.setFont(theme.font(14))
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(
                self.rect().adjusted(8, 0, -8, 0),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                self._empty_label,
            )
        glyph = CONTROL_GLYPH[self.size_step]
        box = self.rect().adjusted(
            self.width() - glyph - 10, (self.height() - glyph) // 2, -10, 0
        )
        box.setWidth(glyph)
        box.setHeight(glyph)
        paint_icon(painter, box, "chevron-down", theme.color("muted_foreground"))
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), radius)
        painter.end()


class ContextSelector(QWidget):
    """The project, the row and the task the user is working on, changed from one popover."""

    #: The project, entity or task changed.
    work_context_changed = Signal(object)
    #: The recents list changed, the newest first.
    recents_changed = Signal(object)
    #: The popover opened or closed.
    open_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        context: Any = None,
        work_context: WorkContext | None = None,
        current_user: EntityRef | None = None,
        recents: Sequence[WorkContext] = (),
        recent_limit: int = 5,
        thumbnail: str | bool = "image",
        label_field: str | None = "content",
        sub_label_field: Any = None,
        sub_label: Callable[[MyTask], str] | None = None,
        secondary_field: Any = "sg_status_list",
        secondary: Callable[[MyTask], str] | None = None,
        show_code: bool = False,
        fields: Sequence[str] = (),
        empty_label: str = NO_ROWS_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        size: str = "md",
        open: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("context-selector")
        self._context = context
        self._work_context = work_context if work_context is not None else WorkContext()
        self._current_user = current_user
        self._recents = list(recents)
        self._recent_limit = int(recent_limit)
        self._thumbnail = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._fields = list(fields)
        self._empty_label = empty_label
        self._loading_label = loading_label
        self._error_label = error_label
        self._size = size
        self._open = False
        self._tasks: SearchControl | None = None

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self._trigger = ContextTrigger(self, size=size, context=context)
        self._trigger.set_refs(self._work_context.refs)
        self._trigger.clicked.connect(self.toggle)
        column.addWidget(self._trigger)

        self._panel = self._build_panel()
        self._popover = Popover(
            self._trigger, self._panel, side="bottom", align="start", width=POPOVER_WIDTH
        )
        self._popover.set_key_handler(self._on_popover_key)
        self._popover.closed.connect(self._on_closed)
        self._popover.dismissed.connect(self._on_closed)
        self._apply_row_props()
        if open:
            self.set_open(True)

    # --- the panel -----------------------------------------------------------------------

    def _build_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("context-selector-panel")
        column = QVBoxLayout(panel)
        column.setContentsMargins(POPOVER_PAD, POPOVER_PAD, POPOVER_PAD, POPOVER_PAD)
        column.setSpacing(SECTION_GAP)

        self._recents_section = QWidget(panel)
        self._recents_section.setObjectName("context-recents")
        recents = QVBoxLayout(self._recents_section)
        recents.setContentsMargins(0, 0, 0, 0)
        recents.setSpacing(0)
        recents.addWidget(_SectionHeading("Recent", self._recents_section))
        self._recents_body = QWidget(self._recents_section)
        self._recents_column = QVBoxLayout(self._recents_body)
        self._recents_column.setContentsMargins(0, 0, 0, 0)
        self._recents_column.setSpacing(0)
        self._recents_scroll = _Section(self._recents_section, RECENTS_HEIGHT)
        self._recents_scroll.setWidget(self._recents_body)
        recents.addWidget(self._recents_scroll)
        column.addWidget(self._recents_section)

        tasks_section = QWidget(panel)
        tasks_section.setObjectName("context-my-tasks")
        tasks = QVBoxLayout(tasks_section)
        tasks.setContentsMargins(0, 0, 0, 0)
        tasks.setSpacing(0)
        tasks.addWidget(_SectionHeading("My tasks", tasks_section))
        self._task_model = PickerRowModel([], self, context=self._context, size=self._size)
        self._tasks = SearchControl(
            tasks_section,
            load=self._load_tasks,
            model=self._task_model,
            shell="bare",
            reads_empty=True,
            enabled=self._current_user is not None,
            request=self._user_key(),
            error_slot="context-tasks-error",
            loading_slot="context-tasks-loading",
            empty_slot="context-tasks-empty",
            empty_label=self._empty_label,
            loading_label=self._loading_label,
            error_label=self._error_label,
            skeleton_lines=2,
            skeleton_lead=QSize(THUMB_SIZE[self._size], THUMB_SIZE[self._size]),
            size=self._size,
            max_height=TASKS_HEIGHT,
            row_mapper=self._task_rows,
        )
        self._tasks.activated.connect(self._on_task)
        # Escape on an empty query is the shell's key, and this shell is the popover.
        self._tasks.dismissed.connect(self._on_dismissed)
        tasks.addWidget(self._tasks)
        column.addWidget(tasks_section)

        browse_section = QWidget(panel)
        browse_section.setObjectName("context-hierarchy")
        browse = QVBoxLayout(browse_section)
        browse.setContentsMargins(0, 0, 0, 0)
        browse.setSpacing(0)
        browse.addWidget(_SectionHeading("Browse", browse_section))
        self._tree = HierarchicalSearch(
            browse_section,
            context=self._context,
            root_path=self._root_path(),
            size=self._size,
            thumbnail=self._thumbnail,
            label_field=self._label_field,
            sub_label_field=self._sub_label_field,
            show_code=self._show_code,
            fields=self._fields,
            loading_label=self._loading_label,
            error_label=self._error_label,
            placeholder="Search for a task or a shot…",
        )
        self._tree.selected.connect(self._on_tree_pick)
        self._tree.search_control().dismissed.connect(self._on_dismissed)
        browse.addWidget(self._tree)
        column.addWidget(browse_section)

        self._fill_recents()
        return panel

    def _root_path(self) -> str:
        project = self._work_context.project
        return f"/Project/{project.id}" if project is not None else "/"

    def _fill_recents(self) -> None:
        while self._recents_column.count():
            item = self._recents_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Hidden before it is let go: a widget reparented to None is a top-level
                # window, and one Qt never saw explicitly hidden stands as a stray window over
                # the panel until the deferred delete runs.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if not self._recents:
            line = StateLine(
                state="empty",
                label="Nothing yet.",
                icon="history",
                slot_name="context-recents-empty",
                size=self._size,
                parent=self._recents_body,
            )
            self._recents_column.addWidget(line)
            return
        for recent in self._recents:
            row = _ChipRow(
                recent.refs, size=self._size, context=self._context, parent=self._recents_body
            )
            row.chosen.connect(lambda held=recent: self.apply(held))
            self._recents_column.addWidget(row)
        self._recents_column.addStretch(1)

    # --- the keywords ---------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._task_model.set_context(value)
        self._tree.set_context(value)

    @property
    def work_context(self) -> WorkContext:
        """The project, row and task on show."""
        return self._work_context

    def set_work_context(self, value: WorkContext) -> None:
        self._work_context = value if value is not None else WorkContext()
        self._trigger.set_refs(self._work_context.refs)
        self._tree.set_root_path(self._root_path())

    @property
    def current_user(self) -> EntityRef | None:
        """Whose assigned tasks the second section lists."""
        return self._current_user

    def set_current_user(self, value: EntityRef | None) -> None:
        self._current_user = value
        self._tasks.set_enabled(value is not None)
        self._tasks.set_request(self._user_key())

    @property
    def recents(self) -> list[WorkContext]:
        """Contexts used before, newest first."""
        return list(self._recents)

    def set_recents(self, value: Sequence[WorkContext]) -> None:
        self._recents = list(value)
        self._fill_recents()

    @property
    def recent_limit(self) -> int:
        """How many recents survive a change."""
        return self._recent_limit

    def set_recent_limit(self, value: int) -> None:
        self._recent_limit = int(value)

    @property
    def thumbnail(self) -> str | bool:
        """Field holding a task row's thumbnail URL."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self._apply_row_props()

    @property
    def label_field(self) -> str | None:
        """Field holding a task row's label."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self._apply_row_props()

    @property
    def sub_label_field(self) -> Any:
        """The muted line under the label."""
        return self._sub_label_field

    def set_sub_label_field(self, value: Any) -> None:
        self._sub_label_field = value
        self._apply_row_props()

    @property
    def sub_label(self) -> Callable[[MyTask], str] | None:
        """The muted line of the caller's own making."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[MyTask], str] | None) -> None:
        self._sub_label = value
        self._apply_row_props()

    @property
    def secondary_field(self) -> Any:
        """The right-aligned value, drawn by its data type."""
        return self._secondary_field

    def set_secondary_field(self, value: Any) -> None:
        self._secondary_field = value
        self._apply_row_props()

    @property
    def secondary(self) -> Callable[[MyTask], str] | None:
        """Right-aligned text of the caller's own making."""
        return self._secondary

    def set_secondary(self, value: Callable[[MyTask], str] | None) -> None:
        self._secondary = value
        self._apply_row_props()

    @property
    def show_code(self) -> bool:
        """Show the row's code beside the label when the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._apply_row_props()

    @property
    def fields(self) -> list[str]:
        """Extra fields to request."""
        return list(self._fields)

    def set_fields(self, value: Sequence[str]) -> None:
        self._fields = list(value)
        self._apply_row_props()

    @property
    def empty_label(self) -> str:
        """Shown when the person has no task assigned."""
        return self._tasks.empty_label

    def set_empty_label(self, value: str) -> None:
        self._empty_label = value
        self._tasks.set_empty_label(value)

    @property
    def loading_label(self) -> str | None:
        """Names the skeletons a read stands behind."""
        return self._tasks.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._loading_label = value
        self._tasks.set_loading_label(value)
        self._tree.set_loading_label(value)

    @property
    def error_label(self) -> str | None:
        """Shown in place of what the failed read said."""
        return self._tasks.error_label

    def set_error_label(self, value: str | None) -> None:
        self._error_label = value
        self._tasks.set_error_label(value)
        self._tree.set_error_label(value)

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value
        self._trigger.set_size(value)
        self._tasks.set_size(value)
        self._tree.set_size(value)
        self._fill_recents()

    @property
    def open(self) -> bool:
        """Whether the popover is showing."""
        return self._open

    def set_open(self, value: bool) -> None:
        value = bool(value)
        if value == self._open:
            return
        self._open = value
        if value:
            self._popover.open()
        else:
            self._popover.close()
        self.open_changed.emit(value)

    def toggle(self) -> None:
        """Open the popover, or close it."""
        self.set_open(not self._open)

    def trigger(self) -> ContextTrigger:
        """The control the popover hangs off."""
        return self._trigger

    def tasks_control(self) -> SearchControl:
        """The assigned-tasks list, a bare search with no query of its own."""
        return self._tasks

    def tree(self) -> HierarchicalSearch:
        """The drill-down in the third section."""
        return self._tree

    def popover(self) -> Popover:
        """The floating panel the three sections sit in."""
        return self._popover

    # --- the read -----------------------------------------------------------------------

    def _user_key(self) -> str:
        user = self._current_user
        return f"{user.type}:{user.id}" if user is not None else ""

    def _load_tasks(self, _request: SearchRequest) -> SearchAnswer:
        """The tasks assigned to the current user."""
        user = self._current_user
        context = self._context
        if user is None or context is None:
            return SearchAnswer(items=[], has_more=False)
        result = context.client.search(
            "Task",
            SearchOptions(
                # `task_assignees` is a multi_entity of Group and HumanUser (entity_types/Task).
                filters={
                    "logical_operator": "and",
                    "conditions": [
                        ["task_assignees", "in", [{"type": user.type, "id": user.id}]]
                    ],
                },
                fields=self._task_model.read_fields(TASK_FIELDS),
                page={"size": TASK_PAGE},
            ),
        )
        return SearchAnswer(items=[self._task_of(row) for row in result.data], has_more=False)

    def _task_of(self, row: Any) -> MyTask:
        flat = flatten_row(row, self._label_field)
        values = flat.values
        label = flat.name or f"Task #{row.id}"
        return MyTask(
            task=EntityRef(type="Task", id=row.id, name=label),
            project=_ref_of(values.get("project")),
            entity=_ref_of(values.get("entity")),
            step=(_ref_of(values.get("step")).name or "") if _ref_of(values.get("step")) else "",
            status=str(values.get("sg_status_list") or ""),
            values=values,
        )

    # --- the rows ------------------------------------------------------------------------

    def _apply_row_props(self) -> None:
        model = self._task_model
        model.set_context(self._context)
        model.set_thumbnail(self._thumbnail)
        model.set_label_field(self._label_field)
        model.set_sub_label_field(self._sub_label_field)
        model.set_secondary_field(self._secondary_field)
        model.set_show_code(self._show_code)
        model.set_fields(self._fields)
        model.set_size(self._size)
        model.set_kind_of(lambda row: "heading" if isinstance(row, _Heading) else "row")
        model.set_glyph_of(lambda _row: TASK_GLYPH)
        named = self._sub_label is not None or not path_of(self._sub_label_field)
        model.set_sub_label(self._sub_of if named else None)
        model.set_secondary(self._secondary_of if self._secondary is not None else None)
        self._tree.set_thumbnail(self._thumbnail)
        self._tree.set_label_field(self._label_field)
        self._tree.set_sub_label_field(self._sub_label_field)
        self._tree.set_show_code(self._show_code)
        self._tree.set_fields(self._fields)
        if self._tasks is not None:
            self._tasks.set_row_mapper(self._task_rows)

    def _sub_of(self, row: Any) -> str:
        """What the task hangs off, and the step it belongs to."""
        if not isinstance(row, MyTask):
            return ""
        if self._sub_label is not None:
            return self._sub_label(row) or ""
        parts = [row.entity.name if row.entity is not None else "", row.step]
        return " · ".join(p for p in parts if p)

    def _secondary_of(self, row: Any) -> str:
        if self._secondary is None or not isinstance(row, MyTask):
            return ""
        return self._secondary(row) or ""

    def _task_rows(self, items: Sequence[Any]) -> list[Any]:
        """Tasks under their project, in the order the projects first appear."""
        groups: dict[str, list[MyTask]] = {}
        names: dict[str, str] = {}
        for task in items:
            key = f"{task.project.type}:{task.project.id}" if task.project is not None else "-"
            names.setdefault(
                key, task.project.name if task.project is not None else "No project"
            )
            groups.setdefault(key, []).append(task)
        rows: list[Any] = []
        for key, tasks in groups.items():
            rows.append(_Heading(names.get(key) or "No project"))
            rows.extend(tasks)
        return rows

    # --- picking -------------------------------------------------------------------------

    def apply(self, next_context: WorkContext) -> None:
        """Take a context: the recents lead with it, and the popover closes."""
        self._recents = prepend_recent(
            self._recents, next_context, self._recent_limit, _key_of
        )
        self._fill_recents()
        self.recents_changed.emit(list(self._recents))
        self.set_work_context(next_context)
        self.work_context_changed.emit(next_context)
        self.set_open(False)

    def _on_task(self, index: int) -> None:
        row = self._task_model.row_at(index)
        if not isinstance(row, MyTask):
            return
        self.apply(WorkContext(project=row.project, entity=row.entity, task=row.task))

    def _on_tree_pick(self, leaf: Any, path: Any) -> None:
        self.apply(context_from_path(leaf, list(path)))

    def _on_closed(self) -> None:
        if self._open:
            self._open = False
            self.open_changed.emit(False)
        self._trigger.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_popover_key(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self.set_open(False)
            return True
        return False

    def _on_dismissed(self) -> None:
        """Escape reached the shell from one of the lists: the popover is that shell."""
        self.set_open(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Escape from the trigger closes the popover, and `_on_closed` gives the caret back.

        Any other key with the panel open is the browse search's: the panel never takes the
        window's focus, so the keyboard delivers here while its search box stands in the
        popover, and the box gets the key as if it were typed in it.
        """
        if self._open and event.key() == Qt.Key.Key_Escape:
            self.set_open(False)
            event.accept()
            return
        if self._open and self._type_into_browse(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def _type_into_browse(self, event: QKeyEvent) -> bool:
        box = self._tree.search_control().input()
        if box is None or not box.isVisible():
            return False
        QApplication.sendEvent(box, event)
        return event.isAccepted()

    @property
    def label(self) -> str:
        """What the trigger says the context is."""
        return _label_of(self._work_context)


class _Section(QScrollArea):
    """A section of the panel that scrolls at its own height, with the overlay bar."""

    def __init__(self, parent: QWidget | None = None, max_height: int = 160) -> None:
        super().__init__(parent)
        self._max_height = max_height
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        install_overlay_scrollbars(self)
        self.viewport().setAutoFillBackground(False)

    def sizeHint(self) -> QSize:  # noqa: N802
        inner = self.widget()
        height = inner.sizeHint().height() if inner is not None else 0
        return QSize(0, min(self._max_height, max(0, height)))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        theme = theme_of(self)
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), theme.color("popover"))
        painter.end()
        super().paintEvent(event)


def _ref_of(value: Any) -> EntityRef | None:
    """A relationship value as a reference, or None."""
    if isinstance(value, EntityRef):
        return value
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    return EntityRef(
        type=str(value.get("type") or ""),
        id=int(value.get("id") or 0),
        name=name if isinstance(name, str) else None,
    )
