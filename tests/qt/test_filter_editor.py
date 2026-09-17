"""The filter tree, edited: rows, groups, operators, values, issues and the wire payload."""
from __future__ import annotations

import time

from qtpy.QtCore import QRect, Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.filter import EntityRef, FilterGroup, condition, group, to_api3_hash
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_qt.primitives.button import Button
from sg_widgets_qt.primitives.remove_control import RemoveControl
from sg_widgets_qt.primitives.select import Select
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.filter_editor import FilterEditor
from sg_widgets_qt.widgets.list_picker import ListPicker
from sg_widgets_qt.widgets.number_editor import NumberEditor
from sg_widgets_qt.widgets.status_multi_picker import StatusMultiPicker
from sg_widgets_qt.widgets.text_editor import TextEditor

#: Every filterable data type the stress drive walks, as the rows it builds on Version.
STRESS_PATHS = [
    "code",
    "sg_first_frame",
    "sg_movie_frame_rate",
    "sg_client_approved",
    "created_at",
    "sg_version_type",
    "sg_status_list",
    "user",
    "playlists",
    "image",
    "entity.Shot.sg_complexity",
    "entity.Shot.sg_working_duration",
    "entity.Shot.sg_turnover_date",
]


def context_for():
    return create_sg_context(MockClient(seed=1, latency_ms=0, now=MOCK_NOW), SgContextOptions())


def spin(qtbot, ms: int = 400) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(5)


def build(qtbot, **props) -> FilterEditor:
    props.setdefault("entity_type", "Version")
    props.setdefault("context", context_for())
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(1000, 700)
    editor = FilterEditor(parent=root, **props)
    editor.setGeometry(10, 10, 980, 680)
    root.show()
    qtbot.waitExposed(root)
    settled(qtbot, editor)
    editor.test_root = root
    return editor


def settled(qtbot, editor: FilterEditor, ms: int = 4000) -> None:
    """Spin until the fields, every dotted leaf and every row's own cells have landed.

    The rows past the first build one to a turn of the loop, so a tree of ten is ready a few
    turns after the schema is.
    """
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if editor.fields() and not editor.unresolved("code") and editor.pending_rows() == 0:
            break
        qtbot.wait(5)
    spin(qtbot, 60)


def buttons(editor: FilterEditor, name: str) -> list[Button]:
    return editor.findChildren(Button, name)


def crosses(editor: FilterEditor, name: str = "filter-remove") -> list[RemoveControl]:
    """The remove controls. They are `RemoveControl`, not buttons: a cross is the glyph and its
    2px, so it sits level with the row rather than standing an icon button's height over it."""
    return editor.findChildren(RemoveControl, name)


def test_add_condition_appends_a_blank_row(qtbot):
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    assert len(editor.rows()) == 1
    buttons(editor, "filter-add-condition")[0].clicked.emit()
    spin(qtbot)
    assert len(editor.rows()) == 2
    assert editor.value.conditions[1].path == ""


def test_remove_condition_drops_the_row(qtbot):
    editor = build(
        qtbot,
        value=group("and", [condition("code", "contains", "sh"), condition("sg_first_frame", "is", 1)]),
    )
    seen: list = []
    editor.changed.connect(seen.append)
    crosses(editor)[-1].clicked.emit()
    spin(qtbot)
    assert len(editor.rows()) == 1
    assert [c.path for c in editor.value.conditions] == ["code"]
    assert len(seen) == 1


def test_changing_the_operator_applies_the_preset(qtbot):
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    select = editor.findChildren(Select, "filter-operator")[0]
    assert "starts_with" in [value for value, _label in select.items]
    select.value_changed.emit("starts_with")
    spin(qtbot)
    assert editor.value.conditions[0].operator == "starts_with"
    assert editor.value.conditions[0].value == "sh"


def test_the_value_editor_swaps_with_the_data_type(qtbot):
    editor = build(
        qtbot,
        value=group(
            "and",
            [
                condition("code", "contains", "sh"),
                condition("sg_status_list", "in", ["rev"]),
                condition("sg_first_frame", "is", 1001),
                condition("sg_version_type", "is", "Type A"),
            ],
        ),
    )
    rows = editor.rows()
    assert rows[0].findChild(TextEditor) is not None
    assert rows[1].findChild(StatusMultiPicker) is not None
    assert rows[2].findChild(NumberEditor) is not None
    assert rows[3].findChild(ListPicker) is not None


def test_a_group_nests_under_the_root(qtbot):
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    buttons(editor, "filter-add-group")[0].clicked.emit()
    spin(qtbot)
    nested = editor.value.conditions[-1]
    assert nested.kind == "group"
    assert nested.logical_operator == "or"
    assert len(editor.findChildren(QWidget, "filter-group")) == 2


def test_the_wire_payload_equals_cores_serialisation_of_the_tree(qtbot):
    tree = group(
        "and",
        [
            condition("sg_status_list", "in", ["rev", "vwd"]),
            condition("entity.Shot.sg_sequence", "is", EntityRef(type="Sequence", id=100)),
            group("or", [condition("code", "contains", "comp"), condition("created_at", "in_last", [3, "MONTH"])]),
        ],
    )
    editor = build(qtbot, value=tree)
    assert to_api3_hash(editor.value) == to_api3_hash(tree)
    assert to_api3_hash(editor.value) == {
        "logical_operator": "and",
        "conditions": [
            ["sg_status_list", "in", ["rev", "vwd"]],
            ["entity.Shot.sg_sequence", "is", {"type": "Sequence", "id": 100}],
            {
                "logical_operator": "or",
                "conditions": [
                    ["code", "contains", "comp"],
                    ["created_at", "in_last", [3, "MONTH"]],
                ],
            },
        ],
    }


def test_an_issue_shows_on_an_incomplete_condition(qtbot):
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    assert editor.issues() == []
    assert editor.error is None
    seen: list = []
    editor.error_changed.connect(seen.append)
    buttons(editor, "filter-add-condition")[0].clicked.emit()
    spin(qtbot)
    assert editor.issues() == ["Pick a field."]
    assert editor.error == "Pick a field."
    assert seen == ["Pick a field."]


def test_a_keyboard_reorder_moves_the_row_and_emits_the_tree(qtbot):
    editor = build(
        qtbot,
        value=group(
            "and", [condition("code", "contains", "sh"), condition("sg_first_frame", "is", 1001)]
        ),
    )
    seen: list = []
    editor.changed.connect(seen.append)
    announced: list = []
    editor.announced.connect(announced.append)
    body = editor.root_group().body()
    assert body.sortable().move_by(0, 1)
    spin(qtbot)
    assert [c.path for c in editor.value.conditions] == ["sg_first_frame", "code"]
    assert len(seen) == 1
    assert announced and "position 2 of 2" in announced[-1]


def test_every_filterable_type_draws_one_row_with_its_own_editor(qtbot):
    """The stress drive's matrix: every data type on Version builds a row that serialises."""
    tree = group("and", [condition(path, "is", None) for path in STRESS_PATHS])
    editor = build(qtbot, value=tree)
    settled(qtbot, editor)
    spin(qtbot, 600)
    assert len(editor.rows()) == len(STRESS_PATHS)
    for row in editor.rows():
        assert row.height() > 0
    # Every row still serialises: an unfilled value is dropped rather than sent.
    assert to_api3_hash(editor.value) is not None


def test_a_field_that_takes_no_filter_says_so_in_place(qtbot):
    """`url` takes no filter at all, so a tree holding one reads as a row that cannot run."""
    editor = build(qtbot, value=group("and", [condition("sg_uploaded_movie", "is", None)]))
    settled(qtbot, editor)
    spin(qtbot, 200)
    assert editor.data_type_of("sg_uploaded_movie") == "url"
    assert editor.issues() == ["Uploaded Movie cannot be filtered on."]


def test_the_and_or_toggle_rewrites_the_group(qtbot):
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    logic = editor.findChild(QWidget, "filter-logic")
    logic.value_changed.emit("or")
    spin(qtbot)
    assert editor.value.logical_operator == "or"


def test_a_disabled_editor_blocks_every_control(qtbot):
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]), disabled=True)
    assert not editor.isEnabled()
    editor.set_disabled(False)
    spin(qtbot)
    assert editor.isEnabled()


def test_a_redraw_keeps_the_rows_whose_condition_did_not_change(qtbot):
    """A row costs a field picker, a menu and a value control; an untouched one is kept."""
    editor = build(
        qtbot,
        value=group(
            "and",
            [
                condition("code", "contains", "sh"),
                condition("sg_status_list", "in", ["rev"]),
                condition("sg_first_frame", "is", 1001),
            ],
        ),
    )
    before = editor.rows()
    assert len(before) == 3
    select = editor.findChildren(Select, "filter-operator")[0]
    select.value_changed.emit("starts_with")
    spin(qtbot)
    after = editor.rows()
    assert len(after) == 3
    # The row that changed was built afresh; its neighbours stand where they were.
    assert after[0] is not before[0]
    assert after[1] is before[1]
    assert after[2] is before[2]


def test_the_rows_past_the_first_build_one_to_a_turn(qtbot):
    """A tall tree never holds the GUI thread: the rest stand on a skeleton until their turn."""
    tree = group("and", [condition(path, "is", None) for path in STRESS_PATHS])
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(1000, 900)
    editor = FilterEditor(entity_type="Version", context=context_for(), value=tree, parent=root)
    editor.setGeometry(10, 10, 980, 880)
    root.show()
    qtbot.waitExposed(root)
    assert editor.pending_rows() == len(STRESS_PATHS) - 1
    settled(qtbot, editor)
    assert editor.pending_rows() == 0
    assert len(editor.rows()) == len(STRESS_PATHS)
    assert all(row.filled for row in editor.rows())


def test_the_all_and_any_toggle_wears_its_own_border(qtbot):
    """`variant="outline"` upstream: the pair reads as one control of its own."""
    from sg_widgets_qt.primitives.checkbox import ToggleGroup

    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    logic = editor.findChild(ToggleGroup, "filter-logic")
    assert logic.variant == "outline"
    assert [t.variant for t in logic.toggles()] == ["outline", "outline"]


def test_rows_removed_and_the_editor_deleted_mid_read_leave_nothing_behind(qtbot):
    """A job outlives the widget that asked for it; PyQt5 crashes rather than raising.

    The editor is built on a tall tree, its rows are dropped while the schema is still out and
    the whole thing is deleted a moment later, then the loop is turned long enough for every
    answer to come back. Nothing may reach a widget that has gone.
    """
    tree = group("and", [condition(path, "is", None) for path in STRESS_PATHS])
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(1000, 900)
    editor = FilterEditor(entity_type="Version", context=context_for(), value=tree, parent=root)
    editor.setGeometry(10, 10, 980, 880)
    root.show()
    qtbot.waitExposed(root)

    # Mid-read: the rows stand on their skeletons and the answers are still out.
    assert editor.reading()
    while editor.value.conditions:
        editor.remove([0])
    QApplication.processEvents()
    editor.setParent(None)
    editor.deleteLater()
    del editor
    spin(qtbot, 500)
    # A second editor on the same context still reads, so the pool was not left broken.
    after = FilterEditor(entity_type="Version", context=context_for(), value=group("and", []), parent=root)
    settled(qtbot, after)
    assert after.fields()


def list_lines(editor: FilterEditor) -> list[QWidget]:
    """The lines a list-shaped value draws, one to a value."""
    return editor.findChildren(QWidget, "filter-list-value")


def test_adding_and_removing_a_list_value_draws_the_lines_again(qtbot):
    """The `Value` button and the crosses beside a list draw the lines the new list needs.

    A value typed into a row leaves the tree standing, so a caret is never rebuilt out from
    under the person typing (`FilterEditor.set_condition_value`). Adding a value and taking one
    away change how many lines there are, so `_ListValues` draws its own again: without that the
    button moved the tree and nothing on the page followed it.
    """
    editor = build(qtbot, value=group("and", [condition("sg_first_frame", "in", [1001, 1101])]))
    assert len(list_lines(editor)) == 2

    add = buttons(editor, "filter-list-add")[0]
    QTest.mouseClick(
        add, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, add.rect().center()
    )
    spin(qtbot)
    assert editor.value.conditions[0].value == [1001, 1101, ""]
    assert len(list_lines(editor)) == 3

    cross = crosses(editor, "filter-list-remove")[-1]
    QTest.mouseClick(
        cross, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, cross.rect().center()
    )
    spin(qtbot)
    assert editor.value.conditions[0].value == [1001, 1101]
    assert len(list_lines(editor)) == 2


def test_a_cross_beside_a_list_value_drops_the_one_it_stands_on(qtbot):
    """Each cross keeps pointing at its own value after the list has been added to.

    The lines were built once from the value the row opened on, so every cross went on asking
    for an index into that first list: the second cross dropped two values at once.
    """
    editor = build(qtbot, value=group("and", [condition("sg_first_frame", "in", [1001, 1101])]))
    buttons(editor, "filter-list-add")[0].clicked.emit()
    spin(qtbot)
    crosses(editor, "filter-list-remove")[0].clicked.emit()
    spin(qtbot)
    assert editor.value.conditions[0].value == [1101, ""]
    assert len(list_lines(editor)) == 2


def every_control_tree() -> FilterGroup:
    """One row per kind of value control a condition can draw.

    The kinds are the ones the showcase's own tree carries: a text, a number with steppers, a day,
    an instant, a colour with its swatch, a status list, a linked row, a list of values, the
    relative-date pair and a multi-value list.
    """
    return group(
        "and",
        [
            condition("code", "contains", "comp"),
            condition("sg_first_frame", "greater_than", 1001),
            condition("entity.Shot.sg_turnover_date", "is", "2026-09-02"),
            condition("created_at", "is", "2026-01-01T00:00:00Z"),
            condition("sg_bar_color", "is", "253,94,99"),
            condition("sg_status_list", "in", ["rev", "vwd"]),
            condition("entity.Shot.sg_sequence", "is", EntityRef(type="Sequence", id=100, name="sh010")),
            condition("sg_version_type", "in", ["Type A", "Type B"]),
            condition("created_at", "in_last", [3, "MONTH"]),
            condition("sg_first_frame", "in", [1001, 1101]),
        ],
    )


def axis_of(row: QWidget, part: QWidget) -> int:
    """The centre line one control stands on, measured in the row it stands in."""
    top = part.mapTo(row, part.rect().topLeft()).y()
    return top + part.height() // 2


def named_in(root: QWidget, name: str) -> QWidget:
    found = root.findChildren(QWidget, name)
    assert found, f"no {name} in the row"
    return found[0]


def test_a_multi_value_row_keeps_every_control_on_its_first_line(qtbot):
    """A row whose value grew onto three lines keeps the field and the operator on the first.

    The first value line sits at the top of the row, the field, the operator, the grip and the
    remove control read level with it, and the add row stands under the last value: a value
    list pushes only the rows under it, never the controls beside it. Upstream's row is
    `items-start` the same way.
    """
    editor = build(qtbot, value=group("and", [condition("sg_first_frame", "in", [1001, 1101])]))
    at_its_own_height(qtbot, editor)

    row = editor.rows()[0]
    lines = row.findChildren(QWidget, "filter-list-value")
    assert len(lines) == 2
    field = named_in(row, "filter-field")
    operator = named_in(row, "filter-operator")
    add = named_in(row, "filter-list-add")
    remove = named_in(row, "filter-remove")
    grip = named_in(row, "filter-grip")

    first, second = (axis_of(row, one) for one in lines)
    assert first < second, (first, second)
    for part in (field, operator, remove, grip):
        assert axis_of(row, part) == first, part.objectName()
    # The add row stands under the last value.
    assert axis_of(row, add) > second
    # The lines are the gap apart upstream gives them, with the add row the same gap under.
    assert second - first == axis_of(row, add) - second


def value_control(row: QWidget) -> QWidget | None:
    """The control a row draws for its value, or None where the operator takes none."""
    cells = row.findChildren(QWidget, "filter-value")
    if not cells:
        return None
    for one in cells[0].findChildren(QWidget):
        if getattr(one, "slot_path", None) is not None:
            return one
    return None


def at_its_own_height(qtbot, editor: FilterEditor, width: int = 1380) -> None:
    """Stand the editor at the height its own tree asks for.

    A caller's box is not the tree's height, and a `_ConditionRow` given more room than it wants
    stretches into it, which would put the cells somewhere no page ever puts them.
    """
    editor.test_root.resize(width + 20, 2000)
    for _ in range(3):
        root = editor.root_group()
        wanted = root.sizeHint().height() if root is not None else editor.sizeHint().height()
        editor.setGeometry(10, 10, width, max(60, wanted))
        spin(qtbot, 200)


def test_the_grip_and_the_cross_keep_the_value_s_first_line(qtbot):
    """One value tall and the grip, the cross and that value all read on one line."""
    editor = build(qtbot, value=group("and", [condition("code", "contains", "sh")]))
    at_its_own_height(qtbot, editor)

    row = editor.rows()[0]
    value = value_control(row)
    assert value is not None
    assert axis_of(row, named_in(row, "filter-grip")) == axis_of(row, value)
    assert axis_of(row, named_in(row, "filter-remove")) == axis_of(row, value)


def test_every_value_control_fits_the_cell_it_is_put_in(qtbot):
    """No data type draws a control the row then cuts the edge off.

    The focus ring is painted inward from the control's own rect, so a control that fits needs no
    room beyond it; what has to hold is that the control lies inside its cell and the cell inside
    the row, at every data type and with the control focused.
    """
    editor = build(qtbot, value=every_control_tree())
    settled(qtbot, editor)
    spin(qtbot, 800)
    at_its_own_height(qtbot, editor)

    kinds: set[str] = set()
    seen = 0
    cut: list = []
    for row in editor.rows():
        value = value_control(row)
        if value is None:
            continue
        seen += 1
        kinds.add(type(value).__name__)
        cell = named_in(row, "filter-value")
        value.setFocus(Qt.FocusReason.TabFocusReason)
        spin(qtbot, 20)
        # `ValueEditor.size` is the control's own step, not `QWidget.size`, so the rect is
        # built from the width and the height.
        at = value.mapTo(cell, value.rect().topLeft())
        in_cell = QRect(at.x(), at.y(), value.width(), value.height())
        where = cell.mapTo(row, cell.rect().topLeft())
        in_row = QRect(where.x(), where.y(), cell.width(), cell.height())
        if not cell.rect().contains(in_cell) or not row.rect().contains(in_row):
            cut.append(
                (
                    type(value).__name__,
                    (in_cell.x(), in_cell.y(), in_cell.width(), in_cell.height()),
                    (cell.width(), cell.height()),
                    (in_row.x(), in_row.y(), in_row.width(), in_row.height()),
                    (row.width(), row.height()),
                )
            )
    assert seen >= 9, seen
    assert len(kinds) >= 8, sorted(kinds)
    assert not cut, cut


def test_a_row_is_as_tall_as_the_control_it_holds(qtbot):
    """A colour swatch is a step over the control ladder, so the row grows to it rather than
    cutting it: every control's height is inside its row's."""
    tree = group(
        "and",
        [
            condition("sg_bar_color", "is", "253,94,99"),
            condition("code", "contains", "sh"),
            condition("sg_first_frame", "is", 1001),
        ],
    )
    editor = build(qtbot, value=tree)
    at_its_own_height(qtbot, editor)

    for row in editor.rows():
        value = value_control(row)
        assert value is not None
        assert value.height() <= row.height(), (type(value).__name__, value.height(), row.height())
        top = value.mapTo(row, value.rect().topLeft()).y()
        assert top >= 0 and top + value.height() <= row.height(), (
            type(value).__name__,
            top,
            value.height(),
            row.height(),
        )
