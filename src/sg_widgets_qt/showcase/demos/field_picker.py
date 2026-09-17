"""The field-picker demo: drill-down, restrictions, computed columns and the states.

The port of `apps/site/src/demos/field-picker/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from ...widgets.field_picker import FieldPicker
from .. import chrome
from ..context import DemoContext
from . import _layout

__all__ = ["build"]

#: The data types the restricted example offers, and the path it hides under them.
DATES = ["date", "date_time"]
HIDDEN = ["image"]

#: Two columns a data source computes, offered beside the real fields.
COMPUTED = [
    {"name": "row_number", "display_name": "Row Number"},
    {"name": "note_count", "display_name": "Note Count"},
]

#: A dotted value the picker shows as its friendly path.
PRESET = "entity.Shot.sg_turnover_date"

#: The width an example takes, so the popup has an anchor of a real size.
EXAMPLE_WIDTH = 360


class FieldPickerDemo(QtWidgets.QWidget):
    """Every example of the page, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("field-picker-demo")
        self._pickers: list[FieldPicker] = []
        #: Nothing here waits on a value, so the page is ready as soon as it stands.
        self.demo_ready = True

        body = _layout.column(self)
        body.addWidget(
            self._case(
                "free",
                "Version, deep links on",
                "Link asks which type, Project descends at once",
                context=context,
                entity_type="Version",
                deep_links=True,
            )
        )
        body.addWidget(
            self._case(
                "dates",
                "Restricted to dates",
                "Links stay on the list so a nested date is reachable",
                context=context,
                entity_type="Version",
                deep_links=True,
                data_types=DATES,
                placeholder="Select a date field",
            )
        )
        body.addWidget(
            self._case(
                "preset",
                "A dotted value",
                "Shown as its friendly path, never the raw one",
                context=context,
                entity_type="Version",
                deep_links=True,
                value=PRESET,
            )
        )
        body.addWidget(
            self._case(
                "computed",
                "Filterable types only",
                "Two computed columns and a hidden path",
                context=context,
                entity_type="Shot",
                filterable_only=True,
                hide_paths=HIDDEN,
                extra_fields=COMPUTED,
            )
        )
        body.addWidget(self._states(context))
        body.addStretch(1)

    # --- the examples ---------------------------------------------------------------------

    def _picker(self, name: str, **props: object) -> FieldPicker:
        picker = FieldPicker(parent=self, **props)
        picker.setObjectName(f"field-picker-{name}")
        picker.setFixedWidth(EXAMPLE_WIDTH)
        self._pickers.append(picker)
        return picker

    def _case(self, name: str, title: str, caption: str, **props: object) -> QtWidgets.QWidget:
        picker = self._picker(name, **props)
        path = chrome.TextLine(picker.value or "—", size=12, parent=self)
        path.setObjectName(f"field-picker-{name}-value")
        picker.value_changed.connect(lambda value, line=path: line.set_text(value or "—"))
        return _layout.section(
            title, _layout.row(picker, path, parent=self), caption=caption, parent=self
        )

    def _states(self, context: DemoContext) -> QtWidgets.QWidget:
        small = self._picker(
            "small", context=context, entity_type="Shot", value="code", size="sm"
        )
        large = self._picker(
            "large", context=context, entity_type="Shot", value="sg_status_list", size="lg"
        )
        readonly = self._picker(
            "readonly", context=context, entity_type="Shot", value="description", readonly=True
        )
        invalid = self._picker("invalid", context=context, entity_type="Shot", invalid=True)
        disabled = self._picker(
            "disabled", context=context, entity_type="Shot", value="sg_cut_in", disabled=True
        )
        return _layout.section(
            "Sizes, read-only and invalid",
            _layout.flow(small, large, readonly, invalid, disabled, parent=self),
            caption="Small and large, then the three blocked states",
            parent=self,
        )

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds, leaving the two that name their own."""
        for picker in self._pickers:
            if picker.objectName() not in ("field-picker-small", "field-picker-large"):
                picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return FieldPickerDemo(context, parent)
