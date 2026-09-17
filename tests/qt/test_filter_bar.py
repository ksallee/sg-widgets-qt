"""The facet pills: their counts, a tick, the clears, and the checklist a pill opens."""
from __future__ import annotations

import time

from qtpy.QtWidgets import QApplication, QWidget

from sg_widgets_core.filter import condition, empty_filter, group
from sg_widgets_core.filter_ux import facet_counts
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.filter_bar import FilterBar

from .test_filter_editor import context_for, spin


def build(qtbot, **props) -> FilterBar:
    props.setdefault("entity_type", "Version")
    props.setdefault("context", context_for())
    props.setdefault("facets", ["sg_status_list", "sg_version_type"])
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(1000, 300)
    bar = FilterBar(parent=root, **props)
    bar.setGeometry(10, 10, 980, 120)
    root.show()
    qtbot.waitExposed(root)
    counted(qtbot, bar)
    bar.test_root = root
    return bar


def counted(qtbot, bar: FilterBar, ms: int = 3000) -> None:
    """Spin until a tally has answered for every facet the bar offers."""
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        if not bar.counting and all(bar.facet_list(name) for name in bar.facets):
            break
        qtbot.wait(5)
    spin(qtbot, 60)


def test_each_facet_lists_its_values_with_their_counts(qtbot):
    bar = build(qtbot, value=empty_filter())
    listed = bar.facet_list("sg_status_list")
    assert listed is not None
    assert listed.values
    # A tallied field carries the schema's whole vocabulary, the unused codes at zero.
    assert any(value.count > 0 for value in listed.values)
    # Without `counts` every field is tallied from one page of rows, and the list says so.
    assert listed.sampled is not None


def test_a_facet_tick_writes_the_condition_and_the_counts_are_read_again(qtbot):
    bar = build(qtbot, value=empty_filter())
    before = {v.key: v.count for v in bar.facet_list("sg_version_type").values}
    option = bar.facet_list("sg_status_list").values[0]
    seen: list = []
    bar.changed.connect(seen.append)
    bar.toggle("sg_status_list", option.key, option.value)
    counted(qtbot, bar)
    assert len(seen) == 1
    assert bar.selected_of("sg_status_list") == [option.value]
    # A facet is counted against the whole filter less its own condition, so the neighbour moved.
    after = {v.key: v.count for v in bar.facet_list("sg_version_type").values}
    assert after != before


def test_a_second_tick_takes_the_value_off_again(qtbot):
    bar = build(qtbot, value=empty_filter())
    option = bar.facet_list("sg_status_list").values[0]
    bar.toggle("sg_status_list", option.key, option.value)
    counted(qtbot, bar)
    bar.toggle("sg_status_list", option.key, option.value)
    counted(qtbot, bar)
    assert bar.selected_of("sg_status_list") == []
    assert bar.value.conditions == []


def test_a_pill_reads_the_field_and_its_values(qtbot):
    bar = build(
        qtbot,
        value=group("and", [condition("sg_status_list", "in", ["rev", "vwd", "fin"])]),
        max_values=2,
    )
    pill = bar.pill("sg_status_list")
    assert pill is not None
    assert bar.label_of("sg_status_list") == "Status"
    overflow = pill.findChild(QWidget, "filter-pill-overflow")
    assert overflow is not None
    assert overflow.text() == "+1"


def test_clear_all_drops_every_facet_condition(qtbot):
    bar = build(
        qtbot,
        value=group(
            "and",
            [
                condition("sg_status_list", "in", ["rev"]),
                condition("sg_version_type", "in", ["Type A"]),
                condition("code", "contains", "sh"),
            ],
        ),
    )
    seen: list = []
    bar.changed.connect(seen.append)
    bar.clear_all_button().clicked.emit()
    counted(qtbot, bar)
    assert len(seen) == 1
    # The condition the editor wrote on a path outside the bar is left alone.
    assert [c.path for c in bar.value.conditions] == ["code"]


def test_the_sites_own_groups_count_a_facet_when_counts_is_given(qtbot):
    client = context_for()
    bar = build(
        qtbot,
        context=client,
        entity_type="Version",
        facets=["sg_status_list"],
        counts=facet_counts(client.client, "Version"),
        value=empty_filter(),
    )
    listed = bar.facet_list("sg_status_list")
    assert listed is not None
    assert listed.values
    # A count from the site's own groups is complete, so the list carries no sample note.
    assert listed.sampled is None


def test_more_filters_shares_the_bars_tree(qtbot):
    bar = build(qtbot, value=group("and", [condition("sg_status_list", "in", ["rev"])]))
    assert bar.more_filters().active == 1
    bar.more_filters().changed.emit(empty_filter())
    counted(qtbot, bar)
    assert bar.value.conditions == []


def test_an_untouched_facet_reads_quiet(qtbot):
    """`text-muted-foreground border-dashed`: a pill nobody ticked is the quiet one."""
    from sg_widgets_qt.widgets.filter_bar import _PillText

    bar = build(qtbot, value=empty_filter())
    pill = bar.pill("sg_status_list")
    runs = pill.findChildren(_PillText)
    assert runs and all(run.muted for run in runs)

    ticked = build(
        qtbot,
        value=group("and", [condition("sg_status_list", "in", ["rev"])]),
    )
    active = ticked.pill("sg_status_list")
    named = [run for run in active.findChildren(_PillText) if run.objectName() == "filter-pill-field"]
    assert named and not named[0].muted
