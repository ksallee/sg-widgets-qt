"""The number-editor demo: one control over six data types.

The port of `apps/site/src/demos/number-editor/Demo.tsx`.
"""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_core.schema import FieldSchema

from ...widgets.number_editor import NumberEditor
from ..context import DemoContext
from . import _editors

__all__ = ["build"]


def field(name: str, display_name: str, data_type: str) -> FieldSchema:
    """One numeric field of the shape the editor reads for its label."""
    return FieldSchema(
        name=name,
        display_name=display_name,
        entity_type="Shot",
        data_type=data_type,
        editable=True,
        mandatory=False,
        unique=False,
    )


class NumberEditorDemo(QtWidgets.QWidget):
    """Eight numeric editors, one per data type and form the docs page names."""

    def __init__(self, context: DemoContext, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("number-editor-demo")
        #: Nothing is read, so the demo is ready as soon as it stands.
        self.demo_ready = True

        self.cases = [
            _editors.Case(
                "number",
                NumberEditor(
                    value=1001,
                    data_type="number",
                    field=field("sg_frame_count", "Frame Count", "number"),
                ),
            ),
            _editors.Case(
                "float, step 0.1",
                NumberEditor(
                    value="1.777778",
                    data_type="float",
                    precision=2,
                    field=field("sg_aspect_ratio", "Aspect Ratio", "float"),
                ),
            ),
            _editors.Case(
                "percent, 0 to 100",
                NumberEditor(
                    value=50,
                    data_type="percent",
                    min=0,
                    max=100,
                    field=field("sg_complete", "Complete", "percent"),
                ),
            ),
            _editors.Case(
                "currency",
                NumberEditor(
                    value=12500,
                    data_type="currency",
                    symbol="$",
                    precision=2,
                    field=field("sg_bid", "Bid", "currency"),
                ),
            ),
            _editors.Case(
                "duration, step 15m",
                NumberEditor(
                    value=480,
                    data_type="duration",
                    hint=True,
                    field=field("sg_bid_duration", "Bid Duration", "duration"),
                ),
            ),
            _editors.Case(
                "duration, 6h day, scrub",
                NumberEditor(
                    value=480,
                    data_type="duration",
                    hours_per_day=6,
                    scrub=True,
                    label="Time Logged",
                    field=field("time_logged", "Time Logged", "duration"),
                ),
            ),
            _editors.Case(
                "timecode, 23.976",
                NumberEditor(
                    value=3600000,
                    data_type="timecode",
                    frame_rate=23.976,
                    field=field("sg_head_in", "Head In", "timecode"),
                ),
            ),
            _editors.Case(
                "inline, size sm",
                NumberEditor(
                    value=75,
                    data_type="percent",
                    inline=True,
                    size="sm",
                    field=field("sg_cut_duration", "Cut Duration", "percent"),
                ),
            ),
        ]
        for case in self.cases:
            _editors.bind(case, case.editor.value)

        column = QtWidgets.QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(_editors.rows(self, self.cases))

    def set_size(self, size: str) -> None:
        """Wear the size step the toolbar holds. The inline case names its own."""
        for case in self.cases:
            if not case.editor.inline:
                case.editor.set_size(size)


def build(context: DemoContext, parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    """The demo."""
    return NumberEditorDemo(context, parent)
