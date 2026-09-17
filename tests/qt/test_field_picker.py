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
        if picker.derived:
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


def test_a_row_behind_a_hop_is_its_label_alone(qtbot):
    """The trail is the breadcrumb bar's to say; upstream draws `row.displayName` alone."""
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
    index = model.index(0, 0)
    runs = model.data(index, Roles.RUNS)
    assert "".join(run[0] for run in runs) == model.data(index, Roles.LABEL)
    assert CRUMB_SEPARATOR not in "".join(run[0] for run in runs)
    assert not any(run[2] for run in runs), "a run is drawn muted before the label"
    assert model.keys()[0].startswith("entity.Shot.")


def test_a_non_filterable_field_is_kept_out_when_asked(qtbot):
    every = build(qtbot, entity_type="Shot", deep_links=False)
    settled(qtbot, every)
    loose = {one.data_type for one in every.derived}
    assert loose & {"url", "summary", "calculated", "password", "serializable"}

    only = build(qtbot, entity_type="Shot", deep_links=False, filterable_only=True)
    settled(qtbot, only)
    tight = {one.data_type for one in only.derived}
    assert not tight & {"url", "summary", "calculated", "password", "serializable"}


def test_restrictions_keep_links_on_the_list(qtbot):
    picker = build(qtbot, data_types=["date", "date_time"])
    settled(qtbot, picker)
    kinds = {one.data_type for one in picker.derived if one.selectable}
    assert kinds <= {"date", "date_time"}
    # A picker restricted to dates still lists the link fields, so a date behind one is reachable.
    assert any(one.traversable and not one.selectable for one in picker.derived)


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
    assert picker.derived[0].computed is True
    assert picker.derived[0].path == "row_number"


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


def shown_row(picker, wanted):
    """A row of the open list as the view itself indexes it, which is what `visualRect` takes."""
    surface = picker.control.list_surface()
    model = surface.model()
    for row in range(model.rowCount()):
        index = model.index(row, 0)
        option = picker.rows_model.option_at(row)
        if option is not None and wanted(option):
            return index
    raise AssertionError("no row of the open list answers that")


def test_a_link_row_carries_the_delegate_s_own_drill_chevron(qtbot):
    """Upstream's descend mark is a 16px button in the row, not a cell that eats the label."""
    from sg_widgets_qt.primitives.row_delegate import DRILL_WIDTH

    picker = build(qtbot)
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    surface = picker.control.list_surface()
    index = shown_row(picker, lambda one: one.traversable)
    assert index.data(Roles.DRILLABLE) is True
    assert index.data(Roles.PAINTER) is None, "the chevron still takes a painter cell"
    rect = surface.visualRect(index)
    assert rect.width() > 0, "the row is not laid out"
    mark = surface.row_delegate().drill_rect(rect, index)
    assert mark.width() == DRILL_WIDTH
    assert rect.contains(mark), "the mark is drawn outside its row"
    flat = shown_row(picker, lambda one: not one.traversable)
    assert flat.data(Roles.DRILLABLE) is False


def test_a_press_on_the_chevron_descends_and_one_beside_it_does_not(qtbot):
    from qtpy.QtCore import QPoint

    def link_row(picker):
        return shown_row(picker, lambda one: one.traversable and one.selectable)

    # A press beside the mark chooses the link, as it does on any other row.
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    surface = picker.control.list_surface()
    index = link_row(picker)
    rect = surface.visualRect(index)
    QTest.mouseClick(
        surface.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(rect.left() + 40, rect.center().y()),
    )
    spin(qtbot, 120)
    assert not picker.levels.deep, "a press on the label descended"
    assert picker.value, "a press on the label of a link chose nothing"

    # A press on the mark itself descends and leaves the value alone.
    other = build(qtbot)
    settled(qtbot, other)
    other.control.set_open(True)
    spin(qtbot, 60)
    surface = other.control.list_surface()
    index = link_row(other)
    mark = surface.row_delegate().drill_rect(surface.visualRect(index), index)
    QTest.mouseClick(
        surface.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        mark.center(),
    )
    spin(qtbot, 200)
    assert other.levels.deep, "a press on the chevron did not descend"
    assert other.value == "", "a press on the chevron chose the link"


def test_the_search_box_asks_which_type_while_a_link_is_being_resolved(qtbot):
    from sg_widgets_qt.widgets.field_picker import CHOOSING_PLACEHOLDER

    picker = build(qtbot, search_placeholder="Search fields…")
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    assert picker.control.search_placeholder == "Search fields…"
    link = next(one for one in picker.derived if one.traversable and len(one.targets) > 1)
    picker.levels.descend_into(link)
    spin(qtbot, 60)
    assert picker.levels.choosing is not None
    assert picker.control.search_placeholder == CHOOSING_PLACEHOLDER
    assert picker.search_placeholder == "Search fields…", "the caller's own is kept"
    picker.levels.reset()
    spin(qtbot, 200)
    assert picker.control.search_placeholder == "Search fields…"


def test_back_and_reset_from_the_bar_clear_the_query(qtbot):
    """Upstream's `back()` and `reset()` both clear the search box, as the Left key does."""
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    link = next(one for one in picker.derived if one.traversable)
    picker.levels.descend_into(link)
    spin(qtbot, 200)
    picker.control.set_query("dat")
    spin(qtbot, 20)
    picker.breadcrumb.back_button.clicked.emit()
    spin(qtbot, 200)
    assert picker.control.query == ""

    picker.levels.descend_into(link)
    spin(qtbot, 200)
    picker.control.set_query("dat")
    spin(qtbot, 20)
    picker.breadcrumb.reset_button.clicked.emit()
    spin(qtbot, 200)
    assert picker.control.query == ""
    assert not picker.levels.deep


def test_the_first_row_is_the_cursor_the_moment_the_list_opens(qtbot):
    """Upstream's Command is `autoHighlight="always"`, so Right acts without a Down first."""
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    assert picker.control.highlight_on_open is True
    assert picker.control.list_surface().highlighted() == 0


def test_the_data_type_glyph_is_drawn_bare(qtbot):
    """A field row has no picture to stand in for, so the glyph takes no plate."""
    picker = build(qtbot)
    assert picker.control.list_surface().row_delegate().bare_glyph is True


def test_the_list_wraps_past_its_last_row(qtbot):
    """Upstream's Command takes `loop`, so ArrowDown past the end comes back to the top."""
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    surface = picker.control.list_surface()
    rows = surface.row_count()
    assert rows > 2
    surface.set_highlight(rows - 1)
    caret = search_caret(picker)
    QTest.keyClick(caret, Qt.Key.Key_Down)
    spin(qtbot, 20)
    assert surface.highlighted() == 0, "the list held at its last row"
    QTest.keyClick(caret, Qt.Key.Key_Up)
    spin(qtbot, 20)
    assert surface.highlighted() == rows - 1, "the list held at its first row"


def test_a_schema_read_stands_behind_two_line_skeletons(qtbot):
    """Upstream's block is a label bar over a sub-label bar, three times over."""
    from sg_widgets_qt.primitives.skeleton import Skeleton
    from sg_widgets_qt.widgets.field_picker import ROW_SKELETON_ROWS, FieldSkeletons

    picker = build(qtbot, latency_ms=400)
    picker.control.set_open(True)
    spin(qtbot, 30)
    block = picker.control.popup().findChild(FieldSkeletons)
    assert block is not None, "the field list stands behind the shared single-bar block"
    bars = block.findChildren(Skeleton)
    assert len(bars) == ROW_SKELETON_ROWS * 2
    block.resize(320, 200)
    spin(qtbot, 20)
    label, sub = bars[0], bars[1]
    assert label.height() > sub.height(), "the two bars are the same step"
    assert label.width() > sub.width(), "the sub-label bar is not the shorter one"
    settled(qtbot, picker)


# --- a caller's own paths, offered flat ----------------------------------------------------

#: The three paths the demo offers flat, one of them through a link.
FIXED = ["code", "sg_status_list", DOTTED]

#: A path the fixtures do not hold, which keeps its place in the list all the same.
MISSING = "sg_nope.Thing.code"


def flat(qtbot, picker, ms: int = 1200) -> None:
    """Spin until the fixed paths have been resolved."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if not picker.levels.loading:
            break
        qtbot.wait(5)
    spin(qtbot, 30)


def row_of(picker, row: int) -> dict:
    """One drawn row, read off the roles the delegate paints."""
    model = picker.rows_model
    index = model.index(row, 0)
    return {
        "label": model.data(index, Roles.LABEL),
        "code": model.data(index, Roles.CODE),
        "sub": model.data(index, Roles.SUB_LABEL),
        "glyph": model.data(index, Roles.GLYPH),
        "drill": model.data(index, Roles.DRILLABLE),
    }


def test_a_fixed_list_draws_the_paths_it_was_given_flat(qtbot):
    """`options` offers exactly those paths, in order, with nothing to descend into."""
    picker = build(qtbot, options=FIXED, show_code=True)
    flat(qtbot, picker)
    assert picker.options == FIXED
    assert picker.levels.flat is True
    assert picker.rows_model.keys() == FIXED
    assert all(row_of(picker, i)["drill"] is False for i in range(3))
    # The schema list is not read at all while a fixed one is on show.
    assert picker.derived == []


def test_a_fixed_list_never_shows_the_breadcrumb(qtbot):
    """Upstream: `breadcrumb = !options && (hops.length > 0 || choosing !== null)`."""
    picker = build(qtbot, options=FIXED)
    flat(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    assert picker.levels.deep is False
    assert picker.breadcrumb.isVisible() is False


def test_a_fixed_row_is_labelled_by_the_path_it_resolves_to(qtbot):
    """A link that could have gone elsewhere names its type, so the row reads the whole path."""
    picker = build(qtbot, options=FIXED, show_code=True)
    flat(qtbot, picker)
    linked = row_of(picker, 2)
    assert linked["label"] == "Link" + CRUMB_SEPARATOR + "Shot" + CRUMB_SEPARATOR + "Turnover Date"
    assert linked["code"] == "sg_turnover_date"
    assert linked["sub"] == "date"
    assert linked["glyph"] == "calendar"


def test_a_path_the_schema_does_not_hold_keeps_its_place_marked(qtbot):
    """A list of columns never comes back shorter than it went in."""
    from sg_widgets_core.pickers import UNRESOLVED_PATH_LABEL

    picker = build(qtbot, options=[*FIXED, MISSING], show_code=True)
    flat(qtbot, picker)
    assert picker.rows_model.rowCount() == 4
    missing = row_of(picker, 3)
    assert missing["label"] == MISSING
    assert missing["code"] == ""
    assert missing["sub"] == UNRESOLVED_PATH_LABEL


def test_the_search_narrows_a_fixed_list_on_the_label_and_on_the_path(qtbot):
    picker = build(qtbot, options=FIXED)
    flat(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    picker.control.set_query("turnover")
    spin(qtbot, 60)
    assert picker.rows_model.keys() == [DOTTED]
    picker.control.set_query("entity.Shot")
    spin(qtbot, 60)
    assert picker.rows_model.keys() == [DOTTED]
    picker.control.set_query("zzznope")
    spin(qtbot, 60)
    assert picker.rows_model.keys() == []
    picker.control.set_query("")
    spin(qtbot, 60)
    assert picker.rows_model.keys() == FIXED


def test_a_pick_from_a_fixed_list_emits_the_dotted_path(qtbot):
    """The emitted value is the path the caller wrote, and the control reads the resolved one."""
    picker = build(qtbot, options=FIXED, show_code=True)
    flat(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    seen: list[str] = []
    picker.value_changed.connect(seen.append)
    picker.control.list_surface().set_highlight(2)
    QTest.keyClick(search_caret(picker), Qt.Key.Key_Return)
    spin(qtbot, 200)
    assert seen == [DOTTED]
    assert picker.value == DOTTED
    assert picker.label_parts == ["Link", "Shot", "Turnover Date"]
    chips = picker.control.chips()
    assert len(chips) == 1
    assert chips[0].text() == picker.label


def test_a_fixed_list_set_after_the_fact_replaces_the_schema_one(qtbot):
    """`set_options` puts the picker in the flat mode, and dropping it gives the schema back."""
    picker = build(qtbot, options=None)
    settled(qtbot, picker)
    assert picker.levels.flat is False
    assert len(picker.derived) > 0

    picker.set_options(FIXED)
    flat(qtbot, picker)
    assert picker.rows_model.keys() == FIXED

    picker.set_options(None)
    settled(qtbot, picker)
    assert picker.levels.flat is False
    assert len(picker.derived) > 0


def test_levels_taken_down_under_a_read_drop_the_answer(qtbot):
    """A picker closed or rebuilt while its schema is being read has nowhere for it to land.

    The answer reaches the levels on the GUI thread through the pool, and `changed.emit` on a
    deleted object raises `RuntimeError` inside the event loop, which pytest-qt fails the test
    on and the showcase prints as a traceback. The levels take their tickets as they go.
    """
    import time

    from qtpy.QtWidgets import QApplication

    from sg_widgets_qt.widgets.field_picker import FieldLevels

    context = context_for(latency_ms=200)
    levels = FieldLevels(context=context, entity_type="Version", deep_links=True)
    levels.read()
    levels.deleteLater()
    del levels
    end = time.time() + 2.0
    while time.time() < end:
        QApplication.processEvents()
        qtbot.wait(10)
    assert True, "the schema landed on levels that had gone"


def test_keys_on_the_anchor_type_into_the_open_popup_search(qtbot):
    """The popup never takes the window's focus, so the keyboard delivers to the anchor.

    With the list open the anchor hands the text keys to the popup's search box: the query
    narrows the rows, Backspace widens them, and a key typed in the box itself lands once.
    """
    picker = build(qtbot)
    settled(qtbot, picker)
    picker.control.set_open(True)
    spin(qtbot, 60)
    before = len(picker.levels.rows(""))
    QTest.keyClicks(picker.control, "stat")
    spin(qtbot, 60)
    assert picker.control.query == "stat"
    narrowed = picker.levels.rows(picker.control.query)
    assert 0 < len(narrowed) < before
    assert all("stat" in (one.display_name + one.name).lower() for one in narrowed)
    QTest.keyClick(picker.control, Qt.Key.Key_Backspace)
    spin(qtbot, 30)
    assert picker.control.query == "sta"
    QTest.keyClicks(picker.control.caret(), "t")
    spin(qtbot, 30)
    assert picker.control.query == "stat", "a key typed in the box itself lands once"
