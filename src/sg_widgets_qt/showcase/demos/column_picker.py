"""The column-picker demo: the default list, a restricted picker, the dual layout and the states.

The port of `apps/site/src/demos/column-picker/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from ...widgets.column_picker import ColumnPicker
from .. import chrome
from ..context import DemoContext
from . import _layout

__all__ = ["build"]

#: The columns the first example starts on, one of them behind a link.
COLUMNS = ["code", "sg_status_list", "entity.Shot.sg_turnover_date"]

#: A timestamp behind a link, which is what the restricted example reaches.
DATES = ["entity.Shot.updated_at"]

#: The two the dual example starts on, and the pair the blocked examples hold.
DUAL = ["code", "sg_cut_in"]
LOCKED = ["code", "sg_cut_in"]


class ColumnPickerDemo(QtWidgets.QWidget):
    """Every example of the page, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("column-picker-demo")
        self._pickers: list[ColumnPicker] = []
        #: Nothing here waits on a value, so the page is ready as soon as it stands.
        self.demo_ready = True

        body = _layout.column(self)

        columns = self._picker(
            "columns", context=context, entity_type="Version", value=COLUMNS, show_count=True
        )
        paths = chrome.TextLine(f"[{', '.join(COLUMNS)}]", size=12, parent=self)
        paths.setObjectName("column-picker-columns-value")
        columns.value_changed.connect(
            lambda value, line=paths: line.set_text(f"[{', '.join(value)}]")
        )
        body.addWidget(
            _layout.section(
                "Columns on Version",
                columns,
                paths,
                caption="Pick a field, then drag the list into order",
                parent=self,
            )
        )

        body.addWidget(
            _layout.section(
                "Date-times only",
                self._picker(
                    "dates",
                    context=context,
                    entity_type="Version",
                    data_types="date_time",
                    value=DATES,
                ),
                caption="Links stay on the list, so a timestamp behind one is reachable",
                parent=self,
            )
        )

        body.addWidget(
            _layout.section(
                "Dual",
                self._picker(
                    "dual",
                    context=context,
                    entity_type="Shot",
                    layout="dual",
                    filterable_only=True,
                    value=DUAL,
                ),
                caption="The fields of the type on the left, the chosen paths on the right",
                parent=self,
            )
        )

        body.addWidget(
            _layout.section(
                "Disabled",
                self._picker(
                    "disabled", context=context, entity_type="Shot", value=LOCKED, disabled=True
                ),
                parent=self,
            )
        )

        body.addWidget(
            _layout.section(
                "Read-only",
                self._picker(
                    "readonly", context=context, entity_type="Shot", value=LOCKED, readonly=True
                ),
                caption="The chosen list alone",
                parent=self,
            )
        )
        body.addStretch(1)

    def _picker(self, name: str, **props: object) -> ColumnPicker:
        picker = ColumnPicker(parent=self, **props)
        picker.setObjectName(f"column-picker-{name}")
        self._pickers.append(picker)
        return picker

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ColumnPickerDemo(context, parent)
