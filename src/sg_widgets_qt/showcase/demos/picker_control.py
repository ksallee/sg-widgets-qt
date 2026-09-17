"""Every shape a picker comes in, over one static list of departments.

The port of `apps/site/src/demos/picker-control/Demo.tsx`: single and several, inline and
summary, a measured row that ends in `+n`, a fixed set with no search row, the three heights,
disabled, read-only and invalid, and a row and a chip of the caller's own. The chip here is a
plain text chip; a picker that draws an entity chip or a status badge passes that instead.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QAbstractListModel, QModelIndex, Qt

from sg_widgets_core.pickers import matches_tokens
from sg_widgets_core.search import match_runs

from ...primitives.badge import Chip
from ...primitives.roles import Roles
from ...primitives.row_delegate import RowDelegate
from ...widgets.picker_control import PICKER_CHIP, PickerControl
from .. import chrome
from ..context import DemoContext

__all__ = ["build"]

#: The rows every control offers. A wrapper's own vocabulary is all it adds.
DEPARTMENTS = (
    ("layout", "Layout", "Anna van der Meer"),
    ("anim", "Animation", "Piet Oosterhuis"),
    ("light", "Lighting", "Mira Halloran"),
    ("comp", "Compositing", "Tomas Bergqvist"),
    ("fx", "Effects", "Iris Nakamura"),
    ("mm", "Matchmove", "Ravi Chandrasekar"),
    ("rig", "Rigging", "Elena Duarte"),
    ("edit", "Editorial", "Jonas Klein"),
)

LABELS = {code: label for code, label, _lead in DEPARTMENTS}
LEADS = {code: lead for code, _label, lead in DEPARTMENTS}

SIZES = ("sm", "md", "lg")

#: At most 320, so the measured row has something to cut against.
NARROW = 320


def matching(query: str) -> list:
    return [code for code, label, _lead in DEPARTMENTS if matches_tokens(query, label, code)]


class _Model(QAbstractListModel):
    """The department rows, with the matched runs of the current query in bold."""

    def __init__(self, parent: QtCore.QObject | None = None, leads: bool = False) -> None:
        super().__init__(parent)
        self._codes = [code for code, _label, _lead in DEPARTMENTS]
        self._query = ""
        self._leads = leads
        self._checked: set = set()

    def set_codes(self, codes: list) -> None:
        self.beginResetModel()
        self._codes = list(codes)
        self.endResetModel()

    def set_checked(self, codes) -> None:
        self._checked = set(codes)
        self._redraw()

    def set_query(self, query: str) -> None:
        self._query = query
        self._redraw()

    def _redraw(self) -> None:
        if self._codes:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._codes) - 1, 0))

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._codes)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        code = self._codes[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
            return LABELS[code]
        if role == Roles.RUNS:
            return [(run.text, run.match, False) for run in match_runs(LABELS[code], self._query)]
        if role == Roles.SUB_LABEL:
            return LEADS[code] if self._leads else ""
        if role == Roles.SECONDARY:
            return code if self._leads else ""
        if role == Roles.CHECKED:
            return code in self._checked
        if role == Roles.ENTITY:
            return code
        return None


class DepartmentPicker(QtWidgets.QWidget):
    """A picker over the fixed vocabulary: the control, plus the value and the rows it feeds it."""

    def __init__(
        self,
        value: list | None = None,
        leads: bool = False,
        parent: QtWidgets.QWidget | None = None,
        **props: Any,
    ) -> None:
        super().__init__(parent)
        self._keys = list(value or [])
        self._model = _Model(self, leads=leads)
        delegate = RowDelegate(
            None,
            size=props.get("size", "md"),
            thumbnail=False,
            indicator="checkbox" if props.get("multiple") else "tick",
        )
        self._control = PickerControl(
            slot="department-picker",
            picker="department",
            row_model=self._model,
            row_delegate=delegate,
            trigger_label="Show the departments",
            parent=self,
            **props,
        )
        delegate.setParent(self._control.list_surface())
        self._control.set_chip_factory(self._chip_for)
        self._control.selected.connect(self._chosen)
        self._control.query_changed.connect(self._typed)
        self._control.remove_requested.connect(self._remove_at)
        self._control.cleared.connect(lambda: self._chosen([]))
        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._control)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        self._typed("")
        self._push()

    @property
    def control(self) -> PickerControl:
        return self._control

    @property
    def value(self) -> list:
        return list(self._keys)

    def set_size(self, size: str) -> None:
        self._control.set_size(size)

    def _chip_for(self, index: int) -> QtWidgets.QWidget | None:
        if not 0 <= index < len(self._keys):
            return None
        if self._control.text_value:
            # A value that reads as plain text, the way a select does.
            return chrome.TextLine(
                LABELS[self._keys[index]], size=14, token="foreground", parent=self._control
            )
        return Chip(
            LABELS[self._keys[index]],
            size=PICKER_CHIP[self._control.size],
            removable=self._control.multiple and not self._control.readonly,
            parent=self._control,
        )

    def _typed(self, query: str) -> None:
        codes = matching(query)
        self._model.set_codes(codes)
        self._model.set_query(query)
        self._control.set_items(codes)
        self._control.set_empty(len(codes) == 0)

    def _chosen(self, keys: list) -> None:
        self._keys = list(keys)
        self._push()

    def _remove_at(self, index: int) -> None:
        if 0 <= index < len(self._keys):
            self._keys.pop(index)
            self._push()

    def _push(self) -> None:
        self._model.set_checked(self._keys)
        self._control.set_keys(self._keys)
        self._control.set_labels([LABELS[key] for key in self._keys])


class PickerControlDemo(QtWidgets.QWidget):
    """Every shape, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("picker-control-demo")
        self._context = context
        #: Nothing here reads a site, so the demo is ready as soon as it is built.
        self.demo_ready = True
        self._pickers: list = []

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(16)

        self._case(
            column,
            "inline",
            "Single, inline: the caret sits beside the chip",
            DepartmentPicker(placeholder="Select a department"),
        )
        self._case(
            column,
            "text",
            "Single, summary: the value reads as plain text, the way a select does",
            DepartmentPicker(
                value=["comp"],
                anchored=True,
                inline=False,
                text_value=True,
                placeholder="Select a department",
                search_placeholder="Search departments…",
            ),
        )
        self._case(
            column,
            "tokens",
            "Several, inline: a token field, chips and query on one line",
            DepartmentPicker(
                value=["fx", "mm"],
                multiple=True,
                chip_row=True,
                placeholder="Select departments",
            ),
        )
        self._case(
            column,
            "summary",
            "Several, summary: the search box moves into the popup",
            DepartmentPicker(
                value=["anim", "light"],
                multiple=True,
                chip_row=True,
                inline=False,
                placeholder="Select departments",
                search_placeholder="Search departments…",
            ),
        )
        crowd = DepartmentPicker(
            value=[code for code, _label, _lead in DEPARTMENTS],
            multiple=True,
            chip_row=True,
            inline=False,
            summary="ellipsis",
            placeholder="Select departments",
            search_placeholder="Search departments…",
        )
        crowd.setMaximumWidth(NARROW)
        self._case(column, "overflow", "Eight selected in 320: whole chips, then a +n pill", crowd)
        self._case(
            column,
            "fixed",
            "A fixed set: no search row, and the control itself holds the keys",
            DepartmentPicker(
                value=["rig"],
                anchored=True,
                inline=False,
                text_value=True,
                searchable=False,
                placeholder="Select a department",
            ),
        )

        heights = self._group(column, "sizes", "The three heights")
        for size, value in zip(SIZES, (["layout"], ["anim"], ["light"])):
            # The three heights are the example, so they do not follow the toolbar.
            heights.addWidget(DepartmentPicker(value=value, size=size, placeholder="Select a department"))

        states = self._group(column, "states", "Disabled, read-only and invalid")
        states.addWidget(self._hold(DepartmentPicker(value=["comp"], disabled=True, placeholder="Select a department")))
        states.addWidget(self._hold(DepartmentPicker(value=["edit"], readonly=True, placeholder="Select a department")))
        states.addWidget(
            self._hold(DepartmentPicker(invalid=True, placeholder="A department is required"))
        )

        self._case(
            column,
            "custom",
            "A row and a chip of the caller's own",
            DepartmentPicker(
                value=["light"],
                multiple=True,
                chip_row=True,
                leads=True,
                placeholder="Select departments",
            ),
        )
        column.addStretch(1)

    def _group(self, column: QtWidgets.QVBoxLayout, case: str, title: str) -> QtWidgets.QVBoxLayout:
        section = QtWidgets.QWidget(self)
        section.setProperty("data_demo_case", case)
        inner = QtWidgets.QVBoxLayout(section)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(8)
        inner.addWidget(chrome.TextLine(title, size=12, parent=section))
        column.addWidget(section)
        return inner

    def _case(
        self,
        column: QtWidgets.QVBoxLayout,
        case: str,
        title: str,
        picker: DepartmentPicker,
    ) -> None:
        self._group(column, case, title).addWidget(self._hold(picker))

    def _hold(self, picker: DepartmentPicker) -> DepartmentPicker:
        self._pickers.append(picker)
        return picker

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return PickerControlDemo(context, parent)
