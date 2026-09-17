"""The launcher for the filter editor.

Ported from `packages/react/src/registry/sg/components/filter-dialog.tsx` and its Svelte twin.
Empty, it is one Add filters button. With filters applied it is an Edit filters button carrying
the count, plus a control that clears them without opening anything. Edits inside the dialog are
staged: only Apply emits, Cancel drops them, and Clear all emits an empty filter.

    launcher = FilterDialog(entity_type="Version", context=context, value=tree)
    launcher.changed.connect(apply)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from qtpy import QtWidgets
from qtpy.QtCore import Signal

from sg_widgets_core.filter import FilterGroup, empty_filter, is_empty_filter
from sg_widgets_core.filter_ux import count_active_conditions

from ..primitives.button import Button
from ..primitives.dialog import Dialog
from .filter_editor import CONTROL_BUTTON, FILTER_EDITOR_SIZE_VALUES, FilterEditor

__all__ = ["COUNT_CHIP_SIZE", "DIALOG_WIDTH", "VIEWPORT_SHARE", "FilterDialog"]

#: The count beside the label is a chip, so it takes the step under the control.
COUNT_CHIP_SIZE: dict[str, str] = {"sm": "xs", "md": "sm", "lg": "md"}

#: The icon-button step beside a control of each height.
ICON_BUTTON: dict[str, str] = {"sm": "icon-sm", "md": "icon", "lg": "icon-lg"}

#: `w-[min(96vw,64rem)]`: a condition row wants room, so the dialog takes 1024 where it fits
#: and the window's own 96% where it does not.
DIALOG_WIDTH = 1024
VIEWPORT_SHARE = 0.96

#: The narrowest the dialog is ever asked for, whatever the window it opens over.
DIALOG_FLOOR = 320

#: Between the launcher and the control that clears the filters beside it.
LAUNCH_GAP = 8


class FilterDialog(QtWidgets.QWidget):
    """The filter editor behind a button that says how many conditions are applied."""

    #: The applied tree. Only Apply, Clear all and the clear control emit.
    changed = Signal(object)
    #: The same payload under the name the query widgets share.
    filters_changed = Signal(object)
    #: The dialog opened or closed.
    open_changed = Signal(bool)

    def __init__(
        self,
        entity_type: str = "",
        context: Any = None,
        value: FilterGroup | None = None,
        hide_paths: Sequence[str] | None = None,
        label: str | None = None,
        title: str = "Filters",
        disabled: bool = False,
        open: bool = False,  # noqa: A002
        size: str = "md",
        field_chooser: Callable[..., QtWidgets.QWidget] | None = None,
        value_editor: Callable[..., QtWidgets.QWidget] | None = None,
        entity_editor: Callable[..., QtWidgets.QWidget] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filter-dialog")
        self._entity_type = str(entity_type or "")
        self._context = context
        self._value = value if value is not None else empty_filter()
        self._hide_paths = list(hide_paths or [])
        self._label = label
        self._title = title
        self._disabled = bool(disabled)
        self._size = size if size in FILTER_EDITOR_SIZE_VALUES else "md"
        self._open = False
        self._dialog: Dialog | None = None
        self._editor: FilterEditor | None = None
        self._field_chooser = field_chooser
        self._value_editor = value_editor
        self._entity_editor = entity_editor

        line = QtWidgets.QHBoxLayout(self)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        self._line = line

        # The count is part of the trigger, a chip inside its own border a glyph gap from the
        # label, and the control that clears the filters a full step further out.
        self._launch = Button("", icon="list-filter", variant="outline", parent=self)
        self._launch.setObjectName("filter-launch")
        self._launch.clicked.connect(lambda: self.set_open(True))
        line.addWidget(self._launch)
        line.addSpacing(LAUNCH_GAP)

        self._clear = Button("", icon="trash-2", variant="ghost", parent=self)
        self._clear.setObjectName("filter-clear")
        self._clear.setAccessibleName("Clear filters")
        self._clear.setToolTip("Clear filters")
        self._clear.clicked.connect(lambda: self._emit(empty_filter()))
        line.addWidget(self._clear)
        line.addStretch(1)

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        self._refresh()
        if open:
            self.set_open(True)

    # --- props ----------------------------------------------------------------------------

    @property
    def entity_type(self) -> str:
        """Type the rows of the editor match on."""
        return self._entity_type

    def set_entity_type(self, value: str) -> None:
        self._entity_type = str(value or "")
        if self._editor is not None:
            self._editor.set_entity_type(self._entity_type)
        self._refresh()

    @property
    def context(self) -> Any:
        """The widget context. Every read goes through it."""
        return self._context

    def set_context(self, value: Any) -> None:
        self._context = value
        if self._editor is not None:
            self._editor.set_context(value)

    @property
    def value(self) -> FilterGroup:
        """The applied tree."""
        return self._value

    def set_value(self, value: FilterGroup | None) -> None:
        """Take a tree from outside. Nothing is emitted."""
        self._value = value if value is not None else empty_filter()
        self._refresh()

    @property
    def hide_paths(self) -> list[str]:
        """Paths kept out of the field list."""
        return list(self._hide_paths)

    def set_hide_paths(self, value: Sequence[str] | None) -> None:
        self._hide_paths = list(value or [])
        if self._editor is not None:
            self._editor.set_hide_paths(self._hide_paths)

    @property
    def label(self) -> str | None:
        """Replaces both button labels. Otherwise Add filters, then Edit filters."""
        return self._label

    def set_label(self, value: str | None) -> None:
        self._label = value
        self._refresh()

    @property
    def title(self) -> str:
        """The dialog's heading."""
        return self._title

    def set_title(self, value: str) -> None:
        self._title = str(value)
        if self._dialog is not None:
            self._dialog.set_title(self._title)

    @property
    def disabled(self) -> bool:
        """Blocks the launcher and the clear control."""
        return self._disabled

    def set_disabled(self, value: bool) -> None:
        self._disabled = bool(value)
        self._refresh()

    @property
    def size(self) -> str:
        """The control ladder the launcher and the editor stand on."""
        return self._size

    def set_size(self, value: str) -> None:
        self._size = value if value in FILTER_EDITOR_SIZE_VALUES else "md"
        if self._editor is not None:
            self._editor.set_size(self._size)
        self._refresh()

    @property
    def open(self) -> bool:
        """Whether the dialog is showing."""
        return self._open

    def set_open(self, value: bool) -> None:
        """Show or hide the dialog. Opening stages the applied tree afresh."""
        want = bool(value) and not self._disabled
        if want == self._open:
            return
        self._open = want
        if want:
            self._show_dialog()
        elif self._dialog is not None:
            self._dialog.close()
        self.open_changed.emit(want)

    @property
    def field_chooser(self) -> Callable[..., QtWidgets.QWidget] | None:
        """A caller's own field control, handed to the editor."""
        return self._field_chooser

    def set_field_chooser(self, value: Callable[..., QtWidgets.QWidget] | None) -> None:
        self._field_chooser = value

    @property
    def value_editor(self) -> Callable[..., QtWidgets.QWidget] | None:
        """A caller's own value control, handed to the editor."""
        return self._value_editor

    def set_value_editor(self, value: Callable[..., QtWidgets.QWidget] | None) -> None:
        self._value_editor = value

    @property
    def entity_editor(self) -> Callable[..., QtWidgets.QWidget] | None:
        """A caller's own entity control, handed to the editor."""
        return self._entity_editor

    def set_entity_editor(self, value: Callable[..., QtWidgets.QWidget] | None) -> None:
        self._entity_editor = value

    # --- the parts ------------------------------------------------------------------------

    @property
    def active(self) -> int:
        """How many conditions of the applied tree would reach the API."""
        return count_active_conditions(self._value)

    def launcher(self) -> Button:
        """The button that opens the dialog."""
        return self._launch

    def dialog(self) -> Dialog | None:
        """The dialog, once it has been opened at least once."""
        return self._dialog

    def editor(self) -> FilterEditor | None:
        """The editor inside the dialog, once it has been opened at least once."""
        return self._editor

    def dialog_width(self) -> int:
        """What the panel asks for: 64rem, or the window's own 96% where that is narrower."""
        window = self.window()
        room = window.width() if window is not None else DIALOG_WIDTH
        return max(DIALOG_FLOOR, min(DIALOG_WIDTH, int(room * VIEWPORT_SHARE)))

    # --- the staging ----------------------------------------------------------------------

    def apply(self) -> None:
        """Emit the staged tree and close. A tree of blank rows applies as no filter at all."""
        draft = self._editor.value if self._editor is not None else empty_filter()
        self._emit(empty_filter() if is_empty_filter(draft) else draft)
        self.set_open(False)

    def cancel(self) -> None:
        """Close and drop the staged edits."""
        self.set_open(False)

    def clear_all(self) -> None:
        """Emit an empty filter and close."""
        self._emit(empty_filter())
        self.set_open(False)

    def _emit(self, value: FilterGroup) -> None:
        self._value = value
        self._refresh()
        self.changed.emit(value)
        self.filters_changed.emit(value)

    def _show_dialog(self) -> None:
        if self._dialog is None:
            self._build_dialog()
        if self._editor is not None:
            # The draft starts from the applied value every time, so a cancelled edit
            # leaves nothing behind.
            self._editor.set_value(self._value)
        dialog = self._dialog
        if dialog is not None:
            # `w-[min(96vw,64rem)]` is read at the moment it opens, so a window resized
            # between two openings gets the width it has now.
            dialog.setMinimumWidth(self.dialog_width())
            dialog.set_description(
                f"Rows match on {self._entity_type}. Nothing applies until you press Apply."
            )
            dialog.open()

    def _build_dialog(self) -> None:
        dialog = Dialog(self, title=self._title)
        dialog.setObjectName("filter-dialog-panel")
        self._editor = FilterEditor(
            entity_type=self._entity_type,
            context=self._context,
            value=self._value,
            hide_paths=self._hide_paths,
            size=self._size,
            field_chooser=self._field_chooser,
            value_editor=self._value_editor,
            entity_editor=self._entity_editor,
        )
        dialog.set_content(self._editor)

        footer = dialog.footer
        clear = Button("Clear all", variant="ghost", parent=footer)
        clear.setObjectName("filter-clear-all")
        clear.clicked.connect(self.clear_all)
        layout = footer.layout()
        if layout is not None:
            layout.insertWidget(0, clear)

        cancel = Button("Cancel", variant="outline", parent=footer)
        cancel.setObjectName("filter-cancel")
        cancel.clicked.connect(self.cancel)
        footer.add_button(cancel)

        apply_button = Button("Apply", variant="default", parent=footer)
        apply_button.setObjectName("filter-apply")
        apply_button.clicked.connect(self.apply)
        footer.add_button(apply_button)

        dialog.dismissed.connect(self._on_dismissed)
        self._dialog = dialog

    def _on_dismissed(self) -> None:
        if self._open:
            self._open = False
            self.open_changed.emit(False)

    # --- the launcher ---------------------------------------------------------------------

    def _refresh(self) -> None:
        active = self.active
        step = CONTROL_BUTTON[self._size]
        self._launch.set_size(step)
        self._launch.set_icon("pencil" if active else "list-filter")
        self._launch.set_text(self._label or ("Edit filters" if active else "Add filters"))
        self._launch.setEnabled(not self._disabled)
        self._launch.set_count_size(COUNT_CHIP_SIZE[self._size])
        self._launch.set_count(str(active) if active else "")
        self._clear.set_size(ICON_BUTTON[self._size])
        self._clear.setVisible(active > 0)
        self._clear.setEnabled(not self._disabled)
