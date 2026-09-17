"""One field, displayed or edited, with the editor chosen by the data type.

Ported from `packages/react/src/registry/sg/components/field-editor.tsx` and its Svelte twin.
The data type picks the editor through core's `editor_kind_for`, and the pair behind this
toggle is the same one a caller can use directly: the value on the display half, the type's own
editor on the other. A status, a link and a multi-entity link open their picker, which reads
through the context; without a context, or without the schema those pickers need, the field
stays on the display half, as a calculated column always does.

`editor_placement` says where the editor opens: in place, or in a popover anchored to the
display half, which is what a table cell wants. Given an `entity`, the commit is written
through `context.client.update` on a worker and the row read back on the field that was
written (024_read_after_write); without one the editor only emits, and the caller writes.

    editor = FieldEditor(value="lighting", field=schema, editable=True, context=context)
    editor.value_changed.connect(store)
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, Signal

from sg_widgets_core.client import SearchOptions
from sg_widgets_core.context import preferences_of
from sg_widgets_core.edit import EditorKind, editor_kind_for, editor_needs_context, editor_placement_for
from sg_widgets_core.filter import EntityRef
from sg_widgets_core.render import FieldTextOptions, field_text
from sg_widgets_core.schema import FieldSchema

from ..primitives.base import CONTROL_HEIGHT, ThemedWidget, painter_for
from ..primitives.button import Button
from ..primitives.popover import Popover
from ..theme import with_alpha
from ..workers import Ticket, default_pool
from .checkbox_editor import CheckboxEditor
from .color_editor import ColorEditor
from .date_editor import DateEditor
from .date_time_editor import DateTimeEditor
from .entity_multi_picker import EntityMultiPicker
from .entity_picker import EntityPicker
from .field_error import FieldError
from .field_value import FieldValue
from .number_editor import NumberEditor
from .text_editor import TextEditor
from .url_editor import UrlEditor

__all__ = [
    "FIELD_EDITOR_MODES",
    "POPOVER_WIDTH",
    "FieldDisplay",
    "FieldEditor",
    "editor_for",
]

#: The two halves of the toggle.
FIELD_EDITOR_MODES: tuple[str, ...] = ("display", "edit")

#: `w-72`, and `w-96` for the one kind that needs the room.
POPOVER_WIDTH = 288
POPOVER_WIDTH_WIDE = 384

#: The popover's inset and the gap between its label, its control and its buttons.
POPOVER_PAD = 12
POPOVER_GAP = 12

#: The display half: `px-2 py-1.5`, on the body step.
DISPLAY_PAD_X = 8
DISPLAY_PAD_Y = 6
DISPLAY_TEXT = 14

#: The field's own name over the control in a popover, on the metadata step.
LABEL_TEXT = 12

#: `CONTROL_BUTTON` of `control-classes.ts`: the step the popover's Cancel and Save stand on.
POPOVER_BUTTON: dict[str, str] = {"sm": "sm", "md": "default", "lg": "lg"}

#: Between the chips of a multi-entity value.
CHIP_GAP = 6


def _import(name: str) -> Any:
    """A picker written on the same base, or None while it has not landed."""
    try:
        module = __import__(f"sg_widgets_qt.widgets.{name}", fromlist=["*"])
    except Exception:  # pragma: no cover - the pickers are the other half of this wave.
        return None
    return module


_list_picker = _import("list_picker")
_status_picker = _import("status_picker")

ListPicker = getattr(_list_picker, "ListPicker", None) if _list_picker else None
StatusPicker = getattr(_status_picker, "StatusPicker", None) if _status_picker else None


def editor_for(data_type: str) -> EditorKind:
    """The editor a data type opens. Core's own dispatch."""
    return editor_kind_for(str(data_type))


def _can_draw(kind: str, data_type: str, context: Any, field: FieldSchema | None) -> bool:
    """Whether the type's editor can be drawn at all.

    A picker reads through the context and needs the schema to say what it offers: a status its
    entity type, a link its valid types. Without either the field stays on the display half.
    """
    if kind == "none":
        return False
    if kind == "list" and ListPicker is None:
        return False
    if kind == "status_list" and StatusPicker is None:
        return False
    if not editor_needs_context(data_type):
        return True
    if context is None:
        return False
    if kind == "status_list":
        return bool(field is not None and field.entity_type)
    return len(field.valid_types or []) > 0 if field is not None else False


class _TextLine(ThemedWidget):
    """One line of a value, elided with the whole of it as the tooltip."""

    def __init__(
        self,
        text: str = "",
        muted: bool = False,
        size: int = DISPLAY_TEXT,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._muted = bool(muted)
        self._size = size
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.setMinimumWidth(0)

    def text(self) -> str:
        return self._text

    def set_text(self, value: str, muted: bool = False) -> None:
        self._text = value
        self._muted = bool(muted)
        self.setToolTip(value)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        metrics = QtGui.QFontMetrics(self.theme.font(self._size))
        return QtCore.QSize(metrics.horizontalAdvance(self._text) + 2, metrics.height())

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        theme = self.theme
        painter = painter_for(self)
        painter.setFont(theme.font(self._size))
        painter.setPen(theme.color("muted_foreground" if self._muted else "foreground"))
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.elide(painter, self._text, self.width()),
        )
        painter.end()


class FieldDisplay(ThemedWidget):
    """The display half: the value drawn by its data type, and the box a press opens it from.

    The value is `FieldValue`, the same widget a table cell draws, which upstream mounts here
    too (`field-editor.tsx:357-372`): a status is its badge, a link its chip, a multi-entity
    link a row of them, a url a link, a checkbox its mark, a colour its swatch and an image its
    thumbnail. A press on an editable half opens the editor rather than reaching the value, so
    the value takes no mouse of its own while the half is editable.
    """

    #: The half was pressed, or Enter or Space landed on it.
    activated = Signal()

    def __init__(
        self,
        value: Any = None,
        data_type: str = "text",
        field: FieldSchema | None = None,
        statuses: dict | None = None,
        context: Any = None,
        options: FieldTextOptions | None = None,
        empty_label: str = "empty",
        size: str = "md",
        editable: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent, size_step=size if size in CONTROL_HEIGHT else "md")
        self._value = value
        self._data_type = data_type
        self._field = field
        self._statuses = statuses
        self._context = context
        self._options = options if options is not None else FieldTextOptions()
        self._empty_label = empty_label
        self._editable = bool(editable)
        self._parts: list[QtWidgets.QWidget] = []
        self._value_widget: FieldValue | None = None
        self.setObjectName("field-editor-display")
        self._hover = self.animated(150)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self._row = QtWidgets.QHBoxLayout(self)
        self._row.setContentsMargins(DISPLAY_PAD_X, DISPLAY_PAD_Y, DISPLAY_PAD_X, DISPLAY_PAD_Y)
        self._row.setSpacing(CHIP_GAP)
        self._rebuild()

    # --- props ----------------------------------------------------------------------------

    def set_value(self, value: Any) -> None:
        self._value = value
        self._rebuild()

    def set_data_type(self, value: str) -> None:
        self._data_type = str(value)
        self._rebuild()

    def set_field(self, value: FieldSchema | None) -> None:
        self._field = value
        self._rebuild()

    def set_statuses(self, value: dict | None) -> None:
        self._statuses = value
        self._rebuild()

    def set_context(self, value: Any) -> None:
        self._context = value
        self._rebuild()

    def set_options(self, value: FieldTextOptions) -> None:
        self._options = value
        self._rebuild()

    def set_empty_label(self, value: str) -> None:
        self._empty_label = str(value)
        self._rebuild()

    def set_editable(self, value: bool) -> None:
        self._editable = bool(value)
        self.setCursor(
            Qt.CursorShape.IBeamCursor if self._editable else Qt.CursorShape.ArrowCursor
        )
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if self._editable else Qt.FocusPolicy.NoFocus
        )
        self._rebuild()

    def text(self) -> str:
        """The value as one line, which is what a drive reads."""
        return field_text(self._value, self._data_type, self._options)

    # --- what it draws ----------------------------------------------------------------------

    def _clear(self) -> None:
        for part in self._parts:
            self._row.removeWidget(part)
            part.setParent(None)
            part.deleteLater()
        self._parts = []

    def _add(self, widget: QtWidgets.QWidget) -> None:
        widget.setParent(self)
        self._row.addWidget(widget)
        self._parts.append(widget)

    def _rebuild(self) -> None:
        self._clear()
        while self._row.count():
            item = self._row.takeAt(0)
            if item.spacerItem() is None and item.widget() is None:
                break
        options = self._options
        site = getattr(self._context, "site_url", "") or ""
        shown = FieldValue(
            value=self._value,
            data_type=self._data_type,
            field=self._field,
            statuses=self._statuses,
            # An empty site leaves a chip inert, so a press on it reaches the half under it.
            site_url="",
            context=self._context,
            hours_per_day=options.hours_per_day,
            locale=options.locale,
            time_zone=options.time_zone,
            frame_rate=options.frame_rate,
            precision=options.decimals,
            currency_symbol=options.currency_symbol,
            empty_label=self._empty_label,
        )
        shown.setObjectName("field-editor-value")
        # A value takes the room it needs and no more, so a number reads from the control's own
        # leading edge rather than from its far side: `FieldValue` right-aligns a number for the
        # table column it was built for, and a field editor is not one.
        shown.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Maximum, QtWidgets.QSizePolicy.Policy.Preferred
        )
        # A url value opens itself on a press; on an editable half the press belongs to the
        # editor instead, so the value is taken out of the mouse and the tab order.
        if self._editable:
            shown.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            shown.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        elif site:
            shown.set_site_url(site)
        self._value_widget = shown
        self._add(shown)
        self._row.addStretch(1)
        self.updateGeometry()
        self.update()

    # --- the box ----------------------------------------------------------------------------

    def on_hover_changed(self, value: bool) -> None:
        self._hover.set(1.0 if value and self._editable else 0.0)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._editable and event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._editable and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.activated.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if not self._editable:
            return
        theme = self.theme
        painter = painter_for(self)
        amount = self._hover.value
        radius = float(theme.radius_px("sm"))
        if amount > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(with_alpha(theme.accent, amount))
            painter.drawRoundedRect(self.rect(), radius, radius)
        if self.keyboard_focus:
            self.paint_focus_ring(painter, self.rect(), radius)
        painter.end()


class FieldEditor(QtWidgets.QWidget):
    """One field, displayed or edited, with the editor chosen by the data type.

    A field whose type has no editor stays on the display half whatever the mode says, and so
    does one the schema calls read-only.
    """

    #: A committed value, in the shape the API takes.
    value_changed = Signal(object)
    #: The half on show changed: `display` or `edit`.
    mode_changed = Signal(str)
    #: The editor's parse error appeared or cleared, or a write failed.
    error_changed = Signal(object)

    def __init__(
        self,
        value: Any = None,
        data_type: str | None = None,
        field: FieldSchema | None = None,
        mode: str = "display",
        editable: bool = False,
        editor_placement: str | None = "inline",
        statuses: dict | None = None,
        context: Any = None,
        entity: EntityRef | None = None,
        hours_per_day: float | None = None,
        frame_rate: float | None = None,
        precision: int | None = None,
        symbol: str = "$",
        project_id: int | None = None,
        time_zone: str | None = None,
        locale: str | None = None,
        multiline: bool | None = None,
        size: str = "md",
        disabled: bool = False,
        readonly: bool = False,
        invalid: bool = False,
        error: str | None = None,
        placeholder: str = "",
        empty_label: str = "empty",
        error_message: Callable[[str], QtWidgets.QWidget] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._data_type = data_type
        self._field = field
        self._mode = mode if mode in FIELD_EDITOR_MODES else "display"
        self._editable = bool(editable)
        self._placement = editor_placement
        self._statuses = statuses
        self._context = context
        self._entity = entity
        self._hours_per_day = hours_per_day
        self._frame_rate = frame_rate
        self._precision = precision
        self._symbol = symbol
        self._project_id = project_id
        self._time_zone = time_zone
        self._locale = locale
        self._multiline = multiline
        self._size = size if size in CONTROL_HEIGHT else "md"
        self._disabled = bool(disabled)
        self._readonly = bool(readonly)
        self._invalid = bool(invalid)
        self._error = error
        self._placeholder = placeholder
        self._error_message = error_message

        self._control: QtWidgets.QWidget | None = None
        self._popover: Popover | None = None
        self._popup: QtWidgets.QWidget | None = None
        self._original: Any = None
        self._live_error: str | None = None
        self._write_ticket = Ticket()
        self._writing = False

        self.setObjectName("field-editor")
        self.setProperty("data_type", self.data_type)
        self._column = QtWidgets.QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(POPOVER_GAP - 4)
        self._display = FieldDisplay(
            value=value,
            data_type=self.data_type,
            field=field,
            statuses=statuses,
            context=context,
            options=self._text_options(),
            empty_label=empty_label,
            size=self._size,
            editable=self._editable and self._can_edit(),
            parent=self,
        )
        self._display.activated.connect(lambda: self._enter(focus=True))
        self._column.addWidget(self._display)
        self._message = FieldError(None, error_message=self._error_message, parent=self)
        self._column.addWidget(self._message)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(0)
        self.setEnabled(not self._disabled)
        self._apply_error()
        # A caller can mount this already in edit mode, as a table cell does. The control is
        # not focused then: only entering the half from the display side moves the caret.
        if self._mode == "edit":
            self._open_editor(focus=False)

    # --- the parts ------------------------------------------------------------------------

    @property
    def display(self) -> FieldDisplay:
        """The display half, which is also the popover's anchor."""
        return self._display

    @property
    def control(self) -> QtWidgets.QWidget | None:
        """The editor on show, or None on the display half."""
        return self._control

    @property
    def popover(self) -> Popover | None:
        """The surface the editor opens in, under `editor_placement='popover'`."""
        return self._popover

    @property
    def kind(self) -> EditorKind:
        """The editor this field's data type opens."""
        return editor_for(self.data_type)

    @property
    def placement(self) -> str:
        """Where the editor opens: `inline` or `popover`."""
        if self._placement in ("inline", "popover"):
            return self._placement
        return editor_placement_for(self.data_type)

    @property
    def has_editor(self) -> bool:
        """True when the type's editor can be drawn at all."""
        return _can_draw(self.kind, self.data_type, self._context, self._field)

    # --- props ----------------------------------------------------------------------------

    @property
    def value(self) -> Any:
        """The raw attribute value, exactly as the API returned it."""
        return self._value

    def set_value(self, value: Any) -> None:
        self._value = value
        self._display.set_value(value)
        setter = getattr(self._control, "set_value", None)
        if callable(setter):
            setter(value)

    @property
    def data_type(self) -> str:
        """The field's `data_type`. Falls back to the schema's, then to text."""
        if self._data_type:
            return str(self._data_type)
        if self._field is not None and self._field.data_type:
            return self._field.data_type
        return "text"

    def set_data_type(self, value: str | None) -> None:
        self._data_type = value
        self.setProperty("data_type", self.data_type)
        self._display.set_data_type(self.data_type)
        self._remount()

    @property
    def field(self) -> FieldSchema | None:
        """The field schema. It names the type, the label and whether the field is writable."""
        return self._field

    def set_field(self, value: FieldSchema | None) -> None:
        self._field = value
        self._display.set_field(value)
        self.setProperty("data_type", self.data_type)
        self._remount()

    @property
    def mode(self) -> str:
        """Which half is showing."""
        return self._mode

    def set_mode(self, value: str) -> None:
        wanted = value if value in FIELD_EDITOR_MODES else "display"
        if wanted == self._mode:
            return
        if wanted == "edit":
            # A caller setting the mode does not move the caret: only entering the half from
            # the display side does, so a page opening every field at once keeps them all open.
            self._enter(focus=False)
        else:
            self._close(restore=False)

    @property
    def editable(self) -> bool:
        """The display half turns into the edit half on a press or on Enter."""
        return self._editable

    def set_editable(self, value: bool) -> None:
        self._editable = bool(value)
        self._display.set_editable(self._editable and self._can_edit())

    @property
    def editor_placement(self) -> str:
        """Where the editor opens: in place, or in a popover anchored to the value."""
        return self.placement

    def set_editor_placement(self, value: str | None) -> None:
        self._placement = value
        self._remount()

    @property
    def statuses(self) -> dict | None:
        """`Status` rows by code, for the display half (probe 010)."""
        return self._statuses

    def set_statuses(self, value: dict | None) -> None:
        self._statuses = value
        self._display.set_statuses(value)

    @property
    def context(self) -> Any:
        """The widget context: the site preferences, and what the pickers read through."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        self._display.set_context(value)
        self._display.set_options(self._text_options())
        self._remount()

    @property
    def entity(self) -> EntityRef | None:
        """The row the commit is written to. Without one the editor only emits."""
        return self._entity

    def set_entity(self, value: EntityRef | None) -> None:
        self._entity = value

    @property
    def hours_per_day(self) -> float | None:
        """The site's `hours_per_day` (field_types/duration). Defaults to the context's."""
        return self._hours_per_day

    def set_hours_per_day(self, value: float | None) -> None:
        self._hours_per_day = value
        self._display.set_options(self._text_options())

    @property
    def frame_rate(self) -> float | None:
        """Frames a second, for the `HH:MM:SS:FF` form (field_types/timecode)."""
        return self._frame_rate

    def set_frame_rate(self, value: float | None) -> None:
        self._frame_rate = value
        self._display.set_options(self._text_options())

    @property
    def precision(self) -> int | None:
        """Decimals on a float."""
        return self._precision

    def set_precision(self, value: int | None) -> None:
        self._precision = value
        self._display.set_options(self._text_options())

    @property
    def symbol(self) -> str:
        """Shown before the value on a currency field."""
        return self._symbol

    def set_symbol(self, value: str) -> None:
        self._symbol = value
        self._display.set_options(self._text_options())

    @property
    def project_id(self) -> int | None:
        """The project the schema was read with. It subtracts a list field's hidden values."""
        return self._project_id

    def set_project_id(self, value: int | None) -> None:
        self._project_id = value
        self._remount()

    @property
    def time_zone(self) -> str | None:
        """IANA zone a typed wall-clock time is read in."""
        return self._time_zone

    def set_time_zone(self, value: str | None) -> None:
        self._time_zone = value
        self._display.set_options(self._text_options())

    @property
    def locale(self) -> str | None:
        return self._locale

    def set_locale(self, value: str | None) -> None:
        self._locale = value
        self._display.set_options(self._text_options())

    @property
    def multiline(self) -> bool:
        """A textarea instead of an input, on a text field. True in a popover by default."""
        if self._multiline is None:
            return self.placement == "popover"
        return bool(self._multiline)

    def set_multiline(self, value: bool | None) -> None:
        self._multiline = value
        self._remount()

    @property
    def size(self) -> str:
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in CONTROL_HEIGHT else "md"
        setter = getattr(self._control, "set_size", None)
        if callable(setter):
            setter(self._size)

    @property
    def disabled(self) -> bool:
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self.setEnabled(not self._disabled)
        self._display.set_editable(self._editable and self._can_edit())

    @property
    def readonly(self) -> bool:
        """Full contrast, and no affordances. A field the schema calls read-only is one."""
        return self._readonly or (self._field is not None and not self._field.editable)

    def set_readonly(self, value: bool) -> None:
        self._readonly = bool(value)
        self._display.set_editable(self._editable and self._can_edit())

    @property
    def invalid(self) -> bool:
        return self._invalid

    def set_invalid(self, value: bool) -> None:
        self._invalid = bool(value)
        setter = getattr(self._control, "set_invalid", None)
        if callable(setter):
            setter(self._invalid)

    @property
    def error(self) -> str | None:
        """A message from the caller, shown in place of the parse error."""
        return self._error

    def set_error(self, value: str | None) -> None:
        self._error = value
        self._apply_error()

    @property
    def placeholder(self) -> str:
        return self._placeholder

    def set_placeholder(self, value: str) -> None:
        self._placeholder = value
        setter = getattr(self._control, "set_placeholder", None)
        if callable(setter):
            setter(value)

    @property
    def empty_label(self) -> str:
        """What the display half shows for an unset value."""
        return self._display._empty_label

    def set_empty_label(self, value: str) -> None:
        self._display.set_empty_label(value)

    def set_error_message(self, value: Callable[[str], QtWidgets.QWidget] | None) -> None:
        """Draw the message some other way than the line under the control."""
        self._error_message = value
        setter = getattr(self._control, "set_error_message", None)
        if callable(setter):
            setter(value)

    # --- the two halves ---------------------------------------------------------------------

    def _can_edit(self) -> bool:
        return self.has_editor and not self._disabled and not self.readonly

    def _text_options(self) -> FieldTextOptions:
        prefs = preferences_of(self._context if self._context is not None else None)
        return FieldTextOptions(
            hours_per_day=self._hours_per_day if self._hours_per_day is not None else prefs.hours_per_day,
            locale=self._locale if self._locale is not None else prefs.locale,
            time_zone=self._time_zone if self._time_zone is not None else prefs.time_zone,
            frame_rate=self._frame_rate if self._frame_rate is not None else prefs.frame_rate,
            decimals=self._precision,
            currency_symbol=self._symbol,
            display_values=self._field.display_values if self._field is not None else None,
        )

    def _enter(self, focus: bool = True) -> None:
        if not self._can_edit() or self._mode == "edit":
            return
        self._original = self._value
        self._mode = "edit"
        self._open_editor(focus=focus)
        self.mode_changed.emit("edit")

    def _close(self, restore: bool) -> None:
        if self._mode == "display":
            return
        # Focus comes off the control before the control goes, so the session's own blur
        # handler commits what it holds while the editor is still on the page.
        focused = QtWidgets.QApplication.focusWidget()
        if focused is not None and self._owns(focused) and focused is not self._display:
            focused.clearFocus()
        if restore:
            # A cancel undoes what the control emitted, so a caller holding a draft has the
            # value the session opened on.
            self.set_value(self._original)
            self.value_changed.emit(self._original)
        self._mode = "display"
        self._live_error = None
        self._tear_down()
        self._display.setVisible(True)
        self._display.setFocus(Qt.FocusReason.OtherFocusReason)
        self.mode_changed.emit("display")

    def _remount(self) -> None:
        self._display.set_editable(self._editable and self._can_edit())
        if self._mode == "edit":
            self._tear_down()
            self._open_editor()

    # --- the editor -------------------------------------------------------------------------

    def _open_editor(self, focus: bool = True) -> None:
        control = self._build_control()
        if control is None:
            self._mode = "display"
            return
        self._control = control
        if self.placement == "popover":
            self._open_popover(control, focus=focus)
        else:
            self._display.setVisible(False)
            self._column.insertWidget(0, control)
            control.show()
            if focus:
                self._focus_control(control)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            app.focusChanged.connect(self._on_focus_changed)

    def _tear_down(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
            try:
                app.focusChanged.disconnect(self._on_focus_changed)
            except (TypeError, RuntimeError):
                pass
        if self._popover is not None:
            self._popover.close()
            self._popover.deleteLater()
            self._popover = None
            self._popup = None
        if self._control is not None:
            self._column.removeWidget(self._control)
            self._control.setParent(None)
            self._control.deleteLater()
            self._control = None

    def _open_popover(self, control: QtWidgets.QWidget, focus: bool = True) -> None:
        popup = QtWidgets.QWidget()
        popup.setObjectName("field-editor-popover")
        column = QtWidgets.QVBoxLayout(popup)
        column.setContentsMargins(POPOVER_PAD, POPOVER_PAD, POPOVER_PAD, POPOVER_PAD)
        column.setSpacing(POPOVER_GAP)
        label = self._label()
        if label:
            line = _TextLine(label, muted=True, size=LABEL_TEXT, parent=popup)
            line.setObjectName("field-editor-label")
            column.addWidget(line)
        control.setParent(popup)
        column.addWidget(control)
        buttons = QtWidgets.QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)
        step = POPOVER_BUTTON.get(self._size, "default")
        cancel = Button("Cancel", variant="ghost", size=step, parent=popup)
        cancel.setObjectName("field-editor-cancel")
        cancel.clicked.connect(lambda: self._close(restore=True))
        save = Button("Save", variant="default", size=step, parent=popup)
        save.setObjectName("field-editor-save")
        save.clicked.connect(lambda: self._close(restore=False))
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        column.addLayout(buttons)
        width = POPOVER_WIDTH_WIDE if self.kind == "multi_entity" else POPOVER_WIDTH
        self._popup = popup
        # A popover holding fields of its own takes the caret, which `popover.py` gates on
        # this flag; without it the window refuses focus and the control never gets it.
        self._popover = Popover(
            self._display, popup, side="bottom", align="start", width=width, takes_focus=True
        )
        self._popover.dismissed.connect(lambda: self._close(restore=False))
        self._popover.open()
        if focus:
            self._focus_control(control)

    def _label(self) -> str:
        if self._field is None:
            return ""
        return self._field.display_name or self._field.name or ""

    def _focus_control(self, control: QtWidgets.QWidget) -> None:
        for kind in (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit):
            found = control.findChild(kind)
            if found is not None and found.isVisibleTo(control):
                found.setFocus(Qt.FocusReason.OtherFocusReason)
                return
        control.setFocus(Qt.FocusReason.OtherFocusReason)

    def _build_control(self) -> QtWidgets.QWidget | None:  # noqa: C901
        """The editor the data type opens. The map is core's `editor_kind_for`."""
        if not self.has_editor:
            return None
        kind = self.kind
        shared: dict[str, Any] = {
            "field": self._field,
            "size": self._size,
            "disabled": self._disabled,
            "readonly": self.readonly,
            "invalid": self._invalid,
            "error": self._error,
            "error_message": self._error_message,
        }
        value = self._value
        made: QtWidgets.QWidget | None = None
        if kind == "text":
            made = TextEditor(
                value=value if isinstance(value, str) else None,
                multiline=self.multiline,
                placeholder=self._placeholder,
                **shared,
            )
        elif kind == "number":
            made = NumberEditor(
                value=value,
                data_type=self.data_type,
                precision=self._precision,
                hours_per_day=self._text_options().hours_per_day,
                frame_rate=self._text_options().frame_rate,
                symbol=self._symbol,
                placeholder=self._placeholder,
                **shared,
            )
        elif kind == "checkbox":
            made = CheckboxEditor(value=value is True, placeholder=self._placeholder, **shared)
        elif kind == "date":
            made = DateEditor(value=value if isinstance(value, str) else None, **shared)
        elif kind == "date_time":
            made = DateTimeEditor(
                value=value if isinstance(value, str) else None,
                time_zone=self._text_options().time_zone,
                **shared,
            )
        elif kind == "url":
            made = UrlEditor(value=value if isinstance(value, dict) else None, **shared)
        elif kind == "color":
            made = ColorEditor(value=value if isinstance(value, str) else None, **shared)
        elif kind == "list" and ListPicker is not None:
            # Upstream hands the list picker the same `shared` every other editor gets,
            # so the caller's message and its renderer reach this one too.
            made = ListPicker(
                value=value if isinstance(value, str) else None,
                project_id=self._project_id,
                **shared,
            )
        elif kind == "status_list" and StatusPicker is not None:
            made = StatusPicker(
                context=self._context,
                entity_type=(self._field.entity_type if self._field is not None else ""),
                field=(self._field.name if self._field is not None else None),
                project_id=self._project_id,
                value=value if isinstance(value, str) else None,
                size=self._size,
                disabled=self._disabled,
                readonly=self.readonly,
                invalid=self._invalid,
            )
        elif kind == "entity":
            made = EntityPicker(
                context=self._context,
                entity_types=self._link_types(),
                project_id=self._project_id,
                value=_as_ref(value),
                size=self._size,
                disabled=self._disabled,
                readonly=self.readonly,
                invalid=self._invalid,
            )
        elif kind == "multi_entity":
            made = EntityMultiPicker(
                context=self._context,
                entity_types=self._link_types(),
                project_id=self._project_id,
                value=[ref for ref in (_as_ref(one) for one in (value or [])) if ref is not None],
                size=self._size,
                disabled=self._disabled,
                readonly=self.readonly,
                invalid=self._invalid,
            )
        if made is None:
            return None
        made.setObjectName(f"field-editor-{kind}")
        self._wire(made, kind)
        return made

    def _link_types(self) -> list[str]:
        """Types a link field may point at. A picker has nothing to search without them."""
        return list(self._field.valid_types or []) if self._field is not None else []

    def _wire(self, control: QtWidgets.QWidget, kind: str) -> None:
        """Hang the commit and the parse error off whichever signals the editor carries."""
        committed = getattr(control, "committed", None)
        if committed is not None:
            committed.connect(self._commit)
        changed = getattr(control, "value_changed", None)
        if changed is not None and committed is None:
            if kind in ("entity", "multi_entity"):
                changed.connect(lambda value, _row=None: self._commit(_as_write(value)))
            else:
                changed.connect(self._commit)
        errors = getattr(control, "error_changed", None)
        if errors is not None:
            errors.connect(self._note_error)

    # --- committing -------------------------------------------------------------------------

    def _note_error(self, message: object) -> None:
        # An edit session stays open while a parse error stands, because invalid input emits
        # nothing and would otherwise be dropped.
        self._live_error = str(message) if message else None
        self.error_changed.emit(self._live_error)

    def _commit(self, value: Any) -> None:
        self._value = value
        self._display.set_value(value)
        if self._entity is not None and self._context is not None and self._field is not None:
            self._write(value)
            return
        self.value_changed.emit(value)

    def _write(self, value: Any) -> None:
        """Write through the context's client, off the GUI thread, and read the row back."""
        client = getattr(self._context, "client", None)
        ref, name = self._entity, self._field.name if self._field is not None else ""
        if client is None or ref is None or not name:
            self.value_changed.emit(value)
            return
        self._writing = True
        number = self._write_ticket.next()

        def run() -> Any:
            client.update(ref.type, ref.id, {name: value})
            # The write answers the whole record but never resolves a dotted path, so the row
            # is read again on the field that was written (024_read_after_write).
            answer = client.search(
                ref.type,
                SearchOptions(
                    filters={"logical_operator": "and", "conditions": [["id", "is", ref.id]]},
                    fields=[name],
                    page={"size": 1, "number": 1},
                ),
            )
            rows = answer.data
            return rows[0].values.get(name) if rows else value

        default_pool().submit(
            run,
            on_result=self._written,
            on_error=self._write_failed,
            ticket=(self._write_ticket, number),
        )

    def _written(self, value: Any) -> None:
        self._writing = False
        self._value = value
        self._display.set_value(value)
        self._apply_error()
        self.value_changed.emit(value)

    def _write_failed(self, error: object) -> None:
        self._writing = False
        self._error = str(error)
        self._apply_error()
        self.error_changed.emit(self._error)

    def _apply_error(self) -> None:
        message = self._error
        self._message.set_error_message(self._error_message)
        self._message.set_message(message)
        setter = getattr(self._control, "set_error", None)
        if callable(setter):
            setter(message)

    @property
    def writing(self) -> bool:
        """True while a write is in flight."""
        return self._writing

    # --- the keys and the press that leave the edit half ----------------------------------------

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # noqa: N802
        if self._mode == "edit" and self._handle_edit_key(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def _handle_edit_key(self, event: QtGui.QKeyEvent) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._close(restore=True)
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            modifiers = event.modifiers()
            fast = bool(
                modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
            )
            # A textarea keeps Enter for a new line and commits on Cmd or Ctrl with it.
            commits = not (self.kind == "text" and self.multiline) or fast
            if commits and self._live_error is None:
                # The editor commits on the same Enter and its own handler runs after this
                # one, so the toggle waits a turn of the loop before the control goes.
                QtCore.QTimer.singleShot(0, self._close_unless_invalid)
        return False

    def _close_unless_invalid(self) -> None:
        """Close the session a turn after Enter, unless the parse refused what was typed.

        This filter sees the key before the control does, so the parse error the same Enter
        raises is only there a turn later. Invalid input never emits and the edit half stays,
        which is `field-editor-invalid-float.js`.
        """
        if self._live_error is None:
            self._close(restore=False)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if self._mode != "edit":
            return super().eventFilter(obj, event)
        kind = event.type()
        if kind == QtCore.QEvent.Type.KeyPress and self._owns(obj):
            if self._handle_edit_key(event):
                return True
        elif kind == QtCore.QEvent.Type.MouseButtonPress:
            widget = obj if isinstance(obj, QtWidgets.QWidget) else None
            if widget is not None and not self._owns(widget):
                # A press outside the session commits and closes it.
                self._close(restore=False)
        return super().eventFilter(obj, event)

    def _owns(self, obj: QtCore.QObject) -> bool:
        """True while the object is part of the open session.

        A popover and a picker list are top-level windows of their own, so containment in
        this widget alone is not enough.
        """
        widget = obj if isinstance(obj, QtWidgets.QWidget) else None
        if widget is None:
            return False
        walk: QtWidgets.QWidget | None = widget
        while walk is not None:
            if walk is self or walk is self._popup:
                return True
            if isinstance(walk, Popover):
                return True
            walk = walk.parentWidget()
        window = widget.window()
        return isinstance(window, Popover) or window is self._popup

    def _on_focus_changed(self, old: Any, new: Any) -> None:
        # Only the session the caret left closes: several editors may stand open at once, and
        # the one being mounted beside them never takes the others down with it.
        if self._mode != "edit" or new is None or old is None:
            return
        if self._owns(old) and not self._owns(new):
            # Tab out of the editor commits and returns to the display half.
            self._close(restore=False)


def _as_ref(value: Any) -> EntityRef | None:
    """A `{type, id, name}` hash as the reference a picker takes."""
    if isinstance(value, EntityRef):
        return value
    if isinstance(value, dict) and value.get("type") and value.get("id") is not None:
        return EntityRef(type=str(value["type"]), id=int(value["id"]), name=value.get("name"))
    return None


def _as_write(value: Any) -> Any:
    """What a link picker's value is on the wire: one hash, or a list of them."""
    if isinstance(value, EntityRef):
        return {"type": value.type, "id": value.id, "name": value.name}
    if isinstance(value, (list, tuple)):
        return [_as_write(one) for one in value]
    return value
