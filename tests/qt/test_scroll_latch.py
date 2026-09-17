"""The wheel stays on a view at its edge within one gesture, and while a page is on its way."""
from __future__ import annotations

from qtpy import QtWidgets

from sg_widgets_qt.primitives.scroll_latch import WheelLatch


class _Wheel:
    def __init__(self, dy: int) -> None:
        self._dy = dy

    def angleDelta(self):  # noqa: N802
        from qtpy.QtCore import QPoint

        return QPoint(0, self._dy)

    def pixelDelta(self):  # noqa: N802
        from qtpy.QtCore import QPoint

        return QPoint(0, 0)


def _view(qtbot, rows: int = 60) -> QtWidgets.QListWidget:
    view = QtWidgets.QListWidget()
    for i in range(rows):
        view.addItem(f"row {i}")
    view.resize(200, 120)
    qtbot.addWidget(view)
    view.show()
    return view


def test_a_view_not_at_its_edge_keeps_nothing(qtbot):
    view = _view(qtbot)
    latch = WheelLatch(view, clock=lambda: 0.0)
    assert latch.keeps(_Wheel(-120)) is False


def test_the_gesture_that_reached_the_bottom_stays_on_the_view(qtbot):
    view = _view(qtbot)
    now = [0.0]
    latch = WheelLatch(view, clock=lambda: now[0])
    assert latch.keeps(_Wheel(-120)) is False
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    now[0] = 0.1
    assert latch.keeps(_Wheel(-120)) is True
    now[0] = 1.0  # a new gesture, after the pause, reaches the page
    assert latch.keeps(_Wheel(-120)) is False


def test_a_page_on_its_way_keeps_the_wheel_even_on_a_new_gesture(qtbot):
    view = _view(qtbot)
    more = [True]
    now = [0.0]
    latch = WheelLatch(view, more=lambda: more[0], clock=lambda: now[0])
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    assert latch.keeps(_Wheel(-120)) is True
    more[0] = False
    now[0] = 5.0
    assert latch.keeps(_Wheel(-120)) is False


def test_scrolling_up_at_the_top_follows_the_same_rule(qtbot):
    view = _view(qtbot)
    now = [0.0]
    latch = WheelLatch(view, more=lambda: True, clock=lambda: now[0])
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum())
    assert latch.keeps(_Wheel(120)) is False  # the view scrolls up: the gesture is its own
    bar.setValue(bar.minimum())
    now[0] = 0.1
    assert latch.keeps(_Wheel(120)) is True  # the same gesture stays at the top
    now[0] = 1.0
    assert latch.keeps(_Wheel(120)) is False  # a fresh gesture at the top reaches the page


def test_a_gesture_that_began_at_the_edge_never_stays(qtbot):
    """A view already at its edge when the wheel arrives never scrolled, so the page scrolls.

    A grid that shows every row it has is at both edges at once; before, its second event
    within the pause was held, so a page stalled each time the pointer crossed such a grid.
    """
    view = _view(qtbot)
    now = [0.0]
    latch = WheelLatch(view, clock=lambda: now[0])
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    for step in range(5):
        now[0] = step * 0.02
        assert latch.keeps(_Wheel(-120)) is False


def test_a_view_with_no_range_never_stays(qtbot):
    view = _view(qtbot, rows=3)
    now = [0.0]
    latch = WheelLatch(view, clock=lambda: now[0])
    assert view.verticalScrollBar().maximum() == 0
    for step in range(5):
        now[0] = step * 0.02
        assert latch.keeps(_Wheel(-120)) is False
        assert latch.keeps(_Wheel(120)) is False
