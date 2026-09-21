"""Several entities, chosen by server-side search.

The port of `apps/site/src/demos/entity-multi-picker/Demo.tsx`: several shots, a token field the
keyboard walks, a status secondary, three types at once, a secondary of the caller's own, bare
references resolved on the way in, two shots kept out of the results, five a page with a load-more
row, a read armed to fail, what the control shows for five selected wide and narrow, the three
heights, and the three states.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef

from ...widgets.entity_multi_picker import EntityMultiPicker
from .. import chrome
from ..context import DemoContext
from . import _rows
from .entity_picker import _fail_next_of, _own_context, _Readiness

__all__ = ["build"]

#: Rows already on the team, kept out of the results by the server filter.
ALREADY_THERE = _rows.refs("Shot", 862, 863)

PRESET = _rows.refs("Asset", 1226, 1227)

#: Five, so `ellipsis` has something to count and `max` something to cut.
FIVE = [*PRESET, *(EntityRef(type="Asset", id=1228 + i) for i in range(3))]

#: A token field with chips already in it, for the keyboard.
TOKENS = [*PRESET, EntityRef(type="Asset", id=1228)]

#: Bare references: type and id, no name.
BARE = [EntityRef(type="Shot", id=866), EntityRef(type="Asset", id=1226)]

SUMMARIES = ("chips", "ellipsis", "count")
SIZES = ("sm", "md", "lg")

#: At most 320, so the fit has something to cut against.
NARROW = 320


class EntityMultiPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-multi-picker-demo")
        self._context = context
        self._pickers: list = []
        #: False until every value handed in has a name. `_Readiness` flips it.
        self.demo_ready = True

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(16)

        self._case(column, "multi", "Several shots", entity_types=["Shot"])
        self._case(
            column,
            "tokens",
            "A token field: Backspace walks the chips",
            entity_types=["Asset"],
            summary="chips",
            value=list(TOKENS),
        )
        self._case(
            column,
            "status-secondary",
            "Status on the right of every row",
            entity_types=["Shot"],
            secondary_field="sg_status_list",
        )
        self._case(
            column,
            "multi-type",
            "Shots, assets and sequences in one list, the type on the right",
            entity_types=["Shot", "Asset", "Sequence"],
            placeholder="Search shots, assets and sequences…",
        )
        self._case(
            column,
            "custom-secondary",
            "The id, rendered by the caller",
            entity_types=["Shot"],
            secondary=lambda row: f"#{row.id}",
        )
        self._case(
            column,
            "hydrate",
            "Bare references, resolved on the way in",
            entity_types=["Shot", "Asset"],
            value=list(BARE),
        )
        self._case(
            column,
            "exclude",
            "Two shots excluded from the results",
            entity_types=["Shot"],
            exclude=list(ALREADY_THERE),
            placeholder=f"{ALREADY_THERE[0].name} and {ALREADY_THERE[1].name} are not offered…",
        )
        self._case(
            column, "more", "Five a page, with a load more row", entity_types=["Shot"], page_size=5
        )

        self._failing = _own_context(context)
        broken = self._case(
            column,
            "error",
            "Reads a client whose next call can be armed to fail",
            context=self._failing,
            entity_types=["Shot"],
        )
        self._last_error = chrome.TextLine("", size=12, token="destructive", parent=self)
        broken.error.connect(lambda cause: self._last_error.set_text(str(cause)))
        arm = chrome.button(
            "Arm the next call to fail",
            variant="ghost",
            size="sm",
            parent=self,
            on_click=self._arm_failure,
        )
        arm.setObjectName("arm-failure")
        broken.parentWidget().layout().addWidget(arm)
        broken.parentWidget().layout().addWidget(self._last_error)

        summary = self._group(
            column, "summary", "What the control shows for five selected, wide and narrow"
        )
        for mode in SUMMARIES:
            summary.addWidget(chrome.TextLine(f"{mode}, full width", size=12, parent=self))
            summary.addWidget(
                self._picker(
                    entity_types=["Asset"], value=list(FIVE), summary=mode, clearable=False
                )
            )
            summary.addWidget(chrome.TextLine(f"{mode}, at most 320", size=12, parent=self))
            narrow = self._picker(
                entity_types=["Asset"], value=list(FIVE), summary=mode, clearable=False
            )
            narrow.setMaximumWidth(NARROW)
            summary.addWidget(narrow)
        summary.addWidget(chrome.TextLine("chips, two at most", size=12, parent=self))
        summary.addWidget(
            self._picker(
                entity_types=["Asset"],
                value=list(FIVE),
                summary="chips",
                max=2,
                clearable=False,
            )
        )

        heights = self._group(column, "sizes", "Sizes")
        for size in SIZES:
            heights.addWidget(chrome.TextLine(size, size=12, parent=self))
            # The three heights are the example, so they do not follow the toolbar.
            heights.addWidget(
                EntityMultiPicker(
                    entity_types=["Asset"],
                    context=self._context.context,
                    value=list(PRESET),
                    size=size,
                    parent=self,
                )
            )

        states = self._group(column, "states", "Disabled, read-only, invalid")
        for flag in ("disabled", "readonly", "invalid"):
            states.addWidget(chrome.TextLine(flag.capitalize(), size=12, parent=self))
            states.addWidget(
                self._picker(entity_types=["Asset"], value=list(PRESET), **{flag: True})
            )
        column.addStretch(1)
        self._readiness = _Readiness(self, self._pickers)

    # --- building ----------------------------------------------------------------------

    def _picker(self, context: DemoContext | None = None, **props: Any) -> EntityMultiPicker:
        source = context if context is not None else self._context
        picker = EntityMultiPicker(context=source.context, parent=self, **props)
        self._pickers.append(picker)
        return picker

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
        context: DemoContext | None = None,
        **props: Any,
    ) -> EntityMultiPicker:
        picker = self._picker(context=context, **props)
        self._group(column, case, title).addWidget(picker)
        return picker

    def _arm_failure(self) -> None:
        """Arm the mock's next call. A live context has nothing to arm."""
        arm = _fail_next_of(self._failing.client)
        if arm is not None:
            arm()

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds."""
        for picker in self._pickers:
            picker.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityMultiPickerDemo(context, parent)
