"""The launcher for the filter editor: the count, apply, cancel and the two clears."""
from __future__ import annotations

from qtpy.QtWidgets import QWidget

from sg_widgets_core.filter import condition, empty_filter, group, is_empty_filter
from sg_widgets_qt.theme import apply_theme, theme_for
from sg_widgets_qt.widgets.filter_dialog import FilterDialog

from .test_filter_editor import context_for, spin


def applied():
    return group(
        "and",
        [
            condition("sg_status_list", "in", ["rev", "vwd"]),
            condition("created_at", "in_last", [1, "YEAR"]),
        ],
    )


def build(qtbot, **props) -> FilterDialog:
    props.setdefault("entity_type", "Version")
    props.setdefault("context", context_for())
    root = QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(900, 300)
    launcher = FilterDialog(parent=root, **props)
    launcher.setGeometry(10, 10, 880, 60)
    root.show()
    qtbot.waitExposed(root)
    spin(qtbot, 60)
    launcher.test_root = root
    return launcher


def test_the_trigger_carries_the_count_of_applied_conditions(qtbot):
    launcher = build(qtbot, value=applied())
    assert launcher.active == 2
    assert launcher.launcher().text == "Edit filters"
    empty = build(qtbot, value=empty_filter())
    assert empty.active == 0
    assert empty.launcher().text == "Add filters"


def test_apply_emits_the_staged_tree_and_closes(qtbot):
    launcher = build(qtbot, value=applied())
    seen: list = []
    launcher.changed.connect(seen.append)
    launcher.set_open(True)
    spin(qtbot, 400)
    launcher.editor().append([], condition("code", "contains", "comp"))
    spin(qtbot, 200)
    launcher.apply()
    spin(qtbot, 200)
    assert len(seen) == 1
    assert [c.path for c in seen[0].conditions][-1] == "code"
    assert launcher.active == 3
    assert launcher.open is False


def test_cancel_drops_the_staged_edits(qtbot):
    launcher = build(qtbot, value=applied())
    seen: list = []
    launcher.changed.connect(seen.append)
    launcher.set_open(True)
    spin(qtbot, 400)
    launcher.editor().append([], condition("code", "contains", "comp"))
    spin(qtbot, 200)
    launcher.cancel()
    spin(qtbot, 200)
    assert seen == []
    assert launcher.active == 2
    # The draft starts from the applied value again, so the cancelled row is gone.
    launcher.set_open(True)
    spin(qtbot, 400)
    assert len(launcher.editor().rows()) == 2


def test_clear_all_emits_an_empty_filter(qtbot):
    launcher = build(qtbot, value=applied())
    seen: list = []
    launcher.changed.connect(seen.append)
    launcher.set_open(True)
    spin(qtbot, 400)
    launcher.clear_all()
    spin(qtbot, 200)
    assert len(seen) == 1
    assert is_empty_filter(seen[0])
    assert launcher.active == 0
    assert launcher.open is False


def test_open_changed_follows_the_dialog(qtbot):
    launcher = build(qtbot, value=applied())
    seen: list = []
    launcher.open_changed.connect(seen.append)
    launcher.set_open(True)
    spin(qtbot, 300)
    assert launcher.open is True
    launcher.set_open(False)
    spin(qtbot, 300)
    assert seen == [True, False]


def test_a_tree_of_blank_rows_applies_as_no_filter(qtbot):
    launcher = build(qtbot, value=empty_filter())
    seen: list = []
    launcher.changed.connect(seen.append)
    launcher.set_open(True)
    spin(qtbot, 400)
    launcher.editor().append([], condition("", "is", ""))
    spin(qtbot, 200)
    launcher.apply()
    spin(qtbot, 200)
    assert len(seen) == 1
    assert seen[0].conditions == []


def test_a_disabled_launcher_never_opens(qtbot):
    launcher = build(qtbot, value=applied(), disabled=True)
    launcher.set_open(True)
    spin(qtbot, 200)
    assert launcher.open is False
    assert not launcher.launcher().isEnabled()


def test_the_count_is_a_chip_inside_the_trigger(qtbot):
    """Upstream draws the count inside the trigger's own border, and so does this."""
    from sg_widgets_qt.primitives.badge import Badge

    launcher = build(qtbot, value=applied())
    trigger = launcher.launcher()
    assert trigger.count == "2"
    assert trigger.count_size == "sm"
    # Nothing stands beside the trigger carrying it.
    assert launcher.findChildren(Badge) == []
    wide = trigger.sizeHint().width()
    trigger.set_count("")
    assert trigger.sizeHint().width() < wide

    empty = build(qtbot, value=empty_filter())
    assert empty.launcher().count == ""


def test_the_dialog_takes_the_window_up_to_sixty_four_rem(qtbot):
    """`w-[min(96vw,64rem)]`: a condition row wants room (filter-dialog-stress)."""
    from sg_widgets_qt.widgets.filter_dialog import DIALOG_WIDTH, VIEWPORT_SHARE

    launcher = build(qtbot, value=applied())
    root = launcher.test_root
    root.resize(1600, 900)
    spin(qtbot, 60)
    assert launcher.dialog_width() == DIALOG_WIDTH
    root.resize(700, 600)
    spin(qtbot, 60)
    assert launcher.dialog_width() == int(launcher.window().width() * VIEWPORT_SHARE)
