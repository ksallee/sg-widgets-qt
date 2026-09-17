"""The picker contract of `docs/design-rules.md` rule 7, as a checker every picker calls.

`check_contract(qtbot, picker, shape)` walks the clauses that apply to a picker's shape with
real key and mouse events and asserts each one, then answers which it checked. A picker's own
test file calls it once per shape it comes in and then asserts what is its own.

    check_contract(qtbot, picker, PickerShape(multiple=True, inline=False))
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from qtpy.QtCore import QPoint, QPointF, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.picker_control import PICKER_CHIP, PickerControl

#: Every clause of rule 7, by the name `check_contract` answers.
CLAUSES: tuple[str, ...] = (
    "press toggles",
    "caret on open",
    "escape",
    "value keys",
    "highlight in view",
    "pick",
    "outside press",
    "clear control",
    "readonly",
    "disabled",
)


@dataclass
class PickerShape:
    """What a picker is, so the checker knows which clauses apply to it."""

    #: Several keys may be chosen at once.
    multiple: bool = False
    #: The control holds the caret. A summary control keeps it in the popup instead.
    inline: bool = True
    #: A summary control keeps a search row.
    searchable: bool = True
    #: The control offers a clear control once something is chosen.
    clearable: bool = True
    #: Spin the loop until the picker's rows have landed. A static picker needs none.
    settle: Callable[[], None] | None = None
    #: The control holds what was picked. A caller that consumes a pick and clears the picker
    #: — the column picker appends the path and empties the control for the next one — leaves
    #: the keys where they were, so the clause is read on what the pick emitted instead.
    keeps_value: bool = True


def control_of(picker: Any) -> PickerControl:
    """The control box a picker is built on."""
    if isinstance(picker, PickerControl):
        return picker
    found = getattr(picker, "control", None)
    assert isinstance(found, PickerControl), "the picker is not built on PickerControl"
    return found


def spin(qtbot: Any, ms: int = 50) -> None:
    """Turn the event loop for a while, so a queued answer lands."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)


def settle(shape: PickerShape, qtbot: Any) -> None:
    if shape.settle is not None:
        shape.settle()
    else:
        spin(qtbot, 20)


def press_control(control: PickerControl) -> None:
    """A press in the middle of the control, which is not one of its own buttons."""
    QTest.mouseClick(
        control,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(control.width() // 2, control.height() // 2),
    )


def press_outside(widget: QWidget) -> None:
    """A press far from the control and its popup, which is what dismisses the list."""
    where = QPointF(-1000.0, -1000.0)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        where,
        where,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget.window(), event)


def key_target(control: PickerControl, shape: PickerShape) -> QWidget:
    """What the keys are sent to: the caret, or the control where there is none."""
    if shape.inline or shape.searchable:
        return control.caret()
    return control


def holds_caret(control: PickerControl) -> bool:
    """True while the caret is the focus widget of its own window.

    `hasFocus` asks whether the window is active too, and showing a popup deactivates the
    anchor's window on some platforms, so the question here is which widget holds the caret.
    """
    caret = control.caret()
    return caret.window().focusWidget() is caret


def set_prop(picker: Any, name: str, value: Any) -> None:
    """Set a prop on the picker, or on the control where the picker does not carry it."""
    setter = getattr(picker, f"set_{name}", None)
    if setter is None:
        setter = getattr(control_of(picker), f"set_{name}")
    setter(value)


def check_contract(qtbot: Any, picker: QWidget, shape: PickerShape) -> list:  # noqa: C901
    """Walk every clause of rule 7 that applies to this picker's shape. Answers what it checked."""
    control = control_of(picker)
    checked: list = []

    # 1. A press on the control toggles the list, the caret included, and typing opens it.
    assert not control.is_open
    press_control(control)
    settle(shape, qtbot)
    assert control.is_open, "a press on the control opens the list"
    press_control(control)
    settle(shape, qtbot)
    assert not control.is_open, "a further press closes it"
    target = key_target(control, shape)
    if shape.inline or shape.searchable:
        QTest.keyClicks(target, "a")
        settle(shape, qtbot)
        assert control.is_open, "typing opens the list"
    else:
        press_control(control)
        settle(shape, qtbot)
    checked.append("press toggles")

    # 2. The caret lands in the control's own input, or in the popup's search box.
    if shape.inline:
        assert holds_caret(control), "an inline control takes the caret itself"
    elif shape.searchable:
        assert control.search_row().isVisibleTo(control.popup())
        assert holds_caret(control), "a summary control types in the popup's search box"
    else:
        assert not control.search_row().isVisibleTo(control.popup())
    checked.append("caret on open")

    # 3. Escape closes the list and clears the query. On a closed picker it does nothing.
    QTest.keyClick(target, Qt.Key.Key_Escape)
    settle(shape, qtbot)
    assert not control.is_open, "Escape closes the list"
    assert control.query == "", "Escape clears the query"
    before = list(control.keys)
    QTest.keyClick(target, Qt.Key.Key_Escape)
    settle(shape, qtbot)
    assert not control.is_open and list(control.keys) == before, "a closed picker keeps Escape"
    checked.append("escape")

    # 4. Backspace and the arrows in an empty query belong to the value.
    if control.labels:
        count = len(control.labels)
        target.setFocus()
        QTest.keyClick(target, Qt.Key.Key_Backspace)
        settle(shape, qtbot)
        if shape.multiple:
            assert control.armed == count - 1, "Backspace takes the caret to the last chip"
            QTest.keyClick(target, Qt.Key.Key_Left)
            assert control.armed == max(0, count - 2), "the arrows walk the row"
            QTest.keyClick(target, Qt.Key.Key_Right)
            assert control.armed == count - 1
            QTest.keyClick(target, Qt.Key.Key_Down)
            settle(shape, qtbot)
            assert control.is_open, "Down on a chip opens the list"
            assert control.armed is None, "and gives the caret back"
            QTest.keyClick(target, Qt.Key.Key_Escape)
            settle(shape, qtbot)
            QTest.keyClick(target, Qt.Key.Key_Backspace)
            QTest.keyClick(target, Qt.Key.Key_Delete)
            settle(shape, qtbot)
            assert len(control.labels) < count, "Delete on a chip removes it"
        else:
            assert len(control.labels) == 0, "Backspace clears a single picker in one press"
        checked.append("value keys")

    # 5. Up and Down keep the highlighted row in view.
    press_control(control)
    settle(shape, qtbot)
    surface = control.list_surface()
    if surface.row_count() > 1:
        surface.highlight_first()
        first = surface.highlighted()
        QTest.keyClick(target, Qt.Key.Key_Down)
        settle(shape, qtbot)
        assert surface.highlighted() > first, "Down moves the highlight"
        index = surface.model().index(surface.highlighted(), 0)
        assert surface.viewport().rect().intersects(surface.visualRect(index)), "and keeps it in view"
        QTest.keyClick(target, Qt.Key.Key_Up)
        settle(shape, qtbot)
        assert surface.highlighted() == first
        checked.append("highlight in view")

    # 6. A pick keeps a multi picker open and closes a single one.
    if surface.row_count() > 0:
        surface.highlight_first()
        before = list(control.keys)
        QTest.keyClick(target, Qt.Key.Key_Return)
        settle(shape, qtbot)
        if shape.keeps_value:
            assert list(control.keys) != before, "Enter takes the highlighted row"
        assert control.is_open is bool(shape.multiple), "a pick closes a single picker only"
        checked.append("pick")

    # 7. An outside press closes the list.
    if not control.is_open:
        press_control(control)
        settle(shape, qtbot)
    press_outside(control)
    settle(shape, qtbot)
    assert not control.is_open, "a press outside closes the list"
    checked.append("outside press")

    # 8. The clear control follows `clearable`.
    if control.labels:
        assert control.clear_control().isVisibleTo(control) is bool(shape.clearable)
    set_prop(picker, "clearable", False)
    assert not control.clear_control().isVisibleTo(control)
    set_prop(picker, "clearable", shape.clearable)
    checked.append("clear control")

    # 9. Readonly keeps full contrast and drops the affordances.
    set_prop(picker, "readonly", True)
    assert control.disabled_opacity() == 1.0, "readonly keeps full contrast"
    assert not control.open_control().isVisibleTo(control), "and drops the chevron"
    assert not control.clear_control().isVisibleTo(control), "and the clear control"
    press_control(control)
    settle(shape, qtbot)
    assert not control.is_open, "a readonly control does not open"
    set_prop(picker, "readonly", False)
    checked.append("readonly")

    # 10. Disabled is inert.
    set_prop(picker, "disabled", True)
    assert control.disabled_opacity() == 0.5, "a disabled control is at half opacity"
    press_control(control)
    settle(shape, qtbot)
    assert not control.is_open, "a disabled control does not open"
    QTest.keyClicks(target, "a")
    settle(shape, qtbot)
    assert not control.is_open and control.query == "", "and takes no key"
    set_prop(picker, "disabled", False)
    checked.append("disabled")

    return checked


# --- the checker's own picker ------------------------------------------------------------

DEPARTMENTS = [
    ("layout", "Layout"),
    ("anim", "Animation"),
    ("light", "Lighting"),
    ("comp", "Compositing"),
    ("fx", "Effects"),
]


def build_static(qtbot: Any, **props: Any) -> PickerControl:
    """A picker over a fixed vocabulary, which is what the checker is checked against."""
    from qtpy.QtCore import QAbstractListModel, QModelIndex

    from sg_widgets_qt.primitives.badge import Chip
    from sg_widgets_qt.primitives.roles import Roles

    class Model(QAbstractListModel):
        def __init__(self) -> None:
            super().__init__()
            self.codes = [code for code, _ in DEPARTMENTS]

        def rowCount(self, parent=QModelIndex()):  # noqa: B008, N802
            return 0 if parent.isValid() else len(self.codes)

        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            if not index.isValid():
                return None
            if role in (Qt.ItemDataRole.DisplayRole, Roles.LABEL):
                return dict(DEPARTMENTS)[self.codes[index.row()]]
            return None

    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(420, 120)
    control = PickerControl(slot="department-picker", picker="department", parent=root, **props)
    control.setGeometry(10, 10, 400, 40)
    control.set_items([code for code, _ in DEPARTMENTS])
    control.set_row_model(Model())
    labels = dict(DEPARTMENTS)

    def chip_for(index: int):
        # A chip sits one step under the control it is in, which is rule 3's ladder.
        return Chip(labels[control.keys[index]], size=PICKER_CHIP[control.size], removable=True)

    control.set_chip_factory(chip_for)
    control.selected.connect(lambda keys: _settle(control, keys, labels))
    control.remove_requested.connect(lambda i: _settle(control, [k for j, k in enumerate(control.keys) if j != i], labels))
    control.cleared.connect(lambda: _settle(control, [], labels))
    root.show()
    qtbot.waitExposed(root)
    # The window owns the control, and nothing owns the window, so the test holds it here.
    control.test_root = root
    return control


def _settle(control: PickerControl, keys: list, labels: dict) -> None:
    control.set_keys(keys)
    control.set_labels([labels[key] for key in keys])


def test_contract_on_a_single_inline_picker(qtbot):
    control = build_static(qtbot)
    checked = check_contract(qtbot, control, PickerShape())
    assert "press toggles" in checked and "disabled" in checked


def test_contract_on_a_multi_token_field(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True)
    _settle(control, ["layout", "anim"], dict(DEPARTMENTS))
    checked = check_contract(qtbot, control, PickerShape(multiple=True))
    assert "value keys" in checked and "pick" in checked


def test_contract_on_a_summary_trigger(qtbot):
    control = build_static(qtbot, multiple=True, chip_row=True, inline=False, summary="ellipsis")
    _settle(control, ["layout", "anim"], dict(DEPARTMENTS))
    checked = check_contract(qtbot, control, PickerShape(multiple=True, inline=False))
    assert "caret on open" in checked


def test_contract_on_a_fixed_set(qtbot):
    control = build_static(
        qtbot, inline=False, searchable=False, text_value=True, anchored=True
    )
    checked = check_contract(
        qtbot, control, PickerShape(inline=False, searchable=False)
    )
    assert "outside press" in checked
