"""The column of rows a drag reorders: where the rows are drawn while the gesture runs.

`SortableRows` is what the sort picker and the filter editor put under their rows, and
`SortableMotion` is the motion all three of them move with, the column picker included. The
order itself is core's; what is read here is the translate rule 4 asks for: the row under the
pointer follows it, the rows it passes give way by one row, and every offset is back at zero
once the drop has settled.
"""
from __future__ import annotations

import time

from qtpy.QtCore import QPoint, QPointF, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets._sortable_rows import SLIDE_MS, SortableRows, slide_targets

#: The rows the column is built with, and how tall each one stands.
IDS = ["code", "status", "turnover"]
ROW_HEIGHT = 32


def drag_move(widget: QWidget, point: QPoint) -> None:
    """A move with the button still down, delivered the same way on Qt 5 and Qt 6."""
    where = QPointF(float(point.x()), float(point.y()))
    QApplication.sendEvent(
        widget,
        QMouseEvent(
            QMouseEvent.Type.MouseMove,
            where,
            QPointF(widget.mapToGlobal(point)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def spin(qtbot, ms: int = 40) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)


def build(qtbot, reduced: bool = False):
    """A column of three rows, each with a grip, and the sortable watching them."""
    root = QWidget()
    apply_theme(root, theme_for("default", reduced_motion=reduced))
    qtbot.addWidget(root)
    root.resize(300, 200)
    column = QVBoxLayout(root)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    rows: list[QWidget] = []
    grips: list[QWidget] = []
    for one in IDS:
        row = QWidget(root)
        row.setObjectName(one)
        row.setFixedHeight(ROW_HEIGHT)
        grip = QWidget(row)
        grip.setObjectName(f"{one}-grip")
        grip.setGeometry(0, 0, 24, ROW_HEIGHT)
        rows.append(row)
        grips.append(grip)
        column.addWidget(row)
    # The rows stack at the top: a column with room left over spreads what it cannot grow, and
    # the rows would stand a stride apart that has nothing to do with their own height.
    column.addStretch(1)
    root.show()
    qtbot.waitExposed(root)
    sortable = SortableRows(root)
    sortable.set_rows(IDS, rows)
    for index, grip in enumerate(grips):
        sortable.attach_grip(grip, index)
    sortable.test_root = root
    sortable.test_rows = rows
    sortable.test_grips = grips
    spin(qtbot, 20)
    return sortable


def test_the_shifts_are_one_row_either_side_of_the_carried_one():
    """`slide_targets` is the loop of upstream's `project`, on its own."""
    assert slide_targets(4, 0, 2, 32.0) == {1: -32.0, 2: -32.0}
    assert slide_targets(4, 3, 1, 32.0) == {1: 32.0, 2: 32.0}
    assert slide_targets(4, 1, 1, 32.0) == {}
    assert slide_targets(4, -1, 2, 32.0) == {}


def test_a_dragged_row_is_lifted_and_its_neighbours_give_way(qtbot):
    sortable = build(qtbot)
    grip = sortable.test_grips[0]
    start = QPoint(8, ROW_HEIGHT // 2)
    QTest.mousePress(grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    drag_move(grip, QPoint(start.x(), start.y() + ROW_HEIGHT + 8))
    spin(qtbot, 30)
    assert sortable.dragging, "the press never became a drag"
    assert sortable.motion.lifted == 0, "the row under the pointer is the lifted one"
    assert sortable.offset_of(0) > 0, "the lifted row does not follow the pointer"
    assert sortable.offset_of(1) < 0, "the row the drag passed never gave way"
    # Transform only: the row is drawn off its slot, and the column is not laid out again.
    assert sortable.ids == IDS, "the order moved before the drop"


def test_the_rows_settle_back_onto_their_slots_after_the_drop(qtbot):
    sortable = build(qtbot)
    moved: list = []
    sortable.moved.connect(lambda old, new: moved.append((old, new)))
    grip = sortable.test_grips[0]
    start = QPoint(8, ROW_HEIGHT // 2)
    QTest.mousePress(grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    drag_move(grip, QPoint(start.x(), start.y() + ROW_HEIGHT + 8))
    spin(qtbot, 30)
    QTest.mouseRelease(
        grip,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(start.x(), start.y() + ROW_HEIGHT + 8),
    )
    assert moved and moved[-1][0] == 0, "the drop never reported the move"
    end = time.time() + (SLIDE_MS + 200) / 1000.0
    while time.time() < end and sortable.motion.running:
        QApplication.processEvents()
        qtbot.wait(10)
    assert not sortable.motion.running, "the settle never finished"
    assert sortable.motion.lifted == -1, "nothing is left lifted"
    assert all(abs(sortable.offset_of(index)) < 1 for index in range(len(IDS))), (
        "a row was left drawn off its slot"
    )


def test_reduced_motion_takes_the_offsets_at_once(qtbot):
    """Rule 4: the rows give way with no motion at all under the flag."""
    sortable = build(qtbot, reduced=True)
    grip = sortable.test_grips[0]
    start = QPoint(8, ROW_HEIGHT // 2)
    QTest.mousePress(grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    drag_move(grip, QPoint(start.x(), start.y() + ROW_HEIGHT + 8))
    spin(qtbot, 20)
    assert not sortable.motion.running, "reduced motion animated the slide"
    assert sortable.offset_of(1) < 0, "the row the drag passed never gave way"
