"""The ordered columns of a grid: adding, removing, reordering and the two layouts."""
from __future__ import annotations

import time

from qtpy.QtCore import QPoint, Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.column_picker import DUAL_BREAKPOINT, ColumnPicker

from .test_picker_contract import PickerShape, check_contract, spin


def drag_move(widget, point: QPoint) -> None:
    """A move with the button still down, delivered the same way on Qt 5 and Qt 6.

    `QTest.mouseMove` synthesises a move the platform may or may not carry the button on, so
    the event is built with `LeftButton` held and sent straight to the widget.
    """
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QMouseEvent

    where = QPointF(float(point.x()), float(point.y()))
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        where,
        where,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


def search_caret(picker):
    from qtpy.QtWidgets import QLineEdit

    return picker.control.search_row().findChild(QLineEdit)

COLUMNS = ["code", "sg_status_list", "entity.Shot.sg_turnover_date"]


def context_for():
    return create_sg_context(MockClient(seed=1, latency_ms=0, now=MOCK_NOW), SgContextOptions())


def build(qtbot, **props):
    props.setdefault("entity_type", "Version")
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(720, 640)
    picker = ColumnPicker(context=context_for(), parent=root, **props)
    picker.setGeometry(10, 10, 700, 600)
    root.show()
    qtbot.waitExposed(root)
    picker.test_root = root
    return picker


def settled(qtbot, picker, ms: int = 1200) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if picker.field_picker.options:
            break
        qtbot.wait(5)
    spin(qtbot, 60)


def labelled(qtbot, picker, ms: int = 1200) -> None:
    """Spin until every chosen path has its friendly label."""
    end = time.time() + ms / 1000.0
    model = picker.chosen_list.rows_model
    while time.time() < end:
        QApplication.processEvents()
        if all(model.parts_of(path) for path in picker.value):
            break
        qtbot.wait(5)
    spin(qtbot, 30)


def test_the_chosen_paths_read_as_their_friendly_path(qtbot):
    picker = build(qtbot, value=COLUMNS, show_count=True)
    settled(qtbot, picker)
    labelled(qtbot, picker)
    model = picker.chosen_list.rows_model
    assert model.rowCount() == 3
    assert model.label_of("code") == "Version Name"
    assert model.label_of("entity.Shot.sg_turnover_date") == "Link › Turnover Date"
    assert picker.chosen_list.paths == COLUMNS


def test_a_column_reorder_by_keyboard_emits_the_new_order(qtbot):
    picker = build(qtbot, value=COLUMNS)
    settled(qtbot, picker)
    labelled(qtbot, picker)
    seen: list = []
    picker.value_changed.connect(lambda value: seen.append(list(value)))
    rows = picker.chosen_list
    rows.setFocus()
    rows.set_highlight(0)
    QTest.keyClick(rows, Qt.Key.Key_Space)
    assert rows.carrying == "code"
    assert rows.accessibleDescription() == "Picked up Version Name, position 1 of 3"
    QTest.keyClick(rows, Qt.Key.Key_Down)
    assert seen[-1] == ["sg_status_list", "code", "entity.Shot.sg_turnover_date"]
    assert rows.accessibleDescription() == "Moved Version Name to position 2 of 3"
    QTest.keyClick(rows, Qt.Key.Key_Space)
    assert rows.carrying is None
    assert rows.accessibleDescription() == "Dropped Version Name"
    assert picker.value == ["sg_status_list", "code", "entity.Shot.sg_turnover_date"]


def test_escape_puts_a_carried_row_back(qtbot):
    picker = build(qtbot, value=COLUMNS)
    settled(qtbot, picker)
    rows = picker.chosen_list
    rows.setFocus()
    rows.set_highlight(2)
    QTest.keyClick(rows, Qt.Key.Key_Space)
    QTest.keyClick(rows, Qt.Key.Key_Up)
    assert picker.value[1] == "entity.Shot.sg_turnover_date"
    QTest.keyClick(rows, Qt.Key.Key_Escape)
    assert picker.value == COLUMNS
    assert rows.accessibleDescription() == "Cancelled"


def test_alt_and_an_arrow_move_the_row_holding_focus(qtbot):
    picker = build(qtbot, value=COLUMNS)
    settled(qtbot, picker)
    rows = picker.chosen_list
    rows.setFocus()
    rows.set_highlight(0)
    QTest.keyClick(rows, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    assert picker.value == ["sg_status_list", "code", "entity.Shot.sg_turnover_date"]
    assert rows.carrying is None


def test_delete_removes_the_row_under_the_cursor(qtbot):
    picker = build(qtbot, value=COLUMNS)
    settled(qtbot, picker)
    rows = picker.chosen_list
    rows.setFocus()
    rows.set_highlight(1)
    QTest.keyClick(rows, Qt.Key.Key_Delete)
    assert picker.value == ["code", "entity.Shot.sg_turnover_date"]


def test_picking_a_field_appends_it_and_takes_it_off_the_list(qtbot):
    picker = build(qtbot, value=["code"])
    settled(qtbot, picker)
    assert "code" in (picker.field_picker.exclude or [])
    assert all(one.path != "code" for one in picker.field_picker.options)
    seen: list = []
    picker.value_changed.connect(lambda value: seen.append(list(value)))
    inner = picker.field_picker
    inner.set_open(True)
    spin(qtbot, 60)
    row = inner.rows_model.keys().index("description")
    inner.control.list_surface().set_highlight(row)
    QTest.keyClick(search_caret(inner), Qt.Key.Key_Return)
    settled(qtbot, picker)
    assert seen[-1] == ["code", "description"]
    assert picker.value == ["code", "description"]
    assert "description" in (inner.exclude or [])
    # The picker clears as soon as the path is appended, so the next pick starts empty.
    assert inner.value == ""


def test_the_dual_layout_checks_the_chosen_fields(qtbot):
    picker = build(qtbot, entity_type="Shot", layout="dual", value=["code"])
    settled(qtbot, picker)
    spin(qtbot, 200)
    assert picker.available.list_surface().row_count() > 0
    seen: list = []
    picker.value_changed.connect(lambda value: seen.append(list(value)))
    keys = picker.levels.rows(picker.available.query)
    row = next(i for i, one in enumerate(keys) if one.path == "description")
    picker.available.activated.emit(row)
    assert seen[-1] == ["code", "description"]
    # A second press on the same row takes it off again.
    picker.available.activated.emit(row)
    assert seen[-1] == ["code"]


def test_the_panes_stack_under_the_breakpoint(qtbot):
    picker = build(qtbot, entity_type="Shot", layout="dual", value=["code"])
    settled(qtbot, picker)
    panes = picker.findChild(QWidget, "column-picker-panes")
    picker.setFixedWidth(DUAL_BREAKPOINT + 80)
    spin(qtbot, 30)
    wide = picker.findChild(QWidget, "column-picker-available").geometry()
    chosen = picker.findChild(QWidget, "column-picker-chosen").geometry()
    assert wide.left() != chosen.left(), "the two panes stand side by side"
    picker.setFixedWidth(DUAL_BREAKPOINT - 120)
    spin(qtbot, 30)
    assert panes.width() < DUAL_BREAKPOINT
    narrow = picker.findChild(QWidget, "column-picker-available").geometry()
    stacked = picker.findChild(QWidget, "column-picker-chosen").geometry()
    assert narrow.left() == stacked.left(), "and stack under the breakpoint"


def test_readonly_drops_the_picker_and_the_controls(qtbot):
    picker = build(qtbot, value=COLUMNS, readonly=True)
    settled(qtbot, picker)
    assert not picker.field_picker.isVisibleTo(picker)
    rows = picker.chosen_list
    rows.setFocus()
    rows.set_highlight(0)
    QTest.keyClick(rows, Qt.Key.Key_Delete)
    assert picker.value == COLUMNS
    QTest.keyClick(rows, Qt.Key.Key_Space)
    assert rows.carrying is None


def test_the_empty_line_stands_in_for_the_list(qtbot):
    picker = build(qtbot, value=[])
    settled(qtbot, picker)
    empty = picker.findChild(QWidget, "column-picker-empty")
    assert empty is not None and empty.isVisibleTo(picker)
    assert not picker.chosen_list.isVisibleTo(picker)


def test_a_press_on_the_cross_removes_the_row(qtbot):
    picker = build(qtbot, value=COLUMNS)
    settled(qtbot, picker)
    labelled(qtbot, picker)
    rows = picker.chosen_list
    rect = rows.visualRect(rows.model().index(1, 0))
    QTest.mouseClick(
        rows.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(rect.right() - 6, rect.center().y()),
    )
    spin(qtbot, 20)
    assert picker.value == ["code", "entity.Shot.sg_turnover_date"]


def test_the_field_picker_keeps_the_contract(qtbot):
    picker = build(qtbot, entity_type="Shot", value=[])
    settled(qtbot, picker)
    inner = picker.field_picker
    # The column picker consumes a pick at once and clears the picker, which leaves the
    # control's keys where they were, so the checker watches the pick here instead.
    inner.value_changed.disconnect()
    picked: list = []
    inner.value_changed.connect(picked.append)
    checked = check_contract(
        qtbot,
        inner,
        PickerShape(inline=False, clearable=False, settle=lambda: spin(qtbot, 60)),
    )
    assert picked, "Enter took the highlighted field"
    assert "press toggles" in checked
    assert "outside press" in checked
    assert "readonly" in checked


def test_a_drag_emits_the_new_order_once_on_the_release(qtbot):
    """Upstream's `endDrag` emits once per gesture; the rows give way in between."""
    picker = build(qtbot, value=COLUMNS)
    labelled(qtbot, picker)
    heard: list = []
    picker.value_changed.connect(lambda value: heard.append(list(value)))
    chosen = picker.chosen_list
    rows = chosen.viewport()
    third = chosen.visualRect(chosen.model().index(2, 0))
    grip = QPoint(third.left() + 12, third.center().y())
    QTest.mousePress(rows, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip)
    drag_move(rows, QPoint(grip.x(), grip.y() - 8))
    first = chosen.visualRect(chosen.model().index(0, 0))
    drag_move(rows, QPoint(first.left() + 12, first.center().y()))
    spin(qtbot, 20)
    assert heard == [], "the rows gave way but nothing was emitted before the release"
    assert chosen.paths != COLUMNS, "the rows never gave way"
    QTest.mouseRelease(
        rows,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(first.left() + 12, first.center().y()),
    )
    spin(qtbot, 40)
    assert len(heard) == 1
    assert heard[0] == picker.value == chosen.paths


def test_a_cancelled_drag_puts_the_row_back_and_emits_nothing(qtbot):
    picker = build(qtbot, value=COLUMNS)
    labelled(qtbot, picker)
    heard: list = []
    picker.value_changed.connect(heard.append)
    chosen = picker.chosen_list
    rows = chosen.viewport()
    first = chosen.visualRect(chosen.model().index(0, 0))
    grip = QPoint(first.left() + 12, first.center().y())
    QTest.mousePress(rows, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip)
    drag_move(rows, QPoint(grip.x(), grip.y() + 8))
    third = chosen.visualRect(chosen.model().index(2, 0))
    drag_move(rows, QPoint(third.left() + 12, third.center().y()))
    QTest.keyClick(chosen, Qt.Key.Key_Escape)
    spin(qtbot, 40)
    assert heard == []
    assert picker.value == chosen.paths == COLUMNS


def test_a_keyboard_move_still_emits_one_order_per_step(qtbot):
    picker = build(qtbot, value=COLUMNS)
    labelled(qtbot, picker)
    heard: list = []
    picker.value_changed.connect(lambda value: heard.append(list(value)))
    chosen = picker.chosen_list
    chosen.setFocus(Qt.FocusReason.TabFocusReason)
    chosen.set_highlight(0)
    QTest.keyClick(chosen, Qt.Key.Key_Space)
    QTest.keyClick(chosen, Qt.Key.Key_Down)
    spin(qtbot, 20)
    assert heard == [[COLUMNS[1], COLUMNS[0], COLUMNS[2]]]
    QTest.keyClick(chosen, Qt.Key.Key_Space)
    spin(qtbot, 20)
    assert len(heard) == 1, "the drop emitted an order of its own"


def test_a_read_only_row_keeps_no_room_for_a_grip(qtbot):
    """Upstream's read-only row is the label alone: no grip, and none of its inset."""
    picker = build(qtbot, value=COLUMNS, readonly=True)
    labelled(qtbot, picker)
    assert picker.chosen_list.row_delegate().thumbnail is False
    picker.set_readonly(False)
    spin(qtbot, 20)
    assert picker.chosen_list.row_delegate().thumbnail is True


def test_the_grip_is_drawn_bare_rather_than_on_a_picture_plate(qtbot):
    picker = build(qtbot, value=COLUMNS)
    assert picker.chosen_list.row_delegate().bare_glyph is True


def test_the_cross_rides_the_size_ladder(qtbot):
    from sg_widgets_qt.widgets.column_picker import LEAD_GLYPH, _remove_painter

    sizes = {}
    for step in ("sm", "md", "lg"):
        picker = build(qtbot, value=COLUMNS, size=step)
        sizes[step] = picker.chosen_list.rows_model._size
    assert sizes == {"sm": "sm", "md": "md", "lg": "lg"}
    # The painter each step answers draws its own glyph, on the ladder upstream's own uses.
    assert LEAD_GLYPH["sm"] != LEAD_GLYPH["lg"]
    assert callable(_remove_painter("lg"))


def test_a_change_of_root_drops_the_labels_the_old_one_resolved(qtbot):
    """A label belongs to the type the path starts on, so a new root re-resolves it."""
    picker = build(qtbot, entity_type="Version", value=["code"])
    labelled(qtbot, picker)
    before = picker.chosen_list.rows_model.parts_of("code")
    assert before
    picker.set_entity_type("Shot")
    assert picker.chosen_list.rows_model.parts_of("code") is None
    labelled(qtbot, picker)
    assert picker.chosen_list.rows_model.parts_of("code")


def test_the_dual_list_names_the_field_code_beside_its_label(qtbot):
    from sg_widgets_qt.primitives.roles import Roles

    picker = build(qtbot, entity_type="Shot", layout="dual", value=[])
    settled(qtbot, picker)
    model = picker.available.list_surface().model()
    codes = [model.index(row, 0).data(Roles.CODE) for row in range(model.rowCount())]
    assert any(codes), "no row names its programmatic field code"
