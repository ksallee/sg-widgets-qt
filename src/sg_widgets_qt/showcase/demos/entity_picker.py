"""One entity, chosen by server-side search.

The port of `apps/site/src/demos/entity-picker/Demo.tsx`: one shot, a status secondary, three
types at once, a secondary of the caller's own, a picker scoped to one project, a bare reference
resolved on the way in, five a page with a load-more row, a read armed to fail, the row anatomy,
the three heights, and the three states.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtCore, QtWidgets

from sg_widgets_core.filter import EntityRef
from sg_widgets_core.picker import placeholder_name

from ...widgets.entity_picker import EntityPicker
from .. import chrome
from ..context import MOCK_LATENCY_MS, DemoContext, demo_context

__all__ = ["build"]

#: An asset the fixtures always carry, for the examples that come with a value.
PRESET = EntityRef(type="Asset", id=1226, name="charAda")

#: A bare reference: type and id, no name. Resolved on the way in by one id-in read.
BARE = EntityRef(type="Shot", id=866)

#: The project the scoped example reads. The mock's second project.
SCOPED_PROJECT = 71

SIZES = (("sm", "Small"), ("md", "Medium, the default"), ("lg", "Large"))


class EntityPickerDemo(QtWidgets.QWidget):
    """Every example, one under the other."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entity-picker-demo")
        self._context = context
        self._pickers: list = []
        #: False until every value handed in has a name. `_Readiness` flips it.
        self.demo_ready = True

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(16)

        self._case(column, "single", "One shot, clearable", entity_types=["Shot"])
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
            "project",
            "Scoped to one project",
            entity_types=["Shot"],
            project_id=context.project_for(SCOPED_PROJECT),
            placeholder="Shots on one project…",
        )

        bare = self._case(
            column,
            "hydrate",
            "Type and id in, name resolved on the way in",
            entity_types=["Shot"],
            value=BARE,
        )
        again = chrome.button(
            "Hand in another bare reference",
            variant="ghost",
            size="sm",
            parent=self,
            on_click=lambda: bare.set_value(EntityRef(type="Asset", id=1229)),
        )
        again.setObjectName("hand-in-another")
        bare.parentWidget().layout().addWidget(again)

        self._case(
            column, "more", "Five a page, with a load more row", entity_types=["Shot"], page_size=5
        )

        # Its own client, so arming a failure cannot land in another example on the page.
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

        anatomy = self._group(column, "anatomy", "Row anatomy: no thumbnail, a sub-label, the code")
        anatomy.addWidget(self._picker(entity_types=["Shot"], thumbnail=False))
        anatomy.addWidget(
            self._picker(
                entity_types=["Version"],
                sub_label_field="sg_status_list",
                secondary_field="id",
                show_code=True,
            )
        )

        heights = self._group(column, "sizes", "Sizes")
        for size, caption in SIZES:
            heights.addWidget(chrome.TextLine(caption, size=12, parent=self))
            # The three heights are the example, so they do not follow the toolbar.
            heights.addWidget(
                EntityPicker(
                    entity_types=["Asset"],
                    context=self._context.context,
                    value=PRESET,
                    size=size,
                    parent=self,
                )
            )

        states = self._group(column, "states", "Disabled, read-only, invalid")
        for flag in ("disabled", "readonly", "invalid"):
            states.addWidget(chrome.TextLine(flag.capitalize(), size=12, parent=self))
            states.addWidget(
                self._picker(entity_types=["Asset"], value=PRESET, **{flag: True})
            )
        column.addStretch(1)
        self._readiness = _Readiness(self, self._pickers)

    # --- building ----------------------------------------------------------------------

    def _picker(self, context: DemoContext | None = None, **props: Any) -> EntityPicker:
        source = context if context is not None else self._context
        picker = EntityPicker(context=source.context, parent=self, **props)
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
    ) -> EntityPicker:
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


class _Readiness(QtCore.QObject):
    """Holds a demo not ready until every value it was given has a name.

    A picker handed a bare reference reads it on a worker, so the first paint of the page would
    otherwise catch `Asset 1226` rather than the row it resolves to.
    """

    #: How long the poll waits before it calls the page ready anyway.
    LIMIT_MS = 4000
    STEP_MS = 100

    def __init__(self, demo: QtWidgets.QWidget, pickers: list) -> None:
        super().__init__(demo)
        self._demo = demo
        self._pickers = pickers
        self._waited = 0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.STEP_MS)
        self._timer.timeout.connect(self._poll)
        demo.demo_ready = not self._pending()
        if not demo.demo_ready:
            self._timer.start()

    def _pending(self) -> bool:
        for picker in self._pickers:
            for ref, label in zip(_refs_of(picker), picker.control.labels):
                if not label or label == placeholder_name(ref):
                    return True
        return False

    def _poll(self) -> None:
        self._waited += self.STEP_MS
        if not self._pending() or self._waited >= self.LIMIT_MS:
            self._timer.stop()
            self._demo.demo_ready = True


def _refs_of(picker: object) -> list:
    """The references a picker holds, whether its value is one or several."""
    value = getattr(picker, "value", None)
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _own_context(context: DemoContext) -> DemoContext:
    """A context of this example's own, so an armed failure stays in it."""
    if context.live:
        return context
    return demo_context(project_id=context.project_id, latency_ms=MOCK_LATENCY_MS)


def _fail_next_of(client: object):
    """The mock's `fail_next`, through whatever caches and counters wrap it."""
    seen = 0
    while client is not None and seen < 8:
        arm = getattr(client, "fail_next", None)
        if callable(arm):
            return arm
        client = getattr(client, "_client", None)
        seen += 1
    return None


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return EntityPickerDemo(context, parent)
