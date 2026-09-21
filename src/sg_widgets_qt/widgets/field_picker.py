"""One field of an entity type, chosen through a list that descends into linked types.

Ported from `packages/react/src/registry/sg/components/field-picker.tsx` and its Svelte twin.
The value is the dotted path: a root field is its own code, and every hop names the field
followed and the type it landed on. Only a single `entity` field is descended into, a link
declaring several target types asks which one first, and `data_types` and `valid_types` bind
what may be chosen rather than what may be walked through.

The control is `picker_control`, so the press rule, the dismissal guard, the caret and the
states are the shared ones. What this module adds is the breadcrumb over the search row, the
field glyph per data type, and the friendly path the closed control reads. `FieldLevels` holds
where the list stands, so the column picker's own list walks the same path.

    picker = FieldPicker(context=context, entity_type="Version", deep_links=True)
    picker.value_changed.connect(chosen)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QModelIndex, Qt, Signal

from sg_widgets_core.field_icons import icon_name_for
from sg_widgets_core.pickers import (
    DEFAULT_MAX_DEPTH,
    ExtraField,
    FieldHop,
    FieldOption,
    FieldOptionsInput,
    FieldPathOption,
    current_type,
    derive_field_options,
    resolve_field_path_options,
    search_field_options,
    search_field_path_options,
)
from sg_widgets_core.schema import FieldSchema
from sg_widgets_core.search import match_runs
from sg_widgets_core.state import NO_MATCH_LABEL

from ..primitives.base import (
    CONTROL_HEIGHT,
    ThemedWidget,
    elide,
    event_point,
    painter_for,
)
from ..primitives.button import Button
from ..primitives.list_view import LIST_PAD
from ..primitives.roles import Roles
from ..primitives.row_delegate import RowDelegate
from ..primitives.skeleton import Skeleton
from ..primitives.type_scale import line_box
from ..workers import Ticket, default_pool
from .picker_control import PICKER_SIZE_VALUES, PickerControl

__all__ = [
    "CHOOSING_PLACEHOLDER",
    "CRUMB_SEPARATOR",
    "DESCEND_ZONE",
    "Breadcrumb",
    "FieldLevels",
    "FieldOptionModel",
    "FieldPicker",
    "FieldSkeletons",
    "FlatFieldRow",
    "PathLabel",
    "descend_hit",
    "extra_fields_of",
    "flat_field_row",
    "schema_of",
]

#: Between the display names of a resolved path, in the row and in the control.
CRUMB_SEPARATOR = " › "

#: The trailing strip of a row that descends where a press descends rather than chooses.
#: The mark itself is the delegate's drill column, which `drill_rect` measures; this is the
#: fallback for a delegate that draws none.
DESCEND_ZONE = 24

#: The breadcrumb bar: `py-1.5` over the 1px rule under it, inset `px-2`, `gap-1.5`.
CRUMB_BAR_HEIGHT = 29
CRUMB_PAD = 8
CRUMB_GAP = 6

#: The metadata step of rule 6, which the crumbs and a sub-label are on.
CRUMB_TEXT = 12

#: The body step, which a control's own value is on.
VALUE_TEXT = 14

#: The mark a target type carries in its leading slot.
LINK_GLYPH = "link"

#: The search box asks this while a link's target types have replaced the fields.
CHOOSING_PLACEHOLDER = "Which type?"

#: The skeleton a control shows while a path is being resolved.
LABEL_SKELETON_WIDTH = 128
LABEL_SKELETON_HEIGHT = 16

#: `h-5 w-2/3` over `h-3 w-1/4`, three rows at the row's own inset: the block a schema read
#: stands behind, shaped like the two-line rows it replaces (field-picker.tsx:505-518).
ROW_SKELETON_ROWS = 3
ROW_SKELETON_GAP = 4
ROW_SKELETON_PAD_X = 8
ROW_SKELETON_PAD_Y = 6
ROW_SKELETON_LABEL = 20
ROW_SKELETON_SUB = 12
ROW_SKELETON_LABEL_SHARE = 2.0 / 3.0
ROW_SKELETON_SUB_SHARE = 1.0 / 4.0


@dataclass
class FlatFieldRow(FieldOption):
    """One row of a caller's fixed list, shaped like a schema row so both lists draw the same.

    Upstream folds the two lists into one row shape before drawing them
    (field-picker.tsx:311-329). Here that shape is `FieldOption` itself, with the
    sub-label carried alongside because a path the schema does not hold says so in
    words where a schema row names its data type.
    """

    #: The muted line under the label: the leaf's data type, or that the schema has no such path.
    sub_label: str = ""


def flat_field_row(option: FieldPathOption) -> FlatFieldRow:
    """A fixed path as a row: its resolved label, never traversable, always its own value."""
    return FlatFieldRow(
        path=option.path,
        name=option.name,
        display_name=option.label,
        data_type=option.data_type,
        selectable=True,
        traversable=False,
        targets=[],
        computed=False,
        sub_label=option.sub_label,
    )


def extra_fields_of(value: Any) -> list[ExtraField]:
    """The synthetic entries a caller offered, from dataclasses or from plain maps."""
    out: list[ExtraField] = []
    for entry in value or []:
        if isinstance(entry, ExtraField):
            out.append(entry)
        elif isinstance(entry, dict):
            shown = entry.get("display_name", entry.get("displayName"))
            out.append(
                ExtraField(name=str(entry.get("name", "")), display_name=shown if shown else None)
            )
    return out


def schema_of(context: Any) -> Any:
    """The schema service a context reads through, or the object itself where it is one."""
    found = getattr(context, "schema", None)
    return found if found is not None else context


class _SkeletonRow(QtWidgets.QWidget):
    """One row of the block: a label bar over a shorter sub-label bar."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(
            ROW_SKELETON_PAD_X, ROW_SKELETON_PAD_Y, ROW_SKELETON_PAD_X, ROW_SKELETON_PAD_Y
        )
        column.setSpacing(ROW_SKELETON_GAP)
        self._label = Skeleton(height=ROW_SKELETON_LABEL, parent=self)
        self._sub = Skeleton(height=ROW_SKELETON_SUB, parent=self)
        column.addWidget(self._label)
        column.addWidget(self._sub)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        room = max(0, self.width() - 2 * ROW_SKELETON_PAD_X)
        self._label.setFixedWidth(int(room * ROW_SKELETON_LABEL_SHARE))
        self._sub.setFixedWidth(int(room * ROW_SKELETON_SUB_SHARE))


class FieldSkeletons(QtWidgets.QWidget):
    """What a field list stands behind while the schema is read: three two-line rows."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(LIST_PAD, LIST_PAD, LIST_PAD, LIST_PAD)
        column.setSpacing(0)
        for _ in range(ROW_SKELETON_ROWS):
            column.addWidget(_SkeletonRow(self))


def descend_hit(surface: Any, index: QModelIndex, point: QtCore.QPoint) -> bool:
    """True when a press landed on a row's descend chevron rather than on the row.

    Upstream's chevron is a button inside the row that stops the press reaching it, so the
    mark's own box is the hit box. The delegate draws it in its drill column and measures it
    with `drill_rect`; a delegate that draws none falls back to the trailing `DESCEND_ZONE`.
    """
    rect = surface.visualRect(index)
    delegate = getattr(surface, "row_delegate", None)
    if callable(delegate):
        found = delegate().drill_rect(rect, index)
        if not found.isNull():
            return found.contains(point)
    return point.x() >= rect.right() + 1 - DESCEND_ZONE


class FieldLevels(QtCore.QObject):
    """Where a field list stands: the hops taken, the link being resolved, the fields read.

    One read per type, off the GUI thread. `/schema/<Type>/fields` is 48KB and about 330ms
    (probe 002), and the schema service caches it, so a hop back to a type already visited
    costs nothing. `changed` fires whenever the rows a list should draw have moved.

    `options` puts the levels in the flat mode: the caller's own paths, resolved once
    through every type they travel, drawn as one list that never descends.
    """

    #: The level, the fields or a failure moved.
    changed = Signal()

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        context: Any = None,
        entity_type: str = "",
        options: Sequence[str] | None = None,
        deep_links: bool = False,
        max_depth: int = DEFAULT_MAX_DEPTH,
        data_types: str | Sequence[str] | None = None,
        valid_types: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        hide_paths: Sequence[str] | None = None,
        filterable_only: bool = False,
        extra_fields: Sequence[Any] | None = None,
        filter: Callable[[FieldSchema, str], bool] | None = None,  # noqa: A002
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.entity_type = entity_type
        self.options = list(options) if options is not None else None
        self.deep_links = bool(deep_links)
        self.max_depth = int(max_depth)
        self.data_types = data_types
        self.valid_types = list(valid_types) if valid_types is not None else None
        self.exclude = list(exclude) if exclude is not None else None
        self.hide_paths = list(hide_paths) if hide_paths is not None else None
        self.filterable_only = bool(filterable_only)
        self.extra_fields = extra_fields_of(extra_fields)
        self.filter = filter

        self._hops: list[FieldHop] = []
        self._choosing: FieldOption | None = None
        self._fields: dict[str, FieldSchema] | None = None
        self._loaded_type = ""
        self._fixed: list[FieldPathOption] | None = None
        self._failure: str | None = None
        self._ticket = Ticket()
        self._fixed_ticket = Ticket()
        # A picker taken down under a read in flight — a demo the toolbar rebuilds, a popover
        # closed — leaves the schema on its way to levels that have gone, and `changed.emit`
        # on a deleted object raises into the event loop. The tickets are plain objects and
        # outlive this one, so taking them as it goes drops whatever is still out.
        tickets = (self._ticket, self._fixed_ticket)
        self.destroyed.connect(lambda *_ignored: [one.cancel() for one in tickets])

    # --- where it stands ------------------------------------------------------------------

    @property
    def hops(self) -> list[FieldHop]:
        """The hops taken so far. Empty at the root."""
        return list(self._hops)

    @property
    def choosing(self) -> FieldOption | None:
        """The link whose target type is being chosen, where one declares several."""
        return self._choosing

    @property
    def type(self) -> str:
        """The type the fields are read from after these hops."""
        return current_type(self.entity_type, self._hops)

    @property
    def flat(self) -> bool:
        """True while a caller's own paths stand in for the schema list."""
        return self.options is not None

    @property
    def fixed(self) -> list[FieldPathOption]:
        """The caller's paths as the schema read them. Empty until the read lands."""
        return list(self._fixed or [])

    @property
    def loading(self) -> bool:
        """True while what the list draws is in flight: the fixed paths, or a type's fields."""
        if self.flat:
            return self._fixed is None and self._failure is None
        return self._fields is None and self._failure is None

    @property
    def failure(self) -> str | None:
        """What the failed read said."""
        return self._failure

    @property
    def deep(self) -> bool:
        """True once the list is off the root, which is when the breadcrumb shows.

        A flat list has no levels to be off, so it never shows one
        (field-picker.tsx:`breadcrumb = !options && …`).
        """
        return not self.flat and (len(self._hops) > 0 or self._choosing is not None)

    def crumbs(self) -> list[str]:
        """The hop names drawn muted before a row's label."""
        return [hop.display_name for hop in self._hops]

    # --- the rows -------------------------------------------------------------------------

    def derived(self) -> list[FieldOption]:
        """Every schema option of the type the list stands on, before the search."""
        if self._fields is None or self._loaded_type != self.type:
            return []
        types = self.data_types
        return derive_field_options(
            self._fields,
            FieldOptionsInput(
                root_type=self.entity_type,
                hops=list(self._hops),
                deep_links=self.deep_links,
                max_depth=self.max_depth,
                data_types=list(types) if isinstance(types, (list, tuple)) else types,
                valid_types=self.valid_types,
                exclude=self.exclude,
                hide_paths=self.hide_paths,
                filterable_only=self.filterable_only,
                extra_fields=self.extra_fields,
                filter=self.filter,
            ),
        )

    def rows(self, query: str = "") -> list[FieldOption]:
        """The field rows the search leaves. Empty while a link's targets are on show.

        A flat list narrows on the label and on the path behind it; a schema list on the
        display name, the code and the data type.
        """
        if self.flat:
            found = search_field_path_options(self._fixed or [], query)
            return [flat_field_row(row) for row in found]
        if self._choosing is not None:
            return []
        return search_field_options(self.derived(), query)

    def targets(self, query: str = "") -> list[str]:
        """The target types on show, while a link declaring several is being resolved."""
        if self._choosing is None:
            return []
        needle = query.strip().lower()
        return [target for target in self._choosing.targets if needle in target.lower()]

    # --- moving between levels -------------------------------------------------------------

    def read(self) -> None:
        """Read what the list draws, off the GUI thread: the caller's paths, or a type's fields."""
        schema = schema_of(self.context)
        self._failure = None
        if self.flat:
            self._read_fixed(schema)
            return
        wanted = self.type
        self._fields = None
        if schema is None or not wanted:
            self.changed.emit()
            return
        self._loaded_type = wanted
        number = self._ticket.next()
        default_pool().submit(
            schema.fields,
            wanted,
            on_result=lambda fields, t=wanted: self._landed(t, fields),
            on_error=self._failed,
            ticket=(self._ticket, number),
        )
        self.changed.emit()

    def _read_fixed(self, schema: Any) -> None:
        """Resolve the caller's paths through every type they travel, once per list.

        Upstream keys the read on the list it was given so a stale answer is dropped
        (field-picker.tsx:236-249); here the ticket does that, as every other read.
        """
        self._fields = None
        self._fixed = None
        self._hops = []
        self._choosing = None
        wanted = list(self.options or [])
        root = self.entity_type
        if schema is None or not root:
            self.changed.emit()
            return
        number = self._fixed_ticket.next()
        default_pool().submit(
            resolve_field_path_options,
            schema,
            root,
            wanted,
            on_result=self._fixed_landed,
            on_error=self._failed,
            ticket=(self._fixed_ticket, number),
        )
        self.changed.emit()

    def _fixed_landed(self, rows: Any) -> None:
        self._fixed = list(rows or [])
        self.changed.emit()

    def _landed(self, wanted: str, fields: Any) -> None:
        if wanted != self.type:
            return
        self._fields = dict(fields or {})
        self._loaded_type = wanted
        self.changed.emit()

    def _failed(self, error: object) -> None:
        self._failure = str(error)
        self.changed.emit()

    def descend(self, field: FieldOption, through: str) -> None:
        """Take a hop onto one of a link's target types."""
        self._hops = [
            *self._hops,
            FieldHop(name=field.name, display_name=field.display_name, through=through),
        ]
        self._choosing = None
        self.read()

    def descend_into(self, row: FieldOption) -> None:
        """Descend a link, asking which type first where it declares several."""
        if not row.traversable:
            return
        if len(row.targets) == 1:
            self.descend(row, row.targets[0])
            return
        self._choosing = row
        self.changed.emit()

    def back(self) -> None:
        """One level back, or out of the choice of target type."""
        if self._choosing is not None:
            self._choosing = None
            self.changed.emit()
            return
        if not self._hops:
            return
        self._hops = self._hops[:-1]
        self.read()

    def reset(self) -> None:
        """Back to the root type."""
        if not self._hops and self._choosing is None:
            self.read()
            return
        self._hops = []
        self._choosing = None
        self.read()


class FieldOptionModel(QtCore.QAbstractListModel):
    """The rows a field list draws: the fields of one type, or the targets of one link.

    A row answers the roles `RowDelegate` paints: the display name with the matched runs, the
    programmatic name beside it, the data type under it, the field glyph in the leading slot,
    and a chevron on a row that descends.
    """

    def __init__(
        self,
        parent: QtCore.QObject | None = None,
        show_code: bool = False,
        checkable: bool = False,
    ) -> None:
        super().__init__(parent)
        self._rows: list[FieldOption] = []
        self._targets: list[str] = []
        self._query = ""
        self._chosen: list[str] = []
        self._show_code = bool(show_code)
        self._checkable = bool(checkable)

    # --- what it holds --------------------------------------------------------------------

    @property
    def rows(self) -> list[FieldOption]:
        """The field rows on show. Empty while a link's targets are being chosen."""
        return list(self._rows)

    @property
    def targets(self) -> list[str]:
        """The target types on show."""
        return list(self._targets)

    def keys(self) -> list[str]:
        """Every row's value in the order they are drawn, which is what the arrows walk."""
        return list(self._targets) if self._targets else [row.path for row in self._rows]

    def option_at(self, row: int) -> FieldOption | None:
        if self._targets:
            return None
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def target_at(self, row: int) -> str | None:
        return self._targets[row] if 0 <= row < len(self._targets) else None

    def set_rows(self, rows: Sequence[FieldOption], targets: Sequence[str] = ()) -> None:
        """Replace what the list draws. One of the two is always empty."""
        self.beginResetModel()
        self._rows = list(rows)
        self._targets = list(targets)
        self.endResetModel()

    def set_crumbs(self, crumbs: Sequence[str]) -> None:
        """The hops drawn muted before every row's label."""
        self._crumbs = [str(crumb) for crumb in crumbs]
        self._redraw()

    def set_query(self, value: str) -> None:
        self._query = str(value)
        self._redraw()

    def set_chosen(self, paths: Sequence[str]) -> None:
        """The paths that carry the tick or the tick box."""
        self._chosen = [str(path) for path in paths]
        self._redraw()

    @property
    def show_code(self) -> bool:
        """Whether a row shows its programmatic name beside the display name."""
        return self._show_code

    def set_show_code(self, value: bool) -> None:
        self._show_code = bool(value)
        self._redraw()

    def _redraw(self) -> None:
        if self.rowCount() > 0:
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, 0))

    # --- the model ------------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        if parent.isValid():
            return 0
        return len(self._targets) if self._targets else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: C901
        if not index.isValid():
            return None
        if self._targets:
            return self._target_data(self._targets[index.row()], role)
        option = self.option_at(index.row())
        if option is None:
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return option.display_name
        if role == Roles.RUNS:
            return self._runs(option.display_name)
        if role == Roles.CODE:
            code = option.name
            if not self._show_code or code == "" or code == option.display_name:
                return ""
            return code
        if role == Roles.SUB_LABEL:
            # A checkable list is the column picker's dual pane, whose row upstream draws on
            # one line: the code stands in for the data type there (column-picker.tsx:542-549).
            if self._checkable:
                return ""
            # A row of a caller's fixed list carries its own sub-label, so a path the schema
            # does not hold says so where a schema row names its data type.
            if isinstance(option, FlatFieldRow):
                return option.sub_label
            return "computed" if option.computed else option.data_type
        if role == Roles.GLYPH:
            return icon_name_for(option.data_type)
        if role == Roles.CHECKED:
            if self._checkable:
                return option.path in self._chosen
            return True if option.path in self._chosen else None
        if role == Roles.DISABLED:
            return self._checkable and not option.selectable
        if role == Roles.DRILLABLE:
            return option.traversable
        if role == Roles.ENTITY:
            return option
        if role == Qt.ItemDataRole.ToolTipRole:
            return option.path
        return None

    def _target_data(self, target: str, role: int) -> Any:
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return target
        if role == Roles.RUNS:
            return self._runs(target)
        if role == Roles.SUB_LABEL:
            return "" if self._checkable else "entity type"
        if role == Roles.GLYPH:
            return LINK_GLYPH
        if role == Roles.CHECKED:
            return False if self._checkable else None
        if role == Roles.DRILLABLE:
            return True
        if role == Roles.ENTITY:
            return target
        return None

    def _runs(self, label: str) -> list[tuple[str, bool, bool]]:
        """The label as runs: the matched words in DemiBold, and nothing before them.

        Upstream draws `row.displayName` alone; where the list stands is the breadcrumb bar's
        to say, so a row never repeats the trail above it.
        """
        return [(run.text, run.match, False) for run in match_runs(label, self._query)]

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class PathLabel(ThemedWidget):
    """The friendly path a closed control reads: the hops muted, the field itself in ink."""

    def __init__(
        self,
        parts: Sequence[str] = (),
        size: str = "md",
        slot_name: str = "field-picker-label",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size_step=size if size in CONTROL_HEIGHT else "md")
        self._parts = [str(part) for part in parts]
        self.setObjectName(slot_name)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    @property
    def parts(self) -> list[str]:
        """The display names of the path, root first."""
        return list(self._parts)

    def set_parts(self, parts: Sequence[str]) -> None:
        self._parts = [str(part) for part in parts]
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        """The whole path as one line."""
        return CRUMB_SEPARATOR.join(self._parts)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        """The path on one line, as tall as that line and not as tall as the control.

        The label is the control's value, not its box: asking for the whole ladder made the
        control two pixels taller than the ladder once its own border was added, which put a
        filter row off the step every other control in it stands on.
        """
        metrics = QtGui.QFontMetrics(self.theme.font(VALUE_TEXT))
        return QtCore.QSize(metrics.horizontalAdvance(self.text()) + 2, line_box(VALUE_TEXT))

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._parts:
            return
        theme = self.theme
        painter = painter_for(self)
        font = theme.font(VALUE_TEXT)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        whole = self.text()
        text = elide(metrics, whole, self.width())
        trail = CRUMB_SEPARATOR.join(self._parts[:-1])
        box = self.rect()
        flags = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        # The trail is drawn muted only where the whole path survived the elision, so a cut
        # path never shows a crumb that no longer leads anywhere.
        if trail and text == whole:
            head = trail + CRUMB_SEPARATOR
            painter.setPen(theme.color("muted_foreground"))
            painter.drawText(box, flags, head)
            painter.setPen(theme.color("foreground"))
            painter.drawText(box.adjusted(metrics.horizontalAdvance(head), 0, 0, 0), flags, self._parts[-1])
        else:
            painter.setPen(theme.color("foreground"))
            painter.drawText(box, flags, text)
        painter.end()


class Breadcrumb(ThemedWidget):
    """The bar over a field list: back one level, where the path stands, and reset."""

    back_requested = Signal()
    reset_requested = Signal()

    def __init__(self, slot: str = "field-picker", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._root = ""
        self._hops: list[str] = []
        self._choosing = ""
        self.setObjectName(f"{slot}-breadcrumb")
        self.setFixedHeight(CRUMB_BAR_HEIGHT)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self._back = Button(icon="chevron-left", variant="ghost", size="icon-xs", parent=self)
        self._back.setObjectName(f"{slot}-back")
        self._back.setToolTip("Back (Left arrow)")
        self._back.setAccessibleName("Go back one level")
        self._back.clicked.connect(self.back_requested.emit)
        self._reset = Button(icon="rotate-ccw", variant="ghost", size="icon-xs", parent=self)
        self._reset.setObjectName(f"{slot}-reset")
        self._reset.setToolTip("Reset")
        self._reset.setAccessibleName("Back to the root type")
        self._reset.clicked.connect(self.reset_requested.emit)

    def set_path(self, root: str, hops: Sequence[str], choosing: str = "") -> None:
        """The root type, the hops taken, and the link whose target is being chosen."""
        self._root = str(root)
        self._hops = [str(hop) for hop in hops]
        self._choosing = str(choosing)
        trail = [self._root, *self._hops]
        if self._choosing:
            trail.append(self._choosing)
        self.setAccessibleName("Field path")
        self.setAccessibleDescription(CRUMB_SEPARATOR.join(trail))
        self.update()

    def text(self) -> str:
        """The path the bar reads."""
        return self.accessibleDescription()

    @property
    def back_button(self) -> Button:
        """The control that goes one level back."""
        return self._back

    @property
    def reset_button(self) -> Button:
        """The control that goes back to the root type."""
        return self._reset

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        side = self._back.sizeHint()
        top = (CRUMB_BAR_HEIGHT - 1 - side.height()) // 2
        self._back.setGeometry(CRUMB_PAD, top, side.width(), side.height())
        self._reset.setGeometry(
            self.width() - CRUMB_PAD - side.width(), top, side.width(), side.height()
        )

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        font = theme.font(CRUMB_TEXT)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        side = self._back.sizeHint().width()
        left = CRUMB_PAD + side + CRUMB_GAP
        right = self.width() - CRUMB_PAD - side - CRUMB_GAP
        box = QtCore.QRect(left, 0, max(0, right - left), CRUMB_BAR_HEIGHT - 1)
        flags = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text = CRUMB_SEPARATOR.join([self._root, *self._hops])
        painter.setPen(theme.color("muted_foreground"))
        if self._choosing:
            head = text + CRUMB_SEPARATOR
            width = min(metrics.horizontalAdvance(head), box.width())
            painter.drawText(box, flags, elide(metrics, head, box.width()))
            italic = theme.font(CRUMB_TEXT)
            italic.setItalic(True)
            painter.setFont(italic)
            rest = box.adjusted(width, 0, 0, 0)
            painter.drawText(rest, flags, elide(metrics, self._choosing, rest.width()))
        else:
            painter.drawText(box, flags, elide(metrics, text, box.width()))
        painter.fillRect(
            QtCore.QRect(0, CRUMB_BAR_HEIGHT - 1, self.width(), 1), theme.color("border")
        )
        painter.end()


class FieldPicker(QtWidgets.QWidget):
    """One field of one entity type, as a searchable list that descends through links.

    The value is the dotted path. A link declaring one target type descends at once, one
    declaring several replaces the list with its types and asks which. A type already on the
    path is never offered again, and the path stops at `max_depth`.

    `options` replaces the schema list with a caller's own paths, flat: no links, no
    descending, no breadcrumb, and the list restrictions do not apply.
    """

    #: The chosen path, or the empty string once it is cleared.
    value_changed = Signal(str)
    #: The popup opened or closed.
    open_changed = Signal(bool)

    def __init__(
        self,
        context: Any = None,
        entity_type: str = "",
        options: Sequence[str] | None = None,
        value: str = "",
        deep_links: bool = False,
        show_code: bool = False,
        max_depth: int = DEFAULT_MAX_DEPTH,
        data_types: str | Sequence[str] | None = None,
        valid_types: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        hide_paths: Sequence[str] | None = None,
        filterable_only: bool = False,
        extra_fields: Sequence[Any] | None = None,
        filter: Callable[[FieldSchema, str], bool] | None = None,  # noqa: A002
        close_on_select: bool = True,
        placeholder: str = "Select a field",
        search_placeholder: str = "Search fields…",
        empty_label: str = NO_MATCH_LABEL,
        loading_label: str | None = None,
        error_label: str | None = None,
        clearable: bool = True,
        readonly: bool = False,
        disabled: bool = False,
        invalid: bool = False,
        size: str = "md",
        open: bool = False,  # noqa: A002
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("field-picker")
        self._value = str(value or "")
        self._close_on_select = bool(close_on_select)
        self._size = size if size in PICKER_SIZE_VALUES else "md"
        #: The caller's own search placeholder, which the choosing level borrows the box from.
        self._search_placeholder = str(search_placeholder)
        self._label_parts: list[str] | None = None
        self._label_ticket = Ticket()
        #: The path the control last read, so a fixed list rebuilds the chip only when it moves.
        self._shown_label = ""

        #: The breadcrumb over the popup's search row, which comes with the popup.
        self._breadcrumb: Breadcrumb | None = None

        self._levels = FieldLevels(
            self,
            context=context,
            entity_type=entity_type,
            options=options,
            deep_links=deep_links,
            max_depth=max_depth,
            data_types=data_types,
            valid_types=valid_types,
            exclude=exclude,
            hide_paths=hide_paths,
            filterable_only=filterable_only,
            extra_fields=extra_fields,
            filter=filter,
        )
        self._levels.changed.connect(self._refresh)

        self._model = FieldOptionModel(self, show_code=show_code)
        delegate = RowDelegate(None, size=self._size, thumbnail=True, indicator="tick")
        # A data type has a glyph, not a picture, so it is drawn on its own rather than on the
        # plate a row that expects a thumbnail falls back to.
        delegate.set_bare_glyph(True)
        self._control = PickerControl(
            slot="field-picker",
            picker="field",
            multiple=False,
            inline=False,
            token_input=False,
            searchable=True,
            text_value=True,
            size=self._size,
            disabled=disabled,
            readonly=readonly,
            invalid=invalid,
            clearable=clearable,
            placeholder=placeholder,
            search_placeholder=search_placeholder,
            empty_label=empty_label,
            loading_label=loading_label,
            error_label=error_label,
            row_model=self._model,
            row_delegate=delegate,
            highlight_on_open=True,
            loop=True,
            loading_block=FieldSkeletons,
            parent=self,
        )
        self._control.set_chip_factory(self._chip_for)
        self._control.selected.connect(self._on_selected)
        self._control.open_changed.connect(self._on_open_changed)
        self._control.query_changed.connect(lambda _query: self._refresh())
        self._control.remove_requested.connect(lambda _index: self.set_value(""))
        self._control.cleared.connect(lambda: self.set_value(""))

        # The breadcrumb and the filters live in the control's popup, which is built on the
        # first open. Asking for any part of it here would build it for every picker on a page.
        self._control.on_popup_built(self._wire_popup)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._control)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)

        self._levels.read()
        self._resolve_label()
        self._refresh()
        if open:
            self._control.set_open(True)

    # --- the parts ------------------------------------------------------------------------

    @property
    def control(self) -> PickerControl:
        """The control box and popup shell this picker is built on."""
        return self._control

    @property
    def levels(self) -> FieldLevels:
        """Where the list stands: the hops, the link being resolved, the fields read."""
        return self._levels

    @property
    def rows_model(self) -> FieldOptionModel:
        """The rows the list draws."""
        return self._model

    @property
    def breadcrumb(self) -> Breadcrumb:
        """The bar over the search row. Hidden at the root.

        It comes with the popup, so asking for it builds the popup the way opening would.
        """
        self._control.popup()
        return self._breadcrumb

    @property
    def hops(self) -> list[FieldHop]:
        """The hops taken so far."""
        return self._levels.hops

    @property
    def derived(self) -> list[FieldOption]:
        """Every schema option of the type the picker stands on, before the search.

        Upstream's own name for this list, which `options` took when it became a prop
        (field-picker.tsx:295). Empty while a fixed list is on show.
        """
        return self._levels.derived()

    @property
    def label(self) -> str:
        """The friendly path the closed control reads, or the raw one until it resolves."""
        offered = self._offered_parts()
        if offered is not None:
            return CRUMB_SEPARATOR.join(offered)
        if self._label_parts is None:
            return self._value
        return CRUMB_SEPARATOR.join(self._label_parts)

    @property
    def label_parts(self) -> list[str]:
        """The display name of every segment of the chosen path, root first."""
        offered = self._offered_parts()
        if offered is not None:
            return offered
        return list(self._label_parts or [])

    def _offered_parts(self) -> list[str] | None:
        """The label a fixed list already carries for the chosen path, where it holds it.

        A fixed row is labelled through `path_label`, which names the type a link could
        have gone elsewhere from, so the closed control reads what the row read.
        """
        if not self._value:
            return None
        row = next((one for one in self._levels.fixed if one.path == self._value), None)
        return row.label.split(CRUMB_SEPARATOR) if row is not None else None

    # --- props ----------------------------------------------------------------------------

    @property
    def context(self) -> Any:
        """The widget context. The schema is read through it, once per page."""
        return self._levels.context

    def set_context(self, value: Any) -> None:
        self._levels.context = value
        self._levels.reset()
        self._resolve_label()

    @property
    def entity_type(self) -> str:
        """The type the path starts on."""
        return self._levels.entity_type

    def set_entity_type(self, value: str) -> None:
        self._levels.entity_type = str(value)
        self._levels.reset()
        self._resolve_label()

    @property
    def value(self) -> str:
        """The dotted path, `field` or `field.Type.field…`. Empty when nothing is chosen."""
        return self._value

    def set_value(self, value: str) -> None:
        """Choose a path, or nothing. The control reads the friendly path, never the raw one."""
        text = str(value or "")
        if text == self._value:
            return
        self._value = text
        self._label_parts = None
        self._resolve_label()
        self._refresh()
        self.value_changed.emit(text)

    @property
    def options(self) -> list[str] | None:
        """A fixed list of paths, offered flat. The list restrictions do not apply to it."""
        return list(self._levels.options) if self._levels.options is not None else None

    def set_options(self, value: Sequence[str] | None) -> None:
        # The caller hands a fresh list on every pass, so the read is keyed on what it holds
        # and an unchanged list costs nothing (field-picker.tsx:236-238).
        wanted = list(value) if value is not None else None
        if wanted == self._levels.options:
            return
        self._levels.options = wanted
        self._levels.reset()
        self._resolve_label()

    @property
    def deep_links(self) -> bool:
        """Allow descending through entity fields."""
        return self._levels.deep_links

    def set_deep_links(self, value: bool) -> None:
        self._levels.deep_links = bool(value)
        self._refresh()

    @property
    def show_code(self) -> bool:
        """Show the programmatic name beside the display name."""
        return self._model.show_code

    def set_show_code(self, value: bool) -> None:
        self._model.set_show_code(value)

    @property
    def max_depth(self) -> int:
        """How many hops a path may take."""
        return self._levels.max_depth

    def set_max_depth(self, value: int) -> None:
        self._levels.max_depth = int(value)
        self._refresh()

    @property
    def data_types(self) -> str | list[str] | None:
        """Data types a field must have to be selected. Traversal ignores this."""
        return self._levels.data_types

    def set_data_types(self, value: str | Sequence[str] | None) -> None:
        self._levels.data_types = value
        self._refresh()

    @property
    def valid_types(self) -> list[str] | None:
        """A field is selectable only if it links one of these. Traversal ignores this."""
        return self._levels.valid_types

    def set_valid_types(self, value: Sequence[str] | None) -> None:
        self._levels.valid_types = list(value) if value is not None else None
        self._refresh()

    @property
    def exclude(self) -> list[str] | None:
        """Full dotted paths to drop."""
        return self._levels.exclude

    def set_exclude(self, value: Sequence[str] | None) -> None:
        self._levels.exclude = list(value) if value is not None else None
        self._refresh()

    @property
    def hide_paths(self) -> list[str] | None:
        """Dotted prefixes to drop, along with everything beneath them."""
        return self._levels.hide_paths

    def set_hide_paths(self, value: Sequence[str] | None) -> None:
        self._levels.hide_paths = list(value) if value is not None else None
        self._refresh()

    @property
    def filterable_only(self) -> bool:
        """Drop the data types the API refuses in a filter."""
        return self._levels.filterable_only

    def set_filterable_only(self, value: bool) -> None:
        self._levels.filterable_only = bool(value)
        self._refresh()

    @property
    def extra_fields(self) -> list[ExtraField]:
        """Synthetic entries offered at the root only."""
        return list(self._levels.extra_fields)

    def set_extra_fields(self, value: Sequence[Any] | None) -> None:
        self._levels.extra_fields = extra_fields_of(value)
        self._resolve_label()
        self._refresh()

    @property
    def filter(self) -> Callable[[FieldSchema, str], bool] | None:
        """The caller's own visibility test over the schema and the candidate's full path."""
        return self._levels.filter

    def set_filter(self, value: Callable[[FieldSchema, str], bool] | None) -> None:
        self._levels.filter = value
        self._refresh()

    @property
    def close_on_select(self) -> bool:
        """Close the popup on a selection. Off keeps it open for the next pick."""
        return self._close_on_select

    def set_close_on_select(self, value: bool) -> None:
        self._close_on_select = bool(value)

    @property
    def placeholder(self) -> str:
        return self._control.placeholder

    def set_placeholder(self, value: str) -> None:
        self._control.set_placeholder(value)

    @property
    def search_placeholder(self) -> str:
        """What the search box asks. The level replaces it while a type is being chosen."""
        return self._search_placeholder

    def set_search_placeholder(self, value: str) -> None:
        self._search_placeholder = str(value)
        self._refresh()

    @property
    def empty_label(self) -> str:
        return self._control.empty_label

    def set_empty_label(self, value: str) -> None:
        self._control.set_empty_label(value)

    @property
    def loading_label(self) -> str | None:
        return self._control.loading_label

    def set_loading_label(self, value: str | None) -> None:
        self._control.set_loading_label(value)

    @property
    def error_label(self) -> str | None:
        return self._control.error_label

    def set_error_label(self, value: str | None) -> None:
        self._control.set_error_label(value)

    @property
    def clearable(self) -> bool:
        return self._control.clearable

    def set_clearable(self, value: bool) -> None:
        self._control.set_clearable(value)

    @property
    def readonly(self) -> bool:
        return self._control.readonly

    def set_readonly(self, value: bool) -> None:
        self._control.set_readonly(value)

    @property
    def disabled(self) -> bool:
        return self._control.disabled

    def set_disabled(self, value: bool) -> None:
        self._control.set_disabled(value)

    @property
    def invalid(self) -> bool:
        return self._control.invalid

    def set_invalid(self, value: bool) -> None:
        self._control.set_invalid(value)

    @property
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in PICKER_SIZE_VALUES else "md"
        self._control.set_size(self._size)
        self._control.rebuild_chips()

    @property
    def open(self) -> bool:
        """Whether the popup is showing."""
        return self._control.is_open

    def set_open(self, value: bool) -> None:
        self._control.set_open(value)

    # --- the label ------------------------------------------------------------------------

    def _resolve_label(self) -> None:
        """The friendly path, resolved through the schema of every type the path travels."""
        if not self._value:
            self._label_parts = []
            return
        computed = next(
            (one for one in self._levels.extra_fields if one.name == self._value), None
        )
        if computed is not None:
            self._label_parts = [computed.display_name or computed.name]
            self._control.rebuild_chips()
            return
        schema = schema_of(self._levels.context)
        if schema is None or not self._levels.entity_type:
            return
        path = self._value
        number = self._label_ticket.next()
        default_pool().submit(
            schema.resolve_path,
            self._levels.entity_type,
            path,
            on_result=lambda segments, p=path: self._label_landed(p, segments),
            # A path the schema no longer holds still has to be readable, so it stays as it is.
            on_error=lambda _error, p=path: self._label_landed(p, None),
            ticket=(self._label_ticket, number),
        )

    def _label_landed(self, path: str, segments: Any) -> None:
        if path != self._value:
            return
        if segments is None:
            self._label_parts = [path]
        else:
            self._label_parts = [segment.display_name for segment in segments]
        self._refresh()
        self._control.rebuild_chips()

    # --- what the control shows ---------------------------------------------------------------

    def _refresh(self) -> None:
        query = self._control.query
        self._model.set_query(query)
        self._model.set_chosen([self._value] if self._value else [])
        self._model.set_rows(self._levels.rows(query), self._levels.targets(query))
        self._control.set_items(self._model.keys())
        self._control.set_loading(self._levels.loading and self._levels.choosing is None)
        self._control.set_error(self._levels.failure)
        self._control.set_empty(len(self._model.keys()) == 0)
        if self._value:
            self._control.set_keys([self._value])
            self._control.set_labels([self.label])
        else:
            self._control.set_keys([])
            self._control.set_labels([])
        self._control.set_search_placeholder(
            CHOOSING_PLACEHOLDER if self._levels.choosing is not None else self._search_placeholder
        )
        # A fixed list labels the chosen path off its own rows, which land after the chip was
        # built, so the chip is rebuilt the once the label moves. A schema list is told by
        # `_label_landed` instead, and is left exactly as it was.
        if self._levels.flat:
            text = self.label
            if text != self._shown_label:
                self._shown_label = text
                self._control.rebuild_chips()
        self._sync_breadcrumb()

    def _wire_popup(self) -> None:
        """The parts of this picker that live in the control's popup, once it has one."""
        self._breadcrumb = Breadcrumb("field-picker", self._control.popup())
        self._breadcrumb.back_requested.connect(self._go_back)
        self._breadcrumb.reset_requested.connect(self._go_root)
        self._breadcrumb.hide()
        layout = self._control.popup().layout()
        if layout is not None:
            layout.insertWidget(0, self._breadcrumb)
        # Left, Right and Enter belong to the levels rather than to the flat list, and these
        # filters run before the control's own handlers, so a descend never closes the popup.
        self._control.caret().installEventFilter(self)
        caret = self._search_caret()
        if caret is not None:
            caret.installEventFilter(self)
        self._control.list_surface().viewport().installEventFilter(self)
        self._sync_breadcrumb()

    def _sync_breadcrumb(self) -> None:
        """Where the list stands, on the bar over the search row."""
        if self._breadcrumb is None:
            return
        self._breadcrumb.set_path(
            self._levels.entity_type,
            self._levels.crumbs(),
            self._levels.choosing.display_name if self._levels.choosing is not None else "",
        )
        self._breadcrumb.setVisible(self._levels.deep)

    def _chip_for(self, index: int) -> QtWidgets.QWidget | None:
        if index != 0 or not self._value:
            return None
        parts = self._offered_parts()
        if parts is None:
            if self._label_parts is None:
                return Skeleton(
                    width=LABEL_SKELETON_WIDTH, height=LABEL_SKELETON_HEIGHT, parent=self._control
                )
            parts = self._label_parts
        return PathLabel(parts, size=self._size, parent=self._control)

    # --- choosing -----------------------------------------------------------------------------

    def _activate(self, row: FieldOption) -> None:
        if row.traversable and not row.selectable:
            self._descend_into(row)
            return
        self.set_value(row.path)
        self._control.set_query("")
        if self._close_on_select:
            self._control.set_open(False)

    def _descend(self, field: FieldOption, through: str) -> None:
        # The search box clears on every hop; nothing is remounted, so the caret stays put.
        self._control.set_query("")
        self._levels.descend(field, through)

    def _descend_into(self, row: FieldOption) -> None:
        self._control.set_query("")
        self._levels.descend_into(row)

    def _go_back(self) -> None:
        """The bar's Back, which clears the query the way the Left key does."""
        self._control.set_query("")
        self._levels.back()

    def _go_root(self) -> None:
        """The bar's Reset, which clears the query too (field-picker.tsx:335-339)."""
        self._control.set_query("")
        self._levels.reset()

    def _on_open_changed(self, is_open: bool) -> None:
        if not is_open:
            self._refresh()
        self.open_changed.emit(is_open)

    def _on_selected(self, keys: list) -> None:
        if not keys:
            self.set_value("")
            return
        key = str(keys[0])
        choosing = self._levels.choosing
        if choosing is not None:
            self._descend(choosing, key)
            return
        row = next((one for one in self._model.rows if one.path == key), None)
        if row is not None:
            self._activate(row)

    # --- the keys and the presses the levels own ----------------------------------------------

    def _search_caret(self) -> QtWidgets.QWidget | None:
        return self._control.search_row().findChild(QtWidgets.QLineEdit)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QtCore.QEvent.Type.KeyPress and self._control.is_open:
            if self._on_level_key(event):
                return True
        elif kind == QtCore.QEvent.Type.MouseButtonRelease and self._control.is_open:
            if obj is self._control.list_surface().viewport() and self._on_row_press(event):
                return True
        return super().eventFilter(obj, event)

    def _on_level_key(self, event: QtGui.QKeyEvent) -> bool:
        """Right descends, Left goes back, and Enter on a link that cannot be chosen descends."""
        key = event.key()
        row = self._control.list_surface().highlighted()
        choosing = self._levels.choosing
        if key == Qt.Key.Key_Right:
            if choosing is not None:
                target = self._model.target_at(row)
                if target is not None:
                    self._descend(choosing, target)
                return True
            option = self._model.option_at(row)
            if option is not None and option.traversable:
                self._descend_into(option)
                return True
            return False
        if key == Qt.Key.Key_Left and self._levels.deep:
            self._control.set_query("")
            self._levels.back()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if choosing is not None:
                target = self._model.target_at(row)
                if target is not None:
                    self._descend(choosing, target)
                    return True
                return False
            option = self._model.option_at(row)
            if option is not None and option.traversable and not option.selectable:
                self._descend_into(option)
                return True
        return False

    def _on_row_press(self, event: QtGui.QMouseEvent) -> bool:
        """A press on a link that cannot be chosen, or on a link's chevron, descends."""
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        surface = self._control.list_surface()
        point = event_point(event)
        index = surface.indexAt(point)
        if not index.isValid():
            return False
        choosing = self._levels.choosing
        if choosing is not None:
            target = self._model.target_at(index.row())
            if target is not None:
                self._descend(choosing, target)
                return True
            return False
        option = self._model.option_at(index.row())
        if option is None or not option.traversable:
            return False
        if descend_hit(surface, index, point) or not option.selectable:
            self._descend_into(option)
            return True
        return False
