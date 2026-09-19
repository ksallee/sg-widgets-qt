"""The overlay scrollbar's handle follows the scroll it stands for."""
from __future__ import annotations

from qtpy import QtCore, QtWidgets

from sg_widgets_qt.primitives.scrollbar import OverlayScrollBar


class _Bar(OverlayScrollBar):
    """An overlay bar that counts the repaints it asks for."""

    def __init__(self, *args: object) -> None:
        self.repaints = 0
        super().__init__(*args)

    def update(self, *args: object) -> None:  # noqa: N802
        self.repaints += 1
        super().update(*args)


def _shown_bar(qtbot, rows: int) -> tuple[QtWidgets.QListWidget, _Bar]:
    view = QtWidgets.QListWidget()
    for i in range(rows):
        view.addItem(f"row {i}")
    view.resize(200, 120)
    qtbot.addWidget(view)
    view.show()
    bar = _Bar(view.verticalScrollBar(), QtCore.Qt.Orientation.Vertical, view)
    bar.setGeometry(190, 0, 8, 120)
    bar.fade_delay_ms = 60_000  # the bar stays shown, so only a scroll may repaint it
    bar.wake()
    assert bar.opacity() == 1.0
    bar.repaints = 0
    return view, bar


def test_a_scroll_while_the_bar_is_shown_repaints_the_handle(qtbot):
    view, bar = _shown_bar(qtbot, rows=200)
    before = bar.handle_rect()
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum() // 2)
    assert bar.repaints >= 1, "the handle was not repainted after the value moved"
    assert bar.handle_rect().y() > before.y()


def test_a_range_change_while_the_bar_is_shown_repaints_the_handle(qtbot):
    view, bar = _shown_bar(qtbot, rows=12)
    before = bar.handle_rect()
    for i in range(12, 200):
        view.addItem(f"row {i}")
    qtbot.wait(20)  # the view lays its rows out, and the range moves, on the next turn
    assert bar.repaints >= 1, "the handle was not repainted after the range changed"
    assert bar.handle_rect().height() < before.height()
