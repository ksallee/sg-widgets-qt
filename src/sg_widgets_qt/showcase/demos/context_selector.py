"""The context with its recents and one person's tasks, and the three sizes beside a button.

The port of `apps/site/src/demos/context-selector/Demo.tsx`. On a real site the context starts
on the project the Connect panel picked and the widget's own reads fill the rest; the rows below
are the mock's.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.filter import EntityRef

from ...widgets.context_selector import ContextSelector, WorkContext
from .. import chrome
from ..context import DemoContext
from . import _layout as lay
from . import _rows

__all__ = ["build"]

#: The mock's first person, as the app would pass the signed-in user.
CURRENT_USER = _rows.ref("HumanUser", 20)

SIZES = ("sm", "md", "lg")


def start_context(context: DemoContext) -> WorkContext:
    """Where the demo opens: the toolbar's project in live mode, the mock's rows otherwise."""
    if context.live:
        return WorkContext(
            project=EntityRef(
                type="Project", id=context.project_id, name=context.project_name
            )
        )
    return WorkContext(
        project=_rows.ref("Project", 70),
        entity=_rows.ref("Shot", 862),
        task=_rows.ref("Task", 5700),
    )


def start_recents(context: DemoContext) -> list[WorkContext]:
    """Two contexts used before, so the first section has rows in it."""
    if context.live:
        return []
    return [
        WorkContext(
            project=_rows.ref("Project", 70),
            entity=_rows.ref("Asset", 1226),
            task=_rows.ref("Task", 5730),
        ),
        WorkContext(
            project=_rows.ref("Project", 71),
            entity=_rows.ref("Shot", 889),
        ),
    ]


class ContextSelectorDemo(QtWidgets.QWidget):
    """The live selector, the line saying what it holds, and the size ladder."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("context-selector-demo")
        self._context = context
        #: True once the first read has answered or failed. The stage polls it.
        self.demo_ready = False
        self._work_context = start_context(context)
        self._recents = start_recents(context)

        body = lay.column(self)
        self.selector = ContextSelector(
            self,
            context=context.context,
            work_context=self._work_context,
            current_user=CURRENT_USER,
            recents=self._recents,
        )
        self.selector.setObjectName("context-selector")
        self.selector.work_context_changed.connect(self._changed)
        self.selector.recents_changed.connect(self._keep_recents)
        self.selector.tasks_control().rows_changed.connect(self._settled)
        self.selector.tasks_control().error.connect(lambda _message: self._settled())
        body.addWidget(
            lay.section(
                "Current context, with recents and one person's tasks", self.selector, parent=self
            )
        )

        self.line = chrome.TextLine(self._line(), size=13, parent=self)
        self.line.setObjectName("demo-context")
        body.addWidget(self.line)

        sizes = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(sizes)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.INNER_GAP)
        for step in SIZES:
            # The sizes row shows a fixed context; it takes no picks.
            fixed = ContextSelector(
                sizes,
                context=context.context,
                work_context=start_context(context),
                current_user=CURRENT_USER,
                size=step,
            )
            fixed.setObjectName(f"context-selector-{step}")
            fixed.setFixedWidth(320)
            column.addWidget(
                lay.row(
                    fixed,
                    chrome.button("Button", variant="outline", size=step, parent=sizes),
                    parent=sizes,
                )
            )
        body.addWidget(
            lay.section("Sizes, each beside a button of the same step", sizes, parent=self)
        )

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The size row names its own."""
        self.selector.set_size(size)

    def _line(self) -> str:
        held = self._work_context
        return (
            f"project {held.project.name if held.project else '-'} / "
            f"entity {held.entity.name if held.entity else '-'} / "
            f"task {held.task.name if held.task else '-'}"
        )

    def _changed(self, work_context: Any) -> None:
        self._work_context = work_context
        self.line.set_text(self._line())

    def _keep_recents(self, recents: Any) -> None:
        self._recents = list(recents)

    def _settled(self) -> None:
        self.demo_ready = True


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ContextSelectorDemo(context, parent)
