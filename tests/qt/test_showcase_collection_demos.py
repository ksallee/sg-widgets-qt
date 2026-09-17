"""The collection pages of the showcase, driven the way a reader drives them.

The demos on these pages carry controls of their own — the paging toggles, the size toggles,
the queue's select-all box — and a control that does nothing, loops or drops what it describes
is as much a defect as one in a widget. Every test runs on both bindings, offscreen, and never
reaches the network: the rows come from the mock client.
"""
from __future__ import annotations

import pytest
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtTest import QTest

from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.showcase.demos.collection_control import CollectionControlDemo
from sg_widgets_qt.showcase.demos.entity_grid import SIZES, EntityGridDemo
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.workers import default_pool

from .collections import settle


def _bindings(demo: QtWidgets.QWidget) -> list:
    """Every source binding the demo holds, which is what a test waits on."""
    from sg_widgets_qt.widgets.collection_control import CollectionControl

    return [one.binding for one in demo.findChildren(CollectionControl)]


def _press(widget: QtWidgets.QWidget) -> None:
    QTest.mouseClick(
        widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, widget.rect().center()
    )


def _demo(made: QtWidgets.QWidget, qtbot):
    """Show one demo, settle every read it started, and stop them all before it goes.

    A demo reads its columns on the shared pool beside its own source, so a test that let one
    of those answers reach a widget Qt had already freed would abort the run on PyQt5.
    """
    apply_theme(made, theme_for("default"))
    qtbot.addWidget(made)
    made.resize(900, 620)
    made.show()
    settle(made, *_bindings(made), rounds=8)
    default_pool().wait(5000)
    settle(made, *_bindings(made), rounds=4)
    yield made
    for binding in _bindings(made):
        binding.close()
    default_pool().cancel_all()
    default_pool().wait(5000)


@pytest.fixture
def queue(qtbot):
    yield from _demo(CollectionControlDemo(demo_context()), qtbot)


@pytest.fixture
def grid_demo(qtbot):
    yield from _demo(EntityGridDemo(demo_context()), qtbot)


def test_the_queue_box_goes_on_and_off_and_never_lands_on_partial(queue):
    """The head's box is tri state to read and two state to press.

    `Checkbox.toggle` cycles through partial when it is tri state, so a second press left a
    minus standing over nothing selected.
    """
    assert queue.control.rows
    _press(queue._head.box)
    assert len(queue.control.selection) == len(queue.control.rows)
    assert queue._head.box.check_state == 2
    assert queue._count.text() == f"{len(queue.control.rows)} selected"

    _press(queue._head.box)
    assert queue.control.selection == []
    assert queue._head.box.check_state == 0
    assert queue._count.text() == "0 selected"


def test_a_read_landing_does_not_drop_what_the_reader_took(queue):
    """The state written back into the head's box is not a press on it.

    `set_check_state` emits `toggled`, so writing the selection's own tri state back was read
    as a press and dropped the rows it was describing.
    """
    queue.toggle_at(0)
    assert len(queue.control.selection) == 1
    assert queue._head.box.check_state == 1, "one of many taken reads as partial"

    queue.control.count()
    settle(queue, queue.control.binding)

    assert len(queue.control.selection) == 1
    assert queue._count.text() == "1 selected"
    assert queue._head.box.check_state == 1


def test_the_queue_keeps_the_wheel_at_its_bottom_edge(queue):
    """A gesture that reached the end of the rows does not scroll the page under them."""
    queue.set_paging("more")
    settle(queue, queue.control.binding)
    bar = queue.view.verticalScrollBar()
    bar.setValue(bar.maximum())
    QtWidgets.QApplication.processEvents()

    def one() -> bool:
        point = queue.view.viewport().rect().center()
        event = QtGui.QWheelEvent(
            QtCore.QPointF(point),
            QtCore.QPointF(queue.view.viewport().mapToGlobal(point)),
            QtCore.QPoint(0, -120),
            QtCore.QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QtWidgets.QApplication.sendEvent(queue.view.viewport(), event)
        return event.isAccepted()

    one()
    assert one(), "the gesture that reached the edge stays on the queue"
    assert one()


def test_a_press_on_a_grid_size_toggle_picks_that_size_and_does_not_loop(grid_demo):
    """Each toggle reports going down *and* coming up.

    A handler that ignores which it was set the others up, was reported for each of them, and
    never returned: a press on a size aborted the showcase.
    """
    for step in ("lg", "sm", "md"):
        _press(grid_demo._sizes[step])
        QtWidgets.QApplication.processEvents()
        assert grid_demo.grid.size == step
        assert [one for one in SIZES if grid_demo._sizes[one].checked] == [step]

    # The one already down stays down when it is pressed again.
    _press(grid_demo._sizes["md"])
    QtWidgets.QApplication.processEvents()
    assert grid_demo.grid.size == "md"
    assert [one for one in SIZES if grid_demo._sizes[one].checked] == ["md"]
