"""The one row every picker, search and tree lists.

Rule 9 of `docs/design-rules.md` and the upstream `picker-row.tsx`: a leading picture, the
label with the matched runs in DemiBold, a code beside it, a muted sub-label, and a
right-aligned secondary rendered by its data type. React draws that row as a component; here
it is a model, because a Qt list draws its rows through a delegate and a model is what the
delegate reads. `PickerRowModel` resolves every part of rule 9 off a core `PickerRow` into the
roles `primitives/row_delegate.py` paints, and `PickerRowWidget` paints one row on its own,
for a card or a chip preview.

    model = PickerRowModel(rows, context=context, secondary_field="sg_status_list")
    view.setModel(model)

The picture is read on a worker and lands on the row that asked for it. A secondary whose
field is a status draws as the status colour and its label, which is what a status is where
it is an option rather than a value.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from qtpy.QtCore import QAbstractListModel, QModelIndex, QObject, QRect, QSize, Qt, Signal
from qtpy.QtGui import QPainter, QPixmap
from qtpy.QtWidgets import QSizePolicy, QStyle, QStyleOptionViewItem, QWidget

from sg_widgets_core.picker import entity_key, placeholder_name
from sg_widgets_core.render import (
    FieldTextOptions,
    field_text,
    initials_of,
    is_empty_value,
    render_kind_for,
)
from sg_widgets_core.row import (
    RowAnatomy,
    path_of,
    row_code,
    row_fields,
    row_secondary,
    row_sub_label,
    row_thumbnail,
    secondary_type,
)
from sg_widgets_core.search import match_runs

from ..images import ImageLoader, image_loader
from ..primitives.roles import Roles
from ..primitives.row_delegate import LEAD, RowDelegate
from ..theme import theme_of, watch_theme
from ..workers import default_pool, run_later
from .entity_glyphs import entity_glyph
from .field_value import (
    FieldValueOptions,
    field_value_size_hint,
    paint_field_value,
    warm_status_glyph,
)

__all__ = [
    "PEOPLE_TYPES",
    "PickerRowModel",
    "PickerRowWidget",
    "status_painter",
]

#: Types whose leading slot is a person rather than a picture of a shot.
PEOPLE_TYPES: tuple[str, ...] = ("HumanUser", "ApiUser", "ClientUser")

#: The crumb separator a hierarchy row draws before its label.
CRUMB_SEPARATOR = " › "

#: The data type a status secondary is drawn by (`field_types/status_list`).
STATUS_TYPE = "status_list"

RowLike = Any
"""A core `PickerRow`, or anything carrying `type`, `id`, `name` and `values`."""

#: The root of a list model, held once so it is not built in a default argument.
_ROOT = QModelIndex()


def status_painter(
    code: str,
    field: Any = None,
    statuses: Mapping[str, Any] | None = None,
    site_url: str = "",
    on_ready: Callable[[], None] | None = None,
) -> Callable[..., None]:
    """A painter for a status secondary: the badge, right-aligned in the column it is given.

    A status in a row's secondary column is a value rather than an option, and rule 9 draws a
    value as the badge; `paint_field_value` is the one face that badge is drawn by, so a row
    and a table cell read the same.
    """

    def paint(painter: QPainter, rect: QRect, option: QStyleOptionViewItem) -> None:
        widget = getattr(option, "widget", None)
        theme = theme_of(widget) if widget is not None else None
        if theme is None:
            return
        options = FieldValueOptions(
            theme=theme,
            field=field,
            statuses=statuses,
            site_url=site_url,
            selected=bool(option.state & QStyle.StateFlag.State_Selected),
            on_ready=on_ready,
        )
        wanted = field_value_size_hint(code, STATUS_TYPE, options).width()
        width = max(0, min(wanted, rect.width()))
        box = QRect(rect.right() + 1 - width, rect.top(), width, rect.height())
        paint_field_value(painter, box, code, STATUS_TYPE, options)

    return paint


class PickerRowModel(QAbstractListModel):
    """Core picker rows, resolved into the roles `RowDelegate` paints.

    The keywords are rule 9's own: `thumbnail`, `label_field`, `sub_label_field` or
    `sub_label`, `secondary_field` or `secondary`, `show_code`, `round_thumbnail` and `size`.
    `sub_label` and `secondary` also take a callable of the row, which is how a wrapper writes
    a line of its own.
    """

    #: A picture landed, or the secondary's schema did, and the rows redrew.
    rows_changed = Signal()

    def __init__(
        self,
        rows: Sequence[RowLike] = (),
        parent: QObject | None = None,
        context: Any = None,
        query: str = "",
        thumbnail: str | bool = "image",
        label_field: str | None = None,
        sub_label_field: Any = None,
        sub_label: str | Callable[[RowLike], str] | None = None,
        secondary_field: Any = None,
        secondary: str | Callable[[RowLike], str] | None = None,
        show_code: bool = False,
        round_thumbnail: bool = False,
        size: str = "md",
        fields: Sequence[str] = (),
        site_url: str | None = None,
        loader: ImageLoader | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows: list[RowLike] = list(rows)
        self._context = context
        self._query = query
        self._thumbnail: str | bool = thumbnail
        self._label_field = label_field
        self._sub_label_field = sub_label_field
        self._sub_label = sub_label
        self._secondary_field = secondary_field
        self._secondary = secondary
        self._show_code = bool(show_code)
        self._round_thumbnail = bool(round_thumbnail)
        self._size = size
        self._fields = list(fields)
        self._site_url = site_url
        self._loader = loader if loader is not None else image_loader()

        self._checked: set[str] = set()
        self._crumbs_of: Callable[[RowLike], Sequence[str]] | None = None
        self._row_painter_of: Callable[[RowLike], Callable[..., None] | None] | None = None
        self._drillable_of: Callable[[RowLike], bool] | None = None
        self._status_redraw = False
        self._warmed: set[str] = set()
        self._glyph_of: Callable[[RowLike], str] | None = None
        self._kind_of: Callable[[RowLike], str] | None = None
        self._pictures: dict[str, QPixmap] = {}
        self._asked: set[str] = set()
        self._field: Any = None
        self._statuses: dict[str, Any] | None = None
        self._plan_for: tuple[str, str] | None = None
        self._plan_pending = False
        self._ask_plan()
        self._ask_pictures()

    # --- the rows ----------------------------------------------------------------------

    @property
    def rows(self) -> list[RowLike]:
        """The rows on show."""
        return list(self._rows)

    def set_rows(self, rows: Sequence[RowLike]) -> None:
        """Replace the rows.

        A load-more page and a pick both answer the rows already on show followed by whatever
        is new, so those two are told as a `dataChanged` and an insert rather than a reset: a
        reset drops the view's scroll position and its keyboard cursor, and the list would jump
        back to the top under a reader. Anything else — a new query — really is a reset.
        """
        wanted = list(rows)
        held = [_key_of(row) for row in self._rows]
        arriving = [_key_of(row) for row in wanted]
        if held and arriving[: len(held)] == held:
            kept = len(held)
            self._rows = wanted[:kept]
            self.dataChanged.emit(self.index(0, 0), self.index(kept - 1, 0))
            extra = wanted[kept:]
            if extra:
                self.beginInsertRows(QModelIndex(), kept, kept + len(extra) - 1)
                self._rows.extend(extra)
                self.endInsertRows()
        else:
            self.beginResetModel()
            self._rows = wanted
            self.endResetModel()
        self._ask_plan()
        self._ask_pictures()

    def append_rows(self, rows: Sequence[RowLike]) -> None:
        """Add a page under the rows already there."""
        extra = list(rows)
        if not extra:
            return
        first = len(self._rows)
        self.beginInsertRows(QModelIndex(), first, first + len(extra) - 1)
        self._rows.extend(extra)
        self.endInsertRows()
        self._ask_pictures()

    def row_at(self, row: int) -> RowLike | None:
        """The row at that index, or None."""
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def index_of_key(self, key: str) -> int:
        """Where the row with that `type:id` key sits, or -1."""
        for i, row in enumerate(self._rows):
            if _key_of(row) == key:
                return i
        return -1

    # --- the keywords ------------------------------------------------------------------

    @property
    def query(self) -> str:
        """The query whose matched runs are bold."""
        return self._query

    def set_query(self, value: str) -> None:
        # A redraw invalidates every row's size hint, and a picker refreshes on every answer,
        # so a query that reads the same is not one.
        wanted = value or ""
        if wanted == self._query:
            return
        self._query = wanted
        self._redraw()

    @property
    def context(self) -> Any:
        """The widget context. The secondary's schema and the status table are read through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._plan_for = None
        self._ask_plan()

    @property
    def thumbnail(self) -> str | bool:
        """`False`, or the field holding the picture URL."""
        return self._thumbnail

    def set_thumbnail(self, value: str | bool) -> None:
        self._thumbnail = value
        self._redraw()
        self._ask_pictures()

    @property
    def label_field(self) -> str | None:
        """The field shown as the main label."""
        return self._label_field

    def set_label_field(self, value: str | None) -> None:
        self._label_field = value
        self._redraw()

    @property
    def sub_label_field(self) -> Any:
        """The muted line under the label: a path, or a resolved column."""
        return self._sub_label_field

    def set_sub_label_field(self, value: Any) -> None:
        self._sub_label_field = value
        self._redraw()

    @property
    def sub_label(self) -> str | Callable[[RowLike], str] | None:
        """The muted line of the caller's own making. Wins over `sub_label_field`."""
        return self._sub_label

    def set_sub_label(self, value: str | Callable[[RowLike], str] | None) -> None:
        self._sub_label = value
        self._redraw()

    @property
    def secondary_field(self) -> Any:
        """The right-aligned value: a path, or a resolved column."""
        return self._secondary_field

    def set_secondary_field(self, value: Any) -> None:
        self._secondary_field = value
        self._plan_for = None
        self._ask_plan()
        self._redraw()

    @property
    def secondary(self) -> str | Callable[[RowLike], str] | None:
        """Right-aligned text of the caller's own making. Wins over `secondary_field`."""
        return self._secondary

    def set_secondary(self, value: str | Callable[[RowLike], str] | None) -> None:
        self._secondary = value
        self._redraw()

    @property
    def show_code(self) -> bool:
        """Show the row's code beside the label when the two differ."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._redraw()

    @property
    def round_thumbnail(self) -> bool:
        """Whether the leading picture is a circle."""
        return self._round_thumbnail

    def set_round_thumbnail(self, value: bool) -> None:
        self._round_thumbnail = bool(value)
        self._redraw()

    @property
    def size(self) -> str:
        """`sm`, `md` or `lg`: the picture and text ladder."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value
        self._pictures.clear()
        self._asked.clear()
        self._redraw()
        self._ask_pictures()

    @property
    def fields(self) -> list[str]:
        """Extra fields a caller's own sub-label or secondary reads."""
        return list(self._fields)

    def set_fields(self, value: Sequence[str]) -> None:
        self._fields = list(value)

    @property
    def site_url(self) -> str:
        """The site a status glyph is served from."""
        if self._site_url is not None:
            return self._site_url
        return str(getattr(self._context, "site_url", "") or "")

    def set_site_url(self, value: str | None) -> None:
        self._site_url = value

    # --- what a wrapper adds ------------------------------------------------------------

    def set_checked_keys(self, keys: Iterable[str]) -> None:
        """The `type:id` keys a multi picker holds, drawn in the indicator column."""
        wanted = set(keys)
        if wanted == self._checked:
            return
        self._checked = wanted
        self._redraw()

    @property
    def checked_keys(self) -> set[str]:
        return set(self._checked)

    def set_crumbs_of(self, fn: Callable[[RowLike], Sequence[str]] | None) -> None:
        """The crumbs drawn muted before a row's label, per row."""
        self._crumbs_of = fn
        self._redraw()

    def set_glyph_of(self, fn: Callable[[RowLike], str] | None) -> None:
        """The lucide glyph a row with no picture draws, per row."""
        self._glyph_of = fn
        self._redraw()

    def set_row_painter_of(
        self, fn: Callable[[RowLike], Callable[..., None] | None] | None
    ) -> None:
        """A painter for the whole of a row that is not the anatomy, per row.

        The palette's recents are an entity chip and the type beside it, which is a row of its
        own shape; every other row answers None and is drawn by the delegate as usual.
        """
        self._row_painter_of = fn
        self._redraw()

    def set_drillable_of(self, fn: Callable[[RowLike], bool] | None) -> None:
        """Which rows open a level of their own, and so draw the drill control."""
        self._drillable_of = fn
        self._redraw()

    def set_kind_of(self, fn: Callable[[RowLike], str] | None) -> None:
        """What a row is: `row`, `heading`, `separator` or `load_more`, per row."""
        self._kind_of = fn
        self._redraw()

    # --- the anatomy --------------------------------------------------------------------

    def anatomy(self) -> RowAnatomy:
        """The six props of rule 9, as core holds them."""
        return RowAnatomy(
            thumbnail=self._thumbnail,
            label_field=self._label_field,
            sub_label_field=self._sub_label_field,
            secondary_field=self._secondary_field,
            show_code=self._show_code,
            fields=list(self._fields),
        )

    def read_fields(self, base: Sequence[str] = ()) -> list[str]:
        """Every field these row props have to read, for the caller's own search."""
        return row_fields(self.anatomy(), base)

    # --- the model ----------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = _ROOT) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: C901
        if not index.isValid():
            return None
        row = self.row_at(index.row())
        if row is None:
            return None
        anatomy = self.anatomy()
        label = _label_of(row)

        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return label
        if role == Roles.RUNS:
            return self._runs(row, label)
        if role == Roles.CODE:
            return row_code(_values(row), label, self._show_code)
        if role == Roles.SUB_LABEL:
            return self._sub_label_of(row, anatomy)
        if role == Roles.DRILLABLE:
            return bool(self._drillable_of(row)) if self._drillable_of is not None else False
        if role == Roles.ROW_PAINTER:
            return self._row_painter_of(row) if self._row_painter_of is not None else None
        if role == Roles.SUB_RUNS:
            sub = self._sub_label_of(row, anatomy)
            return [(run.text, run.match) for run in match_runs(sub, self._query)] if sub else []
        if role == Roles.SECONDARY:
            return self._secondary_text(row, anatomy)
        if role == Roles.PAINTER:
            return self._secondary_paint(row, anatomy)
        if role == Roles.PIXMAP:
            return self._pictures.get(_key_of(row))
        if role == Roles.INITIALS:
            return self._initials_of(row, label)
        if role == Roles.GLYPH:
            return self._glyph(row)
        if role == Roles.CHECKED:
            return _key_of(row) in self._checked if self._checked else None
        if role == Roles.KIND:
            return self._kind_of(row) if self._kind_of is not None else "row"
        if role == Roles.ENTITY:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            crumbs = list(self._crumbs(row))
            return CRUMB_SEPARATOR.join([*crumbs, label])
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # --- resolving one row --------------------------------------------------------------

    def _crumbs(self, row: RowLike) -> Sequence[str]:
        if self._crumbs_of is not None:
            return self._crumbs_of(row) or ()
        found = getattr(row, "crumbs", None)
        return found if isinstance(found, Sequence) and not isinstance(found, str) else ()

    def _runs(self, row: RowLike, label: str) -> list[tuple[str, bool, bool]]:
        """The label as runs, the crumbs before it muted and the matched words in bold."""
        runs: list[tuple[str, bool, bool]] = []
        for crumb in self._crumbs(row):
            runs.append((str(crumb), False, True))
            runs.append((CRUMB_SEPARATOR, False, True))
        runs.extend((run.text, run.match, False) for run in match_runs(label, self._query))
        return runs

    def _sub_label_of(self, row: RowLike, anatomy: RowAnatomy) -> str:
        own = self._sub_label
        if callable(own):
            return own(row) or ""
        if isinstance(own, str):
            return own
        return row_sub_label(_values(row), anatomy)

    def _raw_secondary(self, row: RowLike, anatomy: RowAnatomy) -> Any:
        return row_secondary(_RowValues(row), anatomy)

    def _secondary_text(self, row: RowLike, anatomy: RowAnatomy) -> str:
        own = self._secondary
        if callable(own):
            return own(row) or ""
        if isinstance(own, str):
            return own
        path = path_of(anatomy.secondary_field)
        if not path:
            return ""
        raw = self._raw_secondary(row, anatomy)
        if is_empty_value(raw):
            return ""
        data_type = secondary_type(anatomy, getattr(self._field, "data_type", None))
        if render_kind_for(data_type) == "status":
            return ""
        return field_text(raw, data_type, self._text_options())

    def _secondary_paint(self, row: RowLike, anatomy: RowAnatomy) -> Callable[..., None] | None:
        """A status secondary is a glyph and a name, which no string renders."""
        if self._secondary is not None or self._statuses is None:
            return None
        path = path_of(anatomy.secondary_field)
        if not path:
            return None
        raw = self._raw_secondary(row, anatomy)
        if is_empty_value(raw):
            return None
        data_type = secondary_type(anatomy, getattr(self._field, "data_type", None))
        if render_kind_for(data_type) != "status":
            return None
        return status_painter(
            str(raw),
            field=self._field,
            statuses=self._statuses,
            site_url=self.site_url,
            on_ready=self._status_ready,
        )

    def _warm_statuses(self) -> None:
        """Read the sprite of every status on show, between frames rather than inside one.

        Building a source is what asks for its sprite, and a list of badges would build every
        one of them inside the first repaint, which is a stall on the GUI thread.
        """
        if not self._statuses or not self._rows:
            return
        anatomy = self.anatomy()
        if not path_of(anatomy.secondary_field):
            return
        data_type = secondary_type(anatomy, getattr(self._field, "data_type", None))
        if render_kind_for(data_type) != "status":
            return
        options = FieldValueOptions(
            statuses=self._statuses, site_url=self.site_url, on_ready=self._status_ready
        )
        wanted: list[str] = []
        for row in self._rows:
            raw = self._raw_secondary(row, anatomy)
            if is_empty_value(raw):
                continue
            code = str(raw)
            if code not in self._warmed and code not in wanted:
                wanted.append(code)
        if not wanted:
            return

        def warm_one(rest: list[str] = wanted) -> None:
            # One status a turn of the loop: warming costs a few milliseconds each, and a list
            # of them warmed together would be one stall rather than none.
            if not rest:
                return
            code = rest.pop(0)
            self._warmed.add(code)
            try:
                warm_status_glyph(code, options)
            except RuntimeError:
                return
            if rest:
                run_later(warm_one)

        run_later(warm_one)

    def _status_ready(self) -> None:
        """A status sprite landed.

        A list of badges lands its sprites one after another, so the redraws are coalesced into
        one turn of the loop rather than one repaint a sprite. The model may be gone by then,
        and a late answer is dropped.
        """
        if self._status_redraw:
            return
        self._status_redraw = True
        run_later(self._status_redrawn)

    def _status_redrawn(self) -> None:
        self._status_redraw = False
        try:
            self._redraw()
        except RuntimeError:
            return

    def _status_label(self, code: str) -> str:
        values = getattr(self._field, "display_values", None)
        if isinstance(values, dict):
            found = values.get(code)
            if isinstance(found, str) and found:
                return found
        return code

    def _text_options(self) -> FieldTextOptions:
        from sg_widgets_core.context import preferences_of

        options = preferences_of(self._context if self._context is not None else None)
        values = getattr(self._field, "display_values", None)
        if isinstance(values, dict):
            options.display_values = values
        return options

    def _initials_of(self, row: RowLike, label: str) -> str:
        if _type_of(row) not in PEOPLE_TYPES:
            return ""
        if self._pictures.get(_key_of(row)) is not None:
            return ""
        return initials_of(label)

    @property
    def bare_glyph(self) -> bool:
        """True when the caller named the glyph, so the row has no picture to stand in for."""
        return self._glyph_of is not None

    def _glyph(self, row: RowLike) -> str:
        if self._glyph_of is not None:
            return self._glyph_of(row) or ""
        return entity_glyph(_type_of(row))

    # --- the picture --------------------------------------------------------------------

    def _lead_side(self) -> int:
        return LEAD.get(self._size, LEAD["md"])

    def _ask_pictures(self) -> None:
        """Ask for every picture the rows name and have not asked for yet.

        The loader reads on the job pool and hands the pixmap back on this thread, so a row
        with a picture costs nothing on the way to the first paint.
        """
        anatomy = self.anatomy()
        side = self._lead_side()
        box = QSize(side, side)
        for row in self._rows:
            url = row_thumbnail(_values(row), anatomy)
            key = _key_of(row)
            if not url or key in self._asked:
                continue
            self._asked.add(key)
            self._loader.load(url, lambda picture, key=key: self._picture_landed(key, picture), box)

    def _picture_landed(self, key: str, picture: QPixmap | None) -> None:
        """A url that answered nothing leaves the row on its initials or its glyph."""
        if picture is None or picture.isNull():
            return
        self._pictures[key] = picture
        at = self.index_of_key(key)
        if at < 0:
            return
        try:
            where = self.index(at, 0)
            self.dataChanged.emit(where, where, [int(Roles.PIXMAP), int(Roles.INITIALS)])
            self.rows_changed.emit()
        except RuntimeError:
            # The model went while its picture was on the way. The answer is dropped.
            return

    # --- the secondary's schema ----------------------------------------------------------

    def _ask_plan(self) -> None:
        """Read the secondary's field, and the Status table when that field is a status.

        A resolved column already carries its field, so only a bare path costs a read, and
        that read is the context's cached one.
        """
        spec = self._secondary_field
        if spec is not None and not isinstance(spec, str):
            self._field = getattr(spec, "field", None)
        # A page that landed after the plan did brings codes of its own to warm.
        self._warm_statuses()
        path = path_of(spec)
        if self._context is None or not path or path == "id" or not self._rows:
            return
        # The first row of a grouped list is a heading, which names no type; the schema is
        # read off the first row that is an entity.
        entity_type = next((t for t in (_type_of(row) for row in self._rows) if t), "")
        if not entity_type or self._plan_for == (entity_type, path) or self._plan_pending:
            return
        self._plan_for = (entity_type, path)
        self._plan_pending = True
        context = self._context
        declared = getattr(spec, "data_type", None) if not isinstance(spec, str) else None
        default_pool().submit(
            _read_plan,
            context,
            entity_type,
            path,
            declared,
            on_result=self._plan_landed,
            on_error=lambda _error: setattr(self, "_plan_pending", False),
        )

    def _plan_landed(self, plan: Any) -> None:
        field, statuses = plan
        if field is not None:
            self._field = field
        self._statuses = statuses
        self._plan_pending = False
        self._warm_statuses()
        try:
            self._redraw()
        except RuntimeError:
            # The model went while the schema read was on the way.
            return

    # --- redraw -------------------------------------------------------------------------

    def _redraw(self) -> None:
        if not self._rows:
            self.rows_changed.emit()
            return
        self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0))
        self.rows_changed.emit()


def _read_plan(
    context: Any, entity_type: str, path: str, declared: str | None
) -> tuple[Any, dict[str, Any] | None]:
    """The secondary's field and, where it is a status, the site's Status table by code."""
    field = None
    schema = getattr(context, "schema", None)
    if schema is not None:
        field = schema.field(entity_type, path)
    data_type = declared or getattr(field, "data_type", None)
    statuses = None
    if data_type and render_kind_for(data_type) == "status":
        table = getattr(context, "statuses", None)
        if table is not None:
            statuses = dict(table.by_code())
    return field, statuses


class _RowValues:
    """`row_secondary` reads an id off the row itself, which a bare mapping has not got."""

    __slots__ = ("id", "values")

    def __init__(self, row: RowLike) -> None:
        self.id = int(getattr(row, "id", 0) or 0)
        self.values = _values(row)


def _values(row: RowLike) -> dict[str, Any]:
    found = getattr(row, "values", None)
    return found if isinstance(found, dict) else {}


def _type_of(row: RowLike) -> str:
    return str(getattr(row, "type", "") or "")


def _label_of(row: RowLike) -> str:
    name = getattr(row, "name", "")
    if isinstance(name, str) and name:
        return name
    return placeholder_name(row) if _type_of(row) else ""


def _key_of(row: RowLike) -> str:
    try:
        return entity_key(row)
    except Exception:
        return f"{_type_of(row)}:{getattr(row, 'id', 0)}"


class PickerRowWidget(QWidget):
    """One picker row, painted on its own.

    A card or a chip preview draws a row outside a list, which the delegate cannot do by
    itself. This is that delegate over a one-row model, so the row here and the row in a list
    are the same pixels.
    """

    def __init__(
        self,
        row: RowLike | None = None,
        parent: QWidget | None = None,
        model: PickerRowModel | None = None,
        **props: Any,
    ) -> None:
        super().__init__(parent)
        self._model = model if model is not None else PickerRowModel([], self, **props)
        if row is not None:
            self._model.set_rows([row])
        self._delegate = RowDelegate(
            self,
            size=self._model.size,
            thumbnail=self._model.thumbnail is not False,
            round_thumbnail=self._model.round_thumbnail,
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._model.dataChanged.connect(lambda *_: self.update())
        self._model.modelReset.connect(self._on_reset)
        watch_theme(self, lambda _theme: self.updateGeometry())

    @property
    def model(self) -> PickerRowModel:
        """The one-row model behind the paint, which carries every row keyword."""
        return self._model

    def set_row(self, row: RowLike | None) -> None:
        """Draw that row, or nothing."""
        self._model.set_rows([row] if row is not None else [])

    def set_size(self, value: str) -> None:
        """Wear a rung of the ladder."""
        self._model.set_size(value)
        self._delegate.set_size(value)
        self.updateGeometry()
        self.update()

    def set_query(self, value: str) -> None:
        """The query whose matched runs are bold."""
        self._model.set_query(value)

    def _on_reset(self) -> None:
        self._delegate.set_thumbnail(self._model.thumbnail is not False)
        self.updateGeometry()
        self.update()

    def _option(self) -> QStyleOptionViewItem:
        option = QStyleOptionViewItem()
        option.rect = self.rect()
        option.state = QStyle.StateFlag.State_Enabled
        option.widget = self
        option.font = self.font()
        return option

    def sizeHint(self) -> QSize:  # noqa: N802
        if self._model.rowCount() == 0:
            return QSize(0, 0)
        return self._delegate.sizeHint(self._option(), self._model.index(0, 0))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self.sizeHint().height())

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        if self._model.rowCount() == 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setOpacity(1.0 if self.isEnabled() else 0.5)
        self._delegate.paint(painter, self._option(), self._model.index(0, 0))
        painter.end()
