"""One field of a type: the dotted path, the crumbs, the restrictions and the contract."""
from __future__ import annotations

import time

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.context import SgContextOptions, create_sg_context
from sg_widgets_core.mock import MOCK_NOW, MockClient
from sg_widgets_qt.primitives.roles import Roles
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.field_picker import CRUMB_SEPARATOR, FieldPicker

from .test_picker_contract import PickerShape, check_contract, spin

#: A path through a link the fixtures always carry: a Version links a Shot.
DOTTED = "entity.Shot.sg_turnover_date"


def context_for(latency_ms: int = 0):
    return create_sg_context(MockClient(seed=1, latency_ms=latency_ms, now=MOCK_NOW), SgContextOptions())


def build(qtbot, latency_ms: int = 0, **props):
    """One picker on a themed window."""
    props.setdefault("entity_type", "Version")
    props.setdefault("deep_links", True)
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(560, 160)
    picker = FieldPicker(context=context_for(latency_ms), parent=root, **props)
    picker.setGeometry(10, 10, 540, 40)
    root.show()
    qtbot.waitExposed(root)
    picker.test_root = root
    return picker


def settled(qtbot, picker, ms: int = 1200) -> None:
    """Spin until the schema read has landed."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if picker.options:
            break
        qtbot.wait(5)
    spin(qtbot, 30)


def search_caret(picker):
    from qtpy.QtWidgets import QLineEdit

    return picker.control.search_row().findChild(QLineEdit)


def test_a_dotted_path_resolves_and_the_crumb_draws(qtbot):
    picker = build(qtbot, value=DOTTED)
    settled(qtbot, picker)
    spin(qtbot, 200)
    assert picker.label_parts == ["Link", "Turnover Date"]
    assert picker.label == "Link" + CRUMB_SEPARATOR + "Turnover Date"
    # The control reads the friendly path, never the raw one.
    chips = picker.control.chips()
    assert len(chips) == 1
    assert chips[0].text() == picker.label
    assert chips[0].parts[:-1] == ["Link"]


def test_a_row_behind_a_hop_carries_its_crumb(qtbot):
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.set_open(True)
    spin(qtbot, 50)
    link = next(one for one in picker.rows_model.rows if one.path == "entity")
    picker._descend(link, "Shot")
    settled(qtbot, picker)
    spin(qtbot, 100)
    assert [hop.through for hop in picker.hops] == ["Shot"]
    assert picker.breadcrumb.isVisibleTo(picker.control.popup())
    assert picker.breadcrumb.text().startswith("Version")
    model = picker.rows_model
    runs = model.data(model.index(0, 0), Roles.RUNS)
    # The hop is drawn muted before the label, which is the third item of a run.
    assert runs[0] == ("Link", False, True)
    assert model.keys()[0].startswith("entity.Shot.")


def test_a_non_filterable_field_is_kept_out_when_asked(qtbot):
    every = build(qtbot, entity_type="Shot", deep_links=False)
    settled(qtbot, every)
    loose = {one.data_type for one in every.options}
    assert loose & {"url", "summary", "calculated", "password", "serializable"}

    only = build(qtbot, entity_type="Shot", deep_links=False, filterable_only=True)
    settled(qtbot, only)
    tight = {one.data_type for one in only.options}
    assert not tight & {"url", "summary", "calculated", "password", "serializable"}


def test_restrictions_keep_links_on_the_list(qtbot):
    picker = build(qtbot, data_types=["date", "date_time"])
    settled(qtbot, picker)
    kinds = {one.data_type for one in picker.options if one.selectable}
    assert kinds <= {"date", "date_time"}
    # A picker restricted to dates still lists the link fields, so a date behind one is reachable.
    assert any(one.traversable and not one.selectable for one in picker.options)


def test_a_computed_column_is_offered_and_reads_as_its_name(qtbot):
    picker = build(
        qtbot,
        entity_type="Shot",
        deep_links=False,
        extra_fields=[{"name": "row_number", "display_name": "Row Number"}],
        value="row_number",
    )
    settled(qtbot, picker)
    spin(qtbot, 60)
    assert picker.label == "Row Number"
    assert picker.options[0].computed is True
    assert picker.options[0].path == "row_number"


def test_choosing_a_field_emits_its_path_and_closes(qtbot):
    picker = build(qtbot, entity_type="Shot", deep_links=False)
    settled(qtbot, picker)
    seen: list = []
    picker.value_changed.connect(seen.append)
    picker.set_open(True)
    spin(qtbot, 60)
    surface = picker.control.list_surface()
    surface.highlight_first()
    wanted = picker.rows_model.keys()[surface.highlighted()]
    QTest.keyClick(search_caret(picker), Qt.Key.Key_Return)
    spin(qtbot, 60)
    assert seen == [wanted]
    assert picker.value == wanted
    assert not picker.open


def test_right_descends_and_left_goes_back(qtbot):
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.set_open(True)
    spin(qtbot, 60)
    keys = picker.rows_model.keys()
    row = keys.index("project")
    picker.control.list_surface().set_highlight(row)
    caret = search_caret(picker)
    QTest.keyClick(caret, Qt.Key.Key_Right)
    settled(qtbot, picker)
    spin(qtbot, 80)
    # Project declares one target type, so the hop is taken without asking.
    assert [hop.through for hop in picker.hops] == ["Project"]
    assert picker.open, "a descend never closes the list"
    QTest.keyClick(caret, Qt.Key.Key_Left)
    settled(qtbot, picker)
    spin(qtbot, 80)
    assert picker.hops == []


def test_a_link_with_several_targets_asks_which(qtbot):
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.set_open(True)
    spin(qtbot, 60)
    keys = picker.rows_model.keys()
    row = keys.index("user")
    picker.control.list_surface().set_highlight(row)
    QTest.keyClick(search_caret(picker), Qt.Key.Key_Right)
    spin(qtbot, 60)
    assert picker.levels.choosing is not None
    assert picker.rows_model.targets == ["HumanUser", "ApiUser"]
    assert picker.breadcrumb.text().endswith("Artist")


def test_the_contract(qtbot):
    picker = build(qtbot, entity_type="Shot", deep_links=False)
    settled(qtbot, picker)
    checked = check_contract(
        qtbot,
        picker,
        PickerShape(inline=False, settle=lambda: spin(qtbot, 60)),
    )
    assert "press toggles" in checked
    assert "caret on open" in checked
    assert "escape" in checked
    assert "disabled" in checked
