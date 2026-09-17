"""The filter tree, edited: rows, groups, operators, values, issues and the wire payload."""
from __future__ import annotations

import time

from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.filter import EntityRef, condition, group, to_api3_hash
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_qt.primitives.button import Button
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
    buttons(editor, "filter-remove")[-1].clicked.emit()
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
