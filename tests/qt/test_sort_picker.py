"""The ordered sort keys: the trigger, the direction toggles, the reorder, and the field list."""
from __future__ import annotations

import time

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.filter_ux import SortKey
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.sort_picker import SortPicker

from .test_filter_editor import context_for, spin

KEYS = [SortKey(field="sg_status_list", direction="asc"), SortKey(field="code", direction="desc")]


def build(qtbot, **props) -> SortPicker:
    props.setdefault("entity_type", "Version")
    props.setdefault("context", context_for())
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(800, 300)
    picker = SortPicker(parent=root, **props)
    picker.setGeometry(10, 10, 400, 40)
    root.show()
    qtbot.waitExposed(root)
    labelled(qtbot, picker)
    picker.test_root = root
    return picker


def labelled(qtbot, picker: SortPicker, ms: int = 2000) -> None:
    """Spin until every key has its friendly label."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if all(picker.name_of(key.field) != key.field for key in picker.value):
            break
        qtbot.wait(5)
    spin(qtbot, 60)


def test_the_trigger_names_the_keys_and_carries_their_count(qtbot):
    picker = build(qtbot, value=list(KEYS))
    assert picker.trigger().text == "Status, Version Name"
    assert picker.sort == "sg_status_list,-code"
    one = build(qtbot, value=[SortKey(field="code", direction="asc")])
    # The count appears past one key alone.
    assert one.sort == "code"


def test_a_direction_toggle_rewrites_that_key(qtbot):
    picker = build(qtbot, value=list(KEYS))
    seen: list = []
    picker.changed.connect(lambda keys, sort: seen.append(sort))
    picker.key_rows().rows()[0].direction().value_changed.emit("desc")
    spin(qtbot, 200)
    assert picker.value[0].direction == "desc"
    assert seen == ["-sg_status_list,-code"]


def test_a_reorder_moves_the_key_and_the_sort_string_follows(qtbot):
    picker = build(qtbot, value=list(KEYS))
    announced: list = []
    picker.announced.connect(announced.append)
    seen: list = []
    picker.sort_changed.connect(seen.append)
    assert picker.key_rows().sortable().move_by(0, 1)
    spin(qtbot, 200)
    assert picker.sort == "-code,sg_status_list"
    assert [key.field for key in seen[0]] == ["code", "sg_status_list"]
    assert announced and "position 2 of 2" in announced[-1]


def test_adding_a_field_appends_it_ascending(qtbot):
    picker = build(qtbot, value=[SortKey(field="code", direction="asc")])
    seen: list = []
    picker.changed.connect(lambda keys, sort: seen.append(sort))
    picker.add("sg_status_list")
    spin(qtbot, 200)
    assert picker.sort == "code,sg_status_list"
    assert seen == ["code,sg_status_list"]


def test_removing_a_key_drops_it(qtbot):
    picker = build(qtbot, value=list(KEYS))
    picker.remove(0)
    spin(qtbot, 200)
    assert picker.sort == "-code"
    assert len(picker.key_rows().rows()) == 1


def test_a_field_already_chosen_is_not_offered_again(qtbot):
    picker = build(qtbot, value=list(KEYS))
    from sg_widgets_core.schema import FieldSchema

    chosen = FieldSchema(
        name="code", display_name="Version Name", entity_type="Version", data_type="text",
        editable=True, mandatory=False, unique=False,
    )
    assert picker.offers(chosen, "code") is False
    assert picker.offers(chosen, "description") is True
    # A type the API sorts on nothing for is never offered (026_result_order).
    summary = FieldSchema(
        name="sg_roll_up", display_name="Roll Up", entity_type="Version", data_type="summary",
        editable=False, mandatory=False, unique=False,
    )
    assert picker.offers(summary, "sg_roll_up") is False


def test_open_changed_follows_the_popover(qtbot):
    picker = build(qtbot, value=list(KEYS))
    seen: list = []
    picker.open_changed.connect(seen.append)
    picker.set_open(True)
    spin(qtbot, 200)
    assert picker.open is True
    picker.set_open(False)
    spin(qtbot, 200)
    assert seen == [True, False]


def test_the_count_is_a_chip_inside_the_trigger(qtbot):
    """Upstream draws the count inside the trigger's own border from two keys up."""
    from sg_widgets_qt.primitives.badge import Badge

    picker = build(qtbot, value=list(KEYS))
    trigger = picker.trigger()
    assert trigger.count == "2"
    assert picker.findChildren(Badge) == []
    picker.remove(1)
    spin(qtbot, 120)
    # One key names itself and carries no count, as upstream does.
    assert picker.trigger().count == ""


def until(qtbot, read, ms: int = 5000) -> bool:
    """Spin until `read` answers something truthy, or the time runs out."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        if read():
            return True
        QApplication.processEvents()
        qtbot.wait(5)
    return bool(read())


def test_a_press_in_the_field_list_adds_a_key_and_keeps_the_panel_open(qtbot):
    """The pick a reader makes: the trigger, the field picker inside the panel, a row.

    The field list is a popover standing over the panel's own popover, so the press lands in
    a window of its own. A parent that reads it as a press outside itself shuts the panel
    under the caret and the row is never taken: the pick has to survive real events.
    """
    picker = build(qtbot)
    QTest.mouseClick(
        picker.trigger(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        picker.trigger().rect().center(),
    )
    spin(qtbot, 200)
    assert picker.open is True

    control = picker.field_picker().control
    QTest.mouseClick(
        control, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, control.rect().center()
    )
    view = control.list_surface()
    assert until(qtbot, lambda: view.model().rowCount() > 0)
    assert picker.open is True, "opening the field list dismissed the panel"

    keys: list = []
    picker.sort_changed.connect(keys.append)
    wanted = picker.field_picker()._model.rows[0].path
    index = view.model().index(0, 0)
    view.scrollTo(index)
    spin(qtbot, 60)
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        view.visualRect(index).center(),
    )
    spin(qtbot, 300)

    assert picker.open is True, "the press in the field list dismissed the panel"
    assert [key.field for key in picker.value] == [wanted]
    assert [[key.field for key in one] for one in keys] == [[wanted]]
    assert picker.sort == wanted
    assert len(picker.key_rows().rows()) == 1
    assert picker.key_rows().rows()[0].direction().value == "asc"


def test_the_keyboard_takes_a_field_the_same_way(qtbot):
    picker = build(qtbot)
    picker.set_open(True)
    spin(qtbot, 200)
    control = picker.field_picker().control
    control.set_open(True)
    assert until(qtbot, lambda: control.list_surface().model().rowCount() > 0)

    keys: list = []
    picker.sort_changed.connect(keys.append)
    caret = control.caret()
    QTest.keyClick(caret, Qt.Key.Key_Down)
    spin(qtbot, 120)
    QTest.keyClick(caret, Qt.Key.Key_Return)
    spin(qtbot, 300)

    assert len(keys) == 1
    assert len(picker.value) == 1
    assert picker.open is True
    assert len(picker.key_rows().rows()) == 1


def test_escape_on_the_trigger_closes_the_panel(qtbot):
    """`Escape` closes the list, which is what the keyboard table promises.

    The panel is a popover that does not take focus, so the trigger keeps the caret: without the
    trigger forwarding its keys to the open surface the panel could only be closed by pressing
    the trigger again or the page behind it.
    """
    picker = build(qtbot, value=list(KEYS))
    picker.set_open(True)
    spin(qtbot, 200)
    assert picker.open
    picker.trigger().setFocus(Qt.FocusReason.MouseFocusReason)
    QTest.keyClick(picker.trigger(), Qt.Key.Key_Escape)
    spin(qtbot, 200)
    assert not picker.open
    assert not picker._popover.is_open  # noqa: SLF001


def test_escape_with_the_panel_shut_is_left_to_the_trigger(qtbot):
    """A key the open surface does not want falls through, so a shut picker answers nothing."""
    picker = build(qtbot, value=list(KEYS))
    assert not picker.open
    picker.trigger().setFocus(Qt.FocusReason.MouseFocusReason)
    QTest.keyClick(picker.trigger(), Qt.Key.Key_Escape)
    spin(qtbot, 120)
    assert not picker.open
    assert [key.field for key in picker.value] == ["sg_status_list", "code"]


# --- the flat list a table's toolbar hands it ----------------------------------------------

#: A table's columns, one of them through a link, as the entity-table demo offers them.
COLUMNS = ["code", "entity", "entity.Shot.sg_turnover_date", "sg_status_list"]


def flat(qtbot, picker: SortPicker, ms: int = 2000) -> None:
    """Spin until the field picker has resolved the flat list."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if not picker.field_picker().levels.loading:
            break
        qtbot.wait(5)
    spin(qtbot, 60)


def test_options_hands_the_field_picker_a_flat_list(qtbot):
    """`options` offers exactly those paths, a linked one included, with nothing to descend."""
    picker = build(qtbot, options=list(COLUMNS))
    flat(qtbot, picker)
    inner = picker.field_picker()
    assert picker.options == COLUMNS
    assert inner.levels.flat is True
    assert inner.rows_model.keys() == COLUMNS
    assert inner.levels.deep is False


def test_a_flat_list_drops_a_key_already_chosen(qtbot):
    """A flat list takes no `filter`, so the picker drops the chosen keys from it itself."""
    picker = build(qtbot, options=list(COLUMNS), value=[SortKey(field="code", direction="asc")])
    flat(qtbot, picker)
    assert picker.field_picker().rows_model.keys() == [
        "entity",
        "entity.Shot.sg_turnover_date",
        "sg_status_list",
    ]
    picker.add("sg_status_list")
    flat(qtbot, picker)
    assert picker.field_picker().rows_model.keys() == ["entity", "entity.Shot.sg_turnover_date"]


def test_a_linked_column_of_the_flat_list_becomes_a_key(qtbot):
    """The toolbar sorts on a linked column, which the nested list would have to walk to."""
    picker = build(qtbot, options=list(COLUMNS))
    flat(qtbot, picker)
    picker.field_picker().set_value("entity.Shot.sg_turnover_date")
    spin(qtbot, 200)
    assert [key.field for key in picker.value] == ["entity.Shot.sg_turnover_date"]
    assert picker.sort == "entity.Shot.sg_turnover_date"


def test_paths_is_left_alone_and_still_nests(qtbot):
    """`options` is another way, not a replacement: without it the list is the schema's."""
    picker = build(qtbot, paths=list(COLUMNS))
    assert picker.options is None
    assert picker.field_picker().levels.flat is False
    assert picker.paths == COLUMNS


def test_set_options_swaps_the_two_lists(qtbot):
    picker = build(qtbot)
    assert picker.field_picker().levels.flat is False
    picker.set_options(list(COLUMNS))
    flat(qtbot, picker)
    assert picker.field_picker().rows_model.keys() == COLUMNS
    picker.set_options(None)
    spin(qtbot, 200)
    assert picker.field_picker().levels.flat is False
