"""What a screen reader reads off the painted controls: a role, a name and a state.

The name half runs on both bindings, because `accessibleName` is a `QWidget` property. The
interface half runs where the binding wraps `QAccessible`, which PyQt5 does not.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from qtpy import QtGui, QtWidgets

from sg_widgets_qt.primitives import Button, Checkbox, IconButton, Select, Switch, Toggle
from sg_widgets_qt.primitives.remove_control import RemoveControl
from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.theme import apply_theme, theme_for

QAccessible = getattr(QtGui, "QAccessible", None)

#: PyQt5 wraps none of the accessibility classes, so the interface is asked for only where it
#: exists. The names the interface reads are set on the widget, and those are checked on both.
needs_interface = pytest.mark.skipif(
    QAccessible is None, reason="the binding wraps no QAccessible"
)


@pytest.fixture
def root(qtbot):
    """A shown root wearing the default light theme, which every leaf reads through."""
    widget = QtWidgets.QWidget()
    apply_theme(widget, theme_for("default"))
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    return widget


def place(parent: QtWidgets.QWidget, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
    widget.setParent(parent)
    widget.resize(widget.sizeHint())
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget


def interface(widget: QtWidgets.QWidget):
    made = QAccessible.queryAccessibleInterface(widget)
    assert made is not None
    return made


def name_of(widget: QtWidgets.QWidget) -> str:
    return interface(widget).text(QAccessible.Text.Name)


# --- the name a control carries -------------------------------------------------------------


def test_a_button_is_named_by_its_text(root):
    button = place(root, Button("Save"))
    assert button.accessibleName() == "Save"


def test_a_new_text_renames_the_button(root):
    button = place(root, Button("Save"))
    button.set_text("Apply")
    assert button.accessibleName() == "Apply"


def test_a_name_set_by_the_caller_survives_a_new_text(root):
    button = place(root, Button("Save"))
    button.setAccessibleName("Keep the change")
    button.set_text("Apply")
    assert button.accessibleName() == "Keep the change"


def test_an_icon_only_button_is_named_by_nothing(root):
    button = place(root, Button(icon="plus"))
    assert button.accessibleName() == ""


def test_a_checkbox_a_switch_and_a_toggle_are_named_by_their_text(root):
    assert place(root, Checkbox("Only mine")).accessibleName() == "Only mine"
    assert place(root, Toggle("Match all")).accessibleName() == "Match all"
    switch = place(root, Switch())
    switch.setAccessibleName("Live updates")
    assert switch.accessibleName() == "Live updates"


def test_a_select_is_named_by_its_label(root):
    select = place(root, Select([("ip", "In progress")], placeholder="Status"))
    assert select.accessibleName() == "Status"
    select.set_value("ip")
    assert select.accessibleName() == "In progress"


# --- the role and the state the interface reports --------------------------------------------


@needs_interface
def test_the_button_interface_reports_a_button(root):
    button = place(root, Button("Save"))
    assert interface(button).role() == QAccessible.Role.Button
    assert name_of(button) == "Save"


@needs_interface
def test_a_pressed_button_reports_pressed(root, qtbot):
    button = place(root, Button("Save"))
    assert not interface(button).state().pressed
    button.set_pressed(True)
    assert interface(button).state().pressed


@needs_interface
def test_a_trigger_with_its_popup_up_reports_expanded(root):
    button = place(root, Button("Filters"))
    assert not interface(button).state().expanded
    button.set_expanded(True)
    state = interface(button).state()
    assert state.expanded
    assert state.expandable


@needs_interface
def test_a_disabled_control_reports_disabled(root):
    button = place(root, Button("Save"))
    assert not interface(button).state().disabled
    button.setEnabled(False)
    assert interface(button).state().disabled


@needs_interface
def test_the_checkbox_interface_reports_a_checkbox_and_its_tick(root):
    box = place(root, Checkbox("Only mine"))
    made = interface(box)
    assert made.role() == QAccessible.Role.CheckBox
    assert made.state().checkable
    assert not made.state().checked
    box.set_checked(True)
    assert interface(box).state().checked


@needs_interface
def test_a_partial_checkbox_reports_a_mixed_tick(root):
    box = place(root, Checkbox("Only mine", tri_state=True))
    box.set_check_state(1)
    assert interface(box).state().checkStateMixed


@needs_interface
def test_the_switch_interface_reports_a_checkbox_and_its_tick(root):
    switch = place(root, Switch())
    switch.setAccessibleName("Live updates")
    made = interface(switch)
    assert made.role() == QAccessible.Role.CheckBox
    assert made.state().checkable
    assert not made.state().checked
    assert name_of(switch) == "Live updates"
    switch.set_checked(True)
    assert interface(switch).state().checked


@needs_interface
def test_the_toggle_interface_reports_a_button_that_stays_down(root):
    toggle = place(root, Toggle("Match all"))
    made = interface(toggle)
    assert made.role() == QAccessible.Role.Button
    assert made.state().checkable
    assert not made.state().checked
    toggle.set_checked(True)
    assert interface(toggle).state().checked


@needs_interface
def test_the_select_interface_reports_a_combo_box_its_value_and_its_list(root, qtbot):
    select = place(root, Select([("ip", "In progress")], placeholder="Status"))
    made = interface(select)
    assert made.role() == QAccessible.Role.ComboBox
    assert made.state().expandable
    assert not made.state().expanded
    select.set_value("ip")
    assert interface(select).text(QAccessible.Text.Value) == "In progress"
    select.open()
    qtbot.waitUntil(lambda: select.is_open, timeout=1000)
    assert interface(select).state().expanded
    select.close()


@needs_interface
def test_a_readonly_select_reports_read_only(root):
    select = place(root, Select([("ip", "In progress")]))
    select.set_readonly(True)
    assert interface(select).state().readOnly


# --- the name every icon-only control in a widget carries ------------------------------------

SRC = Path(__file__).resolve().parents[2] / "src" / "sg_widgets_qt"


def widget_demos() -> list[str]:
    """Every demo that stands a widget up, which is where its controls can be walked."""
    widgets = sorted(p.stem for p in (SRC / "widgets").glob("*.py") if not p.stem.startswith("_"))
    demos = sorted(p.stem for p in (SRC / "showcase" / "demos").glob("*.py") if not p.stem.startswith("_"))
    return [
        demo
        for demo in demos
        if any(demo == name or demo.startswith(name + "_") for name in widgets)
    ]


#: The controls that can stand as a glyph and nothing else.
GLYPH_CONTROLS = (Button, Toggle, IconButton, RemoveControl)


def unnamed(parent: QtWidgets.QWidget) -> list[str]:
    """Every control under `parent` that reads as a glyph alone and says nothing."""
    found = []
    for child in parent.findChildren(QtWidgets.QWidget):
        if not isinstance(child, GLYPH_CONTROLS):
            continue
        if getattr(child, "text", ""):
            continue
        glyph = (
            isinstance(child, (IconButton, RemoveControl))
            or child.icon
            or getattr(child, "trailing_icon", None)
        )
        if glyph and not child.accessibleName().strip():
            found.append(f"{type(child).__name__} {child.objectName() or '(unnamed slot)'}")
    return found


@pytest.mark.parametrize("demo", widget_demos())
def test_every_icon_only_control_in_a_widget_is_named(demo, qtbot, qapp):
    root = QtWidgets.QWidget()
    apply_theme(root, theme_for("default"))
    qtbot.addWidget(root)
    root.resize(1200, 900)
    module = importlib.import_module(f"sg_widgets_qt.showcase.demos.{demo}")
    built = module.build(demo_context(), root)
    built.setParent(root)
    root.show()
    qapp.processEvents()
    assert unnamed(root) == []
