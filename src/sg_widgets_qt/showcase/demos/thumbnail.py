"""The thumbnail at every step, in both aspects, playable, and in each of its empty states.

The port of `apps/site/src/demos/thumbnail/Demo.tsx`. The pictures come from the demo context: the
chosen project's own, then that project's Versions that carry one. The last section is built from
values alone, so the three states a row can be in are always on show.
"""
from __future__ import annotations

from typing import Any

from qtpy import QtWidgets

from sg_widgets_core.client import SearchOptions

from ...images import image_loader
from ...widgets.state_line import StateLine
from ...widgets.thumbnail import Thumbnail
from ...workers import default_pool
from ..context import DemoContext
from . import _layout as lay

__all__ = ["build"]

#: The url Flow PT serves while a thumbnail is still transcoding (field_types/image).
PENDING = "https://sg.example.com/images/status/transient/thumbnail_pending.png"

#: A truncated PNG: it fails to decode, which is the load-failure fallback.
BROKEN = "data:image/png;base64,iVBORw0KGgo="

#: The steps the ladder offers.
STEPS = ("sm", "md", "lg", "xl", "2xl")

#: How many rows with a picture the demo asks for.
ROWS = 3


class ThumbnailDemo(QtWidgets.QWidget):
    """The picture of a row at every size, in both shapes, and with nothing to show."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("thumbnail-demo")
        self._context = context
        self._read_done = False

        self._body = lay.column(self)
        self._state = StateLine(state="empty", label="Loading shots…", pad="none", parent=self)
        self._state.setObjectName("demo-state")
        self._body.addWidget(self._state)
        self._body.addWidget(self._empty_states())

        default_pool().submit(self._read, on_result=self._answered, on_error=self._failed)

    def demo_ready(self) -> bool:
        """True once the rows have answered and every picture they named has landed."""
        return self._read_done and image_loader().pending == 0

    def set_size(self, size: str) -> None:
        """The ladder is what this demo is about, so every example names its own step."""

    # --- the read ---

    def _read(self) -> list[tuple[str, str | None]]:
        client = self._context.client
        project = self._context.project_id
        projects = client.search(
            "Project",
            SearchOptions(
                filters={"logical_operator": "and", "conditions": [["id", "is", project]]},
                fields=["name", "image"],
                page={"size": 1},
            ),
        )
        versions = client.search(
            "Version",
            SearchOptions(
                filters={
                    "logical_operator": "and",
                    "conditions": [
                        ["project", "is", {"type": "Project", "id": project}],
                        ["image", "is_not", None],
                    ],
                },
                fields=["code", "image"],
                page={"size": ROWS},
            ),
        )
        rows = [row for row in [*projects.data, *versions.data] if row.values.get("image")]
        if len(rows) < ROWS:
            rows = (rows * ROWS)[:ROWS]
        return [
            (str(row.values.get("code") or row.values.get("name") or ""), row.values.get("image"))
            for row in rows
        ]

    def _answered(self, rows: Any) -> None:
        if not lay.alive(self):
            return
        shots: list[tuple[str, str | None]] = list(rows or [])
        if not shots:
            self._state.apply_state("empty")
            self._read_done = True
            return
        self._state.setParent(None)
        self._body.insertWidget(0, self._from_the_site(shots))
        self._read_done = True

    def _failed(self, error: BaseException) -> None:
        if not lay.alive(self):
            return
        self._state.apply_state("error", message=str(error))
        self._read_done = True

    # --- the sections ---

    def _from_the_site(self, shots: list[tuple[str, str | None]]) -> QtWidgets.QWidget:
        holder = QtWidgets.QWidget(self)
        column = QtWidgets.QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(lay.SECTION_GAP)

        first, second, third = (shots[i % len(shots)] for i in range(3))
        column.addWidget(
            lay.section(
                "Sizes",
                lay.flow(
                    *(
                        Thumbnail(src=first[1], alt=first[0], size=step, parent=self)
                        for step in STEPS
                    )
                ),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "Aspect",
                lay.row(
                    Thumbnail(src=second[1], alt=second[0], size="lg", aspect="16:9", parent=self),
                    Thumbnail(src=second[1], alt=second[0], size="lg", aspect="square", parent=self),
                ),
                parent=self,
            )
        )
        column.addWidget(
            lay.section(
                "Playable",
                lay.flow(
                    *(
                        Thumbnail(src=third[1], alt=third[0], size=step, playable=True, parent=self)
                        for step in STEPS
                    )
                ),
                parent=self,
            )
        )
        return holder

    def _empty_states(self) -> QtWidgets.QWidget:
        section = lay.section(
            "No image, still transcoding, failed to load, and one that is inert",
            lay.flow(
                Thumbnail(src=None, size="lg", parent=self),
                Thumbnail(src=None, size="lg", entity_type="Shot", parent=self),
                Thumbnail(src=None, size="lg", entity_type="Asset", parent=self),
                Thumbnail(src=None, size="lg", entity_type="Version", parent=self),
                Thumbnail(src=PENDING, size="lg", parent=self),
                Thumbnail(src=BROKEN, size="lg", entity_type="Shot", parent=self),
                Thumbnail(
                    src=None, size="lg", aspect="square", entity_type="Task", playable=True, parent=self
                ),
                _inert(Thumbnail(src=None, size="lg", entity_type="Sequence", parent=self)),
            ),
            parent=self,
        )
        section.setObjectName("case-empty")
        return section


def _inert(widget: Thumbnail) -> Thumbnail:
    """A disabled tile: half opacity, and its picture greyed (rule 5)."""
    widget.setEnabled(False)
    return widget


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return ThumbnailDemo(context, parent)
