"""Search across the site by name, as a command palette.

The port of `global-search.tsx`. One `text_search` covers every configured type at once and
every word of the query has to match, each as a case-insensitive substring of the row's name
or of the name of the row it links to (053_text_search_matching). That endpoint has no
`fields` parameter, so the thumbnail and the project on each row are a second read of the page
just returned (post_entity_text_search). Matching is the server's alone: the list never
filters what came back.

    search = GlobalSearch(context=context, hotkey=True)
    search.selected.connect(open_row)

The trigger stands on the control ladder and carries the shortcut beside its label. The
results are a `search_control`, grouped under one heading per type.
"""
from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from qtpy.QtCore import QEvent, QSize, Qt, Signal
from qtpy.QtGui import QKeySequence, QPainter
from qtpy.QtWidgets import QShortcut, QSizePolicy, QVBoxLayout, QWidget

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import placeholder_name
from sg_widgets_core.row import path_of
from sg_widgets_core.search import (
    SEARCH_PAGE_SIZE,
    SearchHit,
    has_more_page,
    hydrate,
    prepend_recent,
    scope_to_project,
    search_type_map,
)
from sg_widgets_core.state import NO_MATCH_LABEL

from ..icons import paint_icon
from ..primitives.base import (
    CONTROL_GLYPH,
    CONTROL_HEIGHT,
    DURATION,
    THUMB_SIZE,
    ThemedWidget,
    elide,
    fill_round_rect,
)
from ..theme import with_alpha
from ..workers import default_pool
from .picker_row import PickerRowModel
from .search_control import SearchAnswer, SearchControl, SearchRequest

__all__ = [
    "GLOBAL_SEARCH_TYPES",
    "GlobalSearch",
    "GlobalSearchRow",
    "SearchTrigger",
]

#: Types a stock site is searched over. A caller with custom entities passes its own.
GLOBAL_SEARCH_TYPES: list[str] = [
    "Asset",
    "Shot",
    "Sequence",
    "Task",
    "Version",
    "HumanUser",
    "Project",
]

#: The modifier the hotkey shows. Qt maps `Ctrl` in a key sequence to Command on macOS.
META = "⌘" if sys.platform == "darwin" else "Ctrl"

#: The heading a list of what was picked before sits under.
RECENT_HEADING = "Recent"

#: Room inside the kbd pill, and its type step.
KBD_PAD = 6
KBD_TEXT = 11


@dataclass
class GlobalSearchRow:
    """One row of the list: what the search answered, ready for the row anatomy."""

    type: str
    id: int
    name: str
    values: dict = dc_field(default_factory=dict)
    #: The hit behind it, so a caller's own sub-label or secondary reads the whole answer.
    hit: Any = None
    #: The muted line the widget settled on when the caller named none.
    sub: str = ""
    #: True on a row that came from the recents rather than from a read.
    recent: bool = False

    @property
    def ref(self) -> EntityRef:
        """The reference a pick emits."""
        return EntityRef(type=self.type, id=self.id, name=self.name)


@dataclass
class _Heading:
    """A group heading among the rows. The list draws it and the highlight walks over it."""

    name: str
    type: str = ""
    id: int = 0
    values: dict = dc_field(default_factory=dict)


class SearchTrigger(ThemedWidget):
    """The control that opens the palette: a search glyph, a label and the shortcut."""

    clicked = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        label: str = "Search",
        hint: str = "",
        size: str = "md",
    ) -> None:
        super().__init__(parent, size_step=size)
        self._label = label
        self._hint = hint
        self._hover = self.animated(DURATION["hover"])
        self.setObjectName("global-search-trigger")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def label(self) -> str:
        return self._label

    def set_label(self, value: str) -> None:
        self._label = value
        self.update()

    @property
    def hint(self) -> str:
        """The shortcut drawn at the trailing edge, or nothing."""
        return self._hint

    def set_hint(self, value: str) -> None:
        self._hint = value
        self.update()

    def set_size(self, value: str) -> None:
        self.set_size_step(value)
        self.updateGeometry()
        self.update()

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value else 0.0)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, CONTROL_HEIGHT[self.size_step])

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def mousePressEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_pressed(True)

    def mouseReleaseEvent(self, event: QEvent) -> None:  # noqa: N802
        was, self._pressed = self.pressed, False
        self.update()
        if was and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.pos()
        ):
            self.clicked.emit()

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        theme = self.theme
        step = self.size_step
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

        glyph = CONTROL_GLYPH[step]
        pad = 10
        box = self.rect().adjusted(pad, 0, -pad, 0)
        mark = box.adjusted(0, (box.height() - glyph) // 2, 0, 0)
        mark.setWidth(glyph)
        mark.setHeight(glyph)
        painter.setOpacity(self.disabled_opacity() * 0.7)
        paint_icon(painter, mark, "search", theme.color("foreground"))
        painter.setOpacity(self.disabled_opacity())

        hint_width = 0
        if self._hint:
            painter.setFont(theme.font(KBD_TEXT))
            hint_width = painter.fontMetrics().horizontalAdvance(self._hint) + 2 * KBD_PAD
            pill = box.adjusted(box.width() - hint_width, (box.height() - 20) // 2, 0, 0)
            pill.setWidth(hint_width)
            pill.setHeight(20)
            fill_round_rect(
                painter,
                pill,
                float(theme.radius_px("sm")),
                brush=with_alpha(theme.muted, 1.0),
                border=theme.color("border"),
            )
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), self._hint)

        text = box.adjusted(glyph + 6, 0, -(hint_width + 8 if hint_width else 0), 0)
        painter.setFont(theme.font(14))
        painter.setPen(theme.color("foreground"))
        painter.drawText(
            text,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(painter, self._label, text.width()),
        )
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), radius)
        painter.end()


class GlobalSearch(QWidget):
    """The site-wide search: a trigger, a palette, and the rows grouped by type.

    `inline` draws the box in the page instead of a dialog behind a trigger. `hotkey` opens
    the palette on Cmd or Ctrl and K, or on the key a string names.
    """

    #: A row was picked.
    selected = Signal(object)
    #: The recents list changed, the pick first.
    recents_changed = Signal(object)
    #: The palette opened or closed.
    open_changed = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        context: Any = None,
        entity_types: Sequence[str] | dict[str, Any] | None = None,
        project_id: int | None = None,
        thumbnail: str | bool = "image",
        label_field: str | None = None,
        sub_label_field: Any = None,
        sub_label: Callable[[SearchHit], str] | None = None,
        secondary_field: Any = None,
        secondary: Callable[[SearchHit], str] | None = None,
        show_code: bool = False,
        fields: Sequence[str] = (),
        hotkey: bool | str = False,
        inline: bool = False,
        recents: Sequence[EntityRef] = (),
        recent_limit: int = 5,
        label: str = "Search",
        size: str = "md",
        open: bool = False,
        placeholder: str = "Search…",
        empty_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("global-search")
        self._context = context
        self._entity_types: Any = (
            list(GLOBAL_SEARCH_TYPES) if entity_types is None else entity_types
        )
        self._project_id = project_id
        self._thumbnail = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._fields = list(fields)
        self._inline = bool(inline)
        self._recents = list(recents)
        self._recent_limit = int(recent_limit)
        self._size = size
        self._display_names: dict[str, str] = {}
        self._shortcut: QShortcut | None = None
        self._control: SearchControl | None = None

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self._trigger: SearchTrigger | None = None
        if not self._inline:
            self._trigger = SearchTrigger(self, label=label, size=size)
            self._trigger.clicked.connect(lambda: self.set_open(True))
            column.addWidget(self._trigger)

        self._model = PickerRowModel([], self, context=context, size=size)
        self._control = SearchControl(
            self,
            load=self._load,
            model=self._model,
            shell="command" if self._inline else "dialog",
            paging=True,
            placeholder=placeholder,
            empty_label=empty_label,
            loading_label=loading_label,
            error_label=error_label,
            title="Search",
            description="Search across the site by name.",
            size=size,
            skeleton_lead=QSize(THUMB_SIZE[size], THUMB_SIZE[size]),
            row_mapper=self._rows_of,
        )
        if self._inline:
            column.addWidget(self._control)
        self._control.activated.connect(self._on_activated)
        self._control.query_changed.connect(self._on_query)
        self._control.open_changed.connect(self.open_changed.emit)

        self._apply_row_props()
        self.set_hotkey(hotkey)
        self._read_display_names()
        if open:
            self.set_open(True)

    # --- the keywords ---------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._model.set_context(value)
        self._display_names = {}
        self._read_display_names()
        self._control.set_request(self._request_key())

    @property
    def entity_types(self) -> Any:
        """Types to search, with an optional filter each."""
        return self._entity_types

    def set_entity_types(self, value: Sequence[str] | dict[str, Any]) -> None:
        self._entity_types = value
        self._control.set_request(self._request_key())

    @property
    def project_id(self) -> int | None:
        """Scopes every searched type that has a `project` field."""
        return self._project_id

    def set_project_id(self, value: int | None) -> None:
        self._project_id = value
        self._control.set_request(self._request_key())

    @property
    def thumbnail(self) -> str | bool:
        """Field holding the thumbnail URL. `False` hides the leading slot."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self._apply_row_props()

    @property
    def label_field(self) -> str | None:
        """Field holding the row label."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self._apply_row_props()
        self._control.set_request(self._request_key())

    @property
    def sub_label_field(self) -> Any:
        """The muted line under the label."""
        return self._sub_label_field

    def set_sub_label_field(self, value: Any) -> None:
        self._sub_label_field = value
        self._apply_row_props()

    @property
    def sub_label(self) -> Callable[[SearchHit], str] | None:
        """The muted line of the caller's own making. Wins over `sub_label_field`."""
        return self._sub_label

    def set_sub_label(self, value: Callable[[SearchHit], str] | None) -> None:
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
    def secondary(self) -> Callable[[SearchHit], str] | None:
        """Right-aligned text of the caller's own making."""
        return self._secondary

    def set_secondary(self, value: Callable[[SearchHit], str] | None) -> None:
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
    def hotkey(self) -> bool | str:
        """Opens the palette on Cmd or Ctrl and K; a string names another key."""
        return self._hotkey

    def set_hotkey(self, value: bool | str) -> None:
        self._hotkey = value
        if self._shortcut is not None:
            self._shortcut.setParent(None)
            self._shortcut = None
        if not value or self._inline:
            if self._trigger is not None:
                self._trigger.set_hint("")
            return
        key = value if isinstance(value, str) else "k"
        self._shortcut = QShortcut(QKeySequence("Ctrl+" + key.upper()), self.window())
        self._shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._shortcut.activated.connect(self._toggle)
        if self._trigger is not None:
            self._trigger.set_hint(META + key.upper())

    @property
    def inline(self) -> bool:
        """Draws the box in the page instead of a dialog behind a trigger."""
        return self._inline

    @property
    def recents(self) -> list[EntityRef]:
        """Rows picked before, newest first, shown on an empty query."""
        return list(self._recents)

    def set_recents(self, value: Sequence[EntityRef]) -> None:
        self._recents = list(value)
        self._refresh_rows()

    @property
    def recent_limit(self) -> int:
        """How many recents survive a pick."""
        return self._recent_limit

    def set_recent_limit(self, value: int) -> None:
        self._recent_limit = int(value)

    @property
    def label(self) -> str:
        """Text on the trigger."""
        return self._trigger.label if self._trigger is not None else ""

    def set_label(self, value: str) -> None:
        if self._trigger is not None:
            self._trigger.set_label(value)

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value
        if self._trigger is not None:
            self._trigger.set_size(value)
        self._control.set_size(value)
        self._control.set_skeleton_lead(QSize(THUMB_SIZE[value], THUMB_SIZE[value]))

    @property
    def open(self) -> bool:
        """Whether the palette is showing."""
        return self._control.open if not self._inline else True

    def set_open(self, value: bool) -> None:
        if self._inline:
            return
        self._control.set_open(bool(value))

    @property
    def placeholder(self) -> str:
        """Text in the search box."""
        return self._control.placeholder

    def set_placeholder(self, value: str) -> None:
        self._control.set_placeholder(value)

    @property
    def empty_label(self) -> str:
        """Shown when a query matches nothing."""
        return self._control.empty_label

    def set_empty_label(self, value: str) -> None:
        self._control.set_empty_label(value)

    @property
    def loading_label(self) -> str | None:
        """Names the skeletons a read stands behind."""
        return self._control.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._control.set_loading_label(value)

    @property
    def error_label(self) -> str | None:
        """Shown in place of what the failed read said."""
        return self._control.error_label

    def set_error_label(self, value: str | None) -> None:
        self._control.set_error_label(value)

    @property
    def query(self) -> str:
        """What the caret holds."""
        return self._control.query

    def set_query(self, value: str) -> None:
        self._control.set_query(value)

    def search_control(self) -> SearchControl:
        """The lifecycle and the list under the palette."""
        return self._control

    def trigger(self) -> SearchTrigger | None:
        """The control that opens the palette, or None on the inline variant."""
        return self._trigger

    # --- the read -----------------------------------------------------------------------

    def _request_key(self) -> str:
        """What the read depends on besides the query."""
        types = ",".join(sorted(search_type_map(self._entity_types)))
        return f"{types}|{self._project_id}|{self._label_field or ''}"

    def _load(self, request: SearchRequest) -> SearchAnswer:
        """One text search across every configured type, then the read that fills the rows."""
        context = self._context
        if context is None:
            return SearchAnswer(items=[], has_more=False)
        types = search_type_map(self._entity_types)
        if self._project_id is not None:
            types = scope_to_project(context.schema, types, int(self._project_id))
        found = context.client.text_search(
            request.query, types, {"size": SEARCH_PAGE_SIZE, "number": request.page}
        )
        hits = hydrate(
            context.client,
            found,
            fields=self._model.read_fields(),
            label_field=self._label_field,
        )
        return SearchAnswer(
            items=hits, has_more=has_more_page(len(found), SEARCH_PAGE_SIZE)
        )

    def _read_display_names(self) -> None:
        """A heading falls back to the schema name, which is always readable."""
        context = self._context
        if context is None:
            return
        default_pool().submit(
            context.schema.entity_types,
            on_result=self._names_landed,
            on_error=lambda _error: None,
        )

    def _names_landed(self, types: Any) -> None:
        self._display_names = {t.name: t.display_name for t in types or []}
        self._refresh_rows()

    # --- the rows ------------------------------------------------------------------------

    def _apply_row_props(self) -> None:
        model = self._model
        model.set_context(self._context)
        model.set_thumbnail(self._thumbnail)
        model.set_label_field(self._label_field)
        model.set_sub_label_field(self._sub_label_field)
        model.set_secondary_field(self._secondary_field)
        model.set_show_code(self._show_code)
        model.set_fields(self._fields)
        model.set_size(self._size)
        model.set_kind_of(lambda row: "heading" if isinstance(row, _Heading) else "row")
        named = self._sub_label is not None or not path_of(self._sub_label_field)
        model.set_sub_label(self._sub_of if named else None)
        model.set_secondary(self._secondary_of if self._secondary is not None else None)
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        if self._control is not None:
            self._control.set_row_mapper(self._rows_of)

    def _sub_of(self, row: Any) -> str:
        if self._sub_label is not None and getattr(row, "hit", None) is not None:
            return self._sub_label(row.hit) or ""
        return str(getattr(row, "sub", "") or "")

    def _secondary_of(self, row: Any) -> str:
        hit = getattr(row, "hit", None)
        if self._secondary is None or hit is None:
            return ""
        return self._secondary(hit) or ""

    def _type_label(self, entity_type: str) -> str:
        return self._display_names.get(entity_type, entity_type)

    def _sub_label_of(self, hit: SearchHit) -> str:
        """Where the row sits: its project, else the row it links to, else its type."""
        if hit.project is not None and hit.project.name:
            return hit.project.name
        if hit.link is not None:
            return f"{self._type_label(hit.link.type)} {hit.link.name}"
        return self._type_label(hit.ref.type)

    def _row_of(self, hit: SearchHit) -> GlobalSearchRow:
        return GlobalSearchRow(
            type=hit.ref.type,
            id=hit.ref.id,
            name=hit.ref.name or placeholder_name(hit.ref),
            values=dict(hit.values),
            hit=hit,
            sub=self._sub_label_of(hit),
        )

    def _recent_rows(self) -> list[Any]:
        rows: list[Any] = [_Heading(RECENT_HEADING)]
        for ref in self._recents:
            rows.append(
                GlobalSearchRow(
                    type=ref.type,
                    id=ref.id,
                    name=ref.name or placeholder_name(ref),
                    values={},
                    hit=None,
                    sub=self._type_label(ref.type),
                    recent=True,
                )
            )
        return rows

    def _rows_of(self, items: Sequence[Any]) -> list[Any]:
        """The rows the list draws: the recents on an empty query, else one group per type."""
        query = self._control.query if self._control is not None else ""
        if not query.strip() and self._recents:
            return self._recent_rows()
        order = list(search_type_map(self._entity_types))
        by_type: dict[str, list[SearchHit]] = {}
        for hit in items:
            by_type.setdefault(hit.ref.type, []).append(hit)
        rows: list[Any] = []
        for entity_type in order:
            hits = by_type.get(entity_type)
            if not hits:
                continue
            rows.append(_Heading(self._type_label(entity_type)))
            rows.extend(self._row_of(hit) for hit in hits)
        return rows

    # --- picking -------------------------------------------------------------------------

    def _on_query(self, _text: str) -> None:
        self._refresh_rows()

    def _on_activated(self, row: int) -> None:
        found = self._model.row_at(row)
        if not isinstance(found, GlobalSearchRow):
            return
        self.choose(found.ref)

    def choose(self, entity: EntityRef) -> None:
        """Take a row: the recents lead with it, and the palette closes."""
        self._recents = prepend_recent(
            self._recents, entity, self._recent_limit, lambda ref: f"{ref.type}:{ref.id}"
        )
        self.recents_changed.emit(list(self._recents))
        self.selected.emit(entity)
        if not self._inline:
            self.set_open(False)
        self._control.set_query("")

    def _toggle(self) -> None:
        self.set_open(not self.open)
