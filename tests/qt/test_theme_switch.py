"""Switching the theme: one emission, and only what a reader is looking at is dressed again.

A stylesheet set on a root makes Qt polish every widget under it, so the switch is cheap only
while it lands on one root. A top-level that is hidden, and a stage that stands inside a root
already wearing the theme, are dressed when they next need it rather than on the switch.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest
from qtpy import QtCore, QtWidgets

from sg_widgets_qt.primitives.popover import Popover
from sg_widgets_qt.showcase.context import demo_context
from sg_widgets_qt.showcase.prefs import Prefs
from sg_widgets_qt.showcase.stage import DemoStage
from sg_widgets_qt.showcase.window import ShowcaseWindow
from sg_widgets_qt.theme import (
    apply_theme,
    dress,
    generate_qss,
    theme_bus,
    theme_for,
    theme_of,
    watch_theme,
)


class Roots:
    """The roots a theme landed on while it was listening."""

    def __init__(self) -> None:
        self.seen: list = []

    def __call__(self, root: QtWidgets.QWidget) -> None:
        self.seen.append(root)

    def __enter__(self) -> Roots:
        theme_bus.changed.connect(self)
        return self

    def __exit__(self, *_: object) -> None:
        theme_bus.changed.disconnect(self)


class Polished(QtWidgets.QWidget):
    """Counts the restyles Qt sends it."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.styles = 0

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.Type.StyleChange:
            self.styles += 1


@pytest.fixture
def window(qapp):
    made = ShowcaseWindow(prefs=Prefs(persist=False), context=demo_context())
    made.resize(900, 700)
    made.show()
    qapp.processEvents()
    yield made
    made.close()


def test_the_switch_is_one_emission(window, qapp):
    window.open_page("hello")
    qapp.processEvents()
    with Roots() as roots:
        window.prefs.set("theme", "dark")
    assert [root.objectName() for root in roots.seen] == ["showcase"]


def test_the_switch_reaches_every_widget_of_the_page(window, qapp):
    page = window.open_page("hello")
    qapp.processEvents()
    window.prefs.set("theme", "dark")
    qapp.processEvents()
    assert theme_of(page).dark is True
    assert all(theme_of(child).dark for child in page.findChildren(QtWidgets.QWidget))


def test_the_switch_carries_reduced_motion(window, qapp):
    page = window.open_page("hello")
    qapp.processEvents()
    window.prefs.set("motion", "reduced")
    qapp.processEvents()
    assert theme_of(page).reduced_motion is True
    assert theme_of(page.stages[0]).reduced_motion is True


def test_a_stage_inside_a_themed_window_wears_the_window_s_sheet(window, qapp):
    page = window.open_page("hello")
    qapp.processEvents()
    window.prefs.set("theme", "dark")
    qapp.processEvents()
    stage = page.stages[0]
    assert stage.styleSheet() == ""
    assert theme_of(stage).dark is True


def test_a_stage_on_its_own_dresses_itself(qapp):
    prefs = Prefs(persist=False)
    stage = DemoStage("hello", prefs=prefs)
    prefs.set("theme", "dark")
    qapp.processEvents()
    assert stage.styleSheet() != ""
    assert theme_of(stage).dark is True
    stage.deleteLater()


def test_a_closed_popover_waits_for_its_next_open(qapp):
    root = QtWidgets.QWidget()
    anchor = QtWidgets.QPushButton("anchor", root)
    apply_theme(root, theme_for("default"))
    popover = Popover(anchor, QtWidgets.QLabel("content"))
    with Roots() as roots:
        apply_theme(root, theme_for("default", dark=True))
    assert roots.seen == [root]
    popover.open()
    qapp.processEvents()
    assert theme_of(popover).dark is True
    assert theme_of(popover.content()).dark is True
    popover.close()
    popover.deleteLater()
    root.deleteLater()


def test_an_open_popover_follows_the_theme(qapp):
    root = QtWidgets.QWidget()
    anchor = QtWidgets.QPushButton("anchor", root)
    apply_theme(root, theme_for("default"))
    root.show()
    popover = Popover(anchor, QtWidgets.QLabel("content"))
    popover.open()
    qapp.processEvents()
    apply_theme(root, theme_for("default", dark=True))
    assert theme_of(popover).dark is True
    assert theme_of(popover.content()).dark is True
    popover.close()
    popover.deleteLater()
    root.deleteLater()


def test_a_page_built_earlier_is_dressed_before_it_is_shown(window, qapp):
    first = window.open_page("hello")
    second = window.open_page("status-badge")
    qapp.processEvents()
    window.prefs.set("theme", "dark")
    qapp.processEvents()
    sheet = generate_qss(window.prefs.theme_object())
    assert second.styleSheet() == sheet
    assert window.sidebar.styleSheet() == sheet
    assert first.styleSheet() != sheet
    window.open_page("hello")
    assert first.styleSheet() == sheet


def test_a_sheet_that_has_not_changed_leaves_the_tree_alone(qapp):
    root = QtWidgets.QWidget()
    leaf = Polished(root)
    theme = theme_for("default")
    dress(root, theme)
    qapp.processEvents()
    polished = leaf.styles
    assert polished > 0
    dress(root, theme)
    qapp.processEvents()
    assert leaf.styles == polished
    root.deleteLater()


#: A watched widget built, dressed and dropped, then the interpreter torn down.
TEARDOWN = """
import gc
from qtpy import QtWidgets
from sg_widgets_qt.theme import apply_theme, theme_for, watch_theme

app = QtWidgets.QApplication([])
seen = []
widget = QtWidgets.QWidget()
watch_theme(widget, seen.append)
apply_theme(widget, theme_for("default"))
assert len(seen) == 1
del widget
gc.collect()
"""


def test_a_watched_widget_is_torn_down_without_a_callback(qapp):
    """Nothing of the subscription runs from a destructor, which is what a binding may refuse."""
    done = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(TEARDOWN)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    noise = [
        line
        for line in done.stderr.splitlines()
        if "Skipping callback call" in line or "Failed to disconnect" in line
    ]
    assert noise == []


def test_a_theme_reaches_every_widget_watching_under_the_root(qapp):
    seen: list = []
    root = QtWidgets.QWidget()
    first = QtWidgets.QWidget(root)
    second = QtWidgets.QWidget(root)
    watch_theme(first, seen.append)
    watch_theme(second, seen.append)
    watch_theme(first, seen.append)
    apply_theme(root, theme_for("default"))
    assert len(seen) == 3, "a widget watching twice hears a theme twice, as it asked"
    # A theme that lands somewhere else reaches none of them.
    apply_theme(QtWidgets.QWidget(), theme_for("dark"))
    assert len(seen) == 3
